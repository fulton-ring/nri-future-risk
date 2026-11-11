/** Census tract GEOIDs begin with their five-digit county-equivalent GEOID. */
export function countyContextId(id: string): string | null {
  return /^(?:\d{5}|\d{11})$/.test(id) ? id.slice(0,5) : null;
}
