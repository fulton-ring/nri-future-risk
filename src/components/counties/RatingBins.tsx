import { useState } from 'react';
import { binIndex, formatDollars, formatExactNumber, formatNumber, intervalLabel, ratingIntervals } from '../../lib/calculations';
import { palette, type ViewState } from '../../lib/risk';

type Props = {view: ViewState; value?: number | null; inline?: boolean};
const ratingLabels=['Very low','Low','Moderate','High','Very high'];
const multiplierLabels=['≤1×','1–1.5×','1.5–2×','2–4×','>4×'];

function BinChart({view,value,inline}:Props) {
  const intervals=ratingIntervals(view.hazard,view.metric);
  const labels=view.metric === 'multiplier' ? multiplierLabels : ratingLabels;
  const current=value === null || value === undefined ? -1 : binIndex(value,intervals);
  const [pinned,setPinned]=useState<number|null>(null);
  const [hovered,setHovered]=useState<number|null>(null);
  const active=hovered ?? pinned ?? (!inline && current >= 0 ? current : null);
  const selected=active === null ? null : intervals[active];
  return <div className={`bin-explorer${inline ? " is-inline" : ""}`} onKeyDown={event=>{if(event.key==='Escape'){setPinned(null);setHovered(null);}}}>
    {current >= 0 && <p className="bin-county-value">County value: <strong title={formatExactNumber(value!)}>{view.metric === 'loss' ? formatDollars(value!) : `${formatNumber(value!)}${view.metric === 'multiplier' ? '×' : ''}`}</strong></p>}
    <div className="bin-bars" role="group" aria-label={`${view.metric === 'loss' ? 'Annual loss' : view.metric === 'risk' ? 'Risk value' : 'Map multiplier'} bins`}>
      {intervals.map((interval,i)=><button key={i} type="button"
        className={`bin-bar${i === active ? ' is-expanded' : ''}${i === current ? ' is-county' : ''}`}
        style={{background:palette[i],flexGrow:i === active ? 2.8 : 1}}
        aria-label={`${labels[i]}: ${intervalLabel(interval,view.metric)}${i === current ? '. Selected county' : ''}`}
        aria-pressed={pinned === i} title={intervalLabel(interval,view.metric)}
        onPointerEnter={()=>setHovered(i)} onPointerLeave={()=>setHovered(null)}
        onFocus={()=>setHovered(i)} onBlur={()=>setHovered(null)}
        onClick={()=>setPinned(pinned === i ? null : i)}>
        <span>{labels[i]}</span>{i === current && <small>County</small>}
      </button>)}
    </div>
    {selected ? <div className="bin-inspection" role="status" aria-live="polite">
      <strong>{view.metric === 'multiplier' ? 'Map interval' : selected.label}</strong>
      <span>{intervalLabel(selected,view.metric)}{view.metric === 'loss' ? ' / year' : ''}</span>
      <small>{selected.upper === null ? 'No upper limit' : 'Upper bound included'} · click to pin · Esc to reset</small>
    </div> : null}
    {(inline || !selected) && <p className="bin-hint">{selected ? "Click to pin · Esc to reset" : "Hover or select a band for its exact range."}</p>}
    <p className="bin-caption">{view.metric === 'risk' ? 'Categories use risk value, not the 0–100 percentile score.' : view.metric === 'loss' ? 'Total county loss per year · frozen NRI v1.19 cutoffs.' : 'Fixed map display intervals, not FEMA risk categories.'} Bands are categorical, not proportional.</p>
  </div>;
}

export default function RatingBins(props:Props) {
  const chart=<BinChart key={`${props.view.hazard}-${props.view.metric}-${props.value ?? 'all'}`} {...props} />;
  return props.inline ? chart : <details className="data-details bin-details">
    <summary>{props.view.metric === 'loss' ? 'Annual-loss' : props.view.metric === 'risk' ? 'Risk-rating' : 'Map multiplier'} bins</summary>
    {chart}
  </details>;
}
