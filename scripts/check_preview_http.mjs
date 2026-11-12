import assert from 'node:assert/strict';
import { bytesToHeader, PMTiles } from 'pmtiles';
import { createHash } from 'node:crypto';
import { setTimeout } from 'node:timers/promises';
import { readFile } from 'node:fs/promises';
import { readReleases } from './releases.mjs';
const { archive, current } = await readReleases();
const args = process.argv.slice(2);
// --before-deploy checks only remotely hosted release data, using SITE_URL as the CORS origin,
// so a broken release blocks the deploy instead of being found after it is live.
const beforeDeploy = args.includes('--before-deploy');
const [base] = args.filter(arg => arg !== '--before-deploy');
if (!base) throw new Error('Usage: node scripts/check_preview_http.mjs [--before-deploy] SITE_URL');
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
if (!beforeDeploy) {
const contextResponse=await fetchReady(new URL('/context/counties.json',base),{headers});
assert.equal(contextResponse.status,200,'County context must survive preview packaging');
const contextBytes=Buffer.from(await contextResponse.arrayBuffer());
assert.deepEqual(contextBytes,await readFile('public/context/counties.json'),'Hosted county descriptions must match this build');
const regionsResponse=await fetchReady(new URL('/context/planning-regions.json',base),{headers});
assert.equal(regionsResponse.status,200,'Planning-region context must survive preview packaging');
assert.deepEqual(Buffer.from(await regionsResponse.arrayBuffer()),await readFile('public/context/planning-regions.json'),'Hosted region descriptions must match this build');
}
{
  // The archive is served from the results bucket, like the recreated releases.
  const release = archive;
  const origin = new URL(base).origin;
  const asset = release.assets['counties.pmtiles'];
  const tileUrl = new URL(asset.path, base);
  const head = await fetchReady(tileUrl, {method:'HEAD', headers:{...headers, Origin:origin}});
  assert.equal(head.status, 200, 'Archive PMTiles must be available before exposing the version');
  assert.ok(['*', origin].includes(head.headers.get('access-control-allow-origin')), 'Archive tiles require site-origin CORS');
  assert.equal(head.headers.get('x-goog-meta-sha256'), asset.sha256, 'Archive tile metadata must match the manifest');
  const size = Number(head.headers.get('content-length'));
  for (const start of [0, 16384, size-127]) {
    const response = await fetchReady(tileUrl, {headers:{...headers, Origin:origin, Range:`bytes=${start}-${start+126}`}});
    assert.equal(response.status, 206, 'Archive PMTiles requires byte ranges');
    assert.equal(response.headers.get('content-range'), `bytes ${start}-${start+126}/${size}`);
  }
  const attributes = await fetchReady(new URL(release.assets['counties.json'].path, base), {headers:{...headers, Origin:origin}});
  assert.equal(attributes.status, 200);
  assert.equal(createHash('sha256').update(Buffer.from(await attributes.arrayBuffer())).digest('hex'), release.assets['counties.json'].sha256);
  if (!beforeDeploy) for (const page of ['methodology','data']) {
    const response=await fetchReady(new URL(`/versions/${release.id}/${page}.html`,base),{headers});
    assert.equal(response.status,200);
    const body=await response.text();
    assert.ok(body.includes(`<code>${release.id}</code>`));
    assert.ok(body.includes(`<h1>${page==='data'?'Data':'Methodology'}</h1>`));
  }
  console.log(`Verified remote archive tiles, attributes and version documents: ${release.id}`);
}

for (const release of current) {
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
  if (!beforeDeploy) for(const name of ['methodology','data']) {
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
