import { release, isAnalysis } from "../../data/releases";
import { Download, MapPin, X } from "lucide-react";
import {
  changeLabel,
  colorFor,
  describeValue,
  hazards,
  metricValue,
  periodLabel,
  pathwayLabel,
  type County,
  type ViewState,
  type Period,
} from "../../lib/risk";

type Props = { county?: County; view: ViewState; onClear: () => void };
export default function CountyPanel({ county, view, onClear }: Props) {
  if (!county)
    return (
      <div className="county-empty">
        <MapPin size={30} strokeWidth={1.3} />
        <h2>Select a county</h2>
        <p>Search by name or select a county on the map.</p>
      </div>
    );
  const value = metricValue(county.values, view);
  const multiplier = metricValue(county.values, {
    ...view,
    metric: "multiplier",
    period: view.period === "base" ? "mid" : view.period,
  });
  const baseline = metricValue(county.values, {
    ...view,
    period: "base",
    metric: view.metric === "multiplier" ? "loss" : view.metric,
  });
  const rows = (["base", "mid", "late"] as Period[]).map((period) => ({
    period,
    lower: metricValue(county.values, {
      ...view,
      period,
      emissions: "lower",
      metric:
        view.metric === "multiplier" && period === "base"
          ? "loss"
          : view.metric,
    }),
    higher: metricValue(county.values, {
      ...view,
      period,
      emissions: "higher",
      metric:
        view.metric === "multiplier" && period === "base"
          ? "loss"
          : view.metric,
    }),
  }));
  const hmRows = (["mid", "late"] as Period[]).map((period) => ({
    period,
    values: (["lower", "higher"] as const).map((emissions) =>
      metricValue(county.values, {
        ...view,
        metric: "multiplier",
        period,
        emissions,
      }),
    ),
  }));
  const max = Math.max(
    1,
    ...hmRows.flatMap((row) =>
      row.values.filter((v): v is number => typeof v === "number"),
    ),
  );
  const download = () => {
    const blob = new Blob(
      [
        JSON.stringify(
          {
            release: release.id,
            status: release.status,
            county: { id: county.id, name: county.name, state: county.state },
            view,
            values: county.values,
          },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `future-risk-${county.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <>
      {isAnalysis && county.vintage === "FEMA archive" && <p className="caption">Archived multipliers; drought, wildfire and LOCA2 risk ranks are recomputed across all counties.</p>}
      <div className="county-heading">
        <div>
          <span className="section-label">County profile · {county.state}</span>
          <h2>{county.name}</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Clear selected county"
          onClick={onClear}
        >
          <X size={19} />
        </button>
      </div>
      <div className="county-body">
        <div className="result-context">
          {hazards[view.hazard]} · {periodLabel(view.period)}
          {view.period !== "base" &&
            ` · ${pathwayLabel(view.hazard, view.emissions)}`}
        </div>
        <div className="result-value">
          <span
            className="result-dot"
            style={{ background: colorFor(value, view.metric) }}
          />
          {describeValue(value, view.metric)}
        </div>
        {view.metric === "multiplier" && (
          <p className="result-explanation">{changeLabel(value)}</p>
        )}
        <div className="baseline-row">
          <span>Baseline · NRI v1.19</span>
          <strong>
            {describeValue(
              baseline,
              view.metric === "multiplier" ? "loss" : view.metric,
            )}
          </strong>
        </div>
        {view.period !== "base" && view.metric !== "multiplier" && (
          <p className="change-note">
            Annual loss: <strong>{changeLabel(multiplier)}</strong>
          </p>
        )}
        <section className="comparison" aria-labelledby="comparison-title">
          <div className="section-heading">
            <h3 id="comparison-title">Annual loss change</h3>
          </div>
          <div className="chart-key">
            <span>
              <i className="lower-key" />
              Lower emissions
            </span>
            <span>
              <i className="higher-key" />
              Higher emissions
            </span>
          </div>
          <div
            className="comparison-bars"
            role="img"
            aria-label={`Annual loss multipliers. ${hmRows.map((row) => `${periodLabel(row.period)}: lower emissions ${describeValue(row.values[0], "multiplier")}, higher emissions ${describeValue(row.values[1], "multiplier")}`).join(". ")}`}
          >
            {hmRows.map((row) => (
              <div className="bar-group" key={row.period}>
                <span>{periodLabel(row.period)}</span>
                {row.values.map((v, i) => (
                  <div className="bar-row" key={i}>
                    <div className="bar-track">
                      <div
                        className={i === 0 ? "bar lower" : "bar higher"}
                        style={{
                          width: `${typeof v === "number" ? Math.max(1, (v / max) * 100) : 0}%`,
                        }}
                      />
                    </div>
                    <strong>{describeValue(v, "multiplier")}</strong>
                  </div>
                ))}
              </div>
            ))}
          </div>
          <p className="caption">1× = baseline annual loss.</p>
        </section>
        <details className="data-details">
          <summary>All scenarios</summary>
          <div className="table-scroll">
            <table>
              <caption className="sr-only">
                {view.metric === "multiplier"
                  ? "Annual loss multipliers; baseline row shows the baseline loss category"
                  : "Published ratings"}{" "}
                for {county.name}
              </caption>
              <thead>
                <tr>
                  <th scope="col">Period</th>
                  <th scope="col">Lower</th>
                  <th scope="col">Higher</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.period}>
                    <th scope="row">
                      {periodLabel(row.period)}
                      {row.period === "base" &&
                        view.metric === "multiplier" && (
                          <small>Loss category</small>
                        )}
                    </th>
                    <td colSpan={row.period === "base" ? 2 : 1}>
                      {describeValue(row.lower, view.metric)}
                    </td>
                    {row.period !== "base" && (
                      <td>{describeValue(row.higher, view.metric)}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
        <button className="download-button" onClick={download}>
          <Download size={16} />
          Download county data
        </button>
      </div>
    </>
  );
}
