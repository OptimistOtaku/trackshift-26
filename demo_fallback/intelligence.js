/* Causal replay presentation. Outcomes are revealed only at target_lap <= cursor. */
let engineerTimer, engineerRequest = 0, engineerAbort, playback;

function selectedSnapshot(){
  return RINTEL?.snapshots.find(s => s.lap === +$('#r-lap').value && s.driver === $('#i-driver').value);
}

async function initIntelligence(){
  $('#i-driver').addEventListener('change', drawIntelligence);
  ['compound','gap','response','warmup','traffic','service','pace','decay'].forEach(id =>
    $('#u-'+id).addEventListener('input', drawScenario));
  $('#r-play').onclick = () => {
    if(playback){clearInterval(playback);playback=null;$('#r-play').textContent='Play';return;}
    $('#r-play').textContent='Pause';
    playback=setInterval(() => {
      const slider=$('#r-lap');
      if(+slider.value>=+slider.max){$('#r-play').click();return;}
      slider.value=+slider.value+1;drawReplay();
    },1600);
  };
  try{
    const [report,decision]=await Promise.all([getJSON('intelligence/report.json'),getJSON('intelligence/decision_report.json')]);
    $('#headnums').innerHTML=`<div><b>${fmt(report.rmse_s,3)} s</b>future lap RMSE</div>
      <div><b>+${fmt(report.improvement_pct,1)}%</b>vs ${report.baseline.replaceAll('_',' ')}</div>
      <div><b>${report.n.toLocaleString()}</b>scored forecasts</div>
      <div><b>R09–R12</b>final evaluation</div>`;
    $('#i-validation').innerHTML=`<p class="sub">Model architecture selected on rounds 4–8, then fixed for rounds 9–12.
      Each race is predicted using coefficients trained on earlier races only. Baseline selection also uses rounds 4–8.
      These are same-stint green-flag forecasts; pit stops and neutralisations interrupt the scenario.</p>
      <div class="stat"><div><b>${fmt(report.rmse_s,3)} s</b>hybrid forecast RMSE</div>
        <div><b>${fmt(report.baseline_rmse_s,3)} s</b>persistence RMSE</div>
        <div><b>+${fmt(report.improvement_pct,1)}%</b>improvement</div>
        <div><b>${report.scored_forecasts} / ${report.issued_forecasts}</b>scored / issued final-round forecasts</div></div>
      <table><thead><tr><th>Horizon</th><th>RMSE</th><th>Baseline</th><th>Improvement</th><th>90% interval coverage</th></tr></thead>
        <tbody>${report.horizons.map(h=>`<tr><td>${h.horizon} lap${h.horizon>1?'s':''}</td>
          <td>${fmt(h.rmse_s,3)} s</td><td>${fmt(h.baseline_rmse_s,3)} s</td>
          <td>${fmt(h.improvement_pct,1)}%</td><td>${fmt(h.interval_coverage*100,1)}%</td></tr>`).join('')}</tbody></table>
      <p class="note">Paired event-bootstrap improvement interval: ${report.improvement_event_bootstrap_95.map(v=>fmt(v,1)+'%').join(' to ')}.
        Only four final evaluation races; overlapping forecasts are not independent trials.
        Prediction intervals use errors from previous races, with empirical rather than guaranteed coverage.</p>
      <p class="cost">Pre-stop scenario model: ${fmt(decision.rmse_s,3)} s RMSE versus ${fmt(decision.baseline_rmse_s,3)} s for the mean baseline
        on ${decision.n} stops. It did not improve this test, so the undercut calculator is a sensitivity tool, not a validated overtake predictor.</p>`;
  }catch(e){$('#i-validation').textContent='Intelligence benchmark unavailable: '+e.message;}
}

function drawIntelligence(){
  if(!RINTEL || !RREPLAY)return;
  const L=+$('#r-lap').value,driver=$('#i-driver').value,state=selectedSnapshot();
  const done=RINTEL.evaluation.filter(e=>e.target_lap<=L && e.horizon===1);
  const rmse=key=>done.length ? Math.sqrt(done.reduce((s,e)=>s+(e[key]-e.actual_s)**2,0)/done.length) : null;
  $('#i-score').innerHTML=`<div><b>${done.length}</b>one-lap forecasts resolved so far</div>
    <div><b>${fmt(rmse('predicted_s'),3)} s</b>race forecast RMSE so far</div>
    <div><b>${fmt(rmse('baseline_s'),3)} s</b>persistence RMSE so far</div>
    <div><b>${RINTEL.training_through_round ? 'R'+RINTEL.training_through_round : 'Warming up'}</b>last training race</div>`;
  $('#i-title').textContent=state ? `${driver} / ${state.compound} / age ${state.tyre_age}` : `${driver} / observation only`;
  $('#i-basis').textContent=state ? `Forecast issued after lap ${L}. Shaded band: empirical 90% prediction interval from earlier-race errors.
    Model: ${RINTEL.selected_model}. The snapshot represents the field having completed this lap.` :
    (RINTEL.status==='ready' ? 'Forecast paused: need three representative observations after a stop or neutralisation.' :
      'First three races collect training data. No later-race model is substituted.');
  $('#i-trend').textContent=state ? `Recent pace trend ${state.pace_trend_s_per_lap>=0?'+':''}${fmt(state.pace_trend_s_per_lap,3)} s/lap.
    This includes fuel, traffic, track evolution and tyres; it is not a direct wear measurement.` : '';
  const observed=RREPLAY.laps_data.filter(r=>r.driver===driver && r.lap<=L && r.lap>=L-17
    && r.lap_time_s!=null && r.track_status==='1' && !r.in_lap && !r.out_lap && r.lap>1);
  const forecasts=state?.forecasts||[];
  const completed=RINTEL.evaluation.filter(e=>e.driver===driver && e.horizon===1 && e.target_lap<=L && e.target_lap>=L-17);
  const values=[...observed.map(r=>r.lap_time_s),...forecasts.flatMap(f=>[f.pace_s,f.lower_s,f.upper_s].filter(v=>v!=null)),...completed.map(e=>e.predicted_s)];
  if(values.length){
    const xr=[Math.max(1,L-17),Math.min(RREPLAY.laps,L+6)],yr=nice(Math.min(...values)-.3,Math.max(...values)+.3);
    const {s,plot}=chart(780,320,{l:62,r:20,t:18,b:42});
    const {X,Y}=axes(s,plot,xr,yr,'lap','seconds');
    const bounded=forecasts.filter(f=>f.lower_s!=null);
    if(bounded.length>1){
      const points=[...bounded.map(f=>`${X(f.target_lap)},${Y(f.lower_s)}`),...bounded.slice().reverse().map(f=>`${X(f.target_lap)},${Y(f.upper_s)}`)].join(' ');
      s.appendChild(svgEl('polygon',{points,fill:'#3fa7dc','fill-opacity':.16}));
    }
    function plotLine(points,color,dash){
      if(points.length<2)return;
      s.appendChild(svgEl('polyline',{points:points.map(p=>`${X(p[0])},${Y(p[1])}`).join(' '),fill:'none',stroke:color,'stroke-width':2,'stroke-dasharray':dash||''}));
    }
    // Break the observed line across missing or neutralised laps.
    let run=[];
    observed.forEach((r,i)=>{if(i && r.lap!==observed[i-1].lap+1){plotLine(run,'#e8e9ed');run=[];}run.push([r.lap,r.lap_time_s]);});plotLine(run,'#e8e9ed');
    const last=observed.find(r=>r.lap===L);
    plotLine([...(last?[[L,last.lap_time_s]]:[]),...forecasts.map(f=>[f.target_lap,f.pace_s])],'#3fa7dc','5 4');
    completed.forEach(e=>s.appendChild(svgEl('circle',{cx:X(e.target_lap),cy:Y(e.predicted_s),r:3,fill:'#9bcced'})));
    s.appendChild(svgEl('line',{x1:X(L),x2:X(L),y1:plot.t,y2:plot.t+plot.h,stroke:'#e07a5f','stroke-dasharray':'3 5'}));
    $('#i-chart').replaceChildren(s);
  }else $('#i-chart').textContent='No representative pace observations available yet.';
  drawScenario();
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
    'Sensitivity scenario only. The pre-stop model did not beat its mean baseline on the final four races. A positive margin is not a validated overtake prediction.';
  $('#u-rows').innerHTML=rows.map(r=>`<tr><td>${r.k} lap${r.k>1?'s':''}</td><td>${fmt(r.gain,2)} s</td>
    <td>${fmt(r.margin,2)} s</td><td>${fmt(r.lo,2)} to ${fmt(r.hi,2)} s</td></tr>`).join('');
}
