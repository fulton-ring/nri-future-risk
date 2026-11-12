import assert from "node:assert/strict";
import { test } from "node:test";
import {
  readState,
  writeState,
  metricValue,
  colorFor,
  describeValue,
} from "../src/lib/risk.ts";

test("shared views reject invalid inputs and keep multiplier paired with a future", () => {
  const state = readState(
    "?hazard=invalid&metric=multiplier&period=base&county=bad&lat=NaN&zoom=99",
  );
  assert.equal(state.hazard, "WFIR");
  assert.equal(state.period, "mid");
  assert.equal(state.county, "");
  assert.equal(state.camera, undefined);
});
test("a shared view restores county, science controls, release and camera", () => {
  const state = readState(
    "?hazard=EXHT&metric=risk&period=late&emissions=higher&model=N99&county=06037&lat=34&lng=-118&zoom=6",
  );
  assert.deepEqual(readState(writeState(state)), state);
  assert.equal(
    new URLSearchParams(writeState(state)).get("release"),
    "fema-2024-12-05",
  );
});
test("zero, missing and no-rating multipliers stay distinct", () => {
  const state = readState("?metric=multiplier");
  assert.equal(
    metricValue(
      { WFIR_MID_LOWER_HM: 0, WFIR_MID_LOWER_DELTAR: "No Rating" },
      state,
    ),
    "No Rating",
  );
  assert.equal(metricValue({ WFIR_MID_LOWER_HM: 0 }, state), 0);
  assert.equal(metricValue({}, state), null);
  assert.notEqual(colorFor(0, "multiplier"), colorFor(null, "multiplier"));
  assert.equal(describeValue(0, "multiplier"), "0×");
});
test("baseline heat uses shared EXHT fields and future heat uses model fields", () => {
  const values = {
    EXHT_RISKR: "Very High",
    EXHT_N99_LATE_HIGHER_PRISKR: "Relatively High",
  };
  assert.equal(
    metricValue(values, readState("?hazard=EXHT&metric=risk&period=base")),
    "Very High",
  );
  assert.equal(
    metricValue(
      values,
      readState(
        "?hazard=EXHT&metric=risk&period=late&emissions=higher&model=N99",
      ),
    ),
    "Relatively High",
  );
});
test("rating colors follow published categories rather than scenario-specific extrema", () => {
  assert.equal(
    colorFor("Very High (>49.5M)", "loss"),
    colorFor("Very High (>17.3M)", "loss"),
  );
  assert.notEqual(colorFor("No Rating", "loss"), colorFor(null, "loss"));
});

test("every archived county attribute survives the display asset conversion", async () => {
  const { readFile } = await import("node:fs/promises");
  const original = JSON.parse(
    await readFile(
      new URL("../public/combined_nri_counties_borders.json", import.meta.url),
      "utf8",
    ),
  );
  const display = JSON.parse(
    await readFile(
      new URL("../public/atlas/counties.json", import.meta.url),
      "utf8",
    ),
  );
  const rows = new Map(
    display.counties.map((c: { id: string; values: unknown[] }) => [c.id, c]),
  );
  assert.equal(rows.size, original.features.length);
  for (const feature of original.features) {
    const row = rows.get(feature.properties.STCOFIPS) as { values: unknown[] };
    assert.ok(row);
    for (const [i, column] of display.columns.entries())
      assert.deepEqual(
        row.values[i],
        feature.properties[column],
        `${feature.properties.STCOFIPS}: ${column}`,
      );
  }
});

test("map field selection reads published properties from PMTiles", async () => {
  const { metricField } = await import("../src/lib/risk.ts");
  assert.equal(
    metricField(readState("?hazard=HRCN&metric=loss&period=base")),
    "HRCN_EALR",
  );
  assert.equal(
    metricField(
      readState(
        "?hazard=EXHT&metric=multiplier&model=N99&period=late&emissions=higher",
      ),
    ),
    "EXHT_N99_LATE_HIGHER_HM",
  );
});

test("PMTiles carries the actual archived scores and multipliers for all five hazards", async () => {
  const { readFile } = await import("node:fs/promises");
  const { PMTiles } = await import("pmtiles");
  const { VectorTile } = await import("@mapbox/vector-tile");
  const { PbfReader } = await import("pbf");
  const bytes = await readFile(
    new URL("../public/atlas/counties.pmtiles", import.meta.url),
  );
  const archive = new PMTiles({
    getKey: () => "archive",
    getBytes: async (offset, length) => ({
      data: bytes.buffer.slice(
        bytes.byteOffset + offset,
        bytes.byteOffset + offset + length,
      ),
    }),
  });
  const tile = await archive.getZxy(6, 11, 25);
  assert.ok(tile);
  const layer = new VectorTile(new PbfReader(new Uint8Array(tile.data))).layers
    .counties;
  const properties = Array.from(
    { length: layer.length },
    (_, i) => layer.feature(i).properties,
  ).find((p) => p.fips === "06037");
  assert.ok(properties, "Los Angeles is included in its tile");
  const source = JSON.parse(
    await readFile(
      new URL("../public/combined_nri_counties_borders.json", import.meta.url),
      "utf8",
    ),
  );
  const expected = source.features.find(
    (f: { properties: { STCOFIPS: string } }) =>
      f.properties.STCOFIPS === "06037",
  ).properties;
  for (const key of Object.keys(expected).filter((k) =>
    /^(WFIR|DRGT|EXHT|CFLD|HRCN)_/.test(k),
  )) {
    if (expected[key] !== null)
      assert.equal(properties[key], expected[key], key);
  }
});

test("pathway names follow the archived hazard sources", async () => {
  const { pathwayLabel } = await import("../src/lib/risk.ts");
  for (const hazard of ["DRGT", "EXHT", "WFIR"] as const) {
    assert.equal(pathwayLabel(hazard, "lower"), "SSP2-4.5");
    assert.equal(pathwayLabel(hazard, "higher"), "SSP5-8.5");
  }
  assert.equal(pathwayLabel("HRCN", "lower"), "RCP 4.5");
  assert.equal(pathwayLabel("HRCN", "higher"), "RCP 8.5");
  assert.equal(pathwayLabel("CFLD", "lower"), "Intermediate SLR");
  assert.equal(pathwayLabel("CFLD", "higher"), "High SLR");
});

test("shared map layers restore opacity and terrain with bounded inputs", () => {
  const state = readState("?opacity=0.45&terrain=0");
  assert.equal(state.opacity, 0.45);
  assert.equal(state.terrain, false);
  assert.deepEqual(readState(writeState(state)), state);
  assert.equal(readState("?opacity=7").opacity, 0.7);
  assert.equal(readState("?opacity=0").opacity, 0);
});

test('area selection accepts legacy FIPS and current GEOID tile properties', async () => {
  const {featureAreaId}=await import('../src/lib/risk.ts');
  assert.equal(featureAreaId({fips:'01001'}),'01001');
  assert.equal(featureAreaId({geoid:'09110535200'}),'09110535200');
  assert.equal(featureAreaId({fips:'01001',geoid:'01003'}),'01001');
  assert.equal(featureAreaId({}),null);
  assert.equal(featureAreaId({geoid:9110535200}),null);
});

test('zero baseline losses have a distinct display status for baseline risk and future ratings', () => {
  const zero = 'No Expected Annual Losses';
  for (const hazard of ['WFIR', 'DRGT', 'EXHT'] as const) {
    for (const period of ['base', 'mid', 'late'] as const) {
      for (const metric of ['loss', 'risk'] as const) {
        const state = {...readState(''), hazard, period, metric};
        const field = period === 'base' ? `${hazard}_${metric === 'loss' ? 'EALR' : 'RISKR'}` :
          `${hazard}${hazard === 'EXHT' ? '_L95' : ''}_${period.toUpperCase()}_LOWER_${metric === 'loss' ? 'PALR' : 'PRISKR'}`;
        const values = {[field]: 'No Rating', [`${hazard}_EALR`]: zero};
        assert.equal(metricValue(values, state), zero);
        assert.equal(describeValue(metricValue(values, state), metric), 'No modeled baseline losses');
        assert.notEqual(colorFor(zero, metric), colorFor('No Rating', metric));
        if (field === `${hazard}_EALR`) continue;
        for (const status of [null, 'Not Applicable', 'Insufficient Data', 'Very Low'])
          assert.equal(metricValue({...values, [field]: status}, state), status);
        assert.equal(metricValue({[field]: 'No Rating'}, state), 'No Rating');
        assert.equal(metricValue({[field]: 'No Rating', [`${hazard}_EALT`]: 0}, state), 'No Rating');
        assert.equal(metricValue({[`${hazard}_EALR`]: zero}, state), null);
      }
    }
  }
  assert.equal(describeValue(null, 'loss'), 'Data unavailable');
});

test('zero baseline loss status does not replace multipliers or their no-rating sentinel', () => {
  const state = readState('?metric=multiplier');
  const values = {WFIR_EALR: 'No Expected Annual Losses', WFIR_MID_LOWER_HM: 2};
  assert.equal(metricValue(values, state), 2);
  assert.equal(metricValue({...values, WFIR_MID_LOWER_DELTAR: 'No Rating'}, state), 'No Rating');
  assert.equal(metricValue({WFIR_EALR: values.WFIR_EALR}, state), null);
});

test('map fill colors agree with displayed ratings without changing multiplier bins', async () => {
  const {metricColorExpression, metricField} = await import('../src/lib/risk.ts');
  const {createExpression} = await import('@maplibre/maplibre-gl-style-spec');
  for (const metric of ['loss', 'risk', 'multiplier'] as const) {
    for (const period of ['base', 'mid', 'late'] as const) {
      if (metric === 'multiplier' && period === 'base') continue;
      const state = {...readState(''), metric, period};
      const expression = createExpression(metricColorExpression(state), "layers[0].paint.fill-color");
      assert.equal(expression.result, 'success');
      if (expression.result !== 'success') continue;
      for (const baseline of ['No Expected Annual Losses', 'No Rating', null]) {
        for (const value of [null, 'No Rating', 'Not Applicable', 'Insufficient Data', 'Very High (>49.5M)', ...(metric === 'multiplier' ? [0, 1, 2, 5] : [])]) {
          const properties = {WFIR_EALR: baseline, [metricField(state)]: value};
          assert.equal(expression.value.evaluate({zoom: 0}, {type: 3, properties}), colorFor(metricValue(properties, state), metric));
        }
        const properties = {WFIR_EALR: baseline};
        const expected = colorFor(metricValue(properties, state), metric);
        assert.equal(expression.value.evaluate({zoom: 0}, {type: 3, properties}), expected);
      }
      if (metric === 'multiplier') {
        const properties = {WFIR_EALR: 'No Expected Annual Losses', [metricField(state)]: 2, WFIR_MID_LOWER_DELTAR: 'No Rating', WFIR_LATE_LOWER_DELTAR: 'No Rating'};
        assert.equal(expression.value.evaluate({zoom: 0}, {type: 3, properties}), colorFor('No Rating', metric));
      }
    }
  }
});
