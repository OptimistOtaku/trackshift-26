const test=require('node:test'),assert=require('node:assert/strict');
const M=require('../demo_fallback/motion-engine'),L=require('../demo_fallback/live-strategy');
const C=require('../demo_fallback/clock-forecast');
const replay=require('../artifacts/demo/replay/R11.json'),pace=require('../artifacts/demo/clock/R11.json'),pit=require('../artifacts/demo/decision-clock/R11.json');
const settings={replay,pace,pit,time:5512.916,driver:'NOR',compound:'HARD',pitLoss:22.5,trafficLoss:0,decay:0,inventory:['HARD','MEDIUM','SOFT']};
const path=M.geometry([[0,0],[1000,0],[1000,1000],[0,1000]],400);
const row=(t,arc,speed=180)=>[t,arc*1000,0,arc,speed,5,100,0,1,.1];
test('repeated source coordinates still advance from recorded speed',()=>{
 const rows=M.reconstruct([row(10,.1),row(11,.1),row(12,.1),row(13,.1)],400);
 assert.ok(rows[3].phase>rows[0].phase+100);
 assert.ok(M.sample(rows,12.8,path).phase>M.sample(rows,12.2,path).phase);
});
test('rendered positions follow the road around corners, never the diagonal chord',()=>{
 const rows=M.reconstruct([row(10,.2),row(11,.35),row(12,.45)],400);
 for(let t=11;t<12;t+=.05){const p=M.sample(rows,t,path);assert.ok(Math.min(Math.abs(p.x),Math.abs(p.x-1000),Math.abs(p.y),Math.abs(p.y-1000))<1e-7);}
});
test('position jumps cannot create unbounded forward motion or a reverse jump',()=>{
 const rows=M.reconstruct([row(10,.1),row(11,.8),row(12,.01),row(13,.9)],4000);
 for(let i=1;i<rows.length;i++){assert.ok(rows[i].phase>=rows[i-1].phase);assert.ok(rows[i].phase-rows[i-1].phase<=110);}
});
test('motion is prefix invariant and missing telemetry expires',()=>{
 const raw=[row(10,.1),row(11,.2),row(12,.8)];
 assert.deepEqual(M.sample(M.reconstruct(raw,400),11.5,path),M.sample(M.reconstruct(raw.slice(0,2),400),11.5,path));
 assert.equal(M.sample(M.reconstruct(raw,400),16,path),null);
});
test('live plan uses current driver lap and preserves cost conservation',()=>{
 const a=L.plan(settings),b=L.plan({...settings,trafficLoss:2,decay:.1});
 assert.equal(a.status,'ready');assert.equal(a.lap,26);assert.ok(a.attacks.length>0);
 assert.ok(Math.abs(a.new_tyre_pace_s-(a.current_pace_s-a.step.step_s))<1e-8);
 assert.ok(Math.abs(a.attacks[0].margin_s-b.attacks[0].margin_s-2.3)<1e-8);
 const c=L.plan({...settings,pitLoss:24.5});assert.deepEqual(a.attacks,c.attacks);
 assert.ok(Math.abs(a.windows[0].net5-c.windows[0].net5-2)<1e-8);
});
test('live scenarios cannot consume future lap rows or model snapshots',()=>{
 const r={...replay,laps_data:replay.laps_data.filter(r=>r.completed_s<=settings.time)};
 const p={...pace,snapshots:pace.snapshots.filter(s=>s.issued_s<=settings.time),evaluation:[]};
 const t={...pit,snapshots:pit.snapshots.filter(s=>s.issued_s<=settings.time)};
 assert.deepEqual(L.plan(settings),L.plan({...settings,replay:r,pace:p,pit:t}));
 assert.equal(L.plan({...settings,inventory:[]}).status,'unsupported');
});
test('pinned clock prediction is immutable and resolves only at actual timestamp',()=>{
 const t=C.freezeClockForecast(pace,replay,'NOR',settings.time,1);
 assert.ok(Object.isFrozen(t));assert.equal(t.issued_lap,26);
 const e=pace.evaluation.find(e=>e.driver==='NOR'&&e.issued_lap===26&&e.horizon===1);
 assert.equal(C.resolveClockForecast(t,pace,replay,'NOR',e.target_s-.001).status,'pending');
 assert.equal(C.resolveClockForecast(t,pace,replay,'NOR',e.target_s).actual_s,85.532);
 assert.equal(C.resolveClockForecast(t,pace,replay,'PIA',e.target_s).status,'different_context');
});
test('adaptive chart advances at the driver timestamp, with no future observations or scoring',()=>{
 const e=pace.evaluation.find(e=>e.driver==='NOR'&&e.issued_lap===26&&e.horizon===1);
 const before=C.clockSeries(pace,replay,'NOR',e.target_s-.001);
 const after=C.clockSeries(pace,replay,'NOR',e.target_s);
 assert.equal(before.lap,26);assert.equal(after.lap,27);
 assert.equal(before.forecasts[0].target_lap,27);assert.equal(after.forecasts[0].target_lap,28);
 assert.ok(!before.observed.some(r=>r.lap===27));assert.ok(after.observed.some(r=>r.lap===27));
 assert.equal(after.score.n,before.score.n+1);
 const prefix={...replay,laps_data:replay.laps_data.filter(r=>r.completed_s<=settings.time)};
 const model={...pace,snapshots:pace.snapshots.filter(s=>s.issued_s<=settings.time),evaluation:pace.evaluation.filter(e=>e.target_s<=settings.time)};
 assert.deepEqual(C.clockSeries(pace,replay,'NOR',settings.time),C.clockSeries(model,prefix,'NOR',settings.time));
});
test('audit lock stays fixed while live forecast rolls forward; seeking cannot leak its future issue',()=>{
 const ticket=C.freezeClockForecast(pace,replay,'NOR',settings.time,1);
 const target=pace.evaluation.find(e=>e.driver==='NOR'&&e.issued_lap===26&&e.horizon===1).target_s;
 const a=C.clockSeries(pace,replay,'NOR',settings.time,ticket),b=C.clockSeries(pace,replay,'NOR',settings.time+1,ticket);
 assert.deepEqual(a.forecasts,b.forecasts);assert.ok(b.progress>a.progress);
 const later=C.clockSeries(pace,replay,'NOR',target,ticket);
 assert.equal(later.pinned.predicted_s,ticket.predicted_s);assert.equal(later.audit.status,'resolved');
 assert.notEqual(later.state.lap,ticket.issued_lap);
 assert.equal(C.clockSeries(pace,replay,'NOR',ticket.issued_s-.001,ticket).pinned,null);
 assert.equal(C.clockSeries(pace,replay,'PIA',target,ticket).pinned,null);
 assert.equal(C.clockState({...pace,round:12},replay,'NOR',target),null);
});
test('post-stop warm-up explains missing forecasts and resumes on the third representative lap',()=>{
 const at=lap=>replay.laps_data.find(r=>r.driver==='NOR'&&r.lap===lap).completed_s;
 assert.equal(C.clockSeries(pace,replay,'NOR',at(40)).readiness,'pit');
 const first=C.clockSeries(pace,replay,'NOR',at(41));
 assert.equal(first.readiness,'warming');assert.equal(first.cleanCount,1);assert.equal(first.state,null);
 const second=C.clockSeries(pace,replay,'NOR',at(42));
 assert.equal(second.readiness,'warming');assert.equal(second.cleanCount,2);
 const third=C.clockSeries(pace,replay,'NOR',at(43));
 assert.equal(third.readiness,'ready');assert.equal(third.cleanCount,3);assert.equal(third.forecasts[0].target_lap,44);
});
test('live accuracy trace pairs the issued prediction with its own target and hides the pending actual',()=>{
 const e=pace.evaluation.find(e=>e.driver==='NOR'&&e.issued_lap===26&&e.horizon===1);
 const before=C.clockComparison(C.clockSeries(pace,replay,'NOR',e.target_s-.001));
 assert.equal(before.pending.target_lap,27);assert.equal(before.pending.pace_s,e.predicted_s);
 assert.ok(!before.rows.some(r=>r.target_lap===27));
 const after=C.clockComparison(C.clockSeries(pace,replay,'NOR',e.target_s));
 assert.equal(after.latest.target_lap,27);assert.equal(after.latest.predicted_s,e.predicted_s);assert.equal(after.latest.actual_s,e.actual_s);
 assert.equal(after.pending.target_lap,28);
 const ticket=C.freezeClockForecast(pace,replay,'NOR',settings.time,1);
 assert.deepEqual(after,C.clockComparison(C.clockSeries(pace,replay,'NOR',e.target_s,ticket)));
});
