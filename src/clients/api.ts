import { useMemo } from 'react';
import useSWR from 'swr';
import { release, type Asset } from '../data/releases';
import { metricField, type ViewState } from '../lib/risk';
import { decodeIndex, decodeField, decodeProfile, profileAsset, verifyJson } from './data-assets';

export function assetUrl(path: string): string {
  return new URL(path, new URL(import.meta.env.BASE_URL, window.location.origin)).href;
}
const options = {revalidateOnFocus:false, revalidateOnReconnect:false, shouldRetryOnError:false};
async function fetchAsset(asset: Asset) {
  const response = await fetch(assetUrl(asset.path));
  if (!response.ok) throw new Error(`Area data could not be loaded (${response.status}).`);
  return verifyJson(await response.arrayBuffer(),asset.sha256);
}
export function useCounties(view: ViewState) {
  const index = useSWR([release.id,'index'], async () => decodeIndex(await fetchAsset(release.assets['counties.json']),release.countyCount,release.geography),options);
  const field = metricField(view);
  const fieldAsset = release.fieldAssets?.[field];
  const column = useSWR(index.data && release.fieldAssets ? [release.id,field] : null, async () => {
    if (!fieldAsset) throw new Error('This release does not include the selected metric.');
    return decodeField(await fetchAsset(fieldAsset),index.data!.length);
  },options);
  const baselineField = `${view.hazard}_EALR`;
  const needsBaseline = !!release.fieldAssets && view.metric !== 'multiplier' && field !== baselineField;
  const baseline = useSWR(index.data && needsBaseline ? [release.id,baselineField] : null, async () => {
    const asset = release.fieldAssets?.[baselineField];
    if (!asset) throw new Error('Baseline loss status is unavailable for this hazard.');
    return decodeField(await fetchAsset(asset),index.data!.length);
  },options);
  const data = useMemo(() => {
    if (!index.data || (release.fieldAssets && !column.data) || (needsBaseline && !baseline.data)) return undefined;
    return column.data ? index.data.map((row,i) => ({...row,values:{...row.values,[field]:column.data![i],...(baseline.data ? {[baselineField]:baseline.data[i]} : {})}})) : index.data;
  },[index.data,column.data,field,baseline.data,baselineField,needsBaseline]);
  const selected = data?.find(row => row.id === view.county);
  const profileAssets = release.profileAssets;
  const prefix = view.county.slice(0,profileAssets?.prefixLength ?? 5);
  const profile = useSWR(selected && profileAssets ? [release.id,'profile',prefix] : null, async () => {
    return fetchAsset(profileAsset(profileAssets!,prefix));
  },options);
  let selectedCounty = selected;
  let detailsError = profile.error;
  if (selected && profile.data) {
    try { selectedCounty = {...selected,...decodeProfile(profile.data,selected.id,release.geography)}; }
    catch (error) { detailsError = error; }
  }
  return {
    data, selectedCounty, error:index.error ?? column.error ?? baseline.error,
    isLoading:index.isLoading || column.isLoading || baseline.isLoading,
    mutate:async () => {await Promise.all([index.mutate(),column.mutate(),...(needsBaseline ? [baseline.mutate()] : [])]);},
    detailsLoading:!!selected && !!profileAssets && !profile.data && !detailsError,
    detailsError,
    retryDetails:() => profile.mutate(),
  };
}
