import { useEffect, useRef, useState, useId } from "react";
import * as maplibregl from "maplibre-gl";
import type {
  Map as MapInstance,
  StyleSpecification,
  ExpressionSpecification,
} from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { Protocol } from "pmtiles";
import { Layers } from "lucide-react";
import "maplibre-gl/dist/maplibre-gl.css";
import { assetUrl } from "../../clients/api";
import { release } from "../../data/releases";
import {
  colorFor,
  describeValue,
  metricField,
  metricValue,
  multiplierStops,
  palette,
  ratingNames,
  scenarioKey,
  type Values,
  type County,
  type ViewState,
} from "../../lib/risk";

maplibregl.setWorkerUrl(workerUrl);
const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

type Props = {
  counties: County[];
  view: ViewState;
  onSelect: (id: string) => void;
  onMove: (camera: NonNullable<ViewState["camera"]>) => void;
  resetKey: number;
  onLayerChange: (change: Partial<ViewState>) => void;
};
export default function RiskMap({
  counties,
  view,
  onSelect,
  onMove,
  resetKey,
  onLayerChange,
}: Props) {
  const opacityId = useId();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapInstance | null>(null);
  const latest = useRef({ counties, view, onSelect, onMove });
  latest.current = { counties, view, onSelect, onMove };
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [hover, setHover] = useState("");
  const [contextError, setContextError] = useState("");
  const initialCamera = useRef(view.camera);
  const fittedCounty = useRef(view.camera ? view.county : "");

  useEffect(() => {
    if (!container.current) return;
    setReady(false);
    setError("");
    setContextError("");
    let map: MapInstance;
    try {
      map = new maplibregl.Map({
        container: container.current,
        // The risk overlay remains usable if the optional external basemap fails.
        style: {
          version: 8,
          sources: {},
          layers: [
            {
              id: "background",
              type: "background",
              paint: { "background-color": "#e7eeed" },
            },
          ],
        },
        center: initialCamera.current
          ? [initialCamera.current.lng, initialCamera.current.lat]
          : [-98, 38.5],
        zoom: initialCamera.current?.zoom ?? 3.3,
        minZoom: 1,
        maxZoom: 12,
        attributionControl: false,
      });
    } catch {
      setError(
        "Your browser could not start the map. County search and the data table are still available.",
      );
      return;
    }
    mapRef.current = map;
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    map.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: "County data: FEMA · Boundaries: US Census Bureau",
      }),
      "bottom-right",
    );
    const popup = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
    });
    map.on("load", () => {
      // Start the compact attribution control closed; its info button still exposes all credits.
      map
        .getContainer()
        .querySelector(".maplibregl-ctrl-attrib")
        ?.classList.remove("maplibregl-compact-show");
      map.addSource("counties", {
        type: "vector",
        url: `pmtiles://${assetUrl(release.assets["counties.pmtiles"].path)}`,
      });
      map.addLayer({
        id: "county-fill",
        type: "fill",
        source: "counties",
        "source-layer": release.sourceLayer,
        paint: {
          "fill-color": "#b6b3ac",
          "fill-opacity": [
            "case",
            ["boolean", ["feature-state", "hover"], false],
            Math.max(0, latest.current.view.opacity - 0.22),
            latest.current.view.opacity,
          ],
        },
      });
      map.addLayer({
        id: "county-lines",
        type: "line",
        source: "counties",
        "source-layer": release.sourceLayer,
        paint: {
          "line-color": "#655f51",
          "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.25, 7, 0.8],
          "line-opacity": 0.4,
        },
      });
      map.addLayer({
        id: "county-selected",
        type: "line",
        source: "counties",
        "source-layer": release.sourceLayer,
        filter: ["==", ["get", "fips"], latest.current.view.county],
        paint: { "line-color": "#283f3b", "line-width": 3 },
      });
      map.addSource("terrain", {
        type: "raster-dem",
        tiles: [
          "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
        ],
        encoding: "terrarium",
        tileSize: 256,
        maxzoom: 12,
        attribution:
          '<a href="https://github.com/tilezen/joerd/blob/master/docs/attribution.md">Terrain: USGS, Mapzen & contributors</a>',
      });
      map.addLayer(
        {
          id: "terrain-shade",
          type: "hillshade",
          source: "terrain",
          minzoom: 5,
          layout: {
            visibility: latest.current.view.terrain ? "visible" : "none",
          },
          paint: {
            "hillshade-exaggeration": 0.5,
            "hillshade-shadow-color": "rgba(45, 54, 40, 0.45)",
            "hillshade-highlight-color": "rgba(255, 255, 248, 0.25)",
            "hillshade-accent-color": "rgba(65, 65, 50, 0.2)",
          },
        },
        "county-lines",
      );
      if (!initialCamera.current)
        map.fitBounds(
          [
            [-125, 24],
            [-66, 50],
          ],
          { padding: 30, duration: 0 },
        );
      setReady(true);
      // A basemap is context, not a dependency of the county data.
      fetch("https://tiles.openfreemap.org/styles/bright")
        .then((r) => {
          if (!r.ok) throw new Error();
          return r.json();
        })
        .then((style: StyleSpecification) => {
          if (mapRef.current !== map) return;
          if (style.glyphs) map.setGlyphs(style.glyphs);
          for (const [id, source] of Object.entries(style.sources))
            map.addSource(
              `base-${id}`,
              source as maplibregl.SourceSpecification,
            );
          for (const layer of style.layers) {
            if (layer.type === "background") continue;
            const styled = {
              ...layer,
              id: `base-${layer.id}`,
              source: `base-${layer.source}`,
            };
            if (layer.type === "symbol") {
              if (
                !layer.layout?.["text-field"] ||
                /shield|airport|^poi/.test(layer.id)
              )
                continue;
              const layout = { ...layer.layout };
              delete layout["icon-image"];
              map.addLayer({
                ...styled,
                type: "symbol",
                layout,
              } as maplibregl.LayerSpecification);
            } else if (
              layer.type === "line" &&
              /^(road|highway|bridge|tunnel|waterway|boundary)[_-]/.test(
                layer.id,
              )
            ) {
              map.addLayer(styled, "county-selected");
            } else {
              map.addLayer(styled, "county-fill");
            }
          }
        })
        .catch(() => {
          if (mapRef.current === map)
            setContextError(
              "Basemap unavailable. County results are still available.",
            );
        });
    });
    map.on("error", (event) => {
      if ("sourceId" in event && event.sourceId === "counties")
        setError(
          "County tiles could not be loaded. Try again, or explore the same results in the data table.",
        );
    });
    map.on("click", "county-fill", (event) => {
      const id = event.features?.[0]?.properties.fips;
      if (typeof id === "string") latest.current.onSelect(id);
    });
    let hoveredId: string | number | undefined;
    const clearHover = () => {
      if (hoveredId !== undefined)
        map.setFeatureState(
          {
            source: "counties",
            sourceLayer: release.sourceLayer,
            id: hoveredId,
          },
          { hover: false },
        );
      hoveredId = undefined;
    };
    map.on("mousemove", "county-fill", (event) => {
      const feature = event.features?.[0];
      if (feature?.id !== hoveredId) {
        clearHover();
        hoveredId = feature?.id;
        if (hoveredId !== undefined)
          map.setFeatureState(
            {
              source: "counties",
              sourceLayer: release.sourceLayer,
              id: hoveredId,
            },
            { hover: true },
          );
      }
      const properties = feature?.properties;
      if (!properties) return;
      map.getCanvas().style.cursor = "pointer";
      const label = `${properties.name}, ${properties.state} · ${describeValue(metricValue(properties as Values, latest.current.view), latest.current.view.metric)}`;
      setHover(label);
      popup.setLngLat(event.lngLat).setText(label).addTo(map);
    });
    map.on("mouseleave", "county-fill", () => {
      clearHover();
      map.getCanvas().style.cursor = "";
      popup.remove();
      setHover("");
    });
    map.on("moveend", () => {
      const { lat, lng } = map.getCenter();
      latest.current.onMove({
        lat: +lat.toFixed(4),
        lng: +maplibregl.LngLat.convert([lng, lat]).wrap().lng.toFixed(4),
        zoom: +map.getZoom().toFixed(2),
      });
    });
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      popup.remove();
      map.remove();
      mapRef.current = null;
    };
  }, [retry]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setPaintProperty("county-fill", "fill-opacity", [
      "case",
      ["boolean", ["feature-state", "hover"], false],
      Math.max(0, view.opacity - 0.22),
      view.opacity,
    ]);
    map.setLayoutProperty(
      "terrain-shade",
      "visibility",
      view.terrain ? "visible" : "none",
    );
  }, [ready, view.opacity, view.terrain]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const field = metricField(view);
    const value: ExpressionSpecification = ["get", field];
    const expression: unknown[] = [
      "case",
      ["any", ["!", ["has", field]], ["==", value, null]],
      colorFor(null, view.metric),
    ];
    for (const status of [
      "Insufficient Data",
      "Not Applicable",
      "No Rating",
      "No Expected Annual Losses",
    ])
      expression.push(["==", value, status], colorFor(status, view.metric));
    if (view.metric === "multiplier") {
      expression.push(
        ["==", ["get", `${scenarioKey(view)}_DELTAR`], "No Rating"],
        colorFor("No Rating", view.metric),
      );
      for (const [i, stop] of multiplierStops.entries())
        expression.push(["<=", ["number", value, 0], stop], palette[i]);
      expression.push(palette[4]);
    } else {
      for (const [i, name] of ratingNames.entries())
        expression.push(
          ["==", ["slice", ["to-string", value], 0, name.length], name],
          palette[i],
        );
      expression.push(colorFor(null, view.metric));
    }
    map.setPaintProperty(
      "county-fill",
      "fill-color",
      expression as ExpressionSpecification,
    );
    map.setFilter("county-selected", ["==", ["get", "fips"], view.county]);
  }, [ready, counties, view]);

  useEffect(() => {
    const map = mapRef.current;
    const county = counties.find((c) => c.id === view.county);
    if (ready && map && county && fittedCounty.current !== county.id) {
      fittedCounty.current = county.id;
      map.fitBounds(county.bounds, {
        padding: 65,
        maxZoom: 8,
        duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? 0
          : 550,
      });
    }
    if (!view.county) fittedCounty.current = "";
  }, [ready, counties, view.county]);

  useEffect(() => {
    if (resetKey)
      mapRef.current?.fitBounds(
        [
          [-125, 24],
          [-66, 50],
        ],
        { padding: 30, duration: 0 },
      );
  }, [resetKey]);
  return (
    <>
      <div
        ref={container}
        className="map-canvas"
        role="region"
        aria-label="County risk map. Use county search or the data table for keyboard-accessible results."
      />
      <details className="map-layers">
        <summary>
          <Layers size={15} aria-hidden="true" />
          Map layers
        </summary>
        <div className="map-layers-content">
          <p>Bright · OpenFreeMap</p>
          <label htmlFor={opacityId}>
            County fill <output>{Math.round(view.opacity * 100)}%</output>
          </label>
          <input
            id={opacityId}
            type="range"
            min="0"
            max="100"
            step="5"
            value={Math.round(view.opacity * 100)}
            onChange={(event) =>
              onLayerChange({ opacity: Number(event.target.value) / 100 })
            }
          />
          <label className="terrain-toggle">
            <input
              type="checkbox"
              checked={view.terrain}
              onChange={(event) =>
                onLayerChange({ terrain: event.target.checked })
              }
            />
            Shaded terrain
          </label>
          {contextError && <p role="status">{contextError}</p>}
        </div>
      </details>
      {!ready && !error && (
        <div className="map-status" role="status">
          Loading county map…
        </div>
      )}
      {error && (
        <div className="map-status map-error" role="alert">
          {error}
          <button onClick={() => setRetry((n) => n + 1)}>Retry map</button>
        </div>
      )}
      <span className="sr-only" aria-live="polite">
        {hover}
      </span>
    </>
  );
}
