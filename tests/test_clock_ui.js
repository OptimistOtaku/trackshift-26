const test=require('node:test'),assert=require('node:assert/strict');
const {clockState,clockScore}=require('../demo_fallback/clock-forecast');
const replay=require('../artifacts/demo/replay/R11.json'),payload=require('../artifacts/demo/clock/R11.json');
test('clock predictor picks the driver latest completed lap, not the field cursor',()=>{
  const s=clockState(payload,replay,'NOR',5512.916);
  assert.equal(s.lap,26);assert.equal(s.forecasts[0].target_lap,27);
  assert.ok(s.issued_s<=5512.916);
});
test('a later snapshot cannot enter a previous clock tick',()=>{
  const current=clockState(payload,replay,'NOR',5512.916);
  const future=structuredClone(payload);
  future.snapshots.filter(s=>s.issued_s>5512.916).forEach(s=>s.forecasts[0].pace_s=-999);
  assert.deepEqual(clockState(future,replay,'NOR',5512.916),current);
});
test('an outcome reveals exactly at its target timestamp',()=>{
  const e=payload.evaluation.find(e=>e.driver==='NOR'&&e.issued_lap===26&&e.horizon===1);
  const only={...payload,evaluation:[e]};
  assert.equal(clockScore(only,'NOR',e.target_s-.001).n,0);
  assert.equal(clockScore(only,'NOR',e.target_s).latest.actual_s,85.532);
  assert.equal(clockScore(only,'PIA',e.target_s).n,0);
});
test('pit observations and stale observations suspend the clock model',()=>{
  const pit=replay.laps_data.find(r=>r.driver==='NOR'&&r.in_lap);
  assert.equal(clockState(payload,replay,'NOR',pit.completed_s),null);
  const end=Math.max(...replay.laps_data.filter(r=>r.driver==='NOR').map(r=>r.completed_s));
  assert.equal(clockState(payload,replay,'NOR',end+181),null);
});
