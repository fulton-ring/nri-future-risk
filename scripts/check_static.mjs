import assert from 'node:assert/strict';
import { readFile, access } from 'node:fs/promises';
import { resolve } from 'node:path';

const directory = process.argv[2] || 'dist';
const base = process.env.VITE_BASE_PATH || '/nri-future-risk/';
const html = await readFile(resolve(directory, 'index.html'), 'utf8');
assert.match(html, /<h1[^>]*>Future Risk Index<\/h1>/, 'The initial HTML must contain the project introduction');
assert.ok(html.includes('What is it?'), 'The guide must be readable without running JavaScript');
assert.match(html, /name="description"/);
assert.match(html, /rel="canonical"/);
assert.match(html, /type="module"/);
for (const [, value] of html.matchAll(/(?:src|href)="([^"]+)"/g)) {
  if (/^(https?:|data:|#)/.test(value)) continue;
  assert.ok(value.startsWith(base), `Local asset or link must use ${base}: ${value}`);
  if (value === base || value.includes('?')) continue;
  await access(resolve(directory, decodeURIComponent(value.slice(base.length))));
}
const release = JSON.parse(await readFile('src/data/release.json', 'utf8'));
for (const page of ['methodology', 'data']) {
  assert.ok(html.includes(`${base}versions/${release.id}/${page}.html`), 'Version documents must be discoverable without JavaScript');
  const document = await readFile(resolve(directory, `versions/${release.id}/${page}.html`), 'utf8');
  assert.ok(document.includes(`<code>${release.id}</code>`));
}
console.log(`Verified prerendered HTML, metadata, local assets and version pages at ${base}`);
