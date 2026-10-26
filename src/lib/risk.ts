import { release } from "../data/releases";
export const RELEASE = release.id;
export const hazards = {
  WFIR: "Wildfire",
  DRGT: "Drought",
  EXHT: "Extreme heat",
  CFLD: "Coastal flooding",
  HRCN: "Hurricane",
} as const;
export const metrics = {
  loss: "Annual loss rating",
  multiplier: "Change in annual loss",
  risk: "Risk rating",
} as const;
export type Hazard = keyof typeof hazards;
export type Metric = keyof typeof metrics;
export type Period = "base" | "mid" | "late";
export type Model = "L95" | "L99" | "N95" | "N99";
export type Values = Record<string, string | number | null>;
export type ViewState = {
  hazard: Hazard;
  metric: Metric;
  period: Period;
  emissions: "lower" | "higher";
  model: Model;
  county: string;
  opacity: number;
  terrain: boolean;
  camera?: { lat: number; lng: number; zoom: number };
};
export type County = {
  id: string;
  name: string;
  state: string;
  bounds: [number, number, number, number];
  values: Values;
  vintage?: string;
};
export type Value = string | number | null;
export const ratingNames = [
  "Very Low",
  "Relatively Low",
  "Relatively Moderate",
  "Relatively High",
  "Very High",
];
export const palette = ["#edf0c8", "#c6dba0", "#eab76b", "#cd7753", "#97433f"];
export const multiplierStops = [1, 1.5, 2, 4];
export const lossRanges: Record<Hazard, string[]> = {
  WFIR: ["<$85.9K", "$85.9K–842K", "$842K–5.88M", "$5.88M–49.5M", ">$49.5M"],
  DRGT: ["<$21.9K", "$21.9K–292K", "$292K–2.74M", "$2.74M–25.1M", ">$25.1M"],
  EXHT: ["<$10.9K", "$10.9K–241K", "$241K–1.87M", "$1.87M–17.3M", ">$17.3M"],
  CFLD: ["<$55K", "$55K–932K", "$932K–5.96M", "$5.96M–29.4M", ">$29.4M"],
  HRCN: ["<$625K", "$625K–7.36M", "$7.36M–43M", "$43M–191M", ">$191M"],
};
export function releaseHazards(status = release.status): Hazard[] {
  return status === "analysis" ? ["WFIR", "DRGT", "EXHT"] : Object.keys(hazards) as Hazard[];
}
export function releaseModels(status = release.status): Model[] {
  return status === "analysis" ? ["L95", "L99"] : ["L95", "L99", "N95", "N99"];
}
export function readState(search: string, status = release.status): ViewState {
  const p = new URLSearchParams(search);
  const hazard = p.get("hazard") as Hazard;
  const metric = p.get("metric") as Metric;
  const period = p.get("period");
  const model = p.get("model") as Model;
  const state: ViewState = {
    hazard: releaseHazards(status).includes(hazard)
      ? hazard
      : "WFIR",
    metric: Object.prototype.hasOwnProperty.call(metrics, metric)
      ? metric
      : "loss",
    period: period === "base" || period === "late" ? period : "mid",
    emissions: p.get("emissions") === "higher" ? "higher" : "lower",
    model: releaseModels(status).includes(model) ? model : "L95",
    county: /^\d{5}$/.test(p.get("county") || "") ? p.get("county")! : "",
    opacity:
      p.has("opacity") &&
      p.get("opacity") !== "" &&
      Number.isFinite(Number(p.get("opacity"))) &&
      Number(p.get("opacity")) >= 0 &&
      Number(p.get("opacity")) <= 1
        ? Number(p.get("opacity"))
        : 0.7,
    terrain: p.get("terrain") !== "0",
  };
  if (state.period === "base" && state.metric === "multiplier")
    state.period = "mid";
  const lat = Number(p.get("lat")),
    lng = Number(p.get("lng")),
    zoom = Number(p.get("zoom"));
  if (
    p.has("lat") &&
    p.has("lng") &&
    p.has("zoom") &&
    [lat, lng, zoom].every(Number.isFinite) &&
    Math.abs(lat) <= 85 &&
    Math.abs(lng) <= 180 &&
    zoom >= 1 &&
    zoom <= 12
  )
    state.camera = { lat, lng, zoom };
  return state;
}
export function writeState(state: ViewState): string {
  const p = new URLSearchParams({
    release: RELEASE,
    hazard: state.hazard,
    metric: state.metric,
    period: state.period,
    emissions: state.emissions,
    model: state.model,
    opacity: String(state.opacity),
    terrain: state.terrain ? "1" : "0",
  });
  if (state.county) p.set("county", state.county);
  if (state.camera)
    for (const [key, value] of Object.entries(state.camera))
      p.set(key, String(value));
  return `?${p}`;
}
export function scenarioKey(state: ViewState): string {
  return `${state.hazard}${state.hazard === "EXHT" ? `_${state.model}` : ""}_${state.period === "late" ? "LATE" : "MID"}_${state.emissions.toUpperCase()}`;
}
export function metricField(state: ViewState): string {
  if (state.period === "base")
    return `${state.hazard}_${state.metric === "loss" ? "EALR" : "RISKR"}`;
  return `${scenarioKey(state)}_${state.metric === "loss" ? "PALR" : state.metric === "risk" ? "PRISKR" : "HM"}`;
}
export function metricValue(values: Values, state: ViewState): Value {
  const key = scenarioKey(state);
  if (state.metric === "multiplier" && values[`${key}_DELTAR`] === "No Rating")
    return "No Rating";
  return values[metricField(state)] ?? null;
}
export function colorFor(value: Value, metric: Metric): string {
  if (value === null || value === "Insufficient Data") return "#b6b3ac";
  if (value === "Not Applicable") return "#e5e0d8";
  if (value === "No Rating") return "#fffff8";
  if (value === "No Expected Annual Losses") return "#d9e6e8";
  if (metric === "multiplier" && typeof value === "number")
    return palette[multiplierStops.filter((stop) => value > stop).length];
  const index = ratingNames.findIndex(
    (name) => typeof value === "string" && value.startsWith(name),
  );
  return index < 0 ? "#b6b3ac" : palette[index];
}
export function describeValue(value: Value, metric: Metric): string {
  if (value === null) return "Data unavailable";
  if (typeof value === "number")
    return metric === "multiplier"
      ? `${value.toFixed(2)}×`
      : value.toLocaleString("en-US");
  return value;
}
export function periodLabel(period: Period): string {
  return period === "base"
    ? "Baseline"
    : period === "mid"
      ? "Mid-century"
      : "Late-century";
}
export function changeLabel(value: Value): string {
  if (typeof value !== "number") return describeValue(value, "multiplier");
  const change = (value - 1) * 100;
  return `${Math.abs(change).toLocaleString("en-US", { maximumFractionDigits: 1 })}% ${change < 0 ? "less" : "more"} than baseline`;
}

export function pathwayLabel(
  hazard: Hazard,
  emissions: ViewState["emissions"],
): string {
  if (hazard === "CFLD")
    return emissions === "lower" ? "Intermediate SLR" : "High SLR";
  if (hazard === "HRCN") return emissions === "lower" ? "RCP 4.5" : "RCP 8.5";
  return emissions === "lower" ? "SSP2-4.5" : "SSP5-8.5";
}
