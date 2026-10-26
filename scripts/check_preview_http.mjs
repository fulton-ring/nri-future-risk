import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const [base] = process.argv.slice(2);
if (!base) throw new Error('Usage: node scripts/check_preview_http.mjs PREVIEW_URL');
const bytes = await readFile('public/preview/counties.pmtiles');
for (const start of [0, 16384, bytes.length - 127]) {
  const end = start + 126;
  const response = await fetch(new URL('/preview/counties.pmtiles', base), {headers: {Range: `bytes=${start}-${end}`, 'User-Agent': 'Mozilla/5.0'}});
  assert.equal(response.status, 206, 'PMTiles requires partial responses');
  assert.equal(response.headers.get('content-range'), `bytes ${start}-${end}/${bytes.length}`);
  assert.deepEqual(Buffer.from(await response.arrayBuffer()), bytes.subarray(start, end + 1));
}
console.log('Verified HTTP 206 and exact PMTiles bytes at the header, middle and end.');
for (const id of ['fema-2024-12-05', 'fri-analysis-20261025140637']) {
  for (const page of ['methodology', 'data']) {
    const response = await fetch(new URL(`/versions/${id}/${page}.html`, base), {headers: {'User-Agent':'Mozilla/5.0'}});
    assert.equal(response.status, 200);
    const body = await response.text();
    assert.ok(body.includes(`<code>${id}</code>`), 'documentation must identify the selected release');
    assert.ok(body.includes(`<h1>${page === 'data' ? 'Data' : 'Methodology'}</h1>`), 'documentation must not fall back to the explorer');
  }
}
const parquet = await fetch(new URL('/preview/counties.parquet', base), {method:'HEAD', headers:{'User-Agent':'Mozilla/5.0'}});
assert.equal(parquet.status, 200);
console.log('Verified methodology/data pages for both versions and the analysis GeoParquet download.');
