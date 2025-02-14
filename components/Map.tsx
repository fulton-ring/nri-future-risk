"use client";

// <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
// integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
// crossorigin=""/>
import "leaflet/dist/leaflet.css";
// import "leaflet-defaulticon-compatibility/dist/leaflet-defaulticon-compatibility.webpack.css";
// import "leaflet-defaulticon-compatibility";

import { MapContainer, TileLayer, GeoJSON, useMapEvents } from "react-leaflet";
import type { FeatureCollection, Feature, Geometry } from "geojson";
import { useState } from "react";
import { Layer } from "leaflet";

import { CountyProperties } from "@/schema/county";
import CountyInfoModal from "@/components/counties/CountyInfoModal";

// TODO: combine county data with climate data
const geojson: FeatureCollection<
  Geometry,
  CountyProperties
> = require("@/data/georef-united-states-of-america-county.json");

// Centered over continental US
const center = { lat: 39.8283, lng: -98.5795 };

const Map = () => {
  const [hoveredCounty, setHoveredCounty] = useState<string | undefined>();
  const [selectedCounty, setSelectedCounty] = useState<
    CountyProperties | undefined
  >();

  // TODO: make pinch to zoom smoother
  // TODO: improve hover styling performance (useMemo, maybe maintain some state of styles)

  return (
    <MapContainer
      center={center}
      zoom={4}
      // zoomDelta={0.5}
      scrollWheelZoom={true}
      // style={{ height: 800, width: 1200 }}
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://www.stamen.com/" target="_blank">Stamen Design</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        // url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        url="https://tiles.stadiamaps.com/tiles/stamen_toner_lite/{z}/{x}/{y}{r}.png"
      />

      <GeoJSON
        data={geojson}
        style={(feature: Feature<Geometry, CountyProperties> | undefined) => {
          if (!feature) return {};

          const isHovered = feature.properties.coty_code[0] === hoveredCounty;

          return {
            // TODO: implement getColor depending on chart
            // fillColor: getColor(feature.properties),
            weight: isHovered ? 5 : 2,
            opacity: 1,
            // color: isHovered ? "white" : "black", // dependent on chart
            dashArray: isHovered ? "3" : "",
            fillOpacity: isHovered ? 0.7 : 0.3,
          };
        }}
        onEachFeature={(
          feature: Feature<Geometry, CountyProperties>,
          layer: Layer
        ) => {
          layer.on("mouseover", () => {
            setHoveredCounty(feature.properties.coty_code[0]);
          });

          layer.on("mouseout", () => {
            setHoveredCounty(undefined);
          });

          layer.on("click", () => {
            setSelectedCounty(feature.properties);
          });
        }}
      />

      <CountyInfoModal
        selectedCounty={selectedCounty}
        onClose={() => setSelectedCounty(undefined)}
      />
    </MapContainer>
  );
};

export default Map;
