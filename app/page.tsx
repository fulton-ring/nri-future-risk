"use client";

import Rating from "@/components/filters/Rating";
import dynamic from "next/dynamic";

// TODO: client side map wrapper so page can use SSR
// https://stackoverflow.com/questions/77978480/nextjs-with-react-leaflet-ssr-webpack-window-not-defined-icon-not-found
const Map = dynamic(() => import("@/components/Map"), {
  loading: () => <p>Loading...</p>,
  ssr: false,
});

export default function Home() {
  // TODO: add rating tab
  // TODO: add hazard tab
  // TODO: add scenario tab
  // TODO: optional data source tab
  // TODO: add county search bar
  // TODO: add scenario graph
  // TODO: add old dataset comparison

  return (
    <main>
      <div className="absolute inset-0 z-0 h-screen w-full">
        <Map />
      </div>

      <div className="relative p-4 z-10 pointer-events-none">
        <div className="flex justify-center">
          <div className="flex flex-row gap-4 pointer-events-auto">
            <Rating />
            <Rating />
            <Rating />
          </div>
        </div>
      </div>
    </main>
  );
}
