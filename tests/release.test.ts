import assert from 'node:assert/strict';
import { test } from 'node:test';
import { releases, selectRelease } from '../src/data/releases.ts';

test('the UI release selector exposes only the FEMA archive', () => {
  assert.deepEqual(releases.map(release => release.id), ['fema-2024-12-05']);
  assert.equal(selectRelease().status, 'archive');
  assert.equal(selectRelease('archive', 'fema-2024-12-05').status, 'archive');
  assert.equal(selectRelease('archive', 'fri-analysis-20261025140637').status, 'archive');
  assert.throws(() => selectRelease('analysis-preview'), /Unknown data release/);
});

test('archive controls retain all five hazards and all heat models', async () => {
  const { releaseHazards, releaseModels, readState } = await import('../src/lib/risk.ts');
  assert.deepEqual(releaseHazards(), ['WFIR', 'DRGT', 'EXHT', 'CFLD', 'HRCN']);
  assert.deepEqual(releaseModels(), ['L95', 'L99', 'N95', 'N99']);
  assert.equal(readState('?hazard=HRCN&model=N99').hazard, 'HRCN');
  assert.equal(readState('?hazard=EXHT&model=N99').model, 'N99');
});

test('version pages build without pipeline inputs and local links resolve', async () => {
  const { execFileSync } = await import('node:child_process');
  const { readFile, access } = await import('node:fs/promises');
  const { resolve, dirname } = await import('node:path');
  execFileSync(process.execPath, ['scripts/build_version_pages.mjs']);
  for (const page of ['methodology', 'data']) {
    const file = resolve(`public/versions/fema-2024-12-05/${page}.html`);
    const html = await readFile(file, 'utf8');
    assert.ok(html.includes('<code>fema-2024-12-05</code>'));
    assert.ok(!html.includes('preview/'));
    for (const match of html.matchAll(/href="([^"]+)"/g)) {
      if (match[1].startsWith('https:')) continue;
      await access(resolve(dirname(file), match[1].split('?')[0]));
    }
  }
});
