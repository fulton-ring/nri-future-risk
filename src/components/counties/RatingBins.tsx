import { useState } from 'react';
import { areaLabel } from '../../data/releases';
import { binIndex, formatDollars, formatExactNumber, formatNumber, intervalLabel, ratingIntervals, ratingChartScale } from '../../lib/calculations';
import { palette, type ViewState } from '../../lib/risk';

type Props = {view: ViewState; value?: number | null};
const categoryLabels=['Very low','Low','Moderate','High','Very high'];
const multiplierLabels=['≤1×','1–1.5×','1.5–2×','2–4×','>4×'];

function BinChart({view,value}:Props) {
  const intervals=ratingIntervals(view.hazard,view.metric);
  const labels=view.metric === 'multiplier' ? multiplierLabels : categoryLabels;
  const current=value === null || value === undefined ? -1 : binIndex(value,intervals);
  const [pinned,setPinned]=useState<number|null>(null);
  const [hovered,setHovered]=useState<number|null>(null);
  const active=hovered ?? pinned;
  const selected=active === null ? null : intervals[active];
  const {ceiling,ticks,position}=ratingChartScale(intervals,value ?? null,view.metric);
  const left=60, top=10, plotWidth=330, plotHeight=112, bottom=top+plotHeight, column=plotWidth/5, chartWidth=400, chartHeight=bottom+43;
  const y=(amount:number)=>bottom-position(amount)*plotHeight;
  const tick=(amount:number)=>view.metric === 'loss' ? formatDollars(amount) : `${formatNumber(amount)}${view.metric === 'multiplier' ? '×' : ''}`;
  return <div className="bin-explorer" onKeyDown={event=>{if(event.key==='Escape'){setPinned(null);setHovered(null);}}}>
    <div className="range-chart">
      <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-label={`${view.metric === 'loss' ? 'Annual loss in dollars per year' : view.metric === 'risk' ? 'Risk index value, not a dollar-loss estimate' : 'Multiplier'} on the left axis${view.metric === 'multiplier' ? '' : ', logarithmic scale including zero'}; five categories on the bottom. Bars show each category’s range. The highest range has no upper limit.`}>
        {ticks.map(amount=><g key={amount}>
          <line x1={left} x2={left+plotWidth} y1={y(amount)} y2={y(amount)} className="range-grid" />
          <text x={left-7} y={y(amount)+3} textAnchor="end" className="range-tick">{tick(amount)}</text>
        </g>)}
        {intervals.map((interval,i)=>{
          const center=left+column*(i+0.5), width=column*(i === active ? 0.7 : 0.48);
          const low=interval.lower ?? 0, high=interval.upper ?? ceiling;
          return <g key={i}>
            {interval.upper === null
              ? <path d={`M${center-width/2},${y(low)} V${top+8} L${center},${top} L${center+width/2},${top+8} V${y(low)} Z`} fill={palette[i]} className="range-bar" />
              : <rect x={center-width/2} y={y(high)} width={width} height={Math.max(0,y(low)-y(high))} fill={palette[i]} className="range-bar" />}
            {interval.upper !== null && <line x1={center-width/2} x2={center+width/2} y1={y(high)} y2={y(high)} className="range-bar-cap" />}
            {i === current && value !== null && value !== undefined && <circle cx={center} cy={y(value)} r={3} className="range-county-marker"><title>Selected {areaLabel}: {tick(value)} ({formatExactNumber(value)})</title></circle>}
            <text x={center} y={bottom+15} textAnchor="middle" className={`range-category${i === current ? ' is-county' : ''}`}>{labels[i]}</text>
            {i === current && <text x={center} y={bottom+26} textAnchor="middle" className="range-county-label">{areaLabel === 'county' ? 'County' : 'Tract'}</text>}
          </g>;
        })}
        <line x1={left} x2={left} y1={top} y2={bottom} className="range-axis" />
        <line x1={left} x2={left+plotWidth} y1={bottom} y2={bottom} className="range-axis" />
        <text x={left+plotWidth/2} y={chartHeight-4} textAnchor="middle" className="range-axis-title">Category</text>
      </svg>
      <div className="range-chart-targets" role="group" aria-label="Inspect category ranges"
        style={{left:`${left/chartWidth*100}%`,right:`${(chartWidth-left-plotWidth)/chartWidth*100}%`,top:`${top/chartHeight*100}%`,bottom:`${(chartHeight-bottom-29)/chartHeight*100}%`}}>
        {intervals.map((interval,i)=><button key={i} type="button" className="range-target"
          aria-label={`${labels[i]}: ${intervalLabel(interval,view.metric)}${i === current ? `. Selected ${areaLabel}` : ''}`}
          aria-pressed={pinned === i} title={intervalLabel(interval,view.metric)}
          onPointerEnter={()=>setHovered(i)} onPointerLeave={()=>setHovered(null)}
          onFocus={()=>setHovered(i)} onBlur={()=>setHovered(null)}
          onClick={()=>setPinned(pinned === i ? null : i)} />)}
      </div>
    </div>
    {selected && <div className="bin-inspection" role="status" aria-live="polite">
      <strong>{view.metric === 'multiplier' ? 'Map interval' : selected.label}</strong>
      <span>{intervalLabel(selected,view.metric)}{view.metric === 'loss' ? ' / year' : ''}</span>
      <small>{selected.upper === null ? 'No upper limit.' : 'Upper bound included.'}</small>
    </div>}
    <p className="bin-hint">{selected ? 'Click to pin. Esc to reset.' : 'Select a bar for the exact range.'}</p>
    {view.metric === 'risk' && <p className="bin-caption">Loss adjusted for vulnerability and resilience; not a dollar-loss estimate. The risk score is a separate 0–100 percentile.</p>}
  </div>;
}
export default function RatingBins(props:Props) {
  return <BinChart key={`${props.view.hazard}-${props.view.metric}-${props.value ?? 'all'}`} {...props} />;
}
