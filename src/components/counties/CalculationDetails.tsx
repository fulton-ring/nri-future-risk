import useSWR from 'swr';
import { assetUrl } from '../../clients/api';
import { release } from '../../data/releases';
import { countyCalculation, formatDollars, formatNumber, nriCountyUrl } from '../../lib/calculations';
import { scenarioKey, type County, type ViewState } from '../../lib/risk';
import RatingBins from './RatingBins';

type HeatDetails = {historicalDaysPerYear:number; futureDaysPerYear:number; rawMultiplier:number; appliedMultiplier:number};
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

export default function CalculationDetails({county,view}: {county:County;view:ViewState}) {
  const values=countyCalculation(county.values,view), future=view.period !== 'base';
  const updatedSeries=release.status === 'analysis' && (view.hazard === 'DRGT' || view.hazard === 'WFIR' || (view.hazard === 'EXHT' && ['L95','L99'].includes(view.model)));
  const rebuilt=updatedSeries && county.vintage !== 'FEMA archive';
  const asset=future && rebuilt && view.hazard === 'EXHT' ? extras.heatCalculations : undefined;
  const {data,error,isLoading}=useSWR(asset?.sha256,()=>loadHeat(asset!),{revalidateOnFocus:false,revalidateOnReconnect:false,shouldRetryOnError:false});
  const heat=data?.counties[county.id]?.[scenarioKey(view)];
  const selected=view.metric === 'loss' ? values.annualLoss : view.metric === 'risk' ? values.riskValue : values.multiplier;
  const gamma=extras.parameters?.wildfireElasticity;
  return <section className="county-calculations" aria-label="County values and calculations">
    <dl className="county-numbers">
      <div><dt>Annual loss</dt><dd>{formatDollars(values.annualLoss)}<small>per year</small></dd></div>
      <div><dt>Risk score</dt><dd>{formatNumber(values.riskScore,4)}<small>national percentile · 0–100</small></dd></div>
      {future && <div><dt>Applied multiplier</dt><dd>{formatNumber(values.multiplier)}{values.multiplier !== null && '×'}</dd></div>}
      {heat && <div><dt>Raw heat ratio<small>before the 1× floor</small></dt><dd>{formatNumber(heat.rawMultiplier)}×</dd></div>}
    </dl>
    <details className="data-details calculation-details">
      <summary>How this county is calculated</summary>
      {future ? <>
        <p className="calculation-equation">Annual loss = {formatDollars(values.baselineLoss)} × {formatNumber(values.multiplier)} = <strong>{formatDollars(values.annualLoss)}/year</strong>.</p>
        <p>Risk value = {formatNumber(values.baselineRiskValue)} × {formatNumber(values.multiplier)} = <strong>{formatNumber(values.riskValue)}</strong>. Its percentile rank is the risk score; its value determines the risk category.</p>
        {!rebuilt && <p>The multiplier is from FEMA’s archive. {updatedSeries ? 'Its risk percentile is recomputed across the selected scenario’s full county population.' : 'The risk score is also archived.'} {values.derivedLoss && 'The dollar loss shown here is calculated from the archived multiplier and baseline loss.'} Underlying climate ratios are not included in the archive.</p>}
        {updatedSeries && <p>Risk scores rank all 3,231 baseline counties separately for this scenario. A score can change when other counties change, even if this county’s loss stays constant. Baseline exposure and social conditions stay fixed.</p>}
        {rebuilt && view.hazard === 'EXHT' && <>
          {heat && <dl className="calculation-inputs">
            <div><dt>Historical percentile days/year</dt><dd>{formatNumber(heat.historicalDaysPerYear)}</dd></div>
            <div><dt>Future qualifying days/year</dt><dd>{formatNumber(heat.futureDaysPerYear)}</dd></div>
            <div><dt>Raw heat ratio</dt><dd>{formatNumber(heat.futureDaysPerYear)} ÷ {formatNumber(heat.historicalDaysPerYear)} = {formatNumber(heat.rawMultiplier)}×</dd></div>
            <div><dt>Applied heat multiplier</dt><dd>max(1, {formatNumber(heat.rawMultiplier)}) = {formatNumber(heat.appliedMultiplier)}×</dd></div>
          </dl>}
          {isLoading && <p role="status">Loading verified heat inputs…</p>}
          {error && <p role="status">Heat input details could not be loaded. Published county values remain available.</p>}
          {!asset && <p>This version does not include a verified raw-ratio breakdown. Its source arrays are linked on the data page.</p>}
          <p>Historical days exceed the historical {view.model === 'L99' ? '99th' : '95th'} percentile of daily minimum temperature. Future days must also exceed 23.07°C (73.53°F). County event-day totals are area-weighted over supported cells.</p>
          {asset && <a href={assetUrl(asset.path)}>Verified heat inputs and raw ratios</a>}
          <p>Heat multiplier = max(1, future days ÷ historical days). The temperature screen applies to future days; the historical denominator uses the percentile alone. A 1× floor can hide a raw ratio below one and does not establish no warming.</p>
        </>}
        {rebuilt && view.hazard === 'WFIR' && <p>Wildfire multiplier = (future county-mean FWI ÷ historical county-mean FWI)<sup>γ</sup>. {extras.parameters?.wildfireEnsemble || 'NASA ensemble'} {extras.parameters?.wildfireVariable === 'FWI' ? 'annual mean FWI' : extras.parameters?.wildfireVariable || 'FWI'}; γ {typeof gamma === 'number' ? `= ${formatNumber(gamma,10)}` : 'is fitted for this version'} using baseline wildfire loss, fuel shares and burnable-share weighting.</p>}
        {rebuilt && view.hazard === 'DRGT' && <p>Drought multiplier = max(1, county area-weighted future/historical drought-frequency ratio). SPEI-3 ≤ −1.6 marks drought months; all days in those months count. Historical drought-day denominators are floored at 15 days across the entire 1985–2014 baseline, not 15 days per year.</p>}
      </> : <p>Baseline values are from FEMA’s frozen NRI v1.19 data. Annual loss is the expected total economic loss per year; the risk value also reflects social vulnerability and community resilience. The score is a national percentile, not a probability.</p>}
      <a href={assetUrl(`versions/${release.id}/methodology.html`)}>Methodology for this version</a>
      <a href={assetUrl(`versions/${release.id}/data.html`)}>Data and provenance for this version</a>
    </details>
    <RatingBins view={view} value={selected} />
    <a className="nri-county-link" href={nriCountyUrl(county.id)} target="_blank" rel="noreferrer">View {county.name} in FEMA NRI / RAPT</a>
    <p className="caption nri-baseline-note">FEMA’s current report may use a newer baseline.</p>
  </section>;
}
