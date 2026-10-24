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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import {
  hazards,
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
        <label htmlFor={`${id}-hazard`}>Hazard</label>
        <Select
          value={view.hazard}
          onValueChange={(hazard) => onChange({ hazard: hazard as Hazard })}
        >
          <SelectTrigger className="atlas-select-trigger" id={`${id}-hazard`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="atlas-select-content">
            {Object.entries(hazards).map(([key, label]) => {
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
        <label htmlFor={`${id}-metric`}>Map measure</label>
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
        <legend>Time period</legend>
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
            ? "NRI v1.19 baseline."
            : view.hazard === "CFLD" || view.hazard === "HRCN"
              ? "Archived FEMA scenario. Projection periods vary by source."
              : view.period === "mid"
                ? "2036–2065"
                : "2070–2099"}
        </p>
      </fieldset>
      <fieldset disabled={view.period === "base"}>
        <legend>
          {view.hazard === "CFLD" ? "Sea-level scenario" : "Emissions pathway"}
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
          <label htmlFor={`${id}-model`}>
            Source and historical percentile
          </label>
          <Select
            value={view.model}
            onValueChange={(model) => onChange({ model: model as Model })}
          >
            <SelectTrigger className="atlas-select-trigger" id={`${id}-model`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="atlas-select-content">
              {(["L95", "L99", "N95", "N99"] as Model[]).map((model) => {
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
                        {model.startsWith("L") ? "LOCA" : "NEX"} ·{" "}
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
