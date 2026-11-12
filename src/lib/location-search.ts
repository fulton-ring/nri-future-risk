import type { County } from "./risk";
import type { PlaceResult } from "../clients/geocoding";
export type LocalPlace = PlaceResult & { areaId?: string };
const stateNames =
  "AL Alabama|AK Alaska|AZ Arizona|AR Arkansas|CA California|CO Colorado|CT Connecticut|DE Delaware|DC District of Columbia|FL Florida|GA Georgia|HI Hawaii|ID Idaho|IL Illinois|IN Indiana|IA Iowa|KS Kansas|KY Kentucky|LA Louisiana|ME Maine|MD Maryland|MA Massachusetts|MI Michigan|MN Minnesota|MS Mississippi|MO Missouri|MT Montana|NE Nebraska|NV Nevada|NH New Hampshire|NJ New Jersey|NM New Mexico|NY New York|NC North Carolina|ND North Dakota|OH Ohio|OK Oklahoma|OR Oregon|PA Pennsylvania|RI Rhode Island|SC South Carolina|SD South Dakota|TN Tennessee|TX Texas|UT Utah|VT Vermont|VA Virginia|WA Washington|WV West Virginia|WI Wisconsin|WY Wyoming|PR Puerto Rico|VI Virgin Islands|GU Guam|MP Northern Mariana Islands|AS American Samoa";
const states = Object.fromEntries(
  stateNames.split("|").map((s) => [s.slice(0, 2), s.slice(3)]),
);
const normalize = (s: string) =>
  s
    .toLowerCase()
    .replace(/\b(county|parish|borough|planning region)\b/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
export function localPlaces(counties: County[], query: string): LocalPlace[] {
  const q = normalize(query);
  if (!q) return [];
  const explicit = query.match(
    /^\s*(?:fips\s*)?(\d{11})\s*$|^\s*fips\s*(\d{5})\s*$/i,
  );
  if (explicit)
    return counties
      .filter((c) => c.id === (explicit[1] || explicit[2]))
      .map((c) => asPlace(c, c.id));
  if (/^\d/.test(q)) return [];
  const tokens = q.split(" ");
  const groups = new Map<string, LocalPlace>();
  for (const c of counties) {
    const name =
      c.id.length === 11 ? c.name.split(" · ").slice(1).join(" · ") : c.name;
    if (
      !name ||
      !tokens.every((t) =>
        normalize(`${name} ${c.state} ${states[c.state] ?? ""}`)
          .split(" ")
          .some((w) => w.startsWith(t)),
      )
    )
      continue;
    const key = c.id.slice(0, 5);
    const existing = groups.get(key);
    if (existing && c.id.length === 11) {
      const b = existing.bounds!;
      existing.bounds = [
        Math.min(b[0], c.bounds[0]),
        Math.min(b[1], c.bounds[1]),
        Math.max(b[2], c.bounds[2]),
        Math.max(b[3], c.bounds[3]),
      ];
    } else
      groups.set(key, {
        ...asPlace(c, c.id.length === 5 ? c.id : undefined),
        id: `county:${key}`,
        label: name,
      });
  }
  return [...groups.values()].slice(0, 6);
}
function asPlace(c: County, areaId?: string): LocalPlace {
  return {
    id: c.id,
    label: c.name.replace(/\s*·\s*/g, ", "),
    detail: c.state,
    coordinates: [
      (c.bounds[0] + c.bounds[2]) / 2,
      (c.bounds[1] + c.bounds[3]) / 2,
    ],
    bounds: c.bounds,
    kind: "place",
    source: "Census",
    areaId,
  };
}
