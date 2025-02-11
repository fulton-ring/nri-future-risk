"use client";

import dynamic from "next/dynamic";

// TODO: client side map wrapper so page can use SSR
// https://stackoverflow.com/questions/77978480/nextjs-with-react-leaflet-ssr-webpack-window-not-defined-icon-not-found
const Map = dynamic(() => import("@/components/Map"), {
  loading: () => <p>Loading...</p>,
  ssr: false,
});

export default function Home() {
  return (
    <main>
      <Map />
    </main>
  );
}
