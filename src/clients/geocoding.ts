/** Public, keyless geocoding for the static site. Addresses stay out of app URLs/storage. */
export type PlaceResult = {
  id: string;
  label: string;
  detail: string;
  coordinates: [number, number];
  bounds?: [number, number, number, number];
  kind: "address" | "place";
  source: "OpenStreetMap" | "Census";
};

type RecordValue = Record<string, unknown>;
const record = (value: unknown): RecordValue =>
  value !== null && typeof value === "object" ? (value as RecordValue) : {};
const text = (value: unknown): string =>
  typeof value === "string" ? value.trim() : "";
const unique = (values: string[]) => [...new Set(values.filter(Boolean))];
const states = new Set(
  "01 02 04 05 06 08 09 10 11 12 13 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 44 45 46 47 48 49 50 51 53 54 55 56 60 66 69 72 78".split(
    " ",
  ),
);

function coordinates(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length !== 2) return null;
  const [x, y] = value;
  return typeof x === "number" &&
    typeof y === "number" &&
    Number.isFinite(x) &&
    Number.isFinite(y) &&
    Math.abs(x) <= 180 &&
    Math.abs(y) <= 90
    ? [x, y]
    : null;
}

export function parsePhotonResults(payload: unknown): PlaceResult[] {
  const features = record(payload).features;
  if (!Array.isArray(features)) return [];
  const results: PlaceResult[] = [];
  for (const feature of features) {
    const f = record(feature),
      p = record(f.properties);
    if (
      !["US", "PR", "VI", "GU", "MP", "AS", "UM"].includes(
        text(p.countrycode).toUpperCase(),
      )
    )
      continue;
    const point = coordinates(record(f.geometry).coordinates);
    if (!point) continue;
    const street = [text(p.housenumber), text(p.street)]
      .filter(Boolean)
      .join(" ");
    const label =
      text(p.name) || street || text(p.city) || text(p.county) || text(p.state);
    if (!label) continue;
    const kind =
      [
        "city",
        "town",
        "village",
        "hamlet",
        "suburb",
        "district",
        "locality",
        "county",
        "state",
        "postcode",
        "country",
      ].includes(text(p.type)) ||
      ["city", "town", "village", "county", "state", "postcode"].includes(
        text(p.osm_value),
      )
        ? "place"
        : "address";
    const detail = unique([
      street,
      text(p.city) || text(p.county),
      text(p.state),
      text(p.postcode),
    ])
      .filter((value) => value !== label)
      .join(", ");
    const result: PlaceResult = {
      id: `osm:${text(p.osm_type)}:${String(p.osm_id ?? `${point[0]},${point[1]}`)}`,
      label,
      detail,
      coordinates: point,
      kind,
      source: "OpenStreetMap",
    };
    if (Array.isArray(p.extent) && p.extent.length === 4) {
      const [west, north, east, south] = p.extent;
      if (
        coordinates([west, south]) &&
        coordinates([east, north]) &&
        west <= east &&
        south <= north
      )
        result.bounds = [west, south, east, north];
    }
    if (!results.some((existing) => existing.id === result.id))
      results.push(result);
  }
  return results;
}

export function parseCensusAddresses(payload: unknown): PlaceResult[] {
  const matches = record(record(payload).result).addressMatches;
  if (!Array.isArray(matches)) return [];
  return matches.flatMap((value): PlaceResult[] => {
    const match = record(value),
      c = record(match.coordinates);
    const point = coordinates([c.x, c.y]),
      address = text(match.matchedAddress);
    if (!point || !address) return [];
    const [label, ...rest] = address.split(",").map((part) => part.trim());
    return [
      {
        id: `census:${point.join(",")}`,
        label,
        detail: rest.join(", "),
        coordinates: point,
        kind: "address",
        source: "Census",
      },
    ];
  });
}

export function censusVintage(baseline: string): string {
  return /(?:^|\b)v?1\.20(?:\b|$)/i.test(baseline)
    ? "ACS2024_Current"
    : "Census2020_Current";
}

/** Refuse ambiguous boundaries; callers separately verify membership in their selected dataset. */
export function parseCensusArea(
  payload: unknown,
  geography: "counties" | "tracts" = "tracts",
): string | null {
  const geographies = record(record(record(payload).result).geographies);
  const layers: [string, number][] =
    geography === "counties"
      ? [
          ["Counties", 5],
          ["Census Tracts", 11],
          ["Census Block Groups", 12],
        ]
      : [
          ["Census Tracts", 11],
          ["Census Block Groups", 12],
        ];
  for (const [name, length] of layers) {
    const rows = geographies[name];
    if (!Array.isArray(rows) || !rows.length) continue;
    const ids: string[] = [];
    for (const value of rows) {
      const row = record(value),
        id = text(row.GEOID);
      if (
        !new RegExp(`^\\d{${length}}$`).test(id) ||
        !states.has(id.slice(0, 2)) ||
        id.slice(2, 5) === "000"
      )
        return null;
      if (
        ["STATE", "COUNTY", ...(length >= 11 ? ["TRACT"] : [])].some(
          (field) =>
            row[field] !== undefined &&
            text(row[field]) !==
              (field === "STATE"
                ? id.slice(0, 2)
                : field === "COUNTY"
                  ? id.slice(2, 5)
                  : id.slice(5, 11)),
        )
      )
        return null;
      ids.push(id.slice(0, geography === "counties" ? 5 : 11));
    }
    return new Set(ids).size === 1 ? ids[0] : null;
  }
  return null;
}

const censusBase = "https://geocoding.geo.census.gov/geocoder/";
let callbackSequence = 0;

function abortError() {
  return new DOMException("Location search cancelled", "AbortError");
}
function checkAbort(signal?: AbortSignal) {
  if (signal?.aborted) throw abortError();
}

/** Census explicitly supports JSONP, while its JSON endpoint has no browser CORS. */
function censusRequest(
  path: string,
  params: Record<string, string>,
  signal?: AbortSignal,
): Promise<unknown> {
  checkAbort(signal);
  return new Promise((resolve, reject) => {
    const callback = `__nriGeocoder${Date.now()}_${++callbackSequence}`;
    const callbacks = window as unknown as Record<string, unknown>;
    const script = document.createElement("script");
    const url = new URL(path, censusBase);
    url.search = new URLSearchParams({
      ...params,
      format: "jsonp",
      callback,
    }).toString();
    script.src = url.href;
    script.referrerPolicy = "no-referrer";
    const cleanup = () => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
      script.remove();
      delete callbacks[callback];
    };
    const fail = (error: Error) => {
      cleanup();
      reject(error);
    };
    const onAbort = () => fail(abortError());
    const timer = setTimeout(
      () => fail(new Error("Location service timed out. Please try again.")),
      10000,
    );
    callbacks[callback] = (payload: unknown) => {
      cleanup();
      resolve(payload);
    };
    script.onerror = () =>
      fail(new Error("Location service is unavailable. Please try again."));
    signal?.addEventListener("abort", onAbort, { once: true });
    document.head.append(script);
  });
}

export async function searchPlaces(
  query: string,
  signal?: AbortSignal,
): Promise<PlaceResult[]> {
  checkAbort(signal);
  const trimmed = query.trim();
  if (trimmed.length < 3) return [];
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort, { once: true });
  const timer = setTimeout(() => controller.abort(), 10000);
  let results: PlaceResult[] = [],
    photonFailed = false;
  try {
    const url = new URL("https://photon.komoot.io/api/");
    url.search = new URLSearchParams({
      q: trimmed,
      limit: "8",
      lang: "en",
    }).toString();
    const response = await fetch(url, {
      signal: controller.signal,
      referrerPolicy: "no-referrer",
    });
    if (!response.ok) throw new Error("Location service unavailable");
    results = parsePhotonResults(await response.json());
  } catch {
    checkAbort(signal);
    photonFailed = true;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
  checkAbort(signal);
  // Ask Census only for a street-number query missing a precise Photon address.
  const houseNumber = trimmed.match(/^\s*(\d+[\w-]*)\s+\S/);
  if (
    houseNumber &&
    !results.some(
      (result) =>
        result.kind === "address" &&
        `${result.label} ${result.detail}`.startsWith(`${houseNumber[1]} `),
    )
  ) {
    try {
      const matches = parseCensusAddresses(
        await censusRequest(
          "locations/onelineaddress",
          { address: trimmed, benchmark: "Public_AR_Current" },
          signal,
        ),
      );
      results = [...matches, ...results];
      if (matches.length) photonFailed = false;
    } catch {
      checkAbort(signal);
    }
  }
  checkAbort(signal);
  if (photonFailed && !results.length)
    throw new Error("Location search is unavailable. Please try again.");
  // A city search should put cities ahead of similarly named businesses.
  if (!houseNumber)
    results.sort(
      (a, b) => Number(b.kind === "place") - Number(a.kind === "place"),
    );
  return results;
}

export async function resolvePlaceArea(
  place: PlaceResult,
  baseline: string,
  geography: "counties" | "tracts" = "tracts",
  signal?: AbortSignal,
): Promise<string | null> {
  checkAbort(signal);
  const point = coordinates(place.coordinates);
  if (!point) return null;
  const payload = await censusRequest(
    "geographies/coordinates",
    {
      x: String(point[0]),
      y: String(point[1]),
      benchmark: "Public_AR_Current",
      vintage: censusVintage(baseline),
      layers: "Census Tracts,Counties",
    },
    signal,
  );
  checkAbort(signal);
  return parseCensusArea(payload, geography);
}
