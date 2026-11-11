import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
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
    assert.ok(entry.description.includes(String(entry.population.year)),county.id);
    assert.ok(entry.economy,county.id);
    if(entry.economy.measure === 'earningsByPlaceOfWork') {
      assert.ok(entry.economy.sectors.length > 0,county.id);
      assert.ok(entry.economy.sectors.every((sector:{thousandDollars:number})=>sector.thousandDollars > 0),county.id);
      assert.equal(new Set(entry.economy.sectors.map((sector:{lineCode:string})=>sector.lineCode)).size,entry.economy.sectors.length);
      assert.doesNotMatch(entry.description,/largest|leading|most (?:jobs|workers)/i,county.id);
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
