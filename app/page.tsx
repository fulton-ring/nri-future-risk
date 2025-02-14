"use client";

import Rating from "@/components/filters/Rating";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SearchIcon } from "lucide-react";
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
  // TODO: add scenario graph
  // TODO: add old dataset comparison
  // TODO: Use Outfit font
  // TODO: use combobox for search

  return (
    <main>
      <div className="absolute inset-0 z-0 h-screen w-full">
        <Map />
      </div>

      <div className="relative p-4 z-10 pointer-events-none h-screen flex flex-col justify-between">
        <div className="flex flex-col items-center space-y-4 justify-center">
          <div className="flex flex-row gap-4 pointer-events-auto">
            <Rating />
            <Rating />
            <Rating />
          </div>

          <div className="flex flex-row gap-4 pointer-events-auto w-1/4">
            <div className="relative w-full">
              <Input placeholder="Search Counties" />
              <SearchIcon className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-500" />
              {/* <svg
                className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-500"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg> */}
            </div>
          </div>
        </div>

        <div className="flex-grow flex items-end justify-end py-16 px-4">
          <div className="flex flex-col gap-4 pointer-events-auto">
            <Button>View Datasets</Button>
          </div>
        </div>
      </div>
    </main>
  );
}
