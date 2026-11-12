import { useDeferredValue, useMemo, useState } from "react";
import { areaLabel, areasLabel } from "../data/releases";
import {
  areaName,
  colorFor,
  describeValue,
  hazards,
  metrics,
  metricValue,
  periodLabel,
  type County,
  type ViewState,
} from "../lib/risk";

const PAGE_SIZE = 100;

export default function ResultsTable({
  counties,
  view,
  isLoading,
  onSelect,
}: {
  counties?: County[];
  view: ViewState;
  isLoading: boolean;
  onSelect: (id: string) => void;
}) {
  const [tableQuery, setTableQuery] = useState("");
  const [tablePage, setTablePage] = useState(0);
  const query = useDeferredValue(tableQuery);
  // Tract releases have ~85k rows; build the search text once per dataset.
  const searchable = useMemo(
    () => (counties ?? []).map((c) => [`${areaName(c)} ${c.id}`.toLowerCase(), c] as const),
    [counties],
  );
  const filtered = useMemo(() => {
    const needle = query.toLowerCase();
    return searchable.filter(([text]) => text.includes(needle)).map(([, c]) => c);
  }, [searchable, query]);
  const page = Math.min(tablePage, Math.max(0, Math.ceil(filtered.length / PAGE_SIZE) - 1));
  return (
    <div className="results-table">
      <label htmlFor="table-search">Filter {areasLabel}</label>
      <input
        id="table-search"
        type="search"
        value={tableQuery}
        onChange={(e) => { setTableQuery(e.target.value); setTablePage(0); }}
        placeholder={`${areaLabel}, state abbreviation or FIPS`}
      />
      <p className="caption" role="status">
        {filtered.length.toLocaleString()} {areasLabel}
      </p>
      {filtered.length > PAGE_SIZE && <nav aria-label="Result pages">
        <button disabled={page === 0} onClick={() => setTablePage(page - 1)}>Previous</button>
        <span> Page {page + 1} of {Math.ceil(filtered.length / PAGE_SIZE).toLocaleString()} </span>
        <button disabled={(page + 1) * PAGE_SIZE >= filtered.length} onClick={() => setTablePage(page + 1)}>Next</button>
      </nav>}
      <div className="table-scroll">
        <table>
          <caption className="sr-only">
            {hazards[view.hazard]}, {metrics[view.metric].toLowerCase()}, {periodLabel(view.period).toLowerCase()}, {view.emissions} emissions
          </caption>
          <thead>
            <tr>
              <th scope="col">{areaLabel === "county" ? "County" : "Census tract"}</th>
              <th scope="col">State</th>
              <th scope="col">{metrics[view.metric]}</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map((c) => {
              const value = metricValue(c.values, view);
              return (
                <tr key={c.id} aria-selected={c.id === view.county}>
                  <th scope="row">
                    <button onClick={() => onSelect(c.id)}>
                      {c.name.replace(/\s*·\s*/g, ", ")}
                    </button>
                  </th>
                  <td>{c.state}</td>
                  <td>
                    <span
                      className="table-dot"
                      style={{
                        background: colorFor(value, view.metric),
                      }}
                    />
                    {describeValue(value, view.metric)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!filtered.length && !isLoading && (
          <p>No matching {areasLabel}.</p>
        )}
      </div>
    </div>
  );
}
