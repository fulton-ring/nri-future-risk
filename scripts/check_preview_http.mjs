import assert from 'node:assert/strict';
import { bytesToHeader, PMTiles } from 'pmtiles';
import { createHash } from 'node:crypto';
import { setTimeout } from 'node:timers/promises';
import { readFile, readdir, stat } from 'node:fs/promises';
const [base] = process.argv.slice(2);
if (!base) throw new Error('Usage: node scripts/check_preview_http.mjs PREVIEW_URL');
const headers = {'User-Agent':'Mozilla/5.0'};
// Pages can report a deployment URL before its assets reach the checking region.
async function fetchReady(url, options) {
  for (let attempt=0; ; attempt++) {
    const response = await fetch(url, options);
    if (![404, 502, 503, 504].includes(response.status) || attempt === 11) return response;
    await response.body?.cancel();
    console.log(`Waiting for preview propagation (${response.status}, attempt ${attempt+1}/12)`);
    await setTimeout(5000);
  }
}
const releaseFiles = (await readdir('src/data')).filter(name => ['release.json', 'analysis-2026-10.json', 'analysis-preview.json'].includes(name));
const contextResponse=await fetchReady(new URL('/context/counties.json',base),{headers});
assert.equal(contextResponse.status,200,'County context must survive preview packaging');
const contextBytes=Buffer.from(await contextResponse.arrayBuffer());
assert.deepEqual(contextBytes,await readFile('public/context/counties.json'),'Hosted county descriptions must match this build');
const regionsResponse=await fetchReady(new URL('/context/planning-regions.json',base),{headers});
assert.equal(regionsResponse.status,200,'Planning-region context must survive preview packaging');
assert.deepEqual(Buffer.from(await regionsResponse.arrayBuffer()),await readFile('public/context/planning-regions.json'),'Hosted region descriptions must match this build');
for (const name of releaseFiles) {
  const release = JSON.parse(await readFile(`src/data/${name}`, 'utf8'));
  const path = release.assets['counties.pmtiles'].path;
  const bytes = await readFile(`public/${path}`);
  assert.equal(createHash('sha256').update(bytes).digest('hex'), release.assets['counties.pmtiles'].sha256);
  for (const start of [0, 16384, bytes.length-127]) {
    const end = start+126;
    const response = await fetchReady(new URL(`/${path}`, base), {headers:{...headers,Range:`bytes=${start}-${end}`}});
    assert.equal(response.status,206,'PMTiles requires partial responses');
    assert.equal(response.headers.get('content-range'),`bytes ${start}-${end}/${bytes.length}`);
    assert.deepEqual(Buffer.from(await response.arrayBuffer()),bytes.subarray(start,end+1));
  }
  const hasDocs = await stat(`dist/versions/${release.id}`).then(()=>true, error=>{if(error.code==='ENOENT')return false;throw error;});
  if (hasDocs) for (const page of ['methodology','data']) {
    const response=await fetchReady(new URL(`/versions/${release.id}/${page}.html`,base),{headers});
    assert.equal(response.status,200);
    const body=await response.text();
    assert.ok(body.includes(`<code>${release.id}</code>`));
    assert.ok(body.includes(`<h1>${page==='data'?'Data':'Methodology'}</h1>`));
  }
  if (release.status==='analysis') {
    const response=await fetchReady(new URL(`/${path.replace(/counties\.pmtiles$/, 'counties.parquet')}`,base),{headers});
    assert.equal(response.status,200);
    assert.equal(createHash('sha256').update(Buffer.from(await response.arrayBuffer())).digest('hex'),release.sourceSha256);
  }
  if (release.heatCalculations) {
    const response=await fetchReady(new URL(`/${release.heatCalculations.path}`,base),{headers});
    assert.equal(response.status,200);
    const bytes=Buffer.from(await response.arrayBuffer());
    assert.equal(createHash('sha256').update(bytes).digest('hex'),release.heatCalculations.sha256);
    const details=JSON.parse(bytes.toString());
    assert.equal(details.snapshotSha256,release.heatCalculations.snapshotSha256);
    assert.equal(details.verifiedCountyScenarios,24864);
  }
  console.log(`Verified hosted PMTiles bytes and available version documents/data: ${release.id}`);
}

for (const release of JSON.parse(await readFile('src/data/current-releases.json','utf8'))) {
  const origin=new URL(base).origin;
  const asset=release.assets['counties.pmtiles'];
  const tileUrl=new URL(asset.path,base);
  const head=await fetchReady(tileUrl,{method:'HEAD',headers:{...headers,Origin:origin}});
  assert.equal(head.status,200,'Current PMTiles must be available before exposing the version');
  const size=Number(head.headers.get('content-length'));
  assert.ok(size>127);
  if(tileUrl.origin!==origin) {
    assert.ok(['*',origin].includes(head.headers.get('access-control-allow-origin')),'Current tiles require preview-origin CORS');
    assert.equal(head.headers.get('x-goog-meta-sha256'),asset.sha256,'Public tile metadata must bind the verified renderer output');
  }
  for(const start of [0,16384,size-127]) {
    const response=await fetchReady(tileUrl,{headers:{...headers,Origin:origin,Range:`bytes=${start}-${start+126}`}});
    assert.equal(response.status,206,'Current PMTiles requires byte ranges');
    assert.equal(response.headers.get('content-range'),`bytes ${start}-${start+126}/${size}`);
    const bytes=await response.arrayBuffer();
    assert.equal(bytes.byteLength,127);
    if(start===0 && release.geography==='tracts') assert.equal(bytesToHeader(bytes).minZoom,0,'Tract PMTiles must include the zoomed-out overview');
  }
  if(release.geography==='tracts') {
    const metadata=await new PMTiles(tileUrl.href).getMetadata();
    const fields=metadata.vector_layers.find(layer=>layer.id===release.sourceLayer).fields;
    for(const field of Object.keys(release.fieldAssets)) assert.ok(field in fields,`Tract tiles must retain map field ${field}`);
  }
  async function jsonAsset(spec) {
    const response=await fetchReady(new URL(spec.path,base),{headers});
    assert.equal(response.status,200);
    const bytes=Buffer.from(await response.arrayBuffer());
    assert.equal(createHash('sha256').update(bytes).digest('hex'),spec.sha256);
    return JSON.parse(bytes.toString());
  }
  if(release.heatDiagnostics) {
    const diagnostic=await jsonAsset(release.heatDiagnostics.manifest);
    assert.equal(diagnostic.version,release.resultsVersion);
    assert.equal(diagnostic.geography,release.geography);
    assert.equal(diagnostic.verifiedAreaScenarios,(release.geography==='tracts'?83461:3109)*8);
    assert.equal(diagnostic.assets['heat-calculations.json'].sha256,release.heatDiagnostics.sha256);
    if(release.geography==='counties') {
      const heat=await jsonAsset(release.heatCalculations);
      assert.equal(heat.publishedMultipliersSha256,release.sourceSha256);
    }
  }
  const index=await jsonAsset(release.assets['counties.json']);
  assert.equal(index.counties.length,release.countyCount);
  const ct=index.counties.filter(row=>row.id.startsWith('09'));
  if(release.geography==='counties') assert.deepEqual(ct.map(row=>row.id).sort(),['09110','09120','09130','09140','09150','09160','09170','09180','09190']);
  else {
    assert.equal(ct.length,879);
    for(const hazard of ['DRGT','WFIR','EXHT']) {
      const baseline=await jsonAsset(release.fieldAssets[`${hazard}_EALR`]);
      assert.equal(baseline.length,index.counties.length,'Baseline loss statuses must align with the tract index');
    }
    const column=await jsonAsset(release.fieldAssets.DRGT_MID_LOWER_PALR);
    assert.equal(column.length,index.counties.length);
    const prefix='09110';
    const profile=await jsonAsset({path:release.profileAssets.template.replace('{prefix}',prefix),sha256:release.profileAssets.hashes[prefix]});
    assert.ok(profile.counties.length>0 && profile.counties.every(row=>row.id.startsWith(prefix)));
  }
  for(const name of ['methodology','data']) {
    const response=await fetchReady(new URL(`/versions/${release.id}/${name}.html`,base),{headers});
    assert.equal(response.status,200);
    const body=await response.text();
    assert.ok(body.includes(`<h1>${name==='data'?'Data':'Methodology'}</h1>`));
    assert.ok(body.includes('NRI v1.20'));
  }
  const source=await fetchReady(release.sourceData,{method:'HEAD',headers});
  assert.equal(source.status,200,'Exact current Batch output must be reviewable');
  assert.equal(source.headers.get('x-goog-meta-sha256'),release.sourceSha256);
  console.log(`Verified current ${release.geography}, remote ranges/CORS, pinned attributes and version documents: ${release.id}`);
}
