const test=require('node:test'),assert=require('node:assert/strict');
const S=require('../demo_fallback/strategy-engine');
const replay=require('../artifacts/demo/replay/R11.json'),intel=require('../artifacts/demo/intelligence/R11.json');
const settings={replay,intel,lap:25,driver:'NOR',compound:'HARD',pitLoss:22.5,trafficLoss:0,decay:0,inventory:['HARD','MEDIUM','SOFT']};
const row=(t,x=0,y=0)=>[t,x,y,.2,180,4,90,0,1,.1];
test('position interpolation uses only received samples and expires stale data',()=>{
  const rows=[row(10,100),row(11,200),row(12,99999)];
  assert.equal(S.sampleAt(rows,11.5).x,150);
  assert.deepEqual(S.sampleAt(rows.slice(0,2),11.5),S.sampleAt(rows,11.5));
  assert.equal(S.sampleAt(rows,9),null);assert.equal(S.sampleAt(rows,15),null);
});
test('duplicate source positions cannot become a zero-second gap',()=>{
  const a={x:100,y:100,ontrack:true,arc:.1,speed:180};
  assert.equal(S.trafficAt({A:a,B:{...a}},'A',5000).ambiguous,true);
  const g=S.trafficAt({A:a,B:{...a,x:300,arc:.11}},'A',5000);
  assert.ok(Math.abs(g.gap_s-1)<1e-10);
  assert.equal(S.trafficAt({A:{...a,ontrack:false},B:a},'A',5000),null);
});
test('pit cost inference never consumes later laps',()=>{
  const truncated={...replay,laps_data:replay.laps_data.filter(r=>r.lap<=25)};
  assert.deepEqual(S.pitLossAt(replay,25),S.pitLossAt(truncated,25));
  assert.ok(S.pitLossAt(replay,25).n>=3);
});
test('one pit loss is paid for immediate rejoin and cancels after both stop',()=>{
  const a=S.plan(settings),b=S.plan({...settings,pitLoss:settings.pitLoss+2});
  assert.equal(a.status,'ready');
  assert.ok(Math.abs(a.windows[0].net5-b.windows[0].net5-2)<1e-10);
  assert.deepEqual(a.attacks,b.attacks);
  assert.ok(b.recovery_laps>a.recovery_laps);
});
test('traffic and decay reduce the scenario by exactly their explicit costs',()=>{
  const a=S.plan(settings),b=S.plan({...settings,trafficLoss:2,decay:.1});
  assert.ok(Math.abs(a.windows[0].net5-b.windows[0].net5-3)<1e-10);
  assert.ok(Math.abs(a.attacks[0].margin_s-b.attacks[0].margin_s-2.3)<1e-10);
});
test('inventory, pit and unsupported states abstain',()=>{
  assert.equal(S.plan({...settings,inventory:['SOFT']}).status,'unsupported');
  assert.equal(S.plan({...settings,lap:17}).status,'unsupported');
  assert.equal(S.plan({...settings,pitLoss:NaN}).status,'invalid');
});
test('future rows and evaluation labels cannot change a plan',()=>{
  const r={...replay,laps_data:replay.laps_data.filter(r=>r.lap<=25)};
  const i={...intel,snapshots:intel.snapshots.filter(s=>s.lap<=25),evaluation:[]};
  assert.deepEqual(S.plan(settings),S.plan({...settings,replay:r,intel:i}));
});
test('future rejoin projections disclose persistence fallback instead of dropping cars',()=>{
  const p=S.plan(settings);
  assert.equal(p.windows[0].covered,p.windows[1].covered);
  assert.ok(p.windows[1].baselines>0);
  assert.ok(p.attacks[0].radius_s>Math.abs(p.attacks[0].margin_s));
});
