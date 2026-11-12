import { readFile } from 'node:fs/promises';

// src/data/releases.json is the single list of releases: the FEMA archive plus recreated releases.
export async function readReleases() {
  const all = JSON.parse(await readFile('src/data/releases.json', 'utf8'));
  const archive = all.find(item => item.status === 'archive');
  if (!archive) throw new Error('releases.json must include the FEMA archive');
  return { all, archive, current: all.filter(item => item !== archive) };
}
