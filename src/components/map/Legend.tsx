import { countyCalculation } from "../../lib/calculations";
import RatingBins from "../counties/RatingBins";
import {
  colorFor,
  metrics,
  multiplierStops,
  ratingNames,
  type ViewState,
  type County,
} from "../../lib/risk";
export default function Legend({ view, county }: { view: ViewState; county?: County }) {
  const values=county ? countyCalculation(county.values,view) : null;
  const value=values ? view.metric === "loss" ? values.annualLoss : view.metric === "risk" ? values.riskValue : values.multiplier : null;
  return (
    <div className="map-legend" aria-label={`${metrics[view.metric]} legend`}>
      <RatingBins view={view} value={value} inline />
      <div className="legend-missing">
        {[null, "No Rating", "Not Applicable", "No Expected Annual Losses"].map(
          (value, i) => (
            <span key={i}>
              <i style={{ background: colorFor(value, view.metric) }} />
              {
                [
                  "Unavailable",
                  "No rating",
                  "Not applicable",
                  "No baseline losses",
                ][i]
              }
            </span>
          ),
        )}
      </div>
      <span className="sr-only">
        {view.metric === "multiplier"
          ? `Display thresholds: ${multiplierStops.join(", ")}. These are visualization bins, not FEMA risk ratings.`
          : ratingNames.join(", ")}
      </span>
    </div>
  );
}
