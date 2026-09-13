/* One rolling chart and audit ticket, shared by circuit and detailed telemetry. */
let adaptivePaintKey='',comparisonContext='',comparisonSeen=null;
function initAdaptiveForecast(){
  $('#a-play').onclick=()=>$('#r-play').click();
  $('#a-demo').onclick=()=>{$('#c-speed').value='10';if(!playback)$('#r-play').click();drawClockForecast();};
  $('#a-realtime').onclick=()=>{$('#c-speed').value='1';if(!playback)$('#r-play').click();drawClockForecast();};
  $('#a-lock').onclick=()=>{
    missionTicket=freezeClockForecast(RCLOCK,RREPLAY,$('#i-driver').value,raceClock,1);
    drawClockForecast();
  };
  for(const id of ['a-unlock','m-unlock'])$('#'+id).onclick=()=>{missionTicket=null;drawClockForecast();};
  document.querySelectorAll('[data-flow]').forEach(button=>button.onclick=()=>{
    setMissionView('circuit');
    document.querySelectorAll('.flow-steps [data-flow]').forEach(b=>{if(b.dataset.flow===button.dataset.flow)b.setAttribute('aria-current','step');else b.removeAttribute('aria-current');});
    const target=$('#'+button.dataset.flow);
    target.scrollIntoView({block:'start',behavior:reducedMotion.matches?'instant':'smooth'});
    target.focus({preventScroll:true});
  });
}

function adaptiveChart(data){
  const {s,plot}=chart(800,280,{l:58,r:25,t:28,b:42});
  const model=clockComparison(data);
  s.setAttribute('role','img');s.setAttribute('aria-label',`Live accuracy comparison through lap ${data.lap}. Blue: predictions issued before the lap. White: observed lap times. Paired points reveal prediction error.`);
  const values=model.rows.flatMap(r=>[r.predicted_s,r.actual_s]);
  if(model.pending)values.push(model.pending.pace_s);
  if(!values.length){const t=svgEl('text',{x:400,y:125,'text-anchor':'middle',fill:'#aab7ac','font-size':14});t.textContent='First comparison appears when a forecast lap finishes';s.append(t);return s;}
  // Negative tick count skips fixed lap labels; scrolling labels are drawn below.
  const {X,Y}=axes(s,plot,[model.minLap,model.maxLap],nice(Math.min(...values)-.25,Math.max(...values)+.25),'completed driver lap','lap time / s',-1,4);
  // The viewport scrolls on the shared race clock. Only received actuals are drawn.
  const viewport=svgEl('svg',{x:plot.l,y:plot.t,width:plot.w,height:plot.h,viewBox:`${plot.l} ${plot.t} ${plot.w} ${plot.h}`,overflow:'hidden'});
  const trace=svgEl('g',{'data-comparison-scroll':'','data-span':X(model.minLap+1)-X(model.minLap)});viewport.append(trace);s.append(viewport);
  const label=(parent,x,y,text,color,anchor='start')=>{const t=svgEl('text',{x,y,fill:color,'font-size':11,'font-family':'Consolas,monospace','text-anchor':anchor});t.textContent=text;parent.append(t);};
  const segment=(a,b,key,color,reveal=false)=>{
    if(b.target_lap!==a.target_lap+1)return;
    trace.append(svgEl('path',{d:`M${X(a.target_lap)},${Y(a[key])} L${X(b.target_lap)},${Y(b[key])}`,fill:'none',stroke:color,'stroke-width':2.5,pathLength:1,...(reveal?{class:'comparison-arrival'}:{})}));
  };
  model.rows.forEach((r,i)=>{
    if(i){segment(model.rows[i-1],r,'predicted_s','#62b8ed');segment(model.rows[i-1],r,'actual_s','#f2f3ec',r===model.latest&&data.animateArrival);}
    trace.append(svgEl('line',{x1:X(r.target_lap),x2:X(r.target_lap),y1:Y(r.predicted_s),y2:Y(r.actual_s),stroke:'#bdcdab','stroke-opacity':.45,'stroke-width':1.5}));
    for(const [key,color] of [['predicted_s','#62b8ed'],['actual_s','#f2f3ec']]){
      const point=svgEl('circle',{cx:X(r.target_lap),cy:Y(r[key]),r:r===model.latest?4.5:3,fill:color,...(r===model.latest&&key==='actual_s'&&data.animateArrival?{class:'comparison-point'}:{})});
      const title=svgEl('title');title.textContent=`L${r.target_lap}: predicted ${fmt(r.predicted_s,3)}s / observed ${fmt(r.actual_s,3)}s / error ${fmt(Math.abs(r.predicted_s-r.actual_s),3)}s`;point.append(title);trace.append(point);
    }
  });
  if(model.pending){
    const p=model.pending,last=model.rows.at(-1);
    if(last&&last.target_lap+1===p.target_lap)trace.append(svgEl('path',{d:`M${X(last.target_lap)},${Y(last.predicted_s)} L${X(p.target_lap)},${Y(p.pace_s)}`,fill:'none',stroke:'#62b8ed','stroke-width':2.5,'stroke-dasharray':'5 4'}));
    trace.append(svgEl('circle',{cx:X(p.target_lap),cy:Y(p.pace_s),r:5,fill:'#111916',stroke:'#62b8ed','stroke-width':2}));
    label(trace,X(p.target_lap)-8,Y(p.pace_s)-12,'AWAITING ACTUAL','#62b8ed','end');
  }
  const ticks=svgEl('g',{'data-comparison-scroll':'','data-span':X(model.minLap+1)-X(model.minLap)});
  for(let lap=model.minLap+1;lap<=model.maxLap;lap++)label(ticks,X(lap),plot.t+plot.h+21,'L'+lap,'#a3b199','middle');
  s.append(ticks);
  label(s,plot.l,16,'PREDICTED vs OBSERVED / NEXT-LAP FORECASTS','#b9c7af');
  return s;
}

function drawAdaptiveForecast(){
  if(!RREPLAY)return;
  const driver=$('#i-driver').value,d=clockSeries(RCLOCK,RREPLAY,driver,raceClock,missionTicket),s=d.state;
  const key=[RREPLAY.round,driver,d.lap,s?.issued_s,d.score.n,d.readiness,missionTicket?.issued_s,missionTicket?.target_lap,missionView].join(':');
  const next=d.forecasts.find(f=>f.horizon===1);
  const reason={no_timing:'Waiting for the first timing observation',finished:'Driver has completed the race',stale:'Timing is over 180s old; waiting for a fresh observation',pit:'Pit / out-lap received. Collecting three representative laps on the new set',neutralised:'Flag interruption. Rebuilding the pace estimate after green running returns',warming:`New stint / restart: ${d.cleanCount} of 3 representative laps received`,unavailable:'No supported model snapshot at this timestamp; earlier rounds may still be training',ready:'New model output at each completed driver lap'}[d.readiness];
  const status=!playback?'PAUSED':s?'LIVE REPLAY':'TIMING LIVE / MODEL WAITING';
  const elapsed=next?`${fmt(d.elapsed_s,1)}s since issue · about ${fmt(Math.max(0,next.pace_s-d.elapsed_s),0)}s to predicted lap completion`:`${reason}${d.current?' · '+fmt(Math.max(0,raceClock-d.current.completed_s),1)+'s since last timing':''}`;
  $('#a-readiness').textContent=next?`Blue predicts L${next.target_lap} before it finishes. White reveals the observed time at the finish line; the distance between them is the forecast error. Race + comparison: ${$('#c-speed').value}×.`:reason+'. The comparison retains all resolved predictions and observations.';
  $('#a-play').textContent=playback?'Pause race & forecast':'Play race & forecast';
  $('#a-demo').setAttribute('aria-pressed',$('#c-speed').value==='10');$('#a-realtime').setAttribute('aria-pressed',$('#c-speed').value==='1');
  for(const id of ['a-clock','m-clock','i-live-clock'])$('#'+id).textContent=`${status} / ${formatRaceTime(raceClock)} · ${elapsed}`;
  $('#a-progress').style.transform=`scaleX(${d.progress})`;
  $('#a-live-status').textContent=`${status} / ${driver}`;
  $('#a-live-status').classList.toggle('running',!!playback&&!!s);
  $('#a-lock').disabled=!s;$('#a-lock').textContent=missionTicket?'Replace with next lap':'Lock next lap for audit';$('#a-unlock').disabled=!missionTicket;
  const audit=d.audit;
  $('#a-ticket').textContent=d.pinned?`AUDIT LOCK / ${driver} L${d.pinned.target_lap}: ${fmt(d.pinned.predicted_s,3)}s · ${audit.status==='resolved'?`actual ${fmt(audit.actual_s,3)}s · error ${fmt(audit.error_s,3)}s`:audit.status==='interrupted'?'interrupted by pit, neutralisation or missing data':`awaiting completion · live forecast continues`}`:missionTicket?'Audit belongs to another driver, race or later issue time. Return to its context or release the lock.':'Lock an issued prediction to audit it. The live chart and race keep moving; the actual unlocks at lap completion.';
  $('#flow-context').textContent=`${driver} / ${d.current?.compound||'NO TYRE FEED'} / ${d.current?.tyre_age??'—'} LAPS · ${formatRaceTime(raceClock)} · ONE DRIVER CLOCK`;
  const updateCursor=()=>document.querySelectorAll('[data-comparison-scroll]').forEach(trace=>trace.setAttribute('transform',`translate(${-Number(trace.dataset.span)*d.progress},0)`));
  if(key===adaptivePaintKey){updateCursor();return;}adaptivePaintKey=key;
  const context=RREPLAY.round+':'+driver;
  d.animateArrival=comparisonContext===context&&comparisonSeen!==null&&d.score.latest?.target_s>comparisonSeen;
  comparisonContext=context;comparisonSeen=d.score.latest?.target_s??null;
  for(const id of ['a-chart','m-forecast-chart','i-chart']){
    const target=$('#'+id);target.replaceChildren(adaptiveChart(d));target.dataset.issuedLap=s?.lap||'';target.dataset.driver=driver;
  }
  updateCursor();
  $('#a-next').textContent='Predicted vs observed pace';
  drawComparisonScore(d);
  $('#i-title').textContent=s?`${driver} / ${s.compound} / age ${s.tyre_age}`:`${driver} / observing`;
  $('#i-basis').textContent='Each blue point was issued before its target lap. White points and error connectors appear only when the actual lap resolves. Gaps indicate interrupted or unavailable forecasts. The rolling view shares the race clock.';
  $('#i-trend').textContent=s?`Recent pace trend ${recoverySigned(s.pace_trend_s_per_lap)}s/lap. Tyres, fuel, traffic and track evolution all affect pace; this is not physical wear.`:'';
  $('#i-score').innerHTML=`<div><b>${d.score.n}</b>${driver} next-lap forecasts resolved</div><div><b>${fmt(d.score.rmse,3)}s</b>driver model RMSE so far</div><div><b>${fmt(d.score.baseline_rmse,3)}s</b>driver persistence RMSE so far</div><div><b>${RCLOCK?'R'+RCLOCK.training_through_round:'—'}</b>last training race</div>`;
  const current=d.current;
  $('#tyre-age-basis').textContent=current?`${driver} · recorded tyre age ${current.tyre_age??'unavailable'} laps on ${current.compound||'unknown compound'} at completed L${current.lap}. Age comes from the timing feed, including prior use of the set. It updates on completed laps and follows the new set after a tyre change; no fractional wear is invented.`:'Tyre age waits for a received timing observation.';
}

function drawComparisonScore(data){
  const latest=data.score.latest,next=data.forecasts.find(f=>f.horizon===1);
  const content=latest?`<div class="comparison-result ${data.animateArrival?'result-arrived':''}"><div class="comparison-result-heading"><span>LATEST VERIFIED / ${$('#i-driver').value} LAP ${latest.target_lap}</span><b>${data.score.n} resolved forecasts</b></div><div class="comparison-values"><div><span>PREDICTED BEFORE THE LAP</span><strong class="predicted-value">${fmt(latest.predicted_s,3)}<small>s</small></strong></div><div><span>OBSERVED AT THE FINISH</span><strong>${fmt(latest.actual_s,3)}<small>s</small></strong></div><div><span>ABSOLUTE ERROR</span><strong class="error-value">${fmt(Math.abs(latest.predicted_s-latest.actual_s),3)}<small>s</small></strong></div></div><p>All resolved laps: ${fmt(data.score.rmse,3)}s model RMSE / ${fmt(data.score.baseline_rmse,3)}s persistence RMSE. ${next?`Next: L${next.target_lap} predicted ${fmt(next.pace_s,3)}s · awaiting actual.`:'New forecasts resume after representative running returns.'}</p></div>`:'<p class="audit-note">Waiting for the first scored lap. Predictions appear before the lap; observations unlock at its completion.</p>';
  for(const id of ['a-comparison-score','m-comparison-score'])$('#'+id).innerHTML=content;
}
