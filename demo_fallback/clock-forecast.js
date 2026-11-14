/* Timestamped predictions and outcomes are resolved against the position clock. */
let RCLOCK=null,CLOCKREPORT=null,RPITCLOCK=null,CLOCKDECISIONREPORT=null,livePlan=null,clockPaintKey='';
function clockState(payload,replay,driver,time){
  if(!payload||!replay||payload.round!==replay.round||!Number.isFinite(time))return null;
  const row=replay.laps_data.filter(r=>r.driver===driver&&Number.isFinite(r.completed_s)&&r.completed_s<=time).sort((a,b)=>b.completed_s-a.completed_s)[0];
  if(!row||row.track_status!=='1'||row.in_lap||row.out_lap||time-row.completed_s>180)return null;
  return payload.snapshots.find(s=>s.driver===driver&&s.lap===row.lap&&s.issued_s<=time)||null;
}
function clockScore(payload,driver,time){
  const done=(payload?.evaluation||[]).filter(e=>e.driver===driver&&e.horizon===1&&e.target_s<=time&&e.issued_s<e.target_s);
  return {n:done.length,latest:done.sort((a,b)=>b.target_s-a.target_s)[0]||null,
    rmse:done.length?Math.sqrt(done.reduce((v,e)=>v+(e.predicted_s-e.actual_s)**2,0)/done.length):null,
    baseline_rmse:done.length?Math.sqrt(done.reduce((v,e)=>v+(e.baseline_s-e.actual_s)**2,0)/done.length):null,rows:done};
}
function freezeClockForecast(payload,replay,driver,time,horizon){
  const state=clockState(payload,replay,driver,time),f=state?.forecasts.find(f=>f.horizon===horizon);
  const row=replay.laps_data.find(r=>r.driver===driver&&r.lap===state?.lap);
  if(!f||!Number.isFinite(row?.lap_time_s))return null;
  return Object.freeze({round:payload.round,driver,issued_lap:state.lap,issued_s:state.issued_s,horizon,
    target_lap:f.target_lap,predicted_s:f.pace_s,lower_s:f.lower_s,upper_s:f.upper_s,baseline_s:row.lap_time_s});
}
function resolveClockForecast(ticket,payload,replay,driver,time){
  if(!ticket)return {status:'empty'};
  if(ticket.round!==payload?.round||ticket.driver!==driver)return {status:'different_context'};
  if(time<ticket.issued_s)return {status:'before_issue'};
  const target=replay.laps_data.find(r=>r.driver===driver&&r.lap===ticket.target_lap&&Number.isFinite(r.completed_s)&&r.completed_s<=time);
  if(!target)return {status:'pending'};
  const result=payload.evaluation.find(e=>e.driver===driver&&e.issued_lap===ticket.issued_lap&&e.target_lap===ticket.target_lap&&e.horizon===ticket.horizon&&e.target_s<=time);
  if(!result)return {status:'interrupted'};
  return {status:'resolved',actual_s:result.actual_s,error_s:Math.abs(ticket.predicted_s-result.actual_s),baseline_error_s:Math.abs(ticket.baseline_s-result.actual_s)};
}
// Chart data obeys the same receipt clock as strategy. Never inspect future laps
// to animate progress: elapsed time is measured against the issued prediction.
function clockSeries(payload,replay,driver,time,ticket=null){
  const context=payload&&replay&&payload.round===replay.round&&Number.isFinite(time);
  const received=context?replay.laps_data.filter(r=>r.driver===driver&&Number.isFinite(r.completed_s)&&r.completed_s<=time).sort((a,b)=>a.completed_s-b.completed_s):[];
  const current=received.at(-1)||null,state=context?clockState(payload,replay,driver,time):null;
  const lap=current?.lap||0,minLap=Math.max(1,lap-11);
  const observed=received.filter(r=>r.lap>=minLap&&Number.isFinite(r.lap_time_s)&&r.track_status==='1'&&!r.in_lap&&!r.out_lap&&r.lap>1);
  const score=clockScore(context?payload:null,driver,time);
  const issued=(context?payload.snapshots:[]).filter(s=>s.driver===driver&&s.issued_s<=time&&s.lap>=minLap-1).flatMap(s=>s.forecasts.filter(f=>f.horizon===1&&f.target_lap<=lap).map(f=>({...f,issued_s:s.issued_s})));
  const forecasts=state?.forecasts||[],next=forecasts.find(f=>f.horizon===1);
  const pinned=ticket&&context&&ticket.round===payload.round&&ticket.driver===driver&&ticket.issued_s<=time?ticket:null;
  let cleanCount=0,previous=null;
  for(const row of received){
    if(row.track_status!=='1'||previous&&(row.out_lap||previous.in_lap||row.compound!==previous.compound||Number.isFinite(row.tyre_age)&&Number.isFinite(previous.tyre_age)&&row.tyre_age<previous.tyre_age))cleanCount=0;
    if(row.track_status==='1'&&!row.in_lap&&!row.out_lap&&['SOFT','MEDIUM','HARD'].includes(row.compound)&&Number.isFinite(row.tyre_age)&&row.tyre_age>=1&&Number.isFinite(row.lap_time_s)&&row.lap_time_s>0&&row.lap>1)cleanCount=Math.min(12,cleanCount+1);
    previous=row;
  }
  const readiness=!current?'no_timing':lap>=replay.laps?'finished':time-current.completed_s>180?'stale':current.in_lap||current.out_lap?'pit':current.track_status!=='1'?'neutralised':state?'ready':cleanCount<3?'warming':'unavailable';
  return {lap,current,state,observed,issued,forecasts,score,pinned,readiness,cleanCount,
    audit:resolveClockForecast(pinned,payload,replay,driver,time),
    elapsed_s:next?Math.max(0,time-state.issued_s):null,
    progress:next?Math.min(1,Math.max(0,(time-state.issued_s)/next.pace_s)):0,
    minLap,maxLap:Math.max(lap+5,...forecasts.map(f=>f.target_lap),minLap+1)};
}
function clockComparison(data){
  const minLap=Math.max(1,data.lap-10),maxLap=Math.max(3,data.lap+2);
  const rows=data.score.rows.filter(r=>r.target_lap>=minLap).slice().sort((a,b)=>a.target_lap-b.target_lap);
  return {minLap,maxLap,rows,latest:rows.at(-1)||null,pending:data.forecasts.find(f=>f.horizon===1)||null};
}
if(typeof module!=='undefined')module.exports={clockState,clockScore,freezeClockForecast,resolveClockForecast,clockSeries,clockComparison};
async function initClockForecast(){
  initAdaptiveForecast();
  initRecovery();
  try{CLOCKREPORT=await getJSON('clock/report.json');}catch(e){CLOCKREPORT=null;}
  try{CLOCKDECISIONREPORT=await getJSON('decision-clock/report.json');}catch(e){CLOCKDECISIONREPORT=null;}
}
function drawClockForecast(){
  drawRecovery();
  if(!RREPLAY)return;
  const driver=$('#i-driver').value,state=clockState(RCLOCK,RREPLAY,driver,raceClock);
  const next=state?.forecasts.find(f=>f.horizon===1),score=clockScore(RCLOCK,driver,raceClock);
  drawAdaptiveForecast();
  drawLiveConnections(state,score);
  if(CLOCKDECISIONREPORT?.improvement_pct!==undefined){
    const r=CLOCKDECISIONREPORT;
    $('#t-model-score').innerHTML=`<div><span>TYRE-RESPONSE ERROR</span><strong>${fmt(r.rmse_s,3)}<small>s RMSE</small></strong><p>${fmt(r.previous_rmse_s,3)}s previous model · ${fmt(r.baseline_rmse_s,3)}s historical mean</p></div><div><span>LESS ERROR VS HISTORICAL MEAN</span><strong>${fmt(r.improvement_pct,1)}<small>%</small></strong><p>${r.n} stops · earlier-race training · reused R09–R12</p></div><div><span>CONTROL-ADJUSTED RECOVERY STUDY</span><strong>${fmt(r.strict_relative_validation?.improvement_vs_mean_pct,1)}<small>% less error</small></strong><p>${r.strict_relative_validation?.n} matched stops · separate target and model</p></div>`;
  }
  const current=RREPLAY.laps_data.filter(r=>r.driver===driver&&isNumber(r.completed_s)&&r.completed_s<=raceClock).sort((a,b)=>b.completed_s-a.completed_s)[0];
  $('#c-position').textContent=isNumber(current?.position)?'P'+current.position:'—';
  $('#c-trend').textContent=state?recoverySigned(state.pace_trend_s_per_lap)+'s/lap':'Observing';
  $('#c-compound').textContent=current?.compound||'UNAVAILABLE';$('#c-compound-letter').textContent=current?.compound?.[0]||'—';
  $('#c-age').textContent=isNumber(current?.tyre_age)?current.tyre_age+' laps on tyre':'No tyre observation';
  $('#c-tyre-icon').style.setProperty('--tyre-color',tyreColors[current?.compound]||'#87958e');
  $('#c-track-temp').textContent=displayNumber(current?.track_temp_c,1,'°C');$('#c-air-temp').textContent=displayNumber(current?.air_temp_c,1,'°C');
  $('#c-traffic').textContent=current?.traffic_observed?displayNumber(current.frac_close*100,0,'%'):'No feed';
  $('#c-gap').textContent=current?.traffic_observed?displayNumber(current.gap_med_s,2,'s'):'No feed';
  $('#c-weather-quality').textContent=isNumber(current?.weather_age_s)?Math.round(current.weather_age_s+raceClock-current.completed_s)+'s old':'Unavailable';
  $('#c-traffic-quality').textContent=current?.traffic_observed?displayNumber(current.traffic_coverage*100,0,'% of last lap'):'Unavailable';
  $('#c-pace-label').textContent=next?`CLOCK FORECAST / LAP ${next.target_lap}`:'CLOCK FORECAST / WAITING';
  $('#c-pace').innerHTML=next?`${fmt(next.pace_s,2)}<small>s</small>`:'—<small>s</small>';
  $('#c-interval').textContent=next?isNumber(next.lower_s)?`90% interval ${fmt(next.lower_s,2)}–${fmt(next.upper_s,2)}s`:'Interval calibrating':'Collecting representative timestamped laps';
  $('#clock-basis').textContent=state?`Issued L${state.lap} at ${formatRaceTime(state.issued_s)} · ${Math.max(0,Math.floor(raceClock-state.issued_s))}s ago · trained through R${RCLOCK.training_through_round}`:'Pits, neutralisations and stale/missing timing pause the clock model.';
  $('#c-call').textContent=next?`Lap ${next.target_lap} / ${fmt(next.pace_s,2)}s`:'Collecting clean running.';
  $('#clock-brief').textContent=next?`${driver}: ${state.compound} tyres, ${state.tyre_age} laps old at issue. Next-lap target ${fmt(next.pace_s,2)}s${isNumber(next.lower_s)?`, range ${fmt(next.lower_s,2)}–${fmt(next.upper_s,2)}s`:''}. Assumes continued green running on this stint.`:'The clock model waits for representative observations after a stop or interruption. No later lap is substituted.';
  if(missionView==='forecast')drawClockWitness(state,score);
  if(missionView==='circuit'){
    $('#m-horizons').innerHTML=state?state.forecasts.map(f=>`<div><span>CLOCK MODEL / LAP ${f.target_lap}</span><b>${fmt(f.pace_s,2)}<small>s</small></b><em>${isNumber(f.lower_s)?`${fmt(f.lower_s,2)}–${fmt(f.upper_s,2)}s`:'Calibrating'}</em></div>`).join(''):'<p class="mission-footnote">Clock model waiting for representative laps.</p>';
    $('#m-last-result').textContent=score.latest?`Clock-verified L${score.latest.target_lap}: ${fmt(score.latest.predicted_s,3)}s predicted / ${fmt(score.latest.actual_s,3)}s actual. ${score.n} resolved next-lap predictions, RMSE ${fmt(score.rmse,3)}s.`:'No clock-model outcome has resolved for this driver yet.';
  }
  if(CLOCKREPORT){
    const p=CLOCKREPORT;
    const tyre=CLOCKDECISIONREPORT;
    $('#headnums').innerHTML=tyre?.improvement_pct!==undefined?`<div><b>${fmt(tyre.rmse_s,3)} s</b>tyre-response RMSE</div><div><b>${fmt(tyre.improvement_pct,1)}%</b>less error vs mean</div><div><b>${tyre.n} stops</b>reused R09–R12 evaluation</div><div><b>${fmt(p.rmse_s,3)} s</b>lap-forecast RMSE</div>`:`<div><b>${fmt(p.rmse_s,3)} s</b>clock-model RMSE</div><div><b>${fmt(p.improvement_pct,1)}%</b>less error vs persistence</div><div><b>${p.scored.toLocaleString()}</b>scored forecasts</div><div><b>R09–R12</b>reused evaluation</div>`;
    $('#clock-proof').innerHTML=`<b>Timestamp audit: ${fmt(p.rmse_s,3)}s vs ${fmt(p.baseline_rmse_s,3)}s persistence</b><span>${fmt(p.improvement_pct,1)}% lower RMSE · ${fmt(p.interval_coverage*100,1)}% coverage at nominal 90% · ${p.timing_violations} targets before issue · ${p.scored}/${p.issued} scoreable</span><a href="../artifacts/demo/clock/report.json" target="_blank" rel="noopener">Inspect clock evidence ↗</a>`;
    if(missionView==='proof'){
      let box=$('#clock-results');if(!box){box=document.createElement('div');box.id='clock-results';box.className='clock-proof';$('#mission-proof').prepend(box);}
      box.innerHTML=`<b>CURRENT CLOCK MODEL / ${fmt(p.improvement_pct,1)}% LESS RMSE</b><span>${fmt(p.rmse_s,3)}s vs ${fmt(p.baseline_rmse_s,3)}s persistence. Per-driver timestamps; ${p.scored.toLocaleString()} scored predictions. Reused evaluation races.</span>`;
    }
  }
}

function drawLiveConnections(state,score){
  const driver=$('#i-driver').value,compound=$('#o-compound').value;
  const key=[RREPLAY.round,driver,state?.lap,score.n,Math.floor(raceClock),compound,$('#m-response').value,$('#o-traffic').value,$('#o-pitloss').value,$('#o-decay').value,...['hard','medium','soft'].map(c=>$('#o-'+c).checked)].join(':');
  if(key===clockPaintKey)return;clockPaintKey=key;
  const resolved=RREPLAY.laps_data.filter(r=>Number.isFinite(r.completed_s)&&r.completed_s<=raceClock);
  const pit=PitwallStrategy.pitLossAt({...RREPLAY,laps_data:resolved},Math.max(0,...resolved.map(r=>r.lap)));
  if(!pitLossManual)$('#o-pitloss').value=pit.n>=3?pit.median_s.toFixed(1):'22';
  const settings={replay:RREPLAY,pace:RCLOCK,pit:RPITCLOCK,time:raceClock,driver,compound,
    responseLaps:+$('#m-response').value,pitLoss:+$('#o-pitloss').value,trafficLoss:+$('#o-traffic').value,decay:+$('#o-decay').value,
    inventory:['HARD','MEDIUM','SOFT'].filter(c=>$('#o-'+c.toLowerCase()).checked)};
  const valid=['o-pitloss','o-traffic','o-decay'].every(id=>$('#'+id).value!==''&&$('#'+id).checkValidity());
  livePlan=valid?PitwallLive.plan(settings):{status:'invalid'};
  const drift=recoveryState(RRECOVERY,RREPLAY,driver,raceClock).snapshot;
  const p=livePlan,attack=p.attacks?.[0],rejoin=p.windows?.[0],f=state?.forecasts.find(f=>f.horizon===1);
  $('#m-duel').innerHTML=`<div><b>${driver}</b><span>${state?state.compound+' / '+state.tyre_age+' laps / clock L'+state.lap:'Observing'}</span></div><span class="duel-divider">VS</span><div><b>${attack?.driver||'—'}</b><span>${attack?recoverySigned(attack.margin_s)+'s conditional undercut margin':'No supported rival scenario'}</span></div>`;
  $('#c-rival').textContent=attack?attack.driver+' / '+recoverySigned(attack.margin_s)+'s':'No supported rival scenario';
  $('#c-risk').textContent=attack?`After both stops; ±${fmt(attack.radius_s,2)}s stress range. Computed from clock lap forecasts, tyre response and explicit traffic cost.`:'Waiting for supported clock forecasts.';
  $('#live-chain').innerHTML=`<div><span>01 / TYRE AGE &amp; TREND</span><b>${state?recoverySigned(state.pace_trend_s_per_lap)+'s/lap':'Observing'}</b><small>${state?state.tyre_age+'-lap '+state.compound:'waiting'} · actual model inputs</small></div><i>→</i><div><span>02 / CONTINUE NEXT LAP</span><b>${f?fmt(f.pace_s,2)+'s':'—'}</b><small>age + recent pace → clock model</small></div><i>→</i><div><span>03 / FIT ${compound}</span><b>${p.status==='ready'?fmt(p.new_tyre_pace_s,2)+'s':'—'}</b><small>${p.status==='ready'?recoverySigned(p.step.step_s)+'s/lap stop response':'Unsupported stop response'}</small></div><i>→</i><div><span>04 / PROJECTED REJOIN</span><b>${rejoin?.ahead?rejoin.ahead.driver+' +'+fmt(rejoin.ahead.gap_s,1)+'s':rejoin?'Clear ahead':'—'}</b><small>${rejoin?rejoin.covered+'/'+rejoin.total+' cars · '+fmt(settings.pitLoss,1)+'s pit cost':'Awaiting supported timing'}</small></div>`;
  $('#live-chain-note').textContent=p.status==='ready'?`L${p.lap} age + pace + temperature + observed traffic → tyre-response model → ${fmt(p.current_pace_s,2)} − ${fmt(p.step.step_s,2)} = ${fmt(p.new_tyre_pace_s,2)}s clean-lap scenario. Relative stint drift ${drift?recoverySigned(drift.relative_drift_s)+'s':'unavailable'} is a separate attribution warning. Pit loss ${fmt(settings.pitLoss,1)}s; extra future traffic ${fmt(settings.trafficLoss,1)}s. ${p.step.transition_age_extrapolation?'Age outside this compound transition’s training range; treat the estimate cautiously.':''}`:'Green running and at least five prior stops for the compound transition are required. No forced recommendation.';
  const rows=score.rows.slice(0,5);
  const latest=rows[0];
  $('#track-audit').innerHTML=latest?`<span>AUTO-VERIFIED / ${driver} L${latest.target_lap}</span><div><small>Locked</small><b>${fmt(latest.predicted_s,3)}s</b></div><div><small>Actual</small><b>${fmt(latest.actual_s,3)}s</b></div><p>Error ${fmt(Math.abs(latest.predicted_s-latest.actual_s),3)}s · baseline ${fmt(Math.abs(latest.baseline_s-latest.actual_s),3)}s</p><em>${score.n} scored · ${fmt(score.rmse,3)}s model RMSE</em>`:'<span>AUTOMATIC LAP VERIFICATION</span><p>First supported result appears when its lap finishes.</p>';
  $('#live-results').innerHTML=`<div class="live-results-head"><span>AUTOMATIC FORECAST AUDIT / ${driver}</span><b>${score.n} resolved · ${fmt(score.rmse,3)}s RMSE <small>vs ${fmt(score.baseline_rmse,3)}s persistence</small></b></div><table><thead><tr><th>Lap</th><th>Locked prediction</th><th>Actual</th><th>Error</th><th>Baseline error</th></tr></thead><tbody>${rows.map(e=>`<tr><td>L${e.target_lap}</td><td>${fmt(e.predicted_s,3)}s</td><td>${fmt(e.actual_s,3)}s</td><td>${fmt(Math.abs(e.predicted_s-e.actual_s),3)}s</td><td>${fmt(Math.abs(e.baseline_s-e.actual_s),3)}s</td></tr>`).join('')||'<tr><td colspan="5">Results unlock when the driver crosses the timing line.</td></tr>'}</tbody></table>`;
  if(p.status==='ready'){
    const w=p.windows[0];$('#o-tactical').innerHTML=`<span class="eyebrow">CLOCK STRATEGY / ${driver} L${p.lap}</span><div><span>Tyre age / model pace trend</span><b>${p.inputs.age} / ${recoverySigned(p.inputs.pace_trend_s_per_lap)}s/lap</b></div><div><span>${compound} response</span><b>${recoverySigned(p.step.step_s)} ± ${fmt(p.step.radius_s,2)}s</b></div><div><span>Rejoin projection behind</span><b>${w.ahead?.driver||'Clear covered field'}${w.ahead?' / '+fmt(w.ahead.gap_s,1)+'s':''}</b></div><div><span>Undercut ${attack?.driver||'—'}</span><b>${attack?recoverySigned(attack.margin_s)+'s':'unsupported'} / uncertain</b></div><p class="micro">Individual clock forecasts aligned at a common timing line. Equal rival pit cost assumed; intervals overlap.</p>`;
    $('#o-tyre-value').innerHTML=`<span>CLOCK STOP RESPONSE / ${compound}</span><strong>${recoverySigned(p.step.step_s)}<small>s/lap</small></strong><p>${p.step.training_stops} earlier stops · ±${fmt(p.step.radius_s,2)}s</p>`;
  }else{$('#o-tactical').textContent='Clock strategy waiting for supported pace and tyre inputs.';$('#o-tyre-value').textContent='Clock stop response observing';}
  drawLiveOperations(p,settings,pit);
  if(missionView==='undercut')drawLiveUndercut();
}

function drawClockWitness(state,score){
  const driver=$('#i-driver').value,t=missionTicket,status=resolveClockForecast(t,RCLOCK,RREPLAY,driver,raceClock);
  $('#m-lock').disabled=!state;$('#m-lock').textContent=t?'Replace audit lock':'Lock for audit';
  $('#m-unlock').disabled=!t;
  $('#m-reveal').disabled=status.status!=='pending';$('#m-reveal').textContent=playback?'Race running · result unlocks automatically':'Run replay & verify →';
  $('#m-session-score').innerHTML=`<span>${driver} / ${score.n} verified clock forecasts</span><strong>${fmt(score.rmse,3)}s model RMSE</strong><span>${fmt(score.baseline_rmse,3)}s persistence</span>`;
  if(!t){$('#m-ticket').innerHTML='<p>Select a horizon and pin its prediction. The circuit audit below the track already verifies every next-lap forecast automatically.</p>';return;}
  if(['different_context','before_issue'].includes(status.status)){$('#m-ticket').textContent='Return to this forecast’s race, driver and issue time, or pin a new forecast.';return;}
  $('#m-ticket').innerHTML=`<div class="ticket-heading"><span>PINNED / ${t.driver} L${t.issued_lap} → L${t.target_lap}</span><b>${status.status.toUpperCase()}</b></div><div class="ticket-values"><div><span>LOCKED PREDICTION</span><strong>${fmt(t.predicted_s,3)}s</strong></div><div><span>PERSISTENCE</span><strong>${fmt(t.baseline_s,3)}s</strong></div><div><span>ACTUAL</span><strong>${status.status==='resolved'?fmt(status.actual_s,3)+'s':'Awaiting lap'}</strong></div></div><p class="mission-footnote">${status.status==='resolved'?`Model error ${fmt(status.error_s,3)}s; persistence error ${fmt(status.baseline_error_s,3)}s.`:status.status==='interrupted'?'Pit, neutralisation or missing data invalidated this same-stint forecast. No fabricated score.':`Frozen at ${formatRaceTime(t.issued_s)}. Interval ${fmt(t.lower_s,2)}–${fmt(t.upper_s,2)}s. Keep the replay running to reveal the result.`}</p>`;
}
