"use client";

// <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
// integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
// crossorigin=""/>
import "leaflet/dist/leaflet.css";
// import "leaflet-defaulticon-compatibility/dist/leaflet-defaulticon-compatibility.webpack.css";
// import "leaflet-defaulticon-compatibility";

import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import type { FeatureCollection, Feature, Geometry } from "geojson";
// "properties":{"geo_point_2d":{"lon":-89.68448923303517,"lat":37.383972850288494},"year":"2023","ste_code":["29"],"ste_name":["Missouri"],"coty_code":["29031"],"coty_name":["Cape Girardeau"],"coty_area_code":"USA","coty_type":"county","coty_name_long":["Cape Girardeau County"],"coty_fp_code":"031","coty_gnis_code":"00758470"}

type CountyProperties = {
  geo_point_2d: {
    lon: number;
    lat: number;
  };
  year: string;
  ste_code: string[];
  ste_name: string[];
  coty_code: string[];
  coty_name: string[];
  coty_area_code: string;
  coty_name_long: string[];
  coty_fp_code: string;
  coty_gnis_code: string;
};

// TODO: combine county data with climate data
const geojson: FeatureCollection<
  Geometry,
  CountyProperties
> = require("@/data/georef-united-states-of-america-county.json");

// Centered over continental US
const center = { lat: 39.8283, lng: -98.5795 };

const styleFn = (feature: Feature<Geometry, CountyProperties> | undefined) => {
  if (!feature) return {};

  return {
    // TODO: implement getColor depending on chart
    // fillColor: getColor(feature.properties),
    weight: 2,
    opacity: 1,
    color: "white", // dependent on chart
    dashArray: "3",
    fillOpacity: 0.7,
  };
};

const Map = () => {
  // TODO: take center as props
  // TODO: take map size as props
  // TODO: enable pinch to zoom

  return (
    <MapContainer
      center={center}
      zoom={4}
      scrollWheelZoom={false}
      style={{ height: "400px", width: "600px" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://www.stamen.com/" target="_blank">Stamen Design</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        // url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        url="https://tiles.stadiamaps.com/tiles/stamen_toner_lite/{z}/{x}/{y}{r}.png"
      />

      <GeoJSON data={geojson} style={styleFn} />
    </MapContainer>
  );
};

export default Map;
