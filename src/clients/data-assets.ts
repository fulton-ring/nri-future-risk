import type { Asset, Release } from '../data/releases';
import type { County, Value } from '../lib/risk';

const scalar = (v: unknown): v is Value => v === null || typeof v === 'string' || (typeof v === 'number' && Number.isFinite(v));
export async function verifyJson(bytes: ArrayBuffer, expectedHash?: string): Promise<unknown> {
  if (expectedHash) {
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)), v => v.toString(16).padStart(2,'0')).join('');
    if (hash !== expectedHash) throw new Error('Data asset hash mismatch.');
  }
  return JSON.parse(new TextDecoder().decode(bytes));
}
export function decodeIndex(data: unknown, count?: number, geography?: Release['geography']): County[] {
  if (!data || typeof data !== 'object' || !('columns' in data) || !('counties' in data) ||
      !Array.isArray(data.columns) || !data.columns.every(c => typeof c === 'string') || !Array.isArray(data.counties) ||
      (count !== undefined && data.counties.length !== count)) throw new Error('Area data does not match this release.');
  const columns: string[] = data.columns;
  const ids = new Set<string>();
  return data.counties.map(row => {
    if (!row || typeof row !== 'object' || !/^(?:\d{5}|\d{11})$/.test(row.id) || ids.has(row.id) ||
      typeof row.name !== 'string' || typeof row.state !== 'string' || !Array.isArray(row.bounds) ||
      row.bounds.length !== 4 || !row.bounds.every((n: unknown) => typeof n === 'number' && Number.isFinite(n)) ||
      !Array.isArray(row.values) || row.values.length !== columns.length || !row.values.every(scalar))
      throw new Error('Invalid area metadata or values.');
    if ((geography === 'tracts' && row.id.length !== 11) || (geography === 'counties' && row.id.length !== 5))
      throw new Error('Area identifier does not match the release geography.');
    ids.add(row.id);
    const values = Object.fromEntries(columns.map((name,i) => [name,row.values[i]]));
    if (row.heatCalculations !== undefined) {
      if (!row.heatCalculations || typeof row.heatCalculations !== 'object' || Array.isArray(row.heatCalculations))
        throw new Error('Invalid profile heat diagnostics.');
      const close = (a:number,b:number) => Math.abs(a-b) <= 1e-9 * Math.max(1,Math.abs(a),Math.abs(b));
      for (const [key, details] of Object.entries(row.heatCalculations)) {
        if (!/^EXHT_(?:L95|L99|N95|N99)_(?:MID|LATE)_(?:LOWER|HIGHER)$/.test(key) ||
          !details || typeof details !== 'object') throw new Error('Invalid profile heat diagnostics.');
        const heat = details as Record<string,unknown>;
        if (![heat.historicalDaysPerYear,heat.futureDaysPerYear,heat.rawMultiplier,heat.appliedMultiplier].every(v=>typeof v === 'number' && Number.isFinite(v) && v >= 0))
          throw new Error('Invalid profile heat diagnostics.');
        const historical = heat.historicalDaysPerYear as number, future = heat.futureDaysPerYear as number;
        const raw = heat.rawMultiplier as number, applied = heat.appliedMultiplier as number;
        const hm = values[`${key}_HM`];
        if (historical <= 0 || !close(raw,future/historical) || !close(applied,Math.max(1,raw)) ||
          (Object.prototype.hasOwnProperty.call(values,`${key}_HM`) && (typeof hm !== 'number' || !close(applied,hm))))
          throw new Error('Profile heat diagnostics do not match the ratio, floor or published multiplier.');
      }
    }
    return {...row, values};
  });
}
export function decodeField(data: unknown, count: number): Value[] {
  if (!Array.isArray(data) || data.length !== count) throw new Error('Metric array length does not match the area index.');
  if (!data.every(scalar)) throw new Error('Invalid metric value.');
  return data;
}
export function decodeProfile(data: unknown, id: string, geography?: Release['geography']): County {
  const selected = decodeIndex(data,undefined,geography).find(row => row.id === id);
  if (!selected) throw new Error('Profile shard does not contain the selected area.');
  return selected;
}

export function profileAsset(config: NonNullable<Release['profileAssets']>, prefix: string): Asset {
  const sha256 = config.hashes?.[prefix];
  if (!sha256 || !/^[a-f0-9]{64}$/.test(sha256)) throw new Error('No verified profile shard for the selected area.');
  return {path:config.template.replace('{prefix}',prefix),sha256};
}
