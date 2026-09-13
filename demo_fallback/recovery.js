/* Tyre response evidence; outcome windows unlock only after all sources arrive. */
let RRECOVERY=null,RECOVERYEVIDENCE=null,RECOVERYREPORT=null,TYRECHALLENGE=null,recoveryKey='',recoveryContext='';
function recoverySigned(value){return Number.isFinite(value)?(value>=0?'+':'')+value.toFixed(2):'—';}
function recoveryState(payload,replay,driver,time){
  if(!payload||!replay||payload.round!==replay.round||!Number.isFinite(time))return {snapshot:null,resolved:[]};
  const row=(replay?.laps_data||[]).filter(r=>r.driver===driver&&Number.isFinite(r.completed_s)&&r.completed_s<=time).sort((a,b)=>b.completed_s-a.completed_s)[0];
  const active=row&&row.track_status==='1'&&!row.in_lap&&!row.out_lap&&time-row.completed_s<=180;
  const snapshot=active?(payload?.snapshots||[]).find(s=>s.driver===driver&&s.lap===row.lap&&s.issued_s<=time):null;
  const resolved=(payload?.stops||[]).filter(s=>s.label_s<=time&&s.issued_s<s.label_s).sort((a,b)=>b.label_s-a.label_s);
  return {snapshot,resolved};
}
if(typeof module!=='undefined')module.exports={recoveryState};
async function initRecovery(){
  [RECOVERYEVIDENCE,RECOVERYREPORT,TYRECHALLENGE]=await Promise.all([getJSON('recovery/evidence.json').catch(()=>null),getJSON('recovery/report.json').catch(()=>null),getJSON('tyre-challenge/report.json').catch(()=>null)]);
  document.querySelector('#t-stop').onchange=()=>drawRecovery(true);
  drawRecovery(true);
}
function drawRecovery(force=false){
  if(!document.querySelector('#tyre-response'))return;
  const driver=$('#i-driver').value,{snapshot:s,resolved}=recoveryState(RRECOVERY,RREPLAY,driver,raceClock);
  const key=[RRECOVERY?.round,driver,s?.lap,resolved.length,!!RECOVERYEVIDENCE,!!RECOVERYREPORT,!!TYRECHALLENGE].join(':');
  if(!force&&key===recoveryKey)return; recoveryKey=key;
  $('#t-live').innerHTML=s?`<span>FIELD-RELATIVE STINT DRIFT / ${driver} L${s.lap}</span><strong>${recoverySigned(s.relative_drift_s)}<small>s/lap</small></strong><p>Raw pace drift ${recoverySigned(s.raw_drift_s)}s · reference age ${fmt(s.reference_age,1)} → ${s.age} laps. ${s.reference_span<3?'Reference building.':s.relative_drift_s>0?'Losing pace relative to the field.':'No positive relative pace loss at this issue.'}</p>`:'<span>FIELD-RELATIVE STINT DRIFT</span><strong>Observing</strong><p>Waiting for a current, uninterrupted stint reference.</p>';
  $('#t-context').textContent=s?`${s.track_temp_c===null?'Track temperature unavailable':fmt(s.track_temp_c,1)+'°C track'} · ${s.traffic_missing?'Traffic unavailable in part of reference; attribution uncertain.':'Close-traffic exposure changed '+recoverySigned(100*s.traffic_change)+' percentage points.'} Field composition, fuel and driver changes can also move this signal.`:'Pit, neutralised or stale timing pauses the stint signal.';
  const select=$('#t-stop'),old=select.value;
  select.replaceChildren(...resolved.map(r=>new Option(`${r.driver} · before L${r.lap+1} stop · ${r.pair.replace('>',' → ')}`,`${r.driver}:${r.lap}`)));
  const context=[RRECOVERY?.round,driver].join(':');
  const preserved=(force||context===recoveryContext)?resolved.find(r=>`${r.driver}:${r.lap}`===old):null;
  const preferred=preserved||resolved.find(r=>r.driver===driver)||resolved[0];recoveryContext=context;
  if(preferred)select.value=`${preferred.driver}:${preferred.lap}`;
  select.disabled=!resolved.length;
  const r=resolved.find(r=>`${r.driver}:${r.lap}`===select.value);
  $('#t-observed').innerHTML=r?`<div class="tyre-equation"><div><span>BEFORE / 3 LAPS</span><b>${fmt(r.pre_mean_s,3)}s</b></div><em>−</em><div><span>AFTER / 3 LAPS</span><b>${fmt(r.post_mean_s,3)}s</b></div><em>=</em><div><span>OBSERVED RECOVERY</span><b>${recoverySigned(r.raw_step_s)}s</b></div></div><div class="tyre-equation adjusted"><div><span>STAY-OUT CONTROL CHANGE</span><b>${recoverySigned(r.control_step_s)}s</b></div><em>→</em><div><span>RECOVERY RELATIVE TO CONTROLS</span><b>${recoverySigned(r.relative_step_s)}s/lap</b></div></div><p class="ops-note">${r.control_n>=3?'Controls: '+r.controls.replaceAll(',',', ')+'. Matched on pre-stop pace and trend.':'Fewer than three controls: adjusted recovery unavailable.'} Tyre age ${r.old_age} → ${r.new_age} at the window edges. Source windows resolved by ${formatRaceTime(r.label_s)}. Excludes pit and out-lap cost.</p><p class="ops-note">Close-traffic exposure: ${isNumber(r.pre_traffic)?fmt(100*r.pre_traffic,0)+'%':'unknown'} before → ${isNumber(r.post_traffic)?fmt(100*r.post_traffic,0)+'%':'unknown'} after. Pre-stop no-change placebo: ${isNumber(r.placebo_relative_s)?recoverySigned(r.placebo_relative_s)+'s/lap':'unavailable'}. Observed recovery still includes residual confounding.</p>`:'<p class="ops-note">No eligible stop has fully resolved at this replay time. Play or advance the race: the before/after evidence unlocks only after the third post-stop lap and the matched controls have arrived.</p>';
  if(RECOVERYEVIDENCE){
    const e=RECOVERYEVIDENCE,p=e.paired_same_compound,a=p.actual;
    $('#t-proof').innerHTML=`<span class="eyebrow">ARCHIVE STUDY / ALL AVAILABLE EVENTS</span><h3>Does a tyre reset leave a measurable signal?</h3><div class="tyre-proof"><div><b>${recoverySigned(a.mean_s)}s</b><span>matched recovery / paired subset<br>${a.n} same-compound stops / ${a.events} events</span></div><div><b>${recoverySigned(p.placebo.mean_s)}s</b><span>no-change placebo<br>${p.placebo.n} paired stops</span></div><div><b>${recoverySigned(p.difference.mean_s)}s</b><span>reset minus placebo<br>95% event-bootstrap ${p.difference.event_bootstrap_95_s.map(v=>recoverySigned(v)).join(' to ')}s</span></div></div><p class="ops-note">Across all ${e.same_compound.n} matched same-compound stops, mean recovery is ${recoverySigned(e.same_compound.mean_s)}s. The paired subset above has both checks. Nonzero placebo drift warns that causal separation is incomplete. This is observational evidence of tyre-reset response, not measured rubber wear or a guaranteed benefit from pitting.</p>`;
  }
  if(RECOVERYREPORT){const m=RECOVERYREPORT.targets.relative_step_s;
    $('#t-research').innerHTML=`<b>MODEL CHALLENGE / ${m.n} REUSED EVALUATION STOPS</b><p>${fmt(m.rmse_s,3)}s RMSE for the development-selected model vs ${fmt(m.baseline_rmse_s,3)}s for the historical mean. ${m.rmse_s<m.baseline_rmse_s?'Lower aggregate error; prospective validation still required.':'No reliable predictive uplift: the experimental estimator is not promoted into strategy calls.'} All candidates and losses remain available.</p><a href="../artifacts/demo/recovery/report.json" target="_blank" rel="noopener">Model results ↗</a> · <a href="../artifacts/demo/recovery/evidence.json" target="_blank" rel="noopener">Control study ↗</a>`;}
  if(TYRECHALLENGE){
    const labels={deployed_stop_response:'Deployed stop response',strict_raw_response:'Strict-window recovery',strict_relative_response:'Recovery versus stay-out controls'};
    $('#t-research').innerHTML=`<b>UPDATED TYRE-RESPONSE CHALLENGE / REUSED R09–R12</b><table><thead><tr><th>Target</th><th>Stops</th><th>Selected RMSE</th><th>Mean baseline</th><th>Earlier architecture</th></tr></thead><tbody>${Object.entries(TYRECHALLENGE.experiments).map(([name,r])=>`<tr><td>${labels[name]}</td><td>${r.n}</td><td>${fmt(r.rmse_s,3)}s</td><td>${fmt(r.baseline_rmse_s,3)}s</td><td>${fmt(r.existing_rmse_s,3)}s</td></tr>`).join('')}</tbody></table><p class="ops-note">22 predeclared configurations per target; R04–R08 selects each model before scoring its frozen choice on reused R09–R12. Targets stay separate. The deployed model improves aggregate error; its event-bootstrap interval includes zero. Strict raw recovery does not beat the earlier architecture on the same target. No claim of physical wear accuracy or guaranteed places gained.</p><a href="../artifacts/demo/tyre-challenge/report.json" target="_blank" rel="noopener">Complete new comparison ↗</a> · <a href="../artifacts/demo/recovery/report.json" target="_blank" rel="noopener">Earlier unsuccessful study ↗</a>`;
  }
}
