import { formatExactNumber } from './format';
export { formatNumber, formatDollars, formatExactNumber } from './format';
import bins from '../../pipeline/reference/rating-bins.json';
import { release, type RatingBins } from '../data/releases';
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
export function ratingIntervals(hazard: Hazard, metric: Metric, selectedBins: RatingBins = release.bins ?? bins): RatingInterval[] {
  const edges = metric === 'multiplier' ? multiplierStops : selectedBins.hazards[hazard]?.[metric === 'loss' ? 'annualLoss' : 'riskValue'];
  if (!edges || edges.length !== 4) throw new Error('Rating thresholds unavailable for this release');
  return ratingNames.map((label, i) => ({label, lower: i === 0 ? null : edges[i - 1], upper: i === 4 ? null : edges[i]}));
}
export function binIndex(value: number, intervals: RatingInterval[]) {
  return intervals.findIndex(interval => interval.upper === null || value <= interval.upper);
}
export function ratingChartScale(intervals: RatingInterval[], value: number | null, metric: Metric) {
  const target=Math.max(intervals[3].upper! * 1.25,(value ?? 0) * 1.1);
  if (metric !== 'multiplier') {
    // A smooth log scale retains zero while separating the small dollar/risk bins.
    const unit=10 ** Math.floor(Math.log10(intervals[0].upper! / 100));
    const ceiling=10 ** Math.ceil(Math.log10(target));
    const ticks=[0];
    for(let tick=unit*10;tick<=ceiling;tick*=10) ticks.push(tick);
    return {ceiling,ticks,position:(amount:number)=>Math.log1p(amount/unit)/Math.log1p(ceiling/unit)};
  }
  const power=10 ** Math.floor(Math.log10(target / 5));
  const step=([1,2,2.5,5,10].find(n=>n >= target / 5 / power) ?? 10) * power;
  const ceiling=Math.ceil(target / step) * step;
  return {ceiling,ticks:Array.from({length:Math.round(ceiling/step)+1},(_,i)=>i*step),position:(amount:number)=>amount/ceiling};
}
export function nriCountyUrl(fips: string) {
  if (!/^(?:\d{5}|\d{11})$/.test(fips)) throw new Error('Expected a five- or eleven-digit FIPS');
  // RAPT uses separate NRI data sources for counties and census tracts.
  const source = fips.length === 11 ? 'dataSource_12-d62a395a526349e5bdc9ac8064198347' : 'dataSource_12-a8b034164184436dbadb4c6d1b423d5b';
  const selection = `NRI_ID%3D%27${fips.length === 11 ? 'T' : 'C'}${fips}%27`;
  return `https://experience.arcgis.com/experience/b702d290fee84bdf93cc398172b37058/page/RAPT-Standard?views=Data-Views%2CNRI%2CView#data_s=where:${source}:${selection}&zoom_to_selection=true`;
}
export function intervalLabel(interval: RatingInterval, metric: Metric) {
  const number = (value: number) => (metric === 'loss' ? '$' : '') + formatExactNumber(value) + (metric === 'multiplier' ? '×' : '');
  if (interval.lower === null) return `≤ ${number(interval.upper!)}`;
  if (interval.upper === null) return `> ${number(interval.lower)}`;
  return `> ${number(interval.lower)} to ≤ ${number(interval.upper)}`;
}
