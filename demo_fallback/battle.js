/* The browser mirrors pitwall.battle.attack_budget; cross-runtime tested. */
function attackBudget(step, battle, costs){
  const h=battle.horizon;
  const gain=h*step.step_s-battle.predicted_loss_s-costs.warmup-costs.service-costs.decay*h*(h-1)/2;
  const margin=gain-costs.gap-costs.traffic;
  const radius=h*step.radius_s+battle.radius_s;
  return {horizon:h,margin_s:margin,lower_margin_s:margin-radius,upper_margin_s:margin+radius,
    required_step_s:(costs.gap+battle.predicted_loss_s+costs.warmup+costs.service+costs.traffic+costs.decay*h*(h-1)/2)/h};
}
if(typeof module!=='undefined')module.exports={attackBudget};

async function initBattle(){
  ['gap','warmup','traffic','service','decay','hard','medium','soft'].forEach(id=>
    $('#b-'+id).addEventListener('input',drawBattle));
  try{
    const report=await getJSON('intelligence/battle_report.json');
    const a=report.alerts.selected_s,b=report.alerts[report.baseline];
    $('#b-proof').innerHTML=`<div><b>${fmt(report.improvement_pct,1)}%</b>less relative-time RMSE</div>
      <div><b>${fmt(a.precision*100,1)}%</b>2-second loss alert precision</div>
      <div><b>${report.n.toLocaleString()}</b>scored rival forecasts</div>
      <div><b>R09–R12</b>reused evaluation races</div>`;
    $('#b-validation').innerHTML=`<h3>Opponent-relative evidence</h3>
      <p class="sub">The rival is selected from the running order when the forecast is issued.
        Both cars must continue their stints under green flags. ${report.scored.toLocaleString()} of
        ${report.issued.toLocaleString()} issued forecasts could be scored; interruptions are excluded.</p>
      <table><thead><tr><th>Metric</th><th>PITWALL</th><th>${report.baseline.replaceAll('_',' ')}</th></tr></thead><tbody>
        <tr><td>Relative-time RMSE</td><td>${fmt(report.rmse_s,3)} s</td><td>${fmt(report.baseline_rmse_s,3)} s</td></tr>
        <tr><td>Loss-alert precision</td><td>${fmt(a.precision*100,1)}%</td><td>${fmt(b.precision*100,1)}%</td></tr>
        <tr><td>Loss-alert recall</td><td>${fmt(a.recall*100,1)}%</td><td>${fmt(b.recall*100,1)}%</td></tr>
        <tr><td>Loss-alert AUC</td><td>${fmt(a.auc,3)}</td><td>${fmt(b.auc,3)}</td></tr></tbody></table>
      <p class="note">Race-block bootstrap interval for RMSE improvement:
        ${report.improvement_event_bootstrap_95.map(v=>fmt(v,1)+'%').join(' to ')}.
        Selection used rounds 7–8. Four reused evaluation races provide preliminary evidence.
        Nominal 90% relative-time intervals covered about ${fmt(100*report.horizons[0].coverage,1)}–${fmt(100*report.horizons[1].coverage,1)}%.
        These results measure forecast quality; no observed race-time saving or position gain is claimed.</p>`;
  }catch(error){$('#b-proof').textContent='Battle evidence unavailable: '+error.message;}
  drawBattle();
}

function drawBattle(){
  if(typeof RINTEL==='undefined'||!RINTEL)return;
  const state=selectedSnapshot(),costs={};
  ['gap','warmup','traffic','service','decay'].forEach(id=>{
    costs[id]=+$('#b-'+id).value;
    $('#b-'+id+'-v').textContent=fmt(costs[id],2)+(id==='decay'?' s/lap':' s');
  });
  const battles=state?.battles||[],L=+$('#r-lap').value,driver=$('#i-driver').value;
  const defence=state?.defence?.at(-1);
  $('#b-defence').hidden=!defence;
  if(defence){
    $('#b-defence').textContent=`Pressure from behind: ${defence.rival} is forecast to `+
      `${defence.predicted_closing_s>=0?'close':'lose'} ${fmt(Math.abs(defence.predicted_closing_s),2)} s over ${defence.horizon} laps. `+
      (defence.radius_s==null?'Collecting calibration.':`Closing-time range: ${fmt(defence.lower_s,2)} to ${fmt(defence.upper_s,2)} s. `)+
      'Both cars continue under green flags; this is not a pass probability.';
  }
  $('#b-context').textContent=`Round ${RINTEL.round} / lap ${L} / ${driver}. Change driver, lap or event in Race replay.`;
  $('#b-plans').replaceChildren();$('#b-chart').replaceChildren();
  if(!battles.length){
    $('#b-loss').textContent='Unavailable';$('#b-range').textContent='No forecastable car ahead for this driver and lap.';
    $('#b-interpretation').textContent='A leader, pit lap, neutralisation or insufficient observations can leave no supported comparison.';
    $('#b-verdict').textContent='Wait for evidence';$('#b-plan-note').textContent='No later-race or future-lap fallback is used.';
  }else{
    const last=battles.at(-1),loss=last.predicted_loss_s;
    $('#b-loss').textContent=`${loss>=0?'+':''}${fmt(loss,2)} s`;
    $('#b-loss').style.color=loss>0?'var(--warn)':'var(--good)';
    $('#b-range').textContent=`${driver} versus ${last.rival}, over ${last.horizon} laps. `+
      (last.radius_s==null?'Collecting calibration.':`Empirical range: ${fmt(last.lower_s,2)} to ${fmt(last.upper_s,2)} s.`);
    $('#b-interpretation').textContent=(loss>2?'Review strategy: the central forecast exceeds a two-second relative-loss budget. ':'')+
      'Positive means time lost to the rival; negative means time gained. '+
      'Both cars continue their present stints under green flags. Actual overtakes and track gaps are not inferred.';
    const values=battles.flatMap(b=>[b.predicted_loss_s,b.lower_s,b.upper_s].filter(v=>v!=null));
    const yr=nice(Math.min(0,...values)-.5,Math.max(0,...values)+.5);
    const {s,plot}=chart(750,240,{l:62,r:30,t:18,b:42});
    const {X,Y}=axes(s,plot,[0,6],yr,'laps ahead','relative seconds');
    s.appendChild(svgEl('line',{x1:X(0),x2:X(6),y1:Y(0),y2:Y(0),stroke:'#6b7280','stroke-dasharray':'4 4'}));
    battles.forEach(b=>{
      if(b.radius_s!=null)s.appendChild(svgEl('line',{x1:X(b.horizon),x2:X(b.horizon),y1:Y(b.lower_s),y2:Y(b.upper_s),stroke:'#3fa7dc','stroke-width':8,'stroke-opacity':.3}));
      s.appendChild(svgEl('circle',{cx:X(b.horizon),cy:Y(b.predicted_loss_s),r:5,fill:'#3fa7dc'}));
    });
    $('#b-chart').append(s);
    const plans=[];
    for(const [compound,step] of Object.entries(state.stop_scenarios||{})){
      if(!$('#b-'+compound.toLowerCase())?.checked||!step.supported||step.extrapolating||step.radius_s==null||step.training_stops<5)continue;
      const cases=battles.filter(b=>b.radius_s!=null).map(b=>attackBudget(step,b,costs));
      if(cases.length)plans.push({compound,cases,worst:Math.min(...cases.map(c=>c.lower_margin_s))});
    }
    plans.sort((a,b)=>b.worst-a.worst);
    if(plans.length){
      const best=plans[0];
      $('#b-verdict').textContent=best.worst>0?`${best.compound}: positive across tested responses`:
        'No attack clears the full stress range';
      $('#b-plans').innerHTML=plans.flatMap(p=>p.cases.map(c=>`<tr>
        <td>${p.compound}</td><td>${c.horizon} laps</td><td>${fmt(c.margin_s,2)} s</td>
        <td>${fmt(c.lower_margin_s,2)} to ${fmt(c.upper_margin_s,2)} s</td></tr>`)).join('');
      $('#b-plan-note').textContent=`${best.compound} ranks first by its worst-case margin across available 3/5-lap responses. `+
        'A positive budget is extra delay the scenario can absorb; a negative budget is a shortfall. '+
        'This ranking is conditional on your inputs and inventory, not a command to pit.';
    }else{
      $('#b-verdict').textContent='No supported compound plan';
      $('#b-plan-note').textContent='Choose an available legal tyre. Plans need at least five earlier stops, a supported tyre age and calibrated uncertainty.';
    }
  }
  const done=(RINTEL.battle_evaluation||[]).filter(r=>r.driver===driver&&r.target_lap<=L);
  $('#b-resolved').textContent=`${done.length} resolved comparisons for ${driver} by lap ${L}. Future outcomes stay hidden.`;
  $('#b-history').innerHTML=done.slice(-6).reverse().map(r=>`<tr><td>${r.issued_lap}</td><td>${r.target_lap}</td>
    <td>${r.rival}</td><td>${fmt(r.predicted_s,2)} s</td><td>${fmt(r.actual_s,2)} s</td></tr>`).join('');
}
