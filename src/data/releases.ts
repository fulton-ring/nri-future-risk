import releaseList from './releases.json';

export type Asset = {path: string; sha256: string};
export type RatingBins = {hazards: Partial<Record<string, {annualLoss: number[]; riskValue: number[]}>>};
export type Release = {
  id: string; title: string; date: string; status: string; baseline: string;
  countyCount: number; sourceLayer: string;
  assets: Record<string, Asset>;
  geography?: 'counties' | 'tracts'; rankingPopulation?: string; bins?: RatingBins;
  fieldAssets?: Record<string, Asset>;
  profileAssets?: {template: string; prefixLength: number; hashes?: Record<string,string>};
  heatCalculations?: Asset & {snapshotSha256: string};
  parameters?: {wildfireElasticity?: number; wildfireEnsemble?: string; wildfireVariable?: string};
};
export function validatedRelease(value: unknown): Release {
  if (!value || typeof value !== 'object') throw new Error('Invalid current release');
  const item = value as Release;
  const validAsset = (asset: Asset) => asset && typeof asset.path === 'string' && /^[a-f0-9]{64}$/.test(asset.sha256);
  if (typeof item.id !== 'string' || typeof item.title !== 'string' || typeof item.date !== 'string' ||
      item.status !== 'analysis' || item.baseline !== 'NRI v1.20' || item.rankingPopulation !== 'CONUS' ||
      !['counties','tracts'].includes(item.geography ?? '') || item.sourceLayer !== item.geography ||
      !Number.isInteger(item.countyCount) || item.countyCount < 1 ||
      !validAsset(item.assets?.['counties.json']) || !validAsset(item.assets?.['counties.pmtiles']))
    throw new Error('Invalid current release manifest');
  for (const hazard of ['DRGT','WFIR','EXHT']) for (const metric of ['annualLoss','riskValue'] as const) {
    const edges = item.bins?.hazards[hazard]?.[metric];
    if (!edges || edges.length !== 4 || !edges.every((v,i) => Number.isFinite(v) && v > 0 && (i === 0 || v > edges[i-1])))
      throw new Error('Invalid release rating bins');
  }
  if (item.fieldAssets && !Object.values(item.fieldAssets).every(validAsset)) throw new Error('Invalid field asset');
  if (item.profileAssets && (typeof item.profileAssets.template !== 'string' || !item.profileAssets.template.includes('{prefix}') || item.profileAssets.prefixLength !== 5 ||
    (item.profileAssets.hashes && !Object.values(item.profileAssets.hashes).every(hash => /^[a-f0-9]{64}$/.test(hash))))) throw new Error('Invalid profile assets');
  if (item.geography === 'tracts' && (!item.fieldAssets || !item.profileAssets)) throw new Error('Missing tract assets');
  if (item.geography === 'tracts' && !item.profileAssets?.hashes) throw new Error('Missing verified profile hashes');
  return item;
}


const list = releaseList as unknown[];
const archive: Release = (() => {
  const entry = list.find(item => (item as Release).status === 'archive');
  if (!entry) throw new Error('releases.json must include the FEMA archive');
  return entry as Release;
})();
// Every other entry is a recreated release and must pass validation.
export const releases: Release[] = [archive, ...list.filter(item => item !== archive).map(validatedRelease)];

export function selectRelease(mode?: string, requestedId?: string | null, available: Release[] = releases): Release {
  const requested = available.find((item) => item.id === requestedId);
  if (requested) return requested;
  if (!mode || mode === 'archive') return archive;
  if (mode === 'analysis-preview') return [...available].reverse().find(item => item.status === 'analysis' && item.geography === 'counties') ?? archive;
  throw new Error(`Unknown data release: ${mode}`);
}

const requestedId = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("release");
export const release = selectRelease(import.meta.env?.VITE_DATA_RELEASE, requestedId);
export const isAnalysis = release.status === 'analysis';

export const isTract = release.geography === 'tracts';
export const areaLabel = isTract ? 'census tract' : 'county';
export const areasLabel = isTract ? 'census tracts' : 'counties';

export function selectionForRelease(id: string, from: Release, to: Release): string {
  if ((from.geography ?? 'counties') !== (to.geography ?? 'counties')) return '';
  const retiredConnecticutCounty = /^090(?:01|03|05|07|09|11|13|15)$/.test(id);
  if (from.baseline !== to.baseline && to.baseline === 'NRI v1.20' && retiredConnecticutCounty) return '';
  return id;
}
