import { lazy, Suspense, useEffect, useState } from "react";
import {
  ArrowUpRight,
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
import { release, isAnalysis } from "./data/releases";
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
  const [dialog, setDialog] = useState<
    "methods" | "release" | "settings" | null
  >("methods");
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
      <section className={`release-banner ${isAnalysis ? "release-warning" : ""}`} aria-label="Data version">
        <VersionSelect />
        <p>{isAnalysis
          ? "19 wildfire years are unavailable. Exploratory results; not an approved release."
          : "Original FEMA projections · NRI v1.19 baseline."}</p>
        <nav className="version-links" aria-label="Selected version information">
          <button onClick={() => setDialog("methods")}>Methodology</button>
          <button onClick={() => setDialog("release")}>Data</button>
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
                  <p>
                    No counties match. Try another name or clear your filter.
                  </p>
                )}
              </div>
            </div>
          )}
          <div className="map-footnote">
            <span>County-level estimates</span>
          </div>
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
              {county ? `${county.name}, ${county.state}` : "County profile"}
              <small>
                {county
                  ? `${hazards[view.hazard]} · ${periodLabel(view.period)} · ${describeValue(metricValue(county.values, view), view.metric)}`
                  : "Select a county to explore"}
              </small>
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
              {dialog === "settings"
                ? "Map settings"
                : dialog === "release"
                  ? "Data"
                  : isAnalysis ? "Analysis methodology" : "FEMA methodology"}
            </DialogTitle>
            <DialogDescription>
              {dialog === "settings"
                ? "Choose a hazard, measure and future."
                : isAnalysis ? "Exploratory analysis · NRI v1.19 baseline." : "Archived FEMA data · December 2024."}
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
          ) : dialog === "release" ? (
            <div className="prose">
              <p>
                {isAnalysis ? "Drought, wildfire and LOCA2 heat recalculated for 3,108 CONUS counties using the frozen NRI v1.19 baseline. Only these recalculated series are shown in this version. Select the FEMA archive for coastal flooding, hurricane and NEX heat." : "FEMA’s December 5, 2024 master datasheet, using the NRI v1.19 baseline."}
              </p>
              <dl>
                <dt>Coverage</dt>
                <dd>
                  {release.countyCount.toLocaleString()} counties and county
                  equivalents with archived boundaries
                </dd>
                <dt>Release ID</dt>
                <dd>
                  <code>{release.id}</code>
                </dd>
              </dl>
              <h3>Download & inspect</h3>
              {isAnalysis && <>
                <a href={assetUrl("preview/report.md")}>Analysis report <ArrowUpRight size={15} /></a>
                <a href={assetUrl("preview/provenance.json")}>Source provenance <ArrowUpRight size={15} /></a>
              </>}
              <a
                href={assetUrl(
                  "NRI_Future_Risk_Master_Datasheet_12052024.xlsx",
                )}
              >
                Original master datasheet <ArrowUpRight size={15} />
              </a>
              <a href={assetUrl("NRI_Data_Dictionary.xlsx")}>
                FEMA data dictionary <ArrowUpRight size={15} />
              </a>
              <a href="https://buymeacoffee.com/herzo175">
                Support this project <ArrowUpRight size={15} />
              </a>
              <details>
                <summary>Provenance</summary>
                <p>
                  {isAnalysis ? "Display assets come from the hash-verified Batch GeoParquet. County scores and multipliers are unchanged by tile conversion. GeoParquet SHA-256:" : "Display assets come from the archived county GeoJSON without changing scientific values. Source SHA-256:"}
                </p>
                <code className="checksum">{release.sourceSha256}</code>
              </details>
            </div>
          ) : (
            <div className="prose">
              <p>
                FEMA created the Future Risk Index and later discontinued the
                public tool. Public Environmental Data Partners and Fulton Ring
                preserve its data and methods.
              </p>
              {isAnalysis && <>
                <h3>About this analysis</h3>
                <p>Drought, wildfire and LOCA2 heat use new climate inputs. The analysis omits 19 wildfire years absent from NASA’s catalog, without interpolation. Coastal flooding, hurricane and NEX heat are available in the FEMA archive version. Outside CONUS, archived multipliers are retained; supported risk ranks are recomputed nationally.</p>
                <p>Source masks remain unchanged. LOCA2 valid weighting support varies by county, down to 51.3%; the 0.25° weighting boxes do not imply 6 km county estimates.</p>
                <a href={assetUrl("preview/report.md")}>Read the analysis report <ArrowUpRight size={15} /></a>
              </>}
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
                <caption>Pathways for this version</caption>
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
                  {!isAnalysis && <><tr>
                    <th scope="row">Hurricane</th>
                    <td>RCP 4.5</td>
                    <td>RCP 8.5</td>
                  </tr>
                  <tr>
                    <th scope="row">Coastal flooding</th>
                    <td>Intermediate SLR</td>
                    <td>High SLR</td>
                  </tr></>}
                </tbody>
              </table>
              <p>
                <a href="https://eelp.law.harvard.edu/wp-content/uploads/2025/03/NRI_Future_Risk_Technical_Document.pdf">
                  FEMA technical documentation
                </a>
              </p>
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
