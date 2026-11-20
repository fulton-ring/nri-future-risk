import { readdir, rename, rm } from 'node:fs/promises';
import { join } from 'node:path';

// Deploy only prerendered client files; these hosts do not run a Start server.
const client = join('dist', 'client');
const files = await readdir(client);
for (const file of await readdir('dist')) {
  if (file !== 'client') await rm(join('dist', file), { recursive: true });
}
for (const file of files) await rename(join(client, file), join('dist', file));
await rm(client, { recursive: true });
// Ship only what the explorer uses; source files and release data are served from the results bucket.
const keep = new Set(['index.html', 'assets', 'context', 'guide', 'versions']);
for (const file of await readdir('dist')) {
  if (!keep.has(file)) await rm(join('dist', file), { recursive: true });
}
