import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { test } from 'node:test';

test('every selectable county has a concise description with revision-pinned attribution', () => {
  const inventory=JSON.parse(readFileSync('public/atlas/counties.json','utf8')).counties;
  const context=JSON.parse(readFileSync('public/context/counties.json','utf8'));
  assert.equal(context.schemaVersion,1);
  assert.equal(context.license.url,'https://creativecommons.org/licenses/by-sa/4.0/');
  assert.deepEqual(Object.keys(context.counties).sort(),inventory.map((c:{id:string})=>c.id).sort());
  for(const county of inventory) {
    const entry=context.counties[county.id];
    assert.ok(Number.isInteger(entry.population.value) && entry.population.value > 0,county.id);
    assert.ok(entry.population.year >= 2020,county.id);
    assert.ok(entry.economy,county.id);
    if(entry.economy.measure === 'earningsByPlaceOfWork') {
      assert.ok(entry.economy.sectors.length > 0,county.id);
      assert.ok(entry.economy.sectors.every((sector:{thousandDollars:number})=>sector.thousandDollars > 0),county.id);
      assert.equal(new Set(entry.economy.sectors.map((sector:{lineCode:string})=>sector.lineCode)).size,entry.economy.sectors.length);
    }
    assert.ok(entry.description.length >= 80 && entry.description.length <= 800,county.id);
    assert.doesNotMatch(entry.description,/\{\{|\}\}|<ref|\[\[|\bundefined\b|\(\s*\)/,county.id);
    assert.doesNotMatch(entry.description,/\b(?:available source|provided county profile|profile (?:describes|reports|places)|source offers little|source provides little|description stays)\b/i,county.id);
    assert.ok(entry.sources.length > 0,county.id);
    for(const source of entry.sources) {
      const url=new URL(source.url);
      assert.equal(url.protocol,'https:',county.id);
      if(url.hostname === 'en.wikipedia.org') {
        assert.match(url.searchParams.get('oldid') ?? '',/^\d+$/,county.id);
        assert.equal(Number(url.searchParams.get('oldid')),source.revisionId,county.id);
      }
      assert.ok(source.title.length > 0,county.id);
    }
  }
});

test('researched county context uses source-matched baseline comparisons rather than future-scenario claims', () => {
  const bytes=readFileSync('public/atlas/counties.json');
  const baseline=JSON.parse(bytes.toString());
  const context=JSON.parse(readFileSync('public/context/counties.json','utf8'));
  assert.equal(context.authoringMethod,'researched-risk-context');
  assert.equal(context.researchBaseline.baselineSha256,createHash('sha256').update(bytes).digest('hex'));
  for(const county of baseline.counties) {
    const entry=context.counties[county.id];
    const values=Object.fromEntries(baseline.columns.map((name:string,i:number)=>[name,county.values[i]]));
    assert.ok(Array.isArray(entry.researchComparisons),county.id);
    for(const comparison of entry.researchComparisons) {
      if(comparison.kind === 'riskPercentile') {
        assert.equal(comparison.value,values[`${comparison.hazard}_RISKS`],county.id);
        assert.notEqual(values[`${comparison.hazard}_RISKR`],'No Rating',county.id);
        const n=comparison.value;
        const valid:Record<string,boolean>={top10:n>=90,top25:n>=75,aboveMedian:n>=50,belowMedian:n<50,bottom25:n<=25,bottom10:n<=10};
        assert.ok(valid[comparison.relation],`${county.id}: unsupported percentile claim`);
      }
      if(comparison.kind !== 'populationPercentile' && entry.languageStyle !== 'plain-place-context') assert.match(entry.description,/baseline/i,county.id);
    }
    assert.doesNotMatch(entry.description,/^Census estimated about/,county.id);
    assert.equal(entry.riskContext,undefined,'Researched paragraphs must not acquire an unrelated third sentence');
  }
});

test('all nine Connecticut planning regions have sourced native-v1.20 context', () => {
  const context=JSON.parse(readFileSync('public/context/planning-regions.json','utf8'));
  const research=JSON.parse(readFileSync('scripts/planning-region-context-research.json','utf8'));
  const expected=Array.from({length:9},(_,i)=>`091${i+1}0`);
  assert.deepEqual(Object.keys(context.counties).sort(),expected);
  assert.equal(context.researchBaseline.baseline,'NRI v1.20');
  for(const id of expected) {
    const entry=context.counties[id], evidence=research.regions[id];
    assert.equal(entry.baseline,'NRI v1.20');
    assert.ok(entry.description.length>=120 && entry.description.length<=700,id);
    if(entry.languageStyle !== 'plain-place-context') assert.match(entry.description,/baseline/i,id);
    assert.doesNotMatch(entry.description,/v1\.19|archived/i,id);
    assert.ok(entry.population.value>0 && entry.population.year===2025,id);
    assert.equal(entry.population.value,evidence.population.value,id);
    assert.ok(entry.sources.some((s:{url:string})=>s.url===entry.population.sourceUrl),id);
    assert.ok(entry.sources.some((s:{url:string})=>s.url===evidence.economy.sourceUrl),id);
    for(const comparison of entry.researchComparisons) {
      assert.equal(comparison.value,evidence.baselineRiskScores[comparison.hazard],id);
      assert.ok(Number.isFinite(comparison.value),id);
      const n=comparison.value;
      const valid:Record<string,boolean>={top10:n>=90,top25:n>=75,aboveMedian:n>=50,belowMedian:n<50,bottom25:n<=25,bottom10:n<=10};
      assert.ok(valid[comparison.relation],id);
    }
    assert.ok(entry.researchComparisons.length>0,id);
  }
});

test('tract context resolves the containing county equivalent, including Connecticut planning regions', async () => {
  const { countyContextId } = await import('../src/lib/county-context');
  assert.equal(countyContextId('09110535200'),'09110');
  assert.equal(countyContextId('51683910100'),'51683');
  assert.equal(countyContextId('19153000100'),'19153');
  assert.equal(countyContextId('09110'),'09110');
  assert.equal(countyContextId('09001'),'09001');
  for(const id of ['', '0911', '0911053520', '091105352001', '09110invalid']) assert.equal(countyContextId(id),null);
});


test('plain county and region descriptions avoid academic ranking jargon', () => {
  for(const filename of ['counties.json','planning-regions.json']) {
    const context=JSON.parse(readFileSync(`public/context/${filename}`,'utf8'));
    if(context.languageStyle!=='plain-place-context') continue;
    for(const [id,entry] of Object.entries(context.counties) as [string,{description:string;languageStyle:string}][]) {
      assert.equal(entry.languageStyle,'plain-place-context',id);
      assert.ok(entry.description.length>=80 && entry.description.length<=500,id);
      assert.doesNotMatch(entry.description,/percentile|earnings base|aggregate exposure|national (?:upper|lower) quarter|frames? (?:its |their )?exposure|FEMA[’']s baseline/i,id);
    }
  }
});
