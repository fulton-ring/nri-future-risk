import useSWR from "swr";
import { release } from "../data/releases";
import type { County, Values } from "../lib/risk";

export function assetUrl(path: string): string {
  return new URL(
    path,
    new URL(import.meta.env.BASE_URL, window.location.origin),
  ).href;
}
async function fetchCounties(): Promise<County[]> {
  const response = await fetch(assetUrl(release.assets["counties.json"].path));
  if (!response.ok)
    throw new Error(`County data could not be loaded (${response.status}).`);
  const data: {
    columns: string[];
    counties: (Omit<County, "values"> & {
      values: (string | number | null)[];
    })[];
  } = await response.json();
  if (
    data.counties.length !== release.countyCount ||
    !Array.isArray(data.columns)
  )
    throw new Error("County data does not match this release.");
  return data.counties.map((county) => ({
    ...county,
    values: Object.fromEntries(
      data.columns.map((name, i) => [name, county.values[i]]),
    ) as Values,
  }));
}
export function useCounties() {
  return useSWR<County[]>(release.id, fetchCounties, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: false,
  });
}
