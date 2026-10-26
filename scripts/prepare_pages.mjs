import { readdir, rm, stat, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

// Deploy the explorer's assets; legacy source geometry stays in the repository.
const keep = new Set(['index.html', 'assets', 'atlas', 'preview', 'NRI_Data_Dictionary.xlsx', 'NRI_Future_Risk_Master_Datasheet_12052024.xlsx']);
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
await writeFile('dist/_headers', '/*\n  X-Robots-Tag: noindex, nofollow\n/preview/*\n  Cache-Control: public, max-age=0, must-revalidate\n');

const { readFile } = await import('node:fs/promises');
const tiles = {};
for (const name of ['release.json', 'analysis-preview.json']) {
  const release = JSON.parse(await readFile(join('src/data', name), 'utf8'));
  const asset = release.assets['counties.pmtiles'];
  tiles[`/${asset.path}`] = {sha256: asset.sha256, size: (await stat(join('dist', asset.path))).size};
}
const worker = await readFile('cloudflare/tile-worker.mjs', 'utf8');
await writeFile('dist/_worker.js', `const TILE_ASSETS = ${JSON.stringify(tiles)};\n${worker}`);
await writeFile('dist/_routes.json', JSON.stringify({version: 1, include: Object.keys(tiles), exclude: []}));
