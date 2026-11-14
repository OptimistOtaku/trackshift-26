const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {freezeForecast,resolveForecast,scoreAtCursor}=require('../demo_fallback/evidence.js');
const {attackBudget}=require('../demo_fallback/battle.js');
const root=path.resolve(__dirname,'..');
const race=JSON.parse(fs.readFileSync(path.join(root,'artifacts/demo/intelligence/R11.json'),'utf8'));
const snapshot=race.snapshots.find(s=>s.driver==='NOR'&&s.lap===25);
const ticket=freezeForecast(11,snapshot,3,84.973);
const context={round:11,driver:'NOR',lap:25,evaluation:race.evaluation};
test('locked receipt contains no outcome and cannot be changed by new forecasts',()=>{
  assert.equal(Object.isFrozen(ticket),true);assert.equal('actual_s' in ticket,false);
  const edited=structuredClone(snapshot);const locked=freezeForecast(11,edited,3,84.973);
  edited.forecasts[1].pace_s=900;assert.equal(locked.predicted_s,ticket.predicted_s);
});
test('future poisoned outcomes cannot change the pending receipt',()=>{
  const before=resolveForecast(ticket,context);
  const poisoned=race.evaluation.map(e=>({...e,actual_s:-999999}));
  assert.deepEqual(resolveForecast(ticket,{...context,evaluation:poisoned}),before);
  assert.equal(before.status,'pending');assert.equal('actual_s' in before,false);
});
test('exact target boundary reveals the observed result and both errors',()=>{
  assert.equal(resolveForecast(ticket,{...context,lap:27}).status,'pending');
  const resolved=resolveForecast(ticket,{...context,lap:28});assert.equal(resolved.status,'resolved');
  assert.equal(resolved.actual_s,85.071);assert.ok(Math.abs(resolved.error_s-.004668)<1e-7);
  assert.ok(Math.abs(resolved.baseline_error_s-.098)<1e-7);
});
test('other drivers, rounds and pre-issue cursors cannot reveal a ticket',()=>{
  assert.equal(resolveForecast(ticket,{...context,driver:'VER',lap:40}).status,'different_context');
  assert.equal(resolveForecast(ticket,{...context,round:12,lap:40}).status,'different_context');
  assert.equal(resolveForecast(ticket,{...context,lap:24}).status,'before_issue');
});
test('an interrupted or unscored target is never filled with an invented outcome',()=>{
  assert.equal(resolveForecast(ticket,{...context,lap:28,evaluation:[]}).status,'interrupted');
  assert.equal(freezeForecast(11,null,3,80),null);assert.equal(freezeForecast(11,snapshot,10,80),null);
});
test('as-of scoreboard excludes future and other-driver observations',()=>{
  const earlier=scoreAtCursor(race.evaluation,25,'NOR');
  const withFuture=[...race.evaluation,{target_lap:99,horizon:1,driver:'NOR',predicted_s:0,actual_s:999,baseline_s:9}];
  assert.deepEqual(scoreAtCursor(withFuture,25,'NOR'),earlier);
  assert.equal(earlier.n,race.evaluation.filter(e=>e.driver==='NOR'&&e.horizon===1&&e.target_lap<=25).length);
});
test('jury traffic experiment subtracts exactly two seconds from the entire margin range',()=>{
  const step=snapshot.stop_scenarios.HARD,battle=snapshot.battles.find(b=>b.horizon===3);
  const costs={gap:1.5,warmup:.7,service:0,traffic:0,decay:0};
  const clear=attackBudget(step,battle,costs),traffic=attackBudget(step,battle,{...costs,traffic:2});
  assert.ok(clear.margin_s>0&&traffic.margin_s<0);
  for(const key of ['margin_s','lower_margin_s','upper_margin_s'])assert.ok(Math.abs(clear[key]-traffic[key]-2)<1e-9);
  assert.ok(clear.lower_margin_s<0&&clear.upper_margin_s>0);
});
