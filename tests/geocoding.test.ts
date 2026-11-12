import assert from "node:assert/strict";
import { test } from "node:test";
import {
  censusVintage,
  parseCensusAddresses,
  parseCensusArea,
  parsePhotonResults,
} from "../src/clients/geocoding";

const feature = (
  properties: Record<string, unknown> = {},
  coordinates: unknown = [-87.62, 41.87],
) => ({
  properties: {
    osm_type: "R",
    osm_id: 123,
    countrycode: "US",
    name: "Chicago",
    state: "Illinois",
    type: "city",
    ...properties,
  },
  geometry: { type: "Point", coordinates },
});
const census = (geographies: unknown) => ({ result: { geographies } });

test("Photon yields readable places with correctly ordered bounds and precise addresses", () => {
  const results = parsePhotonResults({
    features: [
      feature({ extent: [-88, 42, -87, 41] }),
      feature({
        osm_id: 124,
        type: "house",
        name: "Library",
        housenumber: "12",
        street: "Main Street",
        city: "Chicago",
      }),
    ],
  });
  assert.equal(results[0].label, "Chicago");
  assert.equal(results[0].detail, "Illinois");
  assert.equal(results[0].kind, "place");
  assert.deepEqual(results[0].bounds, [-88, 41, -87, 42]);
  assert.equal(results[1].kind, "address");
  assert.match(results[1].label + results[1].detail, /12 Main Street/);
});

test("Photon rejects foreign, missing-country, malformed coordinate hits and invalid bounds", () => {
  assert.deepEqual(
    parsePhotonResults({
      features: [
        feature({ countrycode: "CA" }),
        feature({ countrycode: null }),
        feature({}, [200, 40]),
        feature({}, ["-87", 41]),
        feature({}, [0, NaN]),
      ],
    }),
    [],
  );
  assert.equal(
    parsePhotonResults({
      features: [feature({ extent: [-87, 41, -88, 42] })],
    })[0].bounds,
    undefined,
  );
  assert.equal(
    parsePhotonResults({ features: [feature({ countrycode: "PR" })] }).length,
    1,
  );
  assert.deepEqual(parsePhotonResults(null), []);
});

test("Census parses address matches defensively", () => {
  const results = parseCensusAddresses({
    result: {
      addressMatches: [
        {
          matchedAddress: "12 MAIN ST, CHICAGO, IL, 60601",
          coordinates: { x: -87.62, y: 41.87 },
        },
        { matchedAddress: "Bad", coordinates: { x: null, y: 41 } },
      ],
    },
  });
  assert.equal(results.length, 1);
  assert.equal(results[0].source, "Census");
  assert.equal(results[0].kind, "address");
  assert.match(results[0].label, /12 MAIN ST/);
  assert.deepEqual(parseCensusAddresses({}), []);
});

test("Census selects native baseline vintage", () => {
  assert.equal(censusVintage("v1.20"), "ACS2024_Current");
  assert.equal(censusVintage("NRI v1.20"), "ACS2024_Current");
  assert.equal(censusVintage("v1.19"), "Census2020_Current");
});

test("Census prefers named exact layers, preserves leading zeros, and derives prefixes safely", () => {
  assert.equal(
    parseCensusArea(
      census({
        "Census Tracts": [{ GEOID: "09110535200" }],
        "Census Block Groups": [{ GEOID: "090010001001" }],
      }),
    ),
    "09110535200",
  );
  assert.equal(
    parseCensusArea(
      census({ "Census Block Groups": [{ GEOID: "170313204001" }] }),
    ),
    "17031320400",
  );
  assert.equal(
    parseCensusArea(census({ Counties: [{ GEOID: "09110" }] }), "counties"),
    "09110",
  );
  assert.equal(
    parseCensusArea(
      census({ "Census Tracts": [{ GEOID: "17031320400" }] }),
      "counties",
    ),
    "17031",
  );
  assert.equal(
    parseCensusArea(
      census({
        "Census Block Groups": [
          { GEOID: "170313204001" },
          { GEOID: "170313204002" },
        ],
      }),
    ),
    "17031320400",
  );
});

test("Census rejects ambiguous, malformed, contradictory and unsupported identifiers", () => {
  for (const geographies of [
    { "Census Tracts": [{ GEOID: "17031320400" }, { GEOID: "17031320500" }] },
    { "Census Tracts": [{ GEOID: "17031320400suffix" }] },
    { "Census Tracts": [{ GEOID: 17031320400 }] },
    { "Census Tracts": [{ GEOID: "99031320400" }] },
    { "Census Tracts": [{ GEOID: "17000320400" }] },
    { "Census Tracts": [{ GEOID: "17031320400", COUNTY: "001" }] },
    { "Census Blocks": [{ GEOID: "170313204001001" }] },
  ])
    assert.equal(parseCensusArea(census(geographies)), null);
  assert.equal(parseCensusArea(null), null);
});

test("browser JSONP resolves named layers with the selected vintage and cleans up", async () => {
  const { resolvePlaceArea } = await import("../src/clients/geocoding");
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const previousDocument = Object.getOwnPropertyDescriptor(
    globalThis,
    "document",
  );
  const callbacks: Record<string, (payload: unknown) => void> = {};
  let removed = 0;
  const scripts: { src: string; remove: () => void }[] = [];
  Object.defineProperty(globalThis, "window", {
    value: callbacks,
    configurable: true,
  });
  Object.defineProperty(globalThis, "document", {
    value: {
      createElement: () => ({ src: "", remove: () => removed++ }),
      head: {
        append: (script: { src: string; remove: () => void }) =>
          scripts.push(script),
      },
    },
    configurable: true,
  });
  const place = {
    id: "test",
    label: "Chicago",
    detail: "",
    coordinates: [-87.62, 41.87] as [number, number],
    kind: "address" as const,
    source: "Census" as const,
  };
  try {
    const pending = resolvePlaceArea(place, "v1.20");
    const url = new URL(scripts[0].src);
    assert.equal(url.searchParams.get("layers"), "Census Tracts,Counties");
    assert.equal(url.searchParams.get("vintage"), "ACS2024_Current");
    assert.equal(url.searchParams.get("format"), "jsonp");
    const callback = url.searchParams.get("callback")!;
    callbacks[callback](
      census({ "Census Tracts": [{ GEOID: "17031320400" }] }),
    );
    assert.equal(await pending, "17031320400");
    assert.equal(callbacks[callback], undefined);
    assert.equal(removed, 1);

    const controller = new AbortController();
    const aborted = resolvePlaceArea(
      place,
      "v1.19",
      "counties",
      controller.signal,
    );
    const abortCallback = new URL(scripts[1].src).searchParams.get("callback")!;
    const lateResponse = callbacks[abortCallback];
    controller.abort();
    await assert.rejects(aborted, { name: "AbortError" });
    assert.equal(callbacks[abortCallback], undefined);
    assert.equal(removed, 2);
    lateResponse(census({ Counties: [{ GEOID: "17031" }] }));
    assert.equal(Object.keys(callbacks).length, 0);
  } finally {
    if (previousWindow)
      Object.defineProperty(globalThis, "window", previousWindow);
    else Reflect.deleteProperty(globalThis, "window");
    if (previousDocument)
      Object.defineProperty(globalThis, "document", previousDocument);
    else Reflect.deleteProperty(globalThis, "document");
  }
});

test("cancelled requests never start a network operation", async () => {
  const { searchPlaces, resolvePlaceArea } =
    await import("../src/clients/geocoding");
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(searchPlaces("Chicago", controller.signal), {
    name: "AbortError",
  });
  await assert.rejects(
    resolvePlaceArea(
      {
        id: "test",
        label: "Chicago",
        detail: "",
        coordinates: [-87, 41],
        kind: "place",
        source: "OpenStreetMap",
      },
      "v1.20",
      "tracts",
      controller.signal,
    ),
    { name: "AbortError" },
  );
});

test("address fallback failure preserves useful Photon results and JSONP requests time out cleanly", async (t) => {
  const { searchPlaces, resolvePlaceArea } =
    await import("../src/clients/geocoding");
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const previousDocument = Object.getOwnPropertyDescriptor(
    globalThis,
    "document",
  );
  const callbacks: Record<string, (payload: unknown) => void> = {};
  const scripts: { src: string; onerror: () => void; remove: () => void }[] =
    [];
  let removed = 0;
  Object.defineProperty(globalThis, "window", {
    value: callbacks,
    configurable: true,
  });
  Object.defineProperty(globalThis, "document", {
    value: {
      createElement: () => ({ src: "", remove: () => removed++ }),
      head: {
        append: (script: (typeof scripts)[number]) => scripts.push(script),
      },
    },
    configurable: true,
  });
  t.mock.method(globalThis, "fetch", async () => ({
    ok: true,
    json: async () => ({ features: [feature()] }),
  }));
  try {
    const pending = searchPlaces("12 Main Street Chicago IL");
    // Allow the two asynchronous fetch/JSON steps to reach the JSONP fallback.
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(scripts.length, 1);
    scripts[0].onerror();
    assert.equal((await pending)[0].label, "Chicago");
    assert.equal(Object.keys(callbacks).length, 0);

    t.mock.timers.enable({ apis: ["setTimeout"] });
    const timedOut = resolvePlaceArea(
      {
        id: "test",
        label: "Chicago",
        detail: "",
        coordinates: [-87, 41],
        kind: "place",
        source: "OpenStreetMap",
      },
      "v1.20",
    );
    const rejection = assert.rejects(timedOut, /timed out/);
    t.mock.timers.tick(10001);
    await rejection;
    assert.equal(Object.keys(callbacks).length, 0);
    assert.equal(removed, 2);
  } finally {
    t.mock.timers.reset();
    if (previousWindow)
      Object.defineProperty(globalThis, "window", previousWindow);
    else Reflect.deleteProperty(globalThis, "window");
    if (previousDocument)
      Object.defineProperty(globalThis, "document", previousDocument);
    else Reflect.deleteProperty(globalThis, "document");
  }
});
