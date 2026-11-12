import assert from "node:assert/strict";
import { test } from "node:test";
import { localPlaces } from "../src/lib/location-search.ts";
import type { County } from "../src/lib/risk.ts";
const counties = [
  {
    id: "17031010100",
    name: "Tract 0101.00 · Cook",
    state: "IL",
    bounds: [-88, 41, -87, 42],
  },
  {
    id: "17031010200",
    name: "Tract 0102.00 · Cook",
    state: "IL",
    bounds: [-89, 40, -87, 42],
  },
] as County[];
test("county queries group tracts and fit the county without selecting an arbitrary tract", () => {
  const matches = localPlaces(counties, "Cook County, Illinois");
  assert.equal(matches.length, 1);
  assert.equal(matches[0].areaId, undefined);
  assert.equal(matches[0].label, "Cook");
  assert.deepEqual(matches[0].bounds, [-89, 40, -87, 42]);
});
test("ZIP codes are not silently interpreted as county FIPS", () => {
  const rows = [{ ...counties[0], id: "17031", name: "Cook" }];
  assert.equal(localPlaces(rows, "17031").length, 0);
  assert.equal(localPlaces(rows, "FIPS 17031")[0].areaId, "17031");
  assert.equal(localPlaces(counties, "17031010100")[0].areaId, "17031010100");
});
