import assert from 'node:assert/strict';
import { test } from 'node:test';
import { selectRelease, releases } from '../src/data/releases.ts';

const archive = selectRelease('archive');
const analysis = (id: string, geography: 'counties' | 'tracts' = 'counties') =>
  ({...archive, id, status: 'analysis', baseline: 'NRI v1.20', geography});

test('analysis data is opt-in and shared links use its own identity', () => {
  assert.equal(selectRelease(undefined).id, 'fema-2024-12-05');
  assert.equal(archive.status, 'archive');
  const county = analysis('current-county-1');
  assert.equal(selectRelease('archive', county.id, [archive, county]).id, county.id);
  assert.throws(() => selectRelease('unknown'), /Unknown data release/);
});

test('a selected version in a shared URL overrides the deployment default', () => {
  const county = analysis('current-county-1');
  const available = [archive, county];
  assert.equal(selectRelease('analysis-preview', archive.id, available).status, 'archive');
  assert.equal(selectRelease('archive', county.id, available).status, 'analysis');
  assert.equal(selectRelease('archive', 'unavailable-version', available).status, 'archive');
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

test('analysis defaults to the last current county release and preserves explicit archive links', () => {
  const first = analysis('current-county-1');
  const latest = analysis('current-county-2');
  const tracts = analysis('current-tracts', 'tracts');
  const available = [archive, first, latest, tracts];
  assert.equal(selectRelease('analysis-preview', null, available).id, latest.id);
  assert.equal(selectRelease(undefined, null, available).status, 'archive');
  assert.equal(selectRelease('archive', null, available).status, 'archive');
  assert.equal(selectRelease('analysis-preview', first.id, available).id, first.id);
  assert.equal(selectRelease('analysis-preview', tracts.id, available).id, tracts.id);
  assert.equal(selectRelease('analysis-preview', 'unavailable', available).id, latest.id);
  // Without a recomputed county release, the analysis deployment shows the archive.
  assert.equal(selectRelease('analysis-preview', null, [archive, tracts]).id, archive.id);
  const expected = releases.filter(item => item.status === 'analysis' && item.geography === 'counties').at(-1) ?? archive;
  assert.equal(selectRelease('analysis-preview').id, expected.id);
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
