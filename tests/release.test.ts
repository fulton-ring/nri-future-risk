import assert from 'node:assert/strict';
import { test } from 'node:test';
import { selectRelease } from '../src/data/releases.ts';

test('analysis data is opt-in and shared links use its own identity', () => {
  assert.equal(selectRelease(undefined).id, 'fema-2024-12-05');
  assert.equal(selectRelease('archive').status, 'archive');
  const preview = selectRelease('analysis-preview');
  assert.equal(preview.status, 'analysis');
  assert.equal(preview.id, 'fri-analysis-20261025140637');
  assert.notEqual(preview.assets['counties.pmtiles'].path, selectRelease('archive').assets['counties.pmtiles'].path);
  assert.throws(() => selectRelease('unknown'), /Unknown data release/);
});

test('the preview tile contains the new scores and fits Pages', async () => {
  const { readFile } = await import('node:fs/promises');
  const { createHash } = await import('node:crypto');
  const { PMTiles } = await import('pmtiles');
  const { VectorTile } = await import('@mapbox/vector-tile');
  const { PbfReader } = await import('pbf');
  const release = selectRelease('analysis-preview');
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
  assert.equal(selectRelease('archive', 'fri-analysis-20261025140637').status, 'analysis');
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
