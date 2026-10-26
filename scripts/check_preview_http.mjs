import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, readdir, stat } from 'node:fs/promises';
const [base] = process.argv.slice(2);
if (!base) throw new Error('Usage: node scripts/check_preview_http.mjs PREVIEW_URL');
const headers = {'User-Agent':'Mozilla/5.0'};
const releaseFiles = (await readdir('src/data')).filter(name => ['release.json', 'analysis-preview.json'].includes(name));
for (const name of releaseFiles) {
  const release = JSON.parse(await readFile(`src/data/${name}`, 'utf8'));
  const path = release.assets['counties.pmtiles'].path;
  const bytes = await readFile(`public/${path}`);
  assert.equal(createHash('sha256').update(bytes).digest('hex'), release.assets['counties.pmtiles'].sha256);
  for (const start of [0, 16384, bytes.length-127]) {
    const end = start+126;
    const response = await fetch(new URL(`/${path}`, base), {headers:{...headers,Range:`bytes=${start}-${end}`}});
    assert.equal(response.status,206,'PMTiles requires partial responses');
    assert.equal(response.headers.get('content-range'),`bytes ${start}-${end}/${bytes.length}`);
    assert.deepEqual(Buffer.from(await response.arrayBuffer()),bytes.subarray(start,end+1));
  }
  const hasDocs = await stat(`dist/versions/${release.id}`).then(()=>true, error=>{if(error.code==='ENOENT')return false;throw error;});
  if (hasDocs) for (const page of ['methodology','data']) {
    const response=await fetch(new URL(`/versions/${release.id}/${page}.html`,base),{headers});
    assert.equal(response.status,200);
    const body=await response.text();
    assert.ok(body.includes(`<code>${release.id}</code>`));
    assert.ok(body.includes(`<h1>${page==='data'?'Data':'Methodology'}</h1>`));
  }
  if (release.status==='analysis') {
    const response=await fetch(new URL('/preview/counties.parquet',base),{headers});
    assert.equal(response.status,200);
    assert.equal(createHash('sha256').update(Buffer.from(await response.arrayBuffer())).digest('hex'),release.sourceSha256);
  }
  console.log(`Verified hosted PMTiles bytes and available version documents/data: ${release.id}`);
}
