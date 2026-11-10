import assert from 'node:assert/strict';
import { test } from 'node:test';
import { countyCalculation, ratingIntervals, nriCountyUrl, binIndex } from '../src/lib/calculations.ts';
import { readState, changeLabel } from '../src/lib/risk.ts';

const view = readState('?hazard=EXHT&model=L95&period=mid&emissions=lower');
const values = {EXHT_EALT:192187.6093,EXHT_RISKV:250992.4977,EXHT_RISKS:67.61056316,EXHT_L95_MID_LOWER_HM:1,EXHT_L95_MID_LOWER_PRISKS:64.05};
test('county details separate dollar loss, risk value, percentile score and multiplier', () => {
  assert.deepEqual(countyCalculation(values,view), {baselineLoss:192187.6093,annualLoss:192187.6093,baselineRiskValue:250992.4977,riskValue:250992.4977,riskScore:64.05,multiplier:1,derivedLoss:true});
  assert.equal(countyCalculation({...values,EXHT_L95_MID_LOWER_PALT:0},view).annualLoss,0);
  assert.equal(countyCalculation({},view).annualLoss,null);
  assert.equal(countyCalculation(values,{...view,period:'base'}).riskScore,67.61056316);
});
test('exact category edges are inclusive on the upper side and do not use percentile bins', () => {
  const intervals=ratingIntervals('EXHT','loss');
  assert.equal(intervals[1].upper,241379.1141);
  assert.equal(binIndex(241379.1141,intervals),1);
  assert.equal(binIndex(241379.11410001,intervals),2);
  assert.equal(binIndex(295603.5917,intervals),2);
  assert.equal(ratingIntervals('EXHT','risk')[1].upper,306824.0993);
  assert.equal(binIndex(250992.4977,ratingIntervals('EXHT','risk')),1);
  assert.equal(binIndex(1,ratingIntervals('EXHT','multiplier')),0);
  assert.equal(binIndex(1.5,ratingIntervals('EXHT','multiplier')),1);
});
test('NRI county links retain leading zeros and independent-city FIPS', () => {
  assert.ok(decodeURIComponent(new URL(nriCountyUrl('51683')).hash).includes("NRI_ID='C51683'"));
  assert.equal(new URL(nriCountyUrl('51683')).hostname,'experience.arcgis.com');
  assert.ok(decodeURIComponent(new URL(nriCountyUrl('01001')).hash).includes("NRI_ID='C01001'"));
  assert.throws(()=>nriCountyUrl('bad'),/FIPS/);
});


test('a published 1x does not claim an absence of warming',()=>{
  assert.equal(changeLabel(1),'No increase applied');
});
