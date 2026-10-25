import {
  colorFor,
  lossRanges,
  metrics,
  multiplierStops,
  palette,
  ratingNames,
  type ViewState,
} from "../../lib/risk";
export default function Legend({ view }: { view: ViewState }) {
  return (
    <div className="map-legend" aria-label={`${metrics[view.metric]} legend`}>
      <div className="legend-scale">
        {palette.map((color, i) => (
          <div key={color}>
            <i style={{ background: color }} />
            <span>
              {view.metric === "multiplier"
                ? ["≤1×", ">1–1.5×", ">1.5–2×", ">2–4×", ">4×"][i]
                : ["Very low", "Low", "Moderate", "High", "Very high"][i]}
            </span>
          </div>
        ))}
      </div>
      {view.metric === "loss" && (
        <div className="legend-ranges">
          {lossRanges[view.hazard].map((range, i) => (
            <span key={range} title={ratingNames[i]}>
              {range}
            </span>
          ))}
        </div>
      )}
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
