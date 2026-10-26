import { lazy, Suspense, useEffect, useState } from "react";
import {
  CircleHelp,
  Github,
  Check,
  ChevronDown,
  Map as MapIcon,
  Maximize2,
  Share2,
  SlidersHorizontal,
  Table2,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./components/ui/dialog";
import Controls from "./components/filters/Controls";
import VersionSelect from "./components/filters/VersionSelect";
import CountySearch from "./components/counties/CountySearch";
import CountyPanel from "./components/counties/CountyPanel";
import Legend from "./components/map/Legend";
import { assetUrl, useCounties } from "./clients/api";
import { release } from "./data/releases";
import {
  colorFor,
  describeValue,
  hazards,
  metrics,
  metricValue,
  periodLabel,
  pathwayLabel,
  readState,
  RELEASE,
  writeState,
  type ViewState,
} from "./lib/risk";
const RiskMap = lazy(() => import("./components/map/Map"));

export default function App() {
  const [view, setView] = useState(() => readState(window.location.search));
  const [section, setSection] = useState<"map" | "table">("map");
  const [dialog, setDialog] = useState<"primer" | "settings" | null>(() => {
    try { return sessionStorage.getItem("fri-primer-seen") ? null : "primer"; }
    catch { return "primer"; }
  });
  useEffect(() => {
    if (dialog === "primer") {
      try { sessionStorage.setItem("fri-primer-seen", "1"); }
      catch { /* The guide still works when storage is unavailable. */ }
    }
  }, [dialog]);
  const [copied, setCopied] = useState("");
  const [resetKey, setResetKey] = useState(0);
  const [tableQuery, setTableQuery] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [requestedRelease] = useState(() =>
    new URLSearchParams(window.location.search).get("release"),
  );
  const { data: counties, error, isLoading, mutate } = useCounties();
  const update = (change: Partial<ViewState>) =>
    setView((previous) => {
      const next = { ...previous, ...change };
      if (next.metric === "multiplier" && next.period === "base")
        next.period = "mid";
      return next;
    });
  useEffect(() => {
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${writeState(view)}${window.location.hash}`,
    );
  }, [view]);
  useEffect(() => {
    const restore = () => setView(readState(window.location.search));
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);
  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(""), 4000);
    return () => window.clearTimeout(timer);
  }, [copied]);
  const selectCounty = (id: string) => {
    update({ county: id });
    setExpanded(true);
  };
  const county = counties?.find((c) => c.id === view.county);
  const filtered =
    counties?.filter((c) =>
      `${c.name}, ${c.state} ${c.id}`
        .toLowerCase()
        .includes(tableQuery.toLowerCase()),
    ) ?? [];
  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied("Link copied");
    } catch {
      setCopied("Copy the address in your browser to share this view.");
    }
  };
  return (
    <div className="atlas-app">
      <a className="skip-link" href="#explore">
        Skip to exploration controls
      </a>
      <header className="site-header">
        <a className="brand" href={import.meta.env.BASE_URL}>
          <span>
            <h1>Future Risk Index</h1>
          </span>
        </a>
        <nav aria-label="Main navigation">
          <button className="icon-button" onClick={() => setDialog("primer")} aria-label="How to use the map" title="How to use the map"><CircleHelp size={18} /></button>
          <a className="github-link" href="https://github.com/fulton-ring/nri-future-risk" target="_blank" rel="noopener noreferrer"><Github size={17} aria-hidden="true" /> GitHub</a>
          <button
            className="share-button"
            aria-label="Share view"
            onClick={share}
          >
            {copied === "Link copied" ? (
              <Check size={16} />
            ) : (
              <Share2 size={16} />
            )}
            <span>Share view</span>
          </button>
        </nav>
      </header>
      {requestedRelease && requestedRelease !== RELEASE && (
        <div role="alert" className="release-warning">
          The requested release “{requestedRelease}” is unavailable. Showing the
          {release.title}.
        </div>
      )}
      <section className="release-banner" aria-label="Data version">
        <VersionSelect />
        <nav className="version-links" aria-label="Selected version information">
          <a href={assetUrl(`versions/${release.id}/methodology.html`)}>Methodology</a>
          <a href={assetUrl(`versions/${release.id}/data.html`)}>Data</a>
        </nav>
      </section>
      <main className="atlas-layout">
        <aside
          className="explore-panel"
          id="explore"
          tabIndex={-1}
          aria-label="Exploration controls"
        >
          <CountySearch counties={counties ?? []} onSelect={selectCounty} />
          <Controls view={view} onChange={update} />
        </aside>
        <section className="map-panel" aria-label="Risk exploration">
          <div className="mobile-search">
            <CountySearch counties={counties ?? []} onSelect={selectCounty} />
            <button
              className="icon-button"
              aria-label="Change map settings"
              onClick={() => setDialog("settings")}
            >
              <SlidersHorizontal size={20} />
            </button>
          </div>
          <div className="map-toolbar">
            <div>
              <span className="section-label">{hazards[view.hazard]}</span>
              <h2>{metrics[view.metric]}</h2>
              <p>
                {periodLabel(view.period)}
                {view.period !== "base" &&
                  ` · ${pathwayLabel(view.hazard, view.emissions)}`}
                {view.hazard === "EXHT" &&
                  ` · ${view.model.startsWith("L") ? "LOCA" : "NEX"} ${view.model.slice(1)}th`}
              </p>
            </div>
            <div className="view-switch" aria-label="Result format">
              <button
                aria-label="Map view"
                aria-pressed={section === "map"}
                onClick={() => setSection("map")}
              >
                <MapIcon size={17} />
              </button>
              <button
                aria-label="Table view"
                aria-pressed={section === "table"}
                onClick={() => setSection("table")}
              >
                <Table2 size={17} />
              </button>
            </div>
          </div>
          {isLoading && (
            <div className="data-status" role="status">
              <span className="loading-dot" />
              Loading county data…
            </div>
          )}
          {error && (
            <div className="data-status" role="alert">
              <strong>County data could not be loaded.</strong>
              <p>Check your connection and try again.</p>
              <button onClick={() => mutate()}>Retry data</button>
            </div>
          )}
          {counties && view.county && !county && (
            <div className="data-status" role="alert">
              This county is not included in this dataset.
              <button onClick={() => update({ county: "" })}>
                Clear selection
              </button>
            </div>
          )}
          {section === "map" ? (
            <div className="map-stage">
              <Suspense
                fallback={
                  <div className="map-status" role="status">
                    Preparing map…
                  </div>
                }
              >
                <RiskMap
                  counties={counties ?? []}
                  view={view}
                  onSelect={selectCounty}
                  onMove={(camera) =>
                    setView((previous) => ({ ...previous, camera }))
                  }
                  resetKey={resetKey}
                  onLayerChange={update}
                />
              </Suspense>
              <button
                className="extent-button"
                onClick={() => {
                  update({ county: "" });
                  setResetKey((n) => n + 1);
                }}
              >
                <Maximize2 size={15} />
                US extent
              </button>
              <Legend view={view} />
            </div>
          ) : (
            <div className="results-table">
              <label htmlFor="table-search">Filter counties</label>
              <input
                id="table-search"
                type="search"
                value={tableQuery}
                onChange={(e) => setTableQuery(e.target.value)}
                placeholder="County, state abbreviation or FIPS"
              />
              <p className="caption" role="status">
                {filtered.length.toLocaleString()} counties ·{" "}
                {metrics[view.metric]}
              </p>
              <div className="table-scroll">
                <table>
                  <caption className="sr-only">
                    {hazards[view.hazard]} · {metrics[view.metric]} ·{" "}
                    {periodLabel(view.period)} · {view.emissions} emissions
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">County</th>
                      <th scope="col">State</th>
                      <th scope="col">{metrics[view.metric]}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((c) => {
                      const value = metricValue(c.values, view);
                      return (
                        <tr key={c.id} aria-selected={c.id === view.county}>
                          <th scope="row">
                            <button onClick={() => selectCounty(c.id)}>
                              {c.name}
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
                  <p>No matching counties.</p>
                )}
              </div>
            </div>
          )}
        </section>
        <aside
          className={`county-panel ${county ? "has-county" : ""} ${expanded ? "expanded" : ""}`}
          aria-label="County profile"
        >
          <button
            className="sheet-toggle"
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            <span>
              {county ? `${county.name}, ${county.state}` : "Select a county"}
              {county && <small>{`${hazards[view.hazard]} · ${periodLabel(view.period)} · ${describeValue(metricValue(county.values, view), view.metric)}`}</small>}
            </span>
            <ChevronDown size={18} />
          </button>
          <div className="county-content">
            <CountyPanel
              county={county}
              view={view}
              onClear={() => {
                update({ county: "" });
                setExpanded(false);
              }}
            />
          </div>
        </aside>
      </main>
      <footer className="site-footer">
        <div className="project-credit">
          <span>Maintained by</span>
          <a href="https://www.publicenvirodata.org/">
            Public Environmental Data Partners
          </a>
          <span>&</span>
          <a href="https://www.fultonring.com/">Fulton Ring</a>
        </div>
      </footer>
      <div className="share-status" role="status">
        {copied}
      </div>
      <Dialog
        open={dialog !== null}
        onOpenChange={(open) => {
          if (!open) setDialog(null);
        }}
      >
        <DialogContent
          className={`atlas-dialog ${dialog === "settings" ? "settings-dialog" : ""}`}
        >
          <DialogHeader>
            <DialogTitle>
              {dialog === "settings" ? "Map settings" : "How to use the map"}
            </DialogTitle>
            <DialogDescription>
              {dialog === "settings" ? "Choose a hazard, measure and future." : "What the tool represents and how to interpret it."}
            </DialogDescription>
          </DialogHeader>
          {dialog === "settings" ? (
            <>
              <Controls view={view} onChange={update} />
              <button
                className="primary-button"
                onClick={() => setDialog(null)}
              >
                Show results
              </button>
            </>
          ) : (
            <div className="prose">
              <p>FEMA created the Future Risk Index and later discontinued the public tool. Public Environmental Data Partners and Fulton Ring preserve its data and methods.</p>
              <h3>Choose a data version</h3>
              <p>The version header identifies the dataset being shown. Its Methodology and Data links describe that version’s calculations, coverage and downloads. Different versions can include different hazards and climate models.</p>
              <h3>Three ways to read the map</h3>
              <p>
                <strong>Annual loss rating</strong> groups projected yearly
                economic losses into FEMA’s five published categories. Dollar
                ranges are category thresholds, not uncertainty intervals.
              </p>
              <p>
                <strong>Change in annual loss</strong> is the hazard multiplier:
                projected annual loss divided by baseline annual loss. A
                multiplier of 2× means twice the baseline losses. A large
                multiplier does not necessarily mean the largest dollar losses.
              </p>
              <p>
                <strong>Risk rating</strong> is a comparative category combining
                economic loss with social vulnerability and community
                resilience. It is not the probability of an event.
              </p>
              <h3>Two pathways, two time periods</h3>
              <p>
                Lower and higher emissions describe alternative climate futures.
                They are not assigned probabilities. The drought, wildfire and
                extreme heat series use mid-century (2036–2065) and late-century
                (2070–2099) projection periods; historical reference periods
                vary by hazard and source.
              </p>
              <table className="pathway-table">
                <caption>Scenario families by hazard</caption>
                <thead>
                  <tr>
                    <th scope="col">Hazard</th>
                    <th scope="col">Lower</th>
                    <th scope="col">Higher</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th scope="row">Drought, heat, wildfire</th>
                    <td>SSP2-4.5</td>
                    <td>SSP5-8.5</td>
                  </tr>
                  <tr>
                    <th scope="row">Hurricane</th>
                    <td>RCP 4.5</td>
                    <td>RCP 8.5</td>
                  </tr>
                  <tr>
                    <th scope="row">Coastal flooding</th>
                    <td>Intermediate SLR</td>
                    <td>High SLR</td>
                  </tr>
                </tbody>
              </table>
              <h3>What stays fixed</h3>
              <p>
                These projections hold baseline exposure and social conditions
                fixed. They do not account for future population, development,
                adaptation or changing demographics. Baseline refers to the
                archived NRI, not conditions today.
              </p>
              <h3>Geography & missing data</h3>
              <p>
                Results describe entire counties. Zooming in adds geographic
                context, not scientific resolution. Gray means unavailable,
                white means no rating, and pale gray means not applicable. These
                are different from zero losses.
              </p>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
