import bins from '../../pipeline/reference/rating-bins.json';
import { multiplierStops, ratingNames, scenarioKey, metricValue, type Hazard, type Metric, type Values, type ViewState } from './risk';

export type RatingInterval = { label: string; lower: number | null; upper: number | null };
const numeric = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
export function countyCalculation(values: Values, view: ViewState) {
  const key = scenarioKey(view), baseline = view.period === 'base';
  const baselineLoss = numeric(values[`${view.hazard}_EALT`]);
  const baselineRiskValue = numeric(values[`${view.hazard}_RISKV`]);
  const multiplier = baseline ? 1 : numeric(metricValue(values,{...view,metric:"multiplier"}));
  const publishedLoss = numeric(values[`${key}_PALT`]);
  const product = (value: number | null) => value !== null && multiplier !== null ? value * multiplier : null;
  return {
    baselineLoss,
    annualLoss: baseline ? baselineLoss : publishedLoss ?? product(baselineLoss),
    baselineRiskValue,
    riskValue: baseline ? baselineRiskValue : numeric(values[`${key}_PRISKV`]) ?? product(baselineRiskValue),
    riskScore: numeric(values[baseline ? `${view.hazard}_RISKS` : `${key}_PRISKS`]),
    multiplier,
    derivedLoss: !baseline && publishedLoss === null,
  };
}
export function ratingIntervals(hazard: Hazard, metric: Metric): RatingInterval[] {
  const edges = metric === 'multiplier' ? multiplierStops : bins.hazards[hazard][metric === 'loss' ? 'annualLoss' : 'riskValue'];
  return ratingNames.map((label, i) => ({label, lower: i === 0 ? null : edges[i - 1], upper: i === 4 ? null : edges[i]}));
}
export function binIndex(value: number, intervals: RatingInterval[]) {
  return intervals.findIndex(interval => interval.upper === null || value <= interval.upper);
}
export function nriCountyUrl(fips: string) {
  if (!/^\d{5}$/.test(fips)) throw new Error('Expected a five-digit county FIPS');
  // FEMA retired the report viewer; RAPT supports selecting the current NRI county by ID.
  const selection = `NRI_ID%3D%27C${fips}%27`;
  return `https://experience.arcgis.com/experience/b702d290fee84bdf93cc398172b37058/page/RAPT-Standard?views=Data-Views%2CNRI%2CView#data_s=where:dataSource_12-a8b034164184436dbadb4c6d1b423d5b:${selection}&zoom_to_selection=true`;
}
export const formatDollars = (value: number | null) => value === null ? 'Unavailable' : new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',maximumFractionDigits:2}).format(value);
export const formatNumber = (value: number | null, digits = 6) => value === null ? 'Unavailable' : new Intl.NumberFormat('en-US', {maximumFractionDigits:digits}).format(value);
export function intervalLabel(interval: RatingInterval, metric: Metric) {
  const number = (value: number) => (metric === 'loss' ? '$' : '') + formatNumber(value, 10) + (metric === 'multiplier' ? '×' : '');
  if (interval.lower === null) return `≤ ${number(interval.upper!)}`;
  if (interval.upper === null) return `> ${number(interval.lower)}`;
  return `> ${number(interval.lower)} to ≤ ${number(interval.upper)}`;
}
