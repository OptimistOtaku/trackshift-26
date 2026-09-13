const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {recoveryState}=require('../demo_fallback/recovery.js');
const payload={round:1,snapshots:[{driver:'AAA',lap:4,issued_s:400}],stops:[{driver:'AAA',lap:4,issued_s:400,label_s:900}]};
const replay={round:1,laps_data:[{driver:'AAA',lap:4,completed_s:400,track_status:'1'}]};
test('stop outcomes remain hidden until every outcome source resolves',()=>{
  assert.equal(recoveryState(payload,replay,'AAA',899).resolved.length,0);
  assert.equal(recoveryState(payload,replay,'AAA',900).resolved.length,1);
});
test('future, stale, pit and wrong-event signals abstain',()=>{
  assert.equal(recoveryState(payload,replay,'AAA',399).snapshot,null);
  assert.equal(recoveryState(payload,replay,'AAA',581).snapshot,null);
  assert.equal(recoveryState(payload,{...replay,round:2},'AAA',450).snapshot,null);
  assert.equal(recoveryState(payload,null,'AAA',900).resolved.length,0);
  assert.equal(recoveryState(payload,{...replay,laps_data:[{...replay.laps_data[0],in_lap:true}]},'AAA',450).snapshot,null);
});
test('all archived stop outcomes resolve strictly after their issue',()=>{
  for(let round=1;round<=12;round++){
    const data=JSON.parse(fs.readFileSync(`artifacts/demo/recovery/R${String(round).padStart(2,'0')}.json`));
    for(const stop of data.stops)assert.ok(stop.label_s>stop.issued_s);
  }
});
