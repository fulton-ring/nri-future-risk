import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { useDefaultLayout, usePanelRef } from "react-resizable-panels";
import {
  CircleHelp,
  Github,
  Check,
  ChevronDown,
  Map as MapIcon,
  Maximize2,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
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
import type { PlaceResult } from "./clients/geocoding";
import WelcomePrimer from "./components/WelcomePrimer";
import Controls from "./components/filters/Controls";
import VersionSelect from "./components/filters/VersionSelect";
import CountySearch from "./components/counties/CountySearch";
import CountyPanel from "./components/counties/CountyPanel";
import Legend from "./components/map/Legend";
import ResultsTable from "./components/ResultsTable";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "./components/ui/resizable";
import { useMediaQuery } from "./hooks/use-media-query";
import { assetUrl, useCounties } from "./clients/api";
import { release, areaLabel } from "./data/releases";
import {
  areaName,
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

// Layout sizes are a per-viewer convenience; never let blocked storage break the page.
const layoutStorage = {
  getItem: (key: string) => { try { return localStorage.getItem(key); } catch { return null; } },
  setItem: (key: string, value: string) => { try { localStorage.setItem(key, value); } catch { /* not saved */ } },
};

function PanelToggle({ side, open, onToggle }: { side: "left" | "right"; open: boolean; onToggle: () => void }) {
  const label = `${open ? "Hide" : "Show"} ${side === "left" ? "map settings" : "area profile"}`;
  const Icon = side === "left" ? (open ? PanelLeftClose : PanelLeftOpen) : (open ? PanelRightClose : PanelRightOpen);
  return (
    <button type="button" className="icon-button panel-toggle" aria-label={label} title={label} aria-expanded={open} onClick={onToggle}>
      <Icon size={18} aria-hidden="true" />
    </button>
  );
}

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
  const [searchFocus, setSearchFocus] = useState<PlaceResult | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const desktop = useMediaQuery("(min-width: 901px)");
  const leftPanel = usePanelRef();
  const rightPanel = usePanelRef();
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const layout = useDefaultLayout({ id: "atlas-panels", storage: layoutStorage, onlySaveAfterUserInteractions: true });
  const togglePanel = (panel: typeof leftPanel) => {
    if (panel.current?.isCollapsed()) panel.current.expand();
    else panel.current?.collapse();
  };
  const revealProfile = () => {
    setExpanded(true);
    if (rightPanel.current?.isCollapsed()) rightPanel.current.expand();
  };
  const [requestedRelease] = useState(() =>
    new URLSearchParams(window.location.search).get("release"),
  );
  const { data: counties, selectedCounty: county, error, isLoading, mutate, detailsLoading, detailsError, retryDetails } = useCounties(view);
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
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(""), 4000);
    return () => window.clearTimeout(timer);
  }, [copied]);
  const locate = (place: PlaceResult, areaId?: string) => {
    update({ county: areaId ?? "" });
    setSearchFocus(place);
    setSection("map");
    if (areaId) revealProfile();
    else setExpanded(false);
  };
  const selectCounty = (id: string) => {
    setSearchFocus(null);
    update({ county: id });
    revealProfile();
  };
  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied("Link copied");
    } catch {
      setCopied("Copy the address in your browser to share this view.");
    }
  };
  const explorePanel: ReactNode = (
    <aside
      className="explore-panel"
      id="explore"
      tabIndex={-1}
      aria-label="Exploration controls"
    >
      <CountySearch counties={counties ?? []} onLocate={locate} />
      <Controls view={view} onChange={update} />
    </aside>
  );
  const mapPanel: ReactNode = (
    <section className="map-panel" aria-label="Risk exploration">
      <div className="mobile-search">
        <CountySearch counties={counties ?? []} onLocate={locate} />
        <button
          className="icon-button"
          aria-label="Change map settings"
          onClick={() => setDialog("settings")}
        >
          <SlidersHorizontal size={20} />
        </button>
      </div>
      <div className="map-toolbar">
        {desktop && <PanelToggle side="left" open={leftOpen} onToggle={() => togglePanel(leftPanel)} />}
        <div className="map-title">
          <h2>{hazards[view.hazard]} {metrics[view.metric].toLowerCase()}</h2>
          <p>
            {periodLabel(view.period)}
            {view.period !== "base" &&
              ` (${pathwayLabel(view.hazard, view.emissions)})`}
            {view.hazard === "EXHT" &&
              `, ${view.model.startsWith("L") ? "LOCA" : "NEX"} ${view.model.slice(1)}th percentile`}
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
        {desktop && <PanelToggle side="right" open={rightOpen} onToggle={() => togglePanel(rightPanel)} />}
      </div>
      {isLoading && (
        <div className="data-status" role="status">
          <span className="loading-dot" />
          Loading {areaLabel} data…
        </div>
      )}
      {error && (
        <div className="data-status" role="alert">
          <strong>{areaLabel === "county" ? "County" : "Census tract"} data could not be loaded.</strong>
          <p>Check your connection and try again.</p>
          <button onClick={() => mutate()}>Retry data</button>
        </div>
      )}
      {counties && view.county && !county && (
        <div className="data-status" role="alert">
          This {areaLabel} is not included in this dataset.
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
              searchFocus={searchFocus}
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
              setSearchFocus(null);
              update({ county: "" });
              setResetKey((n) => n + 1);
            }}
          >
            <Maximize2 size={15} />
            US extent
          </button>
          <Legend view={view} county={county} />
        </div>
      ) : (
        <ResultsTable
          counties={counties}
          view={view}
          isLoading={isLoading}
          onSelect={selectCounty}
        />
      )}
    </section>
  );
  const countyPanel: ReactNode = (
    <aside
      className={`county-panel ${county ? "has-county" : ""} ${expanded ? "expanded" : ""}`}
      aria-label={`${areaLabel} profile`}
    >
      <button
        className="sheet-toggle"
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
      >
        <span>
          {county ? areaName(county) : `Select a ${areaLabel}`}
          {county && <small>{describeValue(metricValue(county.values, view), view.metric)}</small>}
        </span>
        <ChevronDown size={18} />
      </button>
      <div className="county-content">
        {detailsLoading ? <div className="data-status" role="status">Loading {areaLabel} profile…</div>
          : detailsError ? <div className="data-status" role="alert">
            Profile details could not be loaded.
            <button onClick={() => retryDetails()}>Retry profile</button>
            <button onClick={() => update({county:""})}>Clear selection</button>
          </div> : <CountyPanel
          county={county}
          view={view}
          onClear={() => {
            update({ county: "" });
            setExpanded(false);
          }}
        />}
      </div>
    </aside>
  );
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
        {desktop ? (
          <ResizablePanelGroup id="atlas-panels" orientation="horizontal" defaultLayout={layout.defaultLayout} onLayoutChanged={layout.onLayoutChanged}>
            <ResizablePanel id="settings-panel" panelRef={leftPanel} collapsible collapsedSize={0} defaultSize={280} minSize={220} maxSize={440}
              onResize={(size) => setLeftOpen(size.inPixels > 0)}>
              {explorePanel}
            </ResizablePanel>
            <ResizableHandle withHandle aria-label="Resize map settings" />
            <ResizablePanel id="map-panel" minSize={360}>{mapPanel}</ResizablePanel>
            <ResizableHandle withHandle aria-label="Resize area profile" />
            <ResizablePanel id="profile-panel" panelRef={rightPanel} collapsible collapsedSize={0} defaultSize={340} minSize={280} maxSize={560}
              onResize={(size) => setRightOpen(size.inPixels > 0)}>
              {countyPanel}
            </ResizablePanel>
          </ResizablePanelGroup>
        ) : (
          <>
            {explorePanel}
            {mapPanel}
            {countyPanel}
          </>
        )}
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
              {dialog === "settings" ? "Map settings" : "Welcome to the Future Risk Index"}
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
            <WelcomePrimer />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
