import assert from 'node:assert/strict';
import { test } from 'node:test';
import { decodeIndex, decodeField, decodeProfile, verifyJson } from '../src/clients/data-assets.ts';
const row = {id:'09001010100',name:'Census Tract 101',state:'CT',bounds:[-73,41,-72,42],values:[]};
test('sharded data preserves identifier order and rejects incomplete columns', () => {
  const index=decodeIndex({columns:[],counties:[row]},1);
  assert.deepEqual(index[0].values,{});
  assert.deepEqual(decodeField(['Very Low'],index.length),['Very Low']);
  assert.throws(()=>decodeField([],index.length),/length/);
  assert.throws(()=>decodeField([{}],index.length),/value/);
  assert.throws(()=>decodeIndex({columns:['WFIR_EALT'],counties:[row]},1),/values/);
  const profile=decodeProfile({columns:['WFIR_EALT'],counties:[{...row,values:[100]}]},row.id);
  assert.equal(profile.values.WFIR_EALT,100);
  assert.throws(()=>decodeProfile({columns:[],counties:[row]},'09001010200'),/selected/);
});
test('remote assets are checked against their pinned digest before decoding', async () => {
  const bytes=new TextEncoder().encode('[1]').buffer;
  assert.deepEqual(await verifyJson(bytes,'080a9ed428559ef602668b4c00f114f1a11c3f6b02a435f0bdc154578e4d7f22'),[1]);
  await assert.rejects(verifyJson(bytes,'0'.repeat(64)),/hash/);
});

test('index and profile identifiers match the selected release geography', () => {
  assert.equal(decodeIndex({columns:[],counties:[row]},1,'tracts')[0].id,row.id);
  assert.throws(()=>decodeIndex({columns:[],counties:[row]},1,'counties'),/geography/);
  assert.throws(()=>decodeIndex({columns:[],counties:[{...row,id:'09001'}]},1,'tracts'),/geography/);
  assert.throws(()=>decodeProfile({columns:[],counties:[row]},row.id,'counties'),/geography/);
});

test('a profile fetch requires a valid pinned digest for its selected prefix', async () => {
  const {profileAsset}=await import('../src/clients/data-assets.ts');
  const config={template:'https://example.org/profiles/{prefix}.json',prefixLength:5};
  assert.throws(()=>profileAsset(config,'09001'),/verified profile/);
  assert.throws(()=>profileAsset({...config,hashes:{'09001':'bad'}},'09001'),/verified profile/);
  assert.throws(()=>profileAsset({...config,hashes:{'09003':'a'.repeat(64)}},'09001'),/verified profile/);
  assert.deepEqual(profileAsset({...config,hashes:{'09001':'a'.repeat(64)}},'09001'),{path:'https://example.org/profiles/09001.json',sha256:'a'.repeat(64)});
});

test('profile heat diagnostics propagate only when the ratio, floor and published multiplier agree', () => {
  const key='EXHT_L95_MID_LOWER';
  const heat={historicalDaysPerYear:10,futureDaysPerYear:5,rawMultiplier:0.5,appliedMultiplier:1};
  const payload=(details:unknown,hm=1)=>({columns:[`${key}_HM`],counties:[{...row,values:[hm],heatCalculations:{[key]:details}}]});
  const profile=decodeProfile(payload(heat),row.id,'tracts');
  assert.deepEqual(profile.heatCalculations?.[key],heat);
  assert.throws(()=>decodeProfile(payload({...heat,appliedMultiplier:0.5}),row.id,'tracts'),/heat/);
  assert.throws(()=>decodeProfile(payload({...heat,rawMultiplier:0.8}),row.id,'tracts'),/heat/);
  assert.throws(()=>decodeProfile(payload({...heat,historicalDaysPerYear:0}),row.id,'tracts'),/heat/);
  assert.throws(()=>decodeProfile(payload({...heat,futureDaysPerYear:-1}),row.id,'tracts'),/heat/);
  assert.throws(()=>decodeProfile(payload(heat,2),row.id,'tracts'),/heat/);
});
