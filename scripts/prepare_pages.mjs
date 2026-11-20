import { readdir, stat, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

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

// Every release's PMTiles is hosted in the results bucket, which supports Range + CORS.
// Pages ignores Range requests, so tiles must never be served from the site itself.
const { all } = await (await import('./releases.mjs')).readReleases();
const local = all.filter(release => !/^https:\/\//.test(release.assets['counties.pmtiles'].path));
if (local.length) throw new Error(`PMTiles must be hosted remotely: ${local.map(release => release.id).join(', ')}`);
