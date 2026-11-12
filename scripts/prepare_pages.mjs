import { readdir, rm, stat, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

// Deploy the explorer's assets; legacy source geometry stays in the repository.
const keep = new Set(['index.html', 'assets', 'atlas', 'context', 'versions', 'NRI_Data_Dictionary.xlsx', 'NRI_Future_Risk_Master_Datasheet_12052024.xlsx']);
for (const entry of await readdir('dist')) {
  if (!keep.has(entry)) await rm(join('dist', entry), { recursive: true });
}
async function checkSizes(directory) {
  for (const name of await readdir(directory)) {
    const path = join(directory, name);
    const info = await stat(path);
    if (info.isDirectory()) await checkSizes(path);
    else if (info.size > 25 * 1024 * 1024) throw new Error(`Cloudflare Pages asset exceeds 25 MiB: ${path}`);
  }
}
await checkSizes('dist');
await writeFile('dist/_headers', '/*\n  X-Robots-Tag: noindex, nofollow\n');

const { readFile } = await import('node:fs/promises');
const { archive, current } = await (await import('./releases.mjs')).readReleases();
const tiles = {};
{
  const release = archive;
  const asset = release.assets['counties.pmtiles'];
  tiles[`/${asset.path}`] = {sha256: asset.sha256, size: (await stat(join('dist', asset.path))).size};
}
// Large current assets are hosted directly by GCS, which supports Range + CORS.
// If a future current release uses local assets, route it through the Pages worker too.
for (const release of current) {
  const asset=release.assets['counties.pmtiles'];
  if (!/^https:\/\//.test(asset.path)) {
    tiles[`/${asset.path}`]={sha256:asset.sha256,size:(await stat(join('dist',asset.path))).size};
  }
}
const worker = await readFile('cloudflare/tile-worker.mjs', 'utf8');
await writeFile('dist/_worker.js', `const TILE_ASSETS = ${JSON.stringify(tiles)};\n${worker}`);
await writeFile('dist/_routes.json', JSON.stringify({version: 1, include: Object.keys(tiles), exclude: []}));
