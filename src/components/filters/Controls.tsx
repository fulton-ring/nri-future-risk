import { useId } from "react";
import {
  Flame,
  Droplets,
  Thermometer,
  Waves,
  Wind,
  Banknote,
  TrendingUp,
  Shield,
  Grid2X2,
  Globe,
} from "lucide-react";

const hazardIcons = {
  WFIR: Flame,
  DRGT: Droplets,
  EXHT: Thermometer,
  CFLD: Waves,
  HRCN: Wind,
};
const metricIcons = { loss: Banknote, multiplier: TrendingUp, risk: Shield };
import { release } from "../../data/releases";
import FieldHelp from "./FieldHelp";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import {
  hazards,
  releaseHazards,
  releaseModels,
  pathwayLabel,
  metrics,
  type ViewState,
  type Hazard,
  type Metric,
  type Model,
  type Period,
} from "../../lib/risk";
export default function Controls({
  view,
  onChange,
}: {
  view: ViewState;
  onChange: (change: Partial<ViewState>) => void;
}) {
  const id = useId();
  return (
    <div className="controls">
      <div className="control-field">
        <div className="field-label-row">
          <label htmlFor={`${id}-hazard`}>Hazard</label>
          <FieldHelp label="Hazard">
            The natural hazard to map. Each hazard is estimated separately from its own climate data,
            and the map shows one at a time. NRI v1.20 releases recalculate wildfire, drought and
            extreme heat only.
          </FieldHelp>
        </div>
        <Select
          value={view.hazard}
          onValueChange={(hazard) => onChange({ hazard: hazard as Hazard })}
        >
          <SelectTrigger className="atlas-select-trigger" id={`${id}-hazard`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="atlas-select-content">
            {releaseHazards().map((key) => {
              const label = hazards[key];
              const Icon = hazardIcons[key as Hazard];
              return (
                <SelectItem key={key} value={key} className="atlas-select-item">
                  <span className="select-option-label">
                    <Icon size={17} strokeWidth={1.6} aria-hidden="true" />
                    <span>{label}</span>
                  </span>
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
      </div>
      <div className="control-field">
        <div className="field-label-row">
          <label htmlFor={`${id}-metric`}>Map measure</label>
          <FieldHelp label="Map measure">
            <p><strong>Annual loss rating:</strong> projected average yearly economic loss, grouped into FEMA’s five categories.</p>
            <p><strong>Change in annual loss:</strong> future loss divided by today’s. 4× means four times the baseline; a large change on a small loss can still be a small dollar amount.</p>
            <p><strong>Risk rating:</strong> loss adjusted for social vulnerability and community resilience. It compares places; it is not the chance of an event.</p>
          </FieldHelp>
        </div>
        <Select
          value={view.metric}
          onValueChange={(metric) => onChange({ metric: metric as Metric })}
        >
          <SelectTrigger
            className="atlas-select-trigger"
            id={`${id}-metric`}
            aria-describedby={`${id}-metric-help`}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="atlas-select-content">
            {Object.entries(metrics).map(([key, label]) => {
              const Icon = metricIcons[key as Metric];
              return (
                <SelectItem key={key} value={key} className="atlas-select-item">
                  <span className="select-option-label">
                    <Icon size={17} strokeWidth={1.6} aria-hidden="true" />
                    <span>{label}</span>
                  </span>
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
        <p className="sr-only" id={`${id}-metric-help`}>
          {view.metric === "loss"
            ? "Projected yearly economic loss, grouped into five published categories."
            : view.metric === "risk"
              ? "Loss adjusted for social vulnerability and community resilience."
              : "Projected annual loss divided by baseline annual loss. 1× means no change."}
        </p>
      </div>
      <fieldset>
        <legend className="field-label-row">
          Time period
          <FieldHelp label="Time period">
            Baseline is today’s estimate. Mid-century averages 2036–2065 and late-century
            2070–2099. Population, buildings and adaptation are held at today’s levels, so the
            change comes from climate alone.
          </FieldHelp>
        </legend>
        <div className="segmented">
          {(
            [
              ["base", "Baseline"],
              ["mid", "Mid-century"],
              ["late", "Late-century"],
            ] as [Period, string][]
          ).map(([period, label]) => (
            <button
              key={period}
              aria-pressed={view.period === period}
              disabled={view.metric === "multiplier" && period === "base"}
              onClick={() => onChange({ period })}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="field-hint">
          {view.period === "base"
            ? `${release.baseline} baseline.`
            : view.hazard === "CFLD" || view.hazard === "HRCN"
              ? "Archived FEMA scenario. Projection periods vary by source."
              : view.period === "mid"
                ? "2036–2065"
                : "2070–2099"}
        </p>
      </fieldset>
      <fieldset disabled={view.period === "base"}>
        <legend className="field-label-row">
          {view.hazard === "CFLD" ? "Sea-level scenario" : "Emissions pathway"}
          <FieldHelp label={view.hazard === "CFLD" ? "Sea-level scenario" : "Emissions pathway"}>
            {view.hazard === "CFLD"
              ? "Coastal flooding uses NOAA sea-level rise scenarios: intermediate or high sea-level rise."
              : "How much greenhouse gas the world emits. Lower emissions (SSP2-4.5) assumes moderate cuts; higher emissions (SSP5-8.5) assumes emissions keep rising. Hurricanes use the older RCP 4.5 and 8.5 scenarios."}
          </FieldHelp>
        </legend>
        <div className="segmented">
          <button
            aria-pressed={view.emissions === "lower"}
            onClick={() => onChange({ emissions: "lower" })}
          >
            <span>
              {view.hazard === "CFLD" ? "Lower scenario" : "Lower emissions"}
            </span>
            <small>{pathwayLabel(view.hazard, "lower")}</small>
          </button>
          <button
            aria-pressed={view.emissions === "higher"}
            onClick={() => onChange({ emissions: "higher" })}
          >
            <span>
              {view.hazard === "CFLD" ? "Higher scenario" : "Higher emissions"}
            </span>
            <small>{pathwayLabel(view.hazard, "higher")}</small>
          </button>
        </div>
      </fieldset>
      {view.hazard === "EXHT" && (
        <details className="model-options">
          <summary>Heat model & threshold</summary>
          <div className="field-label-row">
            <label htmlFor={`${id}-model`}>Source and historical percentile</label>
            <FieldHelp label="Heat model and threshold">
              Extreme heat counts days whose overnight low beats the hottest 5% (95th percentile)
              or 1% (99th) of nights in the historical period. LOCA and NEX are two downscaled climate datasets.
              The 99th percentile tracks rarer, more extreme heat.
            </FieldHelp>
          </div>
          <Select
            value={view.model}
            onValueChange={(model) => onChange({ model: model as Model })}
          >
            <SelectTrigger className="atlas-select-trigger" id={`${id}-model`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="atlas-select-content">
              {releaseModels().map((model) => {
                const Icon = model.startsWith("L") ? Grid2X2 : Globe;
                return (
                  <SelectItem
                    key={model}
                    value={model}
                    className="atlas-select-item"
                  >
                    <span className="select-option-label">
                      <Icon size={17} strokeWidth={1.6} aria-hidden="true" />
                      <span>
                        {model.startsWith("L") ? "LOCA" : "NEX"}{" "}
                        {model.slice(1)}th percentile
                      </span>
                    </span>
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
        </details>
      )}
    </div>
  );
}
