import { useId, useState } from "react";
import { List, X } from "lucide-react";
import { countyCalculation } from "../../lib/calculations";
import RatingBins from "../counties/RatingBins";
import {
  colorFor,
  metrics,
  metricValue,
  multiplierStops,
  ratingNames,
  type ViewState,
  type County,
} from "../../lib/risk";
export default function Legend({
  view,
  county,
}: {
  view: ViewState;
  county?: County;
}) {
  const [expanded, setExpanded] = useState(true);
  const contentId = useId();
  const values = county ? countyCalculation(county.values, view) : null;
  const value = values
    ? view.metric === "loss"
      ? values.annualLoss
      : view.metric === "risk"
        ? values.riskValue
        : values.multiplier
    : null;
  const source = county ? metricValue(county.values, view) : null;
  const hasBin =
    typeof source === "number" ||
    (typeof source === "string" &&
      ratingNames.some((name) => source.startsWith(name)));
  return (
    <div
      className="map-legend"
      data-collapsed={!expanded}
      aria-label={`${metrics[view.metric]} legend`}
    >
      <div className="legend-toolbar">
        <button
          type="button"
          className="legend-toggle"
          aria-label={expanded ? "Hide legend" : "Show legend"}
          title={expanded ? "Hide legend" : "Show legend"}
          aria-expanded={expanded}
          aria-controls={contentId}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? (
            <X size={18} aria-hidden="true" />
          ) : (
            <List size={18} aria-hidden="true" />
          )}
        </button>
      </div>
      <div id={contentId} hidden={!expanded}>
        <RatingBins view={view} value={hasBin ? value : null} />
        <div className="legend-missing">
          {[
            null,
            "No Rating",
            "Not Applicable",
            "No Expected Annual Losses",
          ].map((value, i) => (
            <span key={i}>
              <i style={{ background: colorFor(value, view.metric) }} />
              {
                [
                  "Unavailable",
                  "No rating",
                  "Not applicable",
                  "No modeled baseline losses",
                ][i]
              }
            </span>
          ))}
        </div>
        <span className="sr-only">
          {view.metric === "multiplier"
            ? `Display thresholds: ${multiplierStops.join(", ")}. These are visualization bins, not FEMA risk ratings.`
            : ratingNames.join(", ")}
        </span>
      </div>
    </div>
  );
}
