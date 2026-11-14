/* Measured lap inputs and timestamped cached positions; no invented race motion. */
let consoleRound=null, circuitPath=null, circuitLength=0, circuitCars=[], circuitFrame=0;
const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)');
const isNumber=v=>typeof v==='number' && Number.isFinite(v);
const displayNumber=(v,n=1,suffix='')=>isNumber(v)?v.toFixed(n)+suffix:'Unavailable';
const tyreColors={SOFT:'#ff585d',MEDIUM:'#e8ce54',HARD:'#e7e9e7',INTERMEDIATE:'#70bc86',WET:'#669ded'};

function initConsole(){
  initMission();
  initOperations();
  initClockForecast();
  $('#c-run').onclick=()=>{setMissionView('circuit');document.body.classList.add('focus-console');$('#o-focus').textContent='Exit focus ↙';$('#c-speed').value='1';$('#c-loop').checked=true;if(!playback)$('#r-play').click();$('#s-replay').scrollIntoView({block:'start'});};
  for(const [id,delta] of [['c-prev',-1],['c-next',1]]) $('#'+id).onclick=()=>{
    const slider=$('#r-lap');slider.value=Math.max(1,Math.min(+slider.max,+slider.value+delta));drawReplay();
  };
  $('#c-strategy').onclick=()=>$('#operations').scrollIntoView({behavior:reducedMotion.matches?'instant':'smooth',block:'start'});
  $('#c-speed').onchange=()=>{if(playback){$('#r-play').click();$('#r-play').click();}};
  $('#r-rows').addEventListener('click',event=>{
    const row=event.target.closest('[data-driver]');
    if(row){$('#i-driver').value=row.dataset.driver;drawIntelligence();}
  });
  requestAnimationFrame(animateCircuit);
}

function buildCircuit(){
  consoleRound=RREPLAY.round;circuitCars=[];circuitPath=null;
  const svg=$('#c-track');svg.replaceChildren();
  const points=RREPLAY.circuit?.xy;
  if(!points || points.length<3){
    const label=svgEl('text',{x:400,y:245,'text-anchor':'middle',fill:'#a4aaa7','font-size':17});
    label.textContent='Reliable circuit geometry unavailable';svg.append(label);return;
  }
  const xx=points.map(p=>p[0]),yy=points.map(p=>p[1]);
  const xmin=Math.min(...xx),xmax=Math.max(...xx),ymin=Math.min(...yy),ymax=Math.max(...yy);
  const scale=Math.min(730/Math.max(1,xmax-xmin),410/Math.max(1,ymax-ymin));
  circuitMap=(x,y)=>[400+(x-(xmin+xmax)/2)*scale,245-(y-(ymin+ymax)/2)*scale];
  const mapped=points.map(p=>circuitMap(...p));
  const d=mapped.map((p,i)=>(i?'L':'M')+p.map(v=>v.toFixed(2)).join(',')).join(' ')+' Z';
  for(const [stroke,width,dash] of [['#030707',28,null],['#38453d',21,null],['#87957b',17,'5 7'],['#202b29',13,null],['#57665d',.7,'4 8']]){
    const path=svgEl('path',{d,fill:'none',stroke,'stroke-width':width,'stroke-linejoin':'round','stroke-linecap':'round'});
    if(dash)path.setAttribute('stroke-dasharray',dash);svg.append(path);circuitPath=path;
  }
  circuitLength=circuitPath.getTotalLength();
  const start=circuitPath.getPointAtLength(0),next=circuitPath.getPointAtLength(3);
  const flag=svgEl('g',{transform:`translate(${start.x},${start.y}) rotate(${Math.atan2(next.y-start.y,next.x-start.x)*180/Math.PI})`});
  for(let x=0;x<2;x++)for(let y=0;y<4;y++)flag.append(svgEl('rect',{x:x*4-4,y:y*4-8,width:4,height:4,fill:(x+y)%2?'#eef0e7':'#101516'}));
  svg.append(flag);
  const label=svgEl('text',{x:start.x+13,y:start.y-17,fill:'#87958e','font-size':9,'font-family':'Consolas,monospace'});
  label.textContent='START / FINISH';svg.append(label);
}

function updateCars(rows,driver){
  if(!circuitPath)return;
  circuitCars.forEach(car=>{car.group.remove();car.label?.remove();car.trail?.remove();});
  const svg=$('#c-track');
  circuitCars=(RREPLAY.drivers||[]).map(d=>rows.find(r=>r.driver===d)||{driver:d,position:'—'}).map((row,i)=>{
    const selected=row.driver===driver,color=selected?'#e6fc74':tyreColors[row.compound]||'#87958e';
    const group=svgEl('g',{'aria-label':`Inspect ${row.driver}, position ${row.position}`,role:'button',tabindex:0,style:'cursor:pointer',opacity:selected?1:.8});
    const inspect=()=>{$('#i-driver').value=row.driver;drawIntelligence();};
    group.addEventListener('click',inspect);group.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();inspect();}});
    if(selected)group.append(svgEl('circle',{r:15,fill:'#e6fc7418',stroke:'#e6fc7460','stroke-width':1}));
    for(const y of [-5,4])for(const x of [-5,4])group.append(svgEl('rect',{x,y,width:4,height:2.8,rx:.7,fill:'#070b0b',stroke:'#819287','stroke-width':.5}));
    group.append(svgEl('path',{d:'M-8,-4 L-5,-4 L-5,-2 L3,-2 L8,-1 L8,1 L3,2 L-5,2 L-5,4 L-8,4 Z',fill:color}));
    group.append(svgEl('rect',{x:6,y:-4,width:2,height:8,rx:.5,fill:color}));
    group.append(svgEl('rect',{x:-2,y:-1.1,width:3,height:2.2,rx:1,fill:'#141b18'}));
    // Nose, front/rear wings, four slicks, sidewalls, cockpit and halo.
    group.append(svgEl('path',{d:'M-6,-2 L-2,-3.4 L2,-2.5 L6,-.8 L6,.8 L2,2.5 L-2,3.4 L-6,2 Z',fill:color,stroke:'#e7ece2','stroke-width':.35}));
    for(const x of [-5,4])for(const y of [-5.6,3.7]){
      group.append(svgEl('rect',{x,y,width:4,height:2.5,rx:.8,fill:'#060908',stroke:'#89928a','stroke-width':.45}));
      group.append(svgEl('line',{x1:x+.5,x2:x+3.5,y1:y+1.2,y2:y+1.2,stroke:tyreColors[row.compound]||'#aaa','stroke-width':.6}));
    }
    group.append(svgEl('ellipse',{cx:-.6,cy:0,rx:2.5,ry:1.6,fill:'#0a100e',stroke:'#aeb8ac','stroke-width':.55}));
    group.append(svgEl('circle',{cx:-.7,cy:0,r:.8,fill:'#ecebd9'}));
    group.append(svgEl('path',{d:'M1.5,-1.7 L2,0 L1.5,1.7 M2,0 L3,0',fill:'none',stroke:'#bec6be','stroke-width':.6}));
    group.append(svgEl('rect',{x:-8.6,y:-4.2,width:1.3,height:8.4,rx:.4,fill:color,stroke:'#aeb7aa','stroke-width':.4}));
    const title=svgEl('title');title.textContent=`${row.driver} · P${row.position} · ${row.compound}`;group.append(title);svg.append(group);
    let label=svgEl('text',{fill:selected?'#e6fc74':'#bcc5bf','font-size':selected?15:10,'font-family':'Consolas,monospace','font-weight':'bold','paint-order':'stroke',stroke:'#0d1112','stroke-width':4,'pointer-events':'none'});
    label.textContent=row.driver;svg.append(label);
    let trail=null;if(selected){trail=svgEl('polyline',{fill:'none',stroke:'#e6fc74','stroke-width':4,'stroke-opacity':.45,'stroke-linecap':'round'});svg.append(trail);}
    return {group,label,trail,driver:row.driver,selected};
  });
  const selected=circuitCars.find(c=>c.selected);if(selected)svg.append(selected.group,selected.label);
  placeCars();
}

function placeCars(){
  positionMeasuredCars();
}

function animateCircuit(time){
  const dt=circuitFrame?Math.min(time-circuitFrame,100):0;circuitFrame=time;
  if(playback&&!document.hidden&&!$('#s-replay').hidden)advanceRaceClock(dt);
  if(RREPLAY&&(playback||time-feedLastPaint>250)){
    updateFeedSamples();
    if(!reducedMotion.matches||time-feedLastPaint>200)placeCars();
    if(time-feedLastPaint>200){paintFeedReadouts();feedLastPaint=time;}
  }
  requestAnimationFrame(animateCircuit);
}

function clearConsole(message){
  adaptivePaintKey='';
  for(const id of ['a-chart','m-forecast-chart','i-chart'])$('#'+id).replaceChildren();
  for(const id of ['a-next','a-clock','m-clock','i-live-clock','flow-context','tyre-age-basis','a-ticket'])$('#'+id).textContent=message;
  $('#a-lock').disabled=true;$('#a-unlock').disabled=!missionTicket;$('#a-progress').style.transform='scaleX(0)';
  RPITCLOCK=null;livePlan=null;clockPaintKey='';$('#live-chain').textContent=message;$('#live-results').textContent='Waiting for timestamped outcomes';
  RCLOCK=null;$('#clock-proof').textContent='';$('#clock-basis').textContent=message;
  clearOperations(message);RMOTION=null;raceClock=null;feedSamples={};circuitMap=null;
  if(typeof clearMission==='function')clearMission(message);
  circuitPath=null;circuitCars=[];consoleRound=null;$('#c-track').replaceChildren();
  for(const id of ['c-pace','c-position','c-trend','c-compound','c-age','c-rival','c-track-temp','c-air-temp','c-traffic','c-gap','c-track-length','c-weather-quality','c-traffic-quality','c-model-status','c-risk','i-engineer-source']) $('#'+id).textContent='—';
  $('#i-engineer').textContent=message;$('#c-call').textContent='Feed unavailable';$('#c-interval').textContent=message;
  $('#i-chart').replaceChildren();$('#c-environment').replaceChildren();$('#r-stops').replaceChildren();
  paintFeedReadouts();
}

function drawConsole(){
  if(!RREPLAY || !RINTEL)return;
  syncRaceClock();updateFeedSamples();
  if(consoleRound!==RREPLAY.round)buildCircuit();
  const lap=+$('#r-lap').value,driver=$('#i-driver').value,state=selectedSnapshot();
  const rows=RREPLAY.laps_data.filter(r=>r.lap===lap).sort((a,b)=>(a.position??99)-(b.position??99));
  const row=rows.find(r=>r.driver===driver),forecast=state?.forecasts.find(f=>f.horizon===1);
  $('#c-event').textContent=RREPLAY.event.replace('Grand Prix','GP');
  $('#c-progress').textContent=Math.round(lap/RREPLAY.laps*100)+'%';
  $('#c-track-length').textContent=displayNumber(RREPLAY.circuit?.length_m/1000,3,' km');
  $('#c-follow').textContent=driver+' / SCHEMATIC POSITION';
  $('#c-pace').innerHTML=forecast?`${fmt(forecast.pace_s,2)}<small>s</small>`:'—<small>s</small>';
  $('#c-interval').textContent=forecast?isNumber(forecast.lower_s)?`90% interval ${fmt(forecast.lower_s,2)}–${fmt(forecast.upper_s,2)} s`:'Interval calibration warming up':'Waiting for representative laps';
  $('#c-position').textContent=isNumber(row?.position)?'P'+row.position:'—';
  $('#c-trend').textContent=state?`${state.pace_trend_s_per_lap>=0?'+':''}${fmt(state.pace_trend_s_per_lap,3)} s/lap`:'—';
  $('#c-compound').textContent=row?.compound||'UNAVAILABLE';$('#c-compound-letter').textContent=row?.compound?.[0]||'—';
  $('#c-age').textContent=isNumber(row?.tyre_age)?`${row.tyre_age} laps on tyre`:'No tyre observation';
  $('#c-tyre-icon').style.setProperty('--tyre-color',tyreColors[row?.compound]||'#87958e');
  $('#c-track-temp').textContent=displayNumber(row?.track_temp_c,1,'°C');
  $('#c-air-temp').textContent=displayNumber(row?.air_temp_c,1,'°C');
  const traffic=row?.traffic_observed && isNumber(row.frac_close);
  $('#c-traffic').textContent=traffic?displayNumber(row.frac_close*100,0,'%'):'No feed';
  $('#c-gap').textContent=traffic?displayNumber(row.gap_med_s,2,' s'):'No feed';
  $('#c-weather-quality').textContent=isNumber(row?.track_temp_c)?`${fmt(row.weather_age_s,0)} s old`:'Unavailable';
  $('#c-traffic-quality').textContent=traffic?isNumber(row.traffic_coverage)?`${fmt(row.traffic_coverage*100,0)}% of lap`:'Observed':'Unavailable';
  $('#c-model-status').textContent=state?'Through R'+RINTEL.training_through_round:'Collecting laps';
  const battle=state?.battles?.find(b=>b.horizon===3)||state?.battles?.[0];
  $('#c-rival').textContent=battle?`${battle.rival} / ${battle.predicted_loss_s>=0?'+':''}${fmt(battle.predicted_loss_s,2)} s`:'No rival forecast';
  $('#c-risk').textContent=battle?`Relative time loss over ${battle.horizon} laps. ${isNumber(battle.lower_s)?`Range ${fmt(battle.lower_s,2)} to ${fmt(battle.upper_s,2)} s.`:'Interval not yet calibrated.'} Positive means losing time.`:'A supported opponent forecast will appear when enough green laps are observed.';
  $('#c-call').textContent=!row?'No timing observation.':!state?'Collecting clean running.':battle?.lower_s>0?'Rival pace is a threat.':traffic&&row.frac_close>.4?'Traffic is a factor.':'Monitor the next stint laps.';
  $('#c-environment').innerHTML=[['Track temperature',displayNumber(row?.track_temp_c,1,' °C')],['Air temperature',displayNumber(row?.air_temp_c,1,' °C')],['Humidity',displayNumber(row?.humidity_pct,0,' %')],['Wind speed',displayNumber(row?.wind_speed_ms,1,' m/s')],['Rainfall sensor',row?.rainfall===true?'Rain reported':row?.rainfall===false?'No rain reported':'Unavailable'],['Time within 2.5s',traffic?displayNumber(row.frac_near*100,0,' % of lap'):'Unavailable'],['Weather sample age',displayNumber(row?.weather_age_s,0,' seconds')]].map(([label,value])=>`<div class="env-row"><span>${label}</span><b>${value}</b></div>`).join('');
  $('#r-rows').querySelectorAll('[data-driver]').forEach(el=>el.classList.toggle('selected',el.dataset.driver===driver));
  updateCars(rows,driver);
  paintFeedReadouts();
}

function updatePlaybackLabel(){
  $('#c-motion').textContent=playback?'▶ REPLAY RUNNING':'Ⅱ REPLAY PAUSED';
}

function showConditionsEvidence(report){
  const ablation=report.environmental_ablation?{[report.selected_model]:{development_mse:report.candidate_development_mse[report.selected_model],rmse_s:report.rmse_s},...report.environmental_ablation}:null;
  const usesConditions=['weather_model','traffic_model','conditions_model','conditions_blend'].includes(report.selected_model);
  $('#c-conditions-evidence').innerHTML=`<div class="eyebrow">MEASURE. COMPARE. VALIDATE.</div><p class="note">${ablation?'Temperature and traffic candidates are compared using earlier-race training.':'Environmental model comparison not yet available.'} Deployed: ${report.selected_model.replaceAll('_',' ')}.${usesConditions?'':' Weather and traffic are shown as engineer context; the selected pace model does not directly use these sensor features.'}</p><button class="evidence-link" id="c-evidence-link">Inspect the model comparison ↗</button>`;
  $('#c-evidence-link').onclick=()=>$('#nav [data-t="validation"]').click();
  if(ablation){
    const section=document.createElement('div');section.className='environment-proof';
    section.innerHTML=`<h3>Temperature & traffic: measured contribution</h3><p class="note">Coverage among issued forecast requests: weather ${fmt(report.condition_coverage.weather*100,1)}%, traffic ${fmt(report.condition_coverage.traffic*100,1)}%. Missing measurements have explicit indicators. Model choice uses development races; this reused evaluation set is descriptive.</p><table><thead><tr><th>Inputs / candidate</th><th>Development MSE</th><th>Evaluation RMSE</th></tr></thead><tbody>${Object.entries(ablation).map(([name,s])=>`<tr><td>${name.replaceAll('_',' ')}</td><td>${fmt(s.development_mse,4)}</td><td>${fmt(s.rmse_s,3)} s</td></tr>`).join('')}</tbody></table>`;
    $('#i-validation').append(section);
  }
}
