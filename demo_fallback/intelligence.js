/* Causal replay presentation. Outcomes are revealed only at target_lap <= cursor. */
let engineerTimer, engineerRequest = 0, engineerAbort, playback;

function selectedSnapshot(){
  return RINTEL?.snapshots.find(s => s.lap === +$('#r-lap').value && s.driver === $('#i-driver').value);
}

async function initIntelligence(){
  initConsole();
  initBattle();
  $('#i-driver').addEventListener('change', drawIntelligence);
  ['compound','gap','response','warmup','traffic','service','pace','decay'].forEach(id =>
    $('#u-'+id).addEventListener('input', drawScenario));
  $('#r-play').onclick = () => {
    if(playback){playback=null;$('#r-play').textContent='Play';updatePlaybackLabel();return;}
    if(!RREPLAY)return;
    if(+$('#r-lap').value>=+$('#r-lap').max){$('#r-lap').value=1;drawReplay();}
    $('#r-play').textContent='Pause';
    playback=true;
    updatePlaybackLabel();
  };
  try{
    const [report,decision]=await Promise.all([getJSON('intelligence/report.json'),getJSON('intelligence/decision_report.json')]);
    $('#headnums').innerHTML=`<div><b>${fmt(report.rmse_s,3)} s</b>future lap RMSE</div>
      <div><b>+${fmt(report.improvement_pct,1)}%</b>vs ${report.baseline.replaceAll('_',' ')}</div>
      <div><b>${report.n.toLocaleString()}</b>scored forecasts</div>
      <div><b>R09–R12</b>reused evaluation</div>`;
    $('#i-validation').innerHTML=`<p class="sub">Model architecture selected on rounds 4–8, then fixed for rounds 9–12.
      Each race is predicted using coefficients trained on earlier races only. Baseline selection also uses rounds 4–8.
      These are same-stint green-flag forecasts; pit stops and neutralisations interrupt the scenario.</p>
      <div class="stat"><div><b>${fmt(report.rmse_s,3)} s</b>${report.selected_model.replaceAll('_',' ')} RMSE</div>
        <div><b>${fmt(report.baseline_rmse_s,3)} s</b>persistence RMSE</div>
        <div><b>+${fmt(report.improvement_pct,1)}%</b>improvement</div>
        <div><b>${report.scored_forecasts} / ${report.issued_forecasts}</b>scored / issued final-round forecasts</div></div>
      <table><thead><tr><th>Horizon</th><th>RMSE</th><th>Baseline</th><th>Improvement</th><th>90% interval coverage</th></tr></thead>
        <tbody>${report.horizons.map(h=>`<tr><td>${h.horizon} lap${h.horizon>1?'s':''}</td>
          <td>${fmt(h.rmse_s,3)} s</td><td>${fmt(h.baseline_rmse_s,3)} s</td>
          <td>${fmt(h.improvement_pct,1)}%</td><td>${fmt(h.interval_coverage*100,1)}%</td></tr>`).join('')}</tbody></table>
      <p class="note">Paired event-bootstrap improvement interval: ${report.improvement_event_bootstrap_95.map(v=>fmt(v,1)+'%').join(' to ')}.
        Only four evaluation races, already inspected in the previous version; this is not a new blind test.
        Overlapping forecasts are not independent trials.
        Prediction intervals use errors from previous races, with empirical rather than guaranteed coverage.</p>
      <p class="cost">Pre-stop scenario model: ${fmt(decision.rmse_s,3)} s RMSE versus ${fmt(decision.baseline_rmse_s,3)} s for the mean baseline
        on ${decision.n} stops (${fmt(decision.improvement_pct,1)}% RMSE improvement).
        This small difference does not establish a tactical advantage; the undercut calculator remains a sensitivity tool.</p>
      <details><summary>Compare all ${Object.keys(report.candidate_development_mse).length} pace approaches</summary>
        <table><thead><tr><th>Approach</th><th>Development MSE (s²)</th></tr></thead>
        <tbody>${Object.entries(report.candidate_development_mse).sort((a,b)=>a[1]-b[1]).map(([name,mse])=>
          `<tr><td>${name.replaceAll('_',' ')}</td><td>${fmt(mse,4)}</td></tr>`).join('')}</tbody></table></details>`;
    showConditionsEvidence(report);
  }catch(e){$('#i-validation').textContent='Intelligence benchmark unavailable: '+e.message;}
}

function drawIntelligence(){
  if(!RINTEL || !RREPLAY)return;
  drawConsole();
  const L=+$('#r-lap').value,driver=$('#i-driver').value,state=selectedSnapshot();
  const forecasts=state?.forecasts||[];
  drawScenario();
  drawBattle();
  drawMission();
  drawOperations();
  drawClockForecast();
  clearTimeout(engineerTimer);
  const request=++engineerRequest;
  if(engineerAbort)engineerAbort.abort();
  $('#i-engineer').textContent=state ? `If ${driver} continues this stint under green flags, the next lap is forecast at ${fmt(forecasts[0].pace_s,2)} seconds.` :
    'Forecasting is paused while the estimator collects representative laps. The timing feed continues to show the race.';
  $('#i-engineer-source').textContent='Deterministic commentary · no invented telemetry';
  engineerTimer=setTimeout(async()=>{
    engineerAbort=new AbortController();
    try{
      const response=await fetch('/api/engineer',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({round:RINTEL.round,lap:L,driver}),signal:engineerAbort.signal});
      if(!response.ok)return;
      const result=await response.json();
      if(request!==engineerRequest)return;
      $('#i-engineer').textContent=result.text;
      $('#i-engineer-source').textContent=result.source==='local_llm' ? `Local LLM: ${result.model} · validated evidence selection` :
        'Grounded template · '+result.reason;
    }catch(e){/* Static hosting and unavailable LLMs retain the visible template. */}
  },350);
}

function drawScenario(){
  const state=selectedSnapshot(),compound=$('#u-compound').value;
  const values={};
  ['gap','response','warmup','traffic','service','pace','decay'].forEach(id=>{
    values[id]=+$('#u-'+id).value;
    $('#u-'+id+'-v').textContent=fmt(values[id],id==='response'?0:2)+(id==='response'?' laps':id==='pace'||id==='decay'?' s/lap':' s');
  });
  $('#u-context').textContent=state ? `Replay context: round ${RINTEL.round}, lap ${state.lap}, ${state.driver}, ${state.compound} → ${compound}.
    Change race, driver or lap in Race replay to price another situation.` : 'Select a race lap with a forecast in Race replay.';
  const scenario=state?.stop_scenarios?.[compound];
  if(!scenario?.supported || scenario.radius_s==null){
    $('#u-margin').textContent='Unavailable';$('#u-band').textContent='This transition has insufficient earlier-race support or calibration.';
    $('#u-rows').replaceChildren();$('#u-breakdown').replaceChildren();$('#u-limit').textContent='No later-race fallback is substituted.';return;
  }
  const rows=[];
  for(let k=1;k<=values.response;k++){
    const gain=k*(scenario.step_s+values.pace)-values.decay*k*(k-1)/2-values.warmup-values.traffic*k/values.response-values.service;
    const margin=gain-values.gap,radius=k*scenario.radius_s;
    rows.push({k,gain,margin,lo:margin-radius,hi:margin+radius});
  }
  const end=rows.at(-1);
  $('#u-margin').textContent=(end.margin>=0?'+':'')+fmt(end.margin,2)+' s';
  $('#u-margin').style.color=end.lo>0?'var(--good)':end.hi<0?'var(--red)':'var(--warn)';
  $('#u-band').textContent=`Empirical scenario range: ${fmt(end.lo,2)} to ${fmt(end.hi,2)} s. ${end.lo<=0&&end.hi>=0?'The range crosses zero.':''}`;
  $('#u-breakdown').innerHTML=`<div><span class="k">Predicted pace step</span><span>${fmt(scenario.step_s,2)} s/lap</span></div>
    <div><span class="k">Step uncertainty</span><span>±${fmt(scenario.radius_s,2)} s/lap</span></div>
    <div><span class="k">Earlier stops for this pair</span><span>${scenario.training_stops}</span></div>
    <div><span class="k">Tyre age deficit after response</span><span>${end.k} laps</span></div>`;
  $('#u-limit').textContent=(scenario.extrapolating?'This tyre age is outside training support. ':'')+
    'Sensitivity scenario only. Pre-stop accuracy is close to the mean baseline. A positive margin is not a validated overtake prediction.';
  $('#u-rows').innerHTML=rows.map(r=>`<tr><td>${r.k} lap${r.k>1?'s':''}</td><td>${fmt(r.gain,2)} s</td>
    <td>${fmt(r.margin,2)} s</td><td>${fmt(r.lo,2)} to ${fmt(r.hi,2)} s</td></tr>`).join('');
}
