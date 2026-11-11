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
