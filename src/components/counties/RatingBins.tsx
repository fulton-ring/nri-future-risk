import { binIndex, formatNumber, intervalLabel, ratingIntervals } from '../../lib/calculations';
import { palette, type ViewState } from '../../lib/risk';

export default function RatingBins({view, value}: {view: ViewState; value?: number | null}) {
  const intervals=ratingIntervals(view.hazard,view.metric);
  const current=value === null || value === undefined ? -1 : binIndex(value,intervals);
  return <details className="data-details bin-details">
    <summary>Exact {view.metric === 'loss' ? 'annual-loss' : view.metric === 'risk' ? 'risk-rating' : 'map multiplier'} bins</summary>
    <p>{view.metric === 'risk' ? 'Ratings use baseline risk-value cutoffs, not percentile score. The 0–100 score has no fixed category cutoffs.' : view.metric === 'loss' ? 'Cutoffs recovered from the full NRI v1.19 baseline, in dollars per year. Loss totals are not per person.' : 'Fixed display intervals for this map; these are not FEMA risk-rating categories.'} Exact upper boundaries stay in the lower bin.</p>
    {current >= 0 && <p>Selected value: <strong>{view.metric === 'loss' ? '$' : ''}{formatNumber(value!,10)}{view.metric === 'multiplier' ? '×' : ''}</strong></p>}
    <table>
      <thead><tr><th scope="col">{view.metric === 'multiplier' ? 'Map color' : 'Rating'}</th><th scope="col">{view.metric === 'loss' ? 'Annual loss ($/year)' : view.metric === 'risk' ? 'Risk value' : 'Applied multiplier'}</th></tr></thead>
      <tbody>{intervals.map((interval,i)=><tr key={i} className={i === current ? 'active-bin' : undefined}>
        <th scope="row"><i className="bin-swatch" style={{background:palette[i]}} />{view.metric === 'multiplier' ? `Color ${i+1}` : interval.label}{i === current && <small>Selected county</small>}</th>
        <td>{intervalLabel(interval,view.metric)}</td>
      </tr>)}</tbody>
    </table>
  </details>;
}
