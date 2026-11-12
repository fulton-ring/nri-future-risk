import useSWR from 'swr';
import type { ReactNode } from 'react';
import { assetUrl } from '../../clients/api';
import { release, isTract, areaLabel, areasLabel } from '../../data/releases';
import { countyCalculation, formatDollars, formatNumber, formatExactNumber, nriCountyUrl, ratingIntervals, binIndex } from '../../lib/calculations';
import { areaName, scenarioKey, metricValue, ratingNames, type County, type ViewState, type HeatDetails } from '../../lib/risk';

type HeatAsset = {path:string; sha256:string; snapshotSha256:string};
type Explanation = {schemaVersion:number; snapshotSha256:string; counties:Record<string,Record<string,HeatDetails>>};
type ReleaseDetails = {heatCalculations?:HeatAsset; parameters?:{wildfireElasticity?:number;wildfireEnsemble?:string;wildfireVariable?:string}};
const extras=release as typeof release & ReleaseDetails;
async function loadHeat(asset:HeatAsset):Promise<Explanation> {
  const response=await fetch(assetUrl(asset.path));
  if(!response.ok)throw new Error('Calculation inputs could not be loaded');
  const bytes=await response.arrayBuffer();
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
  if(hash !== asset.sha256)throw new Error('Calculation input hash mismatch');
  const result=JSON.parse(new TextDecoder().decode(bytes)) as Explanation;
  if(result.schemaVersion !== 1 || result.snapshotSha256 !== asset.snapshotSha256)throw new Error('Calculation inputs belong to a different snapshot');
  return result;
}

export default function CalculationDetails({county,view,children}: {county:County;view:ViewState;children?:ReactNode}) {
  const values=countyCalculation(county.values,view), future=view.period !== 'base';
  const updatedSeries=release.status === 'analysis' && (view.hazard === 'DRGT' || view.hazard === 'WFIR' || (view.hazard === 'EXHT' && ['L95','L99'].includes(view.model)));
  const rebuilt=updatedSeries && county.vintage !== 'FEMA archive';
  const asset=future && rebuilt && view.hazard === 'EXHT' ? extras.heatCalculations : undefined;
  const {data,error,isLoading}=useSWR(asset?.sha256,()=>loadHeat(asset!),{revalidateOnFocus:false,revalidateOnReconnect:false,shouldRetryOnError:false});
  const heat=county.heatCalculations?.[scenarioKey(view)] ?? data?.counties[county.id]?.[scenarioKey(view)];
  const selected=view.metric === 'loss' ? values.annualLoss : view.metric === 'risk' ? values.riskValue : values.multiplier;
  const gamma=extras.parameters?.wildfireElasticity;
  const publishedRating=metricValue(county.values,view);
  const computedRating=selected === null || view.metric === 'multiplier' ? null : ratingIntervals(view.hazard,view.metric)[binIndex(selected,ratingIntervals(view.hazard,view.metric))].label;
  const mismatch=!rebuilt && computedRating && typeof publishedRating === 'string' && ratingNames.some(label=>publishedRating.startsWith(label)) && !publishedRating.startsWith(computedRating);
  return <section className="county-calculations" aria-label={`${areaLabel} values and calculations`}>
    <dl className="county-numbers">
      <div><dt>Annual loss</dt><dd title={values.annualLoss === null ? undefined : `$${formatExactNumber(values.annualLoss)}/year`}>{formatDollars(values.annualLoss)}<small>per year</small></dd></div>
      <div><dt>Risk score</dt><dd title={formatExactNumber(values.riskScore)}>{formatNumber(values.riskScore)}<small>{future && release.rankingPopulation === 'CONUS' ? 'CONUS percentile' : 'national percentile'} (0–100)</small></dd></div>
      {future && <div><dt>{rebuilt ? 'Applied multiplier' : 'Published multiplier'}</dt><dd title={`${formatExactNumber(values.multiplier)}×`}>{formatNumber(values.multiplier)}{values.multiplier !== null && '×'}{heat && heat.rawMultiplier < 1 && heat.appliedMultiplier === 1 && <span className="multiplier-floor"> (floored to 1 from {formatNumber(heat.rawMultiplier)})</span>}</dd></div>}
    </dl>
    {children}
    <details className="data-details calculation-details">
      <summary>How this {areaLabel} is calculated</summary>
      <p>Downloads include unrounded values.</p>
      {future ? <>
        {values.annualLoss !== null && values.multiplier !== null ? <p className="calculation-equation">Annual loss ≈ {formatDollars(values.baselineLoss)} × {formatNumber(values.multiplier)} ≈ <strong>{formatDollars(values.annualLoss)}/year</strong>.</p> : <p>{release.baseline === 'NRI v1.20' ? values.multiplier === null ? 'Climate coverage is unavailable for this area and hazard. Future values are withheld; baseline values remain available.' : 'The NRI baseline has no annual-loss estimate for this area and hazard.' : 'This record has no usable multiplier for deriving annual loss. Its published rating and score remain available; an unavailable multiplier is not zero losses.'}</p>}
        {values.riskValue !== null && <p>Risk value ≈ {formatNumber(values.baselineRiskValue)} × {formatNumber(values.multiplier)} ≈ <strong>{formatNumber(values.riskValue)}</strong>. Its percentile rank is the risk score; its value determines the risk category.</p>}
        {mismatch && <p className="calculation-warning">Archive discrepancy: the published category is {String(publishedRating)}, while the multiplier-derived value falls in {computedRating}. The original category is retained; review the source fields before using this derived value.</p>}
        {!rebuilt && <p>The multiplier is from FEMA’s archive. {updatedSeries ? 'Its risk percentile is recomputed across the selected scenario’s full county population.' : 'The risk score is also archived.'} {values.derivedLoss && 'The dollar loss shown here is calculated from the archived multiplier and baseline loss.'} Underlying climate ratios are not included in the archive.</p>}
        {updatedSeries && <p>Risk scores rank {release.rankingPopulation === 'CONUS' ? `the CONUS ${areasLabel} population` : 'all 3,231 baseline counties'} separately for this scenario. A score can change when other {areasLabel} change, even if this {areaLabel}’s loss stays constant. Baseline exposure and social conditions stay fixed.</p>}
        {rebuilt && view.hazard === 'EXHT' && <>
          {heat && <dl className="calculation-inputs">
            <div><dt>Historical percentile days/year</dt><dd>{formatNumber(heat.historicalDaysPerYear)}</dd></div>
            <div><dt>Future qualifying days/year</dt><dd>{formatNumber(heat.futureDaysPerYear)}</dd></div>
            <div><dt>Raw heat ratio</dt><dd>{formatNumber(heat.futureDaysPerYear)} ÷ {formatNumber(heat.historicalDaysPerYear)} ≈ {formatNumber(heat.rawMultiplier)}×</dd></div>
            <div><dt>Applied heat multiplier</dt><dd>max(1, {formatNumber(heat.rawMultiplier)}) = {formatNumber(heat.appliedMultiplier)}×</dd></div>
          </dl>}
          {isLoading && <p role="status">Loading verified heat inputs…</p>}
          {error && <p role="status">Heat input details could not be loaded. Published county values remain available.</p>}
          {!asset && !heat && <p>This release does not include a verified raw-ratio breakdown.</p>}
          <p>Historical days exceed the historical {view.model === 'L99' ? '99th' : '95th'} percentile of daily minimum temperature. Future days must also exceed 23.07°C (73.53°F). {areaLabel === 'county' ? 'County' : 'Census tract'} event-day totals are area-weighted over supported cells.</p>
          {asset && <a href={assetUrl(asset.path)}>Verified heat inputs and raw ratios</a>}
          <p>Heat multiplier = max(1, future days ÷ historical days). The temperature screen applies to future days; the historical denominator uses the percentile alone. A 1× floor can hide a raw ratio below one and does not establish no warming.</p>
        </>}
        {rebuilt && view.hazard === 'WFIR' && <p>Wildfire multiplier = (future area-mean FWI ÷ historical area-mean FWI)<sup>γ</sup>. {extras.parameters?.wildfireEnsemble || 'NASA ensemble'} {extras.parameters?.wildfireVariable === 'FWI' ? 'annual mean FWI' : extras.parameters?.wildfireVariable || 'FWI'}; γ {typeof gamma === 'number' ? `= ${formatNumber(gamma)}` : 'is fitted for this version'} using county baseline wildfire loss, fuel shares and burnable-share weighting. {isTract && 'The county-fitted γ is reused for census tracts.'}</p>}
        {rebuilt && view.hazard === 'DRGT' && <p>Drought multiplier = max(1, {areaLabel} area-weighted future/historical drought-frequency ratio). SPEI-3 ≤ −1.6 marks drought months; all days in those months count. Historical drought-day denominators are floored at 15 days across the entire 1985–2014 baseline, not 15 days per year.</p>}
      </> : <p>Baseline values are from FEMA’s frozen {release.baseline} data. Annual loss is the expected total economic loss per year; the risk value also reflects social vulnerability and community resilience. The score is a national percentile, not a probability.</p>}
      <a href={assetUrl(`versions/${release.id}/methodology.html`)}>Methodology for this version</a>
      <a href={assetUrl(`versions/${release.id}/data.html`)}>Data and provenance for this version</a>
    </details>
    <a className="nri-county-link" href={nriCountyUrl(county.id)} target="_blank" rel="noreferrer">View {areaName(county)} in FEMA NRI / RAPT</a>
    <p className="caption nri-baseline-note">FEMA’s current report may use a newer baseline.</p>
  </section>;
}
