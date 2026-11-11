import assert from 'node:assert/strict';
import { test } from 'node:test';
import { selectRelease, releases } from '../src/data/releases.ts';

test('analysis data is opt-in and shared links use its own identity', () => {
  assert.equal(selectRelease(undefined).id, 'fema-2024-12-05');
  assert.equal(selectRelease('archive').status, 'archive');
  const preview = selectRelease('analysis-preview', 'fri-mme50-20261109195422-score');
  assert.equal(preview.status, 'analysis');
  assert.equal(preview.id, 'fri-mme50-20261109195422-score');
  assert.notEqual(preview.assets['counties.pmtiles'].path, selectRelease('archive').assets['counties.pmtiles'].path);
  assert.throws(() => selectRelease('unknown'), /Unknown data release/);
});

test('the preview tile contains the new scores and fits Pages', async () => {
  const { readFile } = await import('node:fs/promises');
  const { createHash } = await import('node:crypto');
  const { PMTiles } = await import('pmtiles');
  const { VectorTile } = await import('@mapbox/vector-tile');
  const { PbfReader } = await import('pbf');
  const release = selectRelease('analysis-preview', 'fri-mme50-20261109195422-score');
  const bytes = await readFile(new URL('../public/preview/counties.pmtiles', import.meta.url));
  assert.ok(bytes.byteLength <= 25 * 1024 * 1024);
  assert.equal(createHash('sha256').update(bytes).digest('hex'), release.assets['counties.pmtiles'].sha256);
  const data = JSON.parse(await readFile(new URL('../public/preview/counties.json', import.meta.url), 'utf8'));
  assert.equal(data.counties.length, release.countyCount);
  const archive = new PMTiles({getKey: () => 'preview', getBytes: async (offset, length) => ({data: bytes.buffer.slice(bytes.byteOffset + offset, bytes.byteOffset + offset + length)})});
  const tile = await archive.getZxy(6, 11, 25);
  assert.ok(tile);
  const layer = new VectorTile(new PbfReader(new Uint8Array(tile.data))).layers.counties;
  const props = Array.from({length: layer.length}, (_, i) => layer.feature(i).properties).find(p => p.fips === '06037');
  assert.ok(props);
  const county = data.counties.find((c: {id: string}) => c.id === '06037');
  for (const [i, key] of data.columns.entries()) if (county.values[i] !== null) assert.equal(props[key], county.values[i], key);
  const baseline = JSON.parse(await readFile(new URL('../public/atlas/counties.json', import.meta.url), 'utf8'));
  const original = baseline.counties.find((c: {id: string}) => c.id === '06037');
  assert.ok(data.columns.some((key: string, i: number) => key.endsWith('_HM') && original.values[baseline.columns.indexOf(key)] !== county.values[i]), 'preview must contain recalculated multipliers');
});

test('a selected version in a shared URL overrides the deployment default', () => {
  assert.equal(selectRelease('analysis-preview', 'fema-2024-12-05').status, 'archive');
  assert.equal(selectRelease('archive', 'fri-mme50-20261109195422-score').status, 'analysis');
  assert.equal(selectRelease('archive', 'unavailable-version').status, 'archive');
});

test('analysis controls and shared URLs only expose recalculated series', async () => {
  const { releaseHazards, releaseModels, readState } = await import('../src/lib/risk.ts');
  assert.deepEqual(releaseHazards('analysis'), ['WFIR', 'DRGT', 'EXHT']);
  assert.deepEqual(releaseModels('analysis'), ['L95', 'L99']);
  assert.ok(releaseHazards('archive').includes('CFLD'));
  assert.ok(releaseHazards('archive').includes('HRCN'));
  assert.ok(releaseModels('archive').includes('N99'));
  assert.equal(readState('?hazard=HRCN&model=N99', 'analysis').hazard, 'WFIR');
  assert.equal(readState('?hazard=EXHT&model=N99', 'analysis').model, 'L95');
  assert.equal(readState('?hazard=HRCN&model=N99', 'archive').hazard, 'HRCN');
});


test('the recomputed preview uses complete MME50 annual-mean inputs', async () => {
  const { readFile } = await import('node:fs/promises');
  const provenance = JSON.parse(await readFile(new URL('../public/preview/provenance.json', import.meta.url), 'utf8'));
  assert.equal(provenance.parameters.wildfireEnsemble, 'MME50');
  assert.equal(provenance.parameters.wildfireVariable, 'FWI');
  assert.ok(Number.isFinite(provenance.parameters.wildfireElasticity));
  assert.equal(provenance.inputSnapshot.methodology, 'fema-2024-county-area-weighted-v2');
  assert.equal(provenance.inputSnapshot.analysis, undefined);
  const files = provenance.inputSnapshot.sources.filter((item: {url: string}) => item.url.includes('/gddpimpact/FWI/'));
  assert.equal(files.length, 150);
  assert.ok(files.every((item: {url: string}) => item.url.includes('/MME/MME50_')));
});


test('October shared links retain their original P95 data', async () => {
  const { readFile } = await import('node:fs/promises');
  const { createHash } = await import('node:crypto');
  const previous = selectRelease('analysis-preview', 'fri-analysis-20261025140637');
  assert.equal(previous.id, 'fri-analysis-20261025140637');
  assert.notEqual(previous.assets['counties.pmtiles'].path, selectRelease('analysis-preview', 'fri-mme50-20261109195422-score').assets['counties.pmtiles'].path);
  const tile = await readFile(`public/${previous.assets['counties.pmtiles'].path}`);
  assert.equal(createHash('sha256').update(tile).digest('hex'), '5d49262218febbc4fe6025eaf180f48539bd75137f8d08253d4af22fa41dd6ee');
});

test('heat explanations are bound to this snapshot and match every published county multiplier', async()=>{
  const {readFile}=await import('node:fs/promises');
  const {createHash}=await import('node:crypto');
  const current=selectRelease('analysis-preview', 'fri-mme50-20261109195422-score');
  const asset=('heatCalculations' in current ? current.heatCalculations : null) as {path:string;sha256:string;snapshotSha256:string} | null;
  assert.ok(asset);
  const bytes=await readFile(`public/${asset.path}`);
  assert.equal(createHash('sha256').update(bytes).digest('hex'),asset.sha256);
  const details=JSON.parse(bytes.toString());
  assert.equal(details.snapshotSha256,asset.snapshotSha256);
  const counties=JSON.parse(await readFile(`public/${current.assets['counties.json'].path}`,'utf8'));
  const byId=new Map(counties.counties.map((c:{id:string;values:number[]})=>[c.id,c.values]));
  let comparisons=0;
  for(const [fips,values] of Object.entries(details.counties))for(const [key,row] of Object.entries(values as Record<string,{rawMultiplier:number;appliedMultiplier:number}>)){
    const actual=(byId.get(fips) as number[])[counties.columns.indexOf(`${key}_HM`)];
    assert.ok(Math.abs(actual-row.appliedMultiplier)<1e-12);
    assert.equal(row.appliedMultiplier,Math.max(1,row.rawMultiplier));
    comparisons++;
  }
  assert.equal(comparisons,24864);
  assert.ok(Math.abs(details.counties['51683'].EXHT_L95_MID_LOWER.rawMultiplier-0.5907061067256821)<1e-12);
});

test('current release manifests require verified assets, geography and their own thresholds', async () => {
  const {validatedRelease}=await import('../src/data/releases.ts');
  const asset={path:'https://example.org/pinned.json',sha256:'a'.repeat(64)};
  const hazard={annualLoss:[1,2,3,4],riskValue:[10,20,30,40]};
  const manifest={id:'verified-tracts',title:'NRI v1.20 · census tracts',date:'2026-11-11',status:'analysis',baseline:'NRI v1.20',rankingPopulation:'CONUS',geography:'tracts',sourceLayer:'tracts',countyCount:85000,assets:{'counties.json':asset,'counties.pmtiles':asset},bins:{hazards:{DRGT:hazard,WFIR:hazard,EXHT:hazard}},fieldAssets:{WFIR_EALR:asset},profileAssets:{template:'https://example.org/profiles/{prefix}.json',prefixLength:5,hashes:{'09001':'b'.repeat(64)}}};
  assert.equal(validatedRelease(manifest).geography,'tracts');
  assert.throws(()=>validatedRelease({...manifest,profileAssets:{...manifest.profileAssets,hashes:undefined}}),/profile/);
  assert.throws(()=>validatedRelease({...manifest,bins:undefined}),/bins/);
  assert.throws(()=>validatedRelease({...manifest,profileAssets:undefined}),/tract assets/);
  assert.throws(()=>validatedRelease({...manifest,fieldAssets:{WFIR_EALR:{...asset,sha256:'wrong'}}}),/field asset/);
});


test('analysis defaults to the last verified current county release and preserves explicit archive links', () => {
  const legacy=selectRelease('analysis-preview','fri-mme50-20261109195422-score');
  const first={...legacy,id:'current-county-1',baseline:'NRI v1.20',geography:'counties' as const};
  const latest={...first,id:'current-county-2'};
  const tracts={...latest,id:'current-tracts',geography:'tracts' as const};
  const available=[selectRelease('archive'),legacy,first,latest,tracts];
  assert.equal(selectRelease('analysis-preview',null,available).id,latest.id);
  assert.equal(selectRelease(undefined,null,available).status,'archive');
  assert.equal(selectRelease('archive',null,available).status,'archive');
  assert.equal(selectRelease('analysis-preview',legacy.id,available).id,legacy.id);
  assert.equal(selectRelease('analysis-preview',tracts.id,available).id,tracts.id);
  assert.equal(selectRelease('analysis-preview','unavailable',available).id,latest.id);
  assert.equal(selectRelease('analysis-preview',null,[legacy,tracts]).id,legacy.id);
  const expected=releases.filter(item=>item.baseline === 'NRI v1.20' && item.geography === 'counties').at(-1) ?? legacy;
  assert.equal(selectRelease('analysis-preview').id,expected.id);
});


test('switching to NRI v1.20 clears only retired Connecticut county selections within county geography', async () => {
  const {selectionForRelease}=await import('../src/data/releases.ts');
  const old=selectRelease('archive');
  const current={...old,baseline:'NRI v1.20',geography:'counties' as const};
  assert.equal(selectionForRelease('09001',old,current),'');
  assert.equal(selectionForRelease('09015',old,current),'');
  assert.equal(selectionForRelease('09110',old,current),'09110');
  assert.equal(selectionForRelease('01001',old,current),'01001');
  assert.equal(selectionForRelease('09001',old,old),'09001');
  assert.equal(selectionForRelease('01001',old,{...current,geography:'tracts'}),'');
});
