/* The centre console is an evidence surface, not a decorative replay. */
let missionView='circuit',missionTicket=null,missionReports=null,juryChapter=-1,juryBusy=false;
const juryChapters=[
  {view:'science',title:'01 / Explain the tyre problem',script:'“A slower lap is not automatically tyre degradation. Fuel, traffic and track evolution distort the signal. Our research separates them; our race product predicts the pace risk an engineer can act on.”'},
  {view:'forecast',title:'02 / Make a prediction, then check it',script:'“This forecast uses only observations available at its driver timestamp. Pin it, run the race, and compare the automatically revealed actual with our prediction and persistence. This is one replay example; the full benchmark comes next.”'},
  {view:'undercut',title:'03 / Show what changes the decision',script:'“Fresh tyres have a predicted pace benefit, but we must pay the gap, rival pace and warm-up. Add two seconds of rejoin traffic: watch the central advantage disappear. The uncertainty remains visible throughout.”'},
  {view:'proof',title:'04 / Show the complete evidence',script:'“Across scored timestamped evaluation forecasts, pace error falls 11.6%. The pit-step model is weaker, so we present the undercut as a stress test. These are reused evaluation races, not a new blind test.”'}
];

function setMissionView(view){
  missionView=view;
  $('#mission-track').hidden=view!=='circuit';
  ['forecast','undercut','science','proof'].forEach(v=>$('#mission-'+v).hidden=view!==v);
  document.querySelectorAll('.mission-tabs button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.view===view));
  drawMission();
}

async function initMission(){
  document.querySelectorAll('.mission-tabs button').forEach(b=>b.onclick=()=>setMissionView(b.dataset.view));
  document.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>setMissionView(b.dataset.open));
  $('#m-lock').onclick=()=>{
    if(!RREPLAY)return;
    missionTicket=freezeClockForecast(RCLOCK,RREPLAY,$('#i-driver').value,raceClock,+$('#m-horizon').value);
    drawClockForecast();
  };
  $('#m-reveal').onclick=()=>{if(missionTicket&&!playback)$('#r-play').click();drawClockForecast();};
  $('#m-horizon').onchange=()=>{drawClockForecast();};
  $('#m-traffic').oninput=()=>{$('#o-traffic').value=$('#m-traffic').value;drawOperations();};
  $('#m-compound').onchange=()=>{$('#o-compound').value=$('#m-compound').value;drawOperations();};
  $('#m-response').onchange=drawOperations;
  $('#m-stress').onclick=()=>{$('#o-traffic').value=Math.min(20,+$('#o-traffic').value+2);drawOperations();};
  $('#m-reset-costs').onclick=()=>{$('#o-traffic').value=0;$('#o-decay').value=0;drawOperations();};
  $('#j-start').onclick=()=>goJuryChapter(0);
  $('#j-exit').onclick=()=>{juryChapter=-1;$('#jury-guide').hidden=true;document.body.classList.remove('jury-present');};
  $('#j-next').onclick=()=>{if(juryChapter===3){$('#j-exit').click();setMissionView('circuit');}else goJuryChapter(juryChapter+1);};
  $('#j-back').onclick=()=>goJuryChapter(Math.max(0,juryChapter-1));
  document.querySelectorAll('[data-chapter]').forEach(b=>b.onclick=()=>goJuryChapter(+b.dataset.chapter));
  drawScience();
  try{
    const [pace,decision,battle]=await Promise.all([getJSON('intelligence/report.json'),getJSON('intelligence/decision_report.json'),getJSON('intelligence/battle_report.json')]);
    missionReports={pace,decision,battle};drawMissionProof();
  }catch(error){$('#mission-proof').textContent='The benchmark could not be loaded. '+error.message;}
}

async function goJuryChapter(index){
  if(juryBusy)return;
  juryBusy=true;$('#j-start').disabled=true;
  try{
    if(playback)$('#r-play').click();
    $('#nav [data-t="replay"]').click();
    // One named example throughout, not a search for the best future outcome.
    if(!RREPLAY||RREPLAY.round!==11){$('#r-race').value='11';await loadReplay();}
    if(!RREPLAY)throw new Error('The demonstration race is unavailable.');
    $('#i-driver').value='NOR';$('#r-lap').value=25;
    if(index===1){missionTicket=null;$('#m-horizon').value=3;}
    if(index===2){$('#m-reset-costs').click();$('#m-response').value=3;$('#m-compound').value='HARD';}
    juryChapter=index;
    $('#jury-guide').hidden=false;document.body.classList.add('jury-present');
    $('#j-title').textContent=juryChapters[index].title;$('#j-script').textContent=juryChapters[index].script;
    $('#j-step-count').textContent=`0${index+1} / 04`;$('#j-back').disabled=index===0;
    $('#j-next').textContent=index===3?'Finish walkthrough ✓':'Next chapter →';
    document.querySelectorAll('[data-chapter]').forEach(b=>b.setAttribute('aria-pressed',+b.dataset.chapter===index));
    setMissionView(juryChapters[index].view);drawReplay();
    if(index===1)$('#m-lock').click();
    $('#jury-guide').scrollIntoView({block:'start',behavior:reducedMotion.matches?'instant':'smooth'});
  }catch(error){$('#m-ticket').textContent=error.message;}
  finally{juryBusy=false;$('#j-start').disabled=false;}
}

function clearMission(message){
  for(const id of ['m-duel','m-horizons','m-last-result','m-ticket','m-session-score','m-verdict'])$('#'+id).textContent=message;
  $('#m-forecast-chart').replaceChildren();$('#m-waterfall').replaceChildren();
  $('#m-lock').disabled=true;$('#m-reveal').disabled=true;
}

function drawMission(){
  if(!RREPLAY||!RINTEL)return;
  const state=selectedSnapshot(),lap=+$('#r-lap').value,driver=$('#i-driver').value;
  const rival=state?.battles?.find(b=>b.horizon===3);
  $('#m-duel').innerHTML=`<div><b>${driver}</b><span>${state?`${state.compound} / ${state.tyre_age} laps`:'Observing timing'}</span></div><span class="duel-divider">VS</span><div><b>${rival?.rival||'—'}</b><span>${rival?`${signed(rival.predicted_loss_s)}s relative loss / 3 laps`:'No supported rival forecast'}</span></div>`;
  $('#m-horizons').innerHTML=state?.forecasts.length?state.forecasts.map(f=>`<div><span>LAP ${f.target_lap} / +${f.horizon}</span><b>${fmt(f.pace_s,2)}<small>s</small></b><em>${isNumber(f.lower_s)?`${fmt(f.lower_s,2)}–${fmt(f.upper_s,2)} s`:'Calibrating interval'}</em></div>`).join(''):'<p class="mission-footnote">Forecasts pause on pit laps, neutralisations and insufficient history.</p>';
  const latest=RINTEL.evaluation.filter(e=>e.driver===driver&&e.horizon===1&&e.target_lap<=lap).sort((a,b)=>b.target_lap-a.target_lap)[0];
  $('#m-last-result').textContent=latest?`Last checked / L${latest.target_lap}: ${fmt(latest.predicted_s,2)}s predicted · ${fmt(latest.actual_s,2)}s actual · ${fmt(Math.abs(latest.predicted_s-latest.actual_s),3)}s error`:'No forecast outcome has resolved yet.';
  if(missionView==='forecast')drawClockWitness(clockState(RCLOCK,RREPLAY,driver,raceClock),clockScore(RCLOCK,driver,raceClock));
  if(missionView==='undercut')drawLiveUndercut();
}

function signed(value){return (value>=0?'+':'')+fmt(value,2);}

function drawScience(){
  const science=MODEL?.degradation_curves,H=science?.practice.compounds.HARD;
  if(!H){$('#mission-science').textContent='Tyre research artifacts unavailable.';return;}
  $('#mission-science').innerHTML=`<div class="mission-heading"><div><span class="eyebrow">TYRE DEGRADATION INTELLIGENCE</span><h3>Separate tyre wear from lap pace.</h3></div></div><div class="science-equation"><b>Lap pace</b><span>=</span><span>Fuel</span><span>+</span><strong>Tyres</strong><span>+</span><span>Traffic</span><span>+</span><span>Track</span></div><div class="science-compare"><div><span>NAIVE HARD-TYRE SLOPE</span><strong class="negative">${signed(H.naive.slope_s_per_lap)}<small>s/lap</small></strong><p>Appears to get faster with age.</p></div><div><span>AFTER CONFOUNDER CORRECTION</span><strong class="positive">${signed(H.deconfounded.slope_s_per_lap)}<small>s/lap</small></strong><p>Wear signal becomes positive.</p></div></div><div id="m-science-chart"></div><div class="science-conclusion"><b>Identification is only the first test.</b><p>The practice curve did not predict race stop-by-stop variation. We therefore validate race pace and rival-time forecasts separately, and show uncertainty on the stop scenario.</p></div><p class="mission-footnote">Historical practice research at tyre age ${science.slope_ref_age}; these research artifacts predate the replay traffic correction. This is not a direct physical-wear or remaining-life sensor.</p>`;
  const {s,plot}=chart(700,210,{l:48,r:15,t:15,b:35});
  const curves=[H.naive.curve,H.deconfounded.curve],values=curves.flatMap(c=>c.map(p=>p.delta_s));
  const {X,Y}=axes(s,plot,[H.age_lo,H.age_hi],nice(Math.min(...values)-.1,Math.max(...values)+.1),'tyre age / laps','pace cost / s',5,3);
  curves.forEach((curve,i)=>s.append(svgEl('polyline',{points:curve.map(p=>`${X(p.age)},${Y(p.delta_s)}`).join(' '),fill:'none',stroke:i?'#e6fc74':'#ff777c','stroke-width':2.5,'stroke-dasharray':i?'':'5 4'})));
  $('#m-science-chart').append(s);
}

function drawMissionProof(){
  if(!missionReports)return;
  const {pace:p,battle:b,decision:d}=missionReports,a=b.alerts.selected_s,base=b.alerts[b.baseline];
  $('#mission-proof').innerHTML=`<div class="mission-heading"><div><span class="eyebrow">ARCHIVED LAP-MODEL / R09–R12</span><h3>The whole evaluation. Not one lap.</h3></div></div><div class="proof-headlines"><div><strong>${fmt(p.improvement_pct,1)}<small>%</small></strong><span>less pace RMSE</span></div><div><strong>${fmt(b.improvement_pct,1)}<small>%</small></strong><span>less rival-time RMSE</span></div><div><strong>${fmt(a.precision*100,1)}<small>%</small></strong><span>loss-alert precision</span></div></div><table class="proof-table"><thead><tr><th>Feature</th><th>PITWALL</th><th>Baseline</th><th>Evidence</th></tr></thead><tbody><tr><td>Lap forecast RMSE</td><td>${fmt(p.rmse_s,3)}s</td><td>${fmt(p.baseline_rmse_s,3)}s</td><td>${p.n.toLocaleString()} forecasts</td></tr><tr><td>Rival forecast RMSE</td><td>${fmt(b.rmse_s,3)}s</td><td>${fmt(b.baseline_rmse_s,3)}s</td><td>${b.n.toLocaleString()} forecasts</td></tr><tr><td>Loss-alert precision</td><td>${fmt(a.precision*100,1)}%</td><td>${fmt(base.precision*100,1)}%</td><td>Recall ${fmt(a.recall*100,1)}%</td></tr><tr><td>Pre-stop pace RMSE</td><td>${fmt(d.rmse_s,3)}s</td><td>${fmt(d.baseline_rmse_s,3)}s</td><td>${d.n} stops / small gain</td></tr></tbody></table><div class="proof-protocol"><span>01 / Train on earlier races</span><span>02 / Select on development</span><span>03 / Freeze architecture</span><span>04 / Score later outcomes</span></div><p class="mission-footnote">${p.scored_forecasts.toLocaleString()} / ${p.issued_forecasts.toLocaleString()} issued pace forecasts and ${b.scored.toLocaleString()} / ${b.issued.toLocaleString()} rival forecasts are scoreable. Stops and neutralisations interrupt the target. Four reused evaluation races; no claim of places gained.</p><div class="proof-links"><a href="pitch.html" target="_blank" rel="noopener">Open presentation ↗</a><a href="../artifacts/demo/intelligence/report.json" target="_blank" rel="noopener">Pace evidence ↗</a><a href="../artifacts/demo/intelligence/decision_report.json" target="_blank" rel="noopener">Stop evidence ↗</a></div>`;
}
