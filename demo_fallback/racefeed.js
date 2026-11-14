/* One session clock drives actual cached positions and completed-lap updates. */
let RMOTION=null,raceClock=null,feedLap=null,feedBoundaries=[],feedSamples={},feedLastPaint=0,circuitMap=null;
let motionPath=null,motionRows={};
function setRaceFeed(data){
  RMOTION=data;feedLap=null;raceClock=null;feedSamples={};
  feedBoundaries=PitwallStrategy.boundaryTimes(RREPLAY);
  motionPath=PitwallMotion.geometry(RREPLAY.circuit?.xy,RREPLAY.circuit?.length_m);
  motionRows=Object.fromEntries(Object.entries(data?.drivers||{}).map(([driver,rows])=>[driver,motionPath?PitwallMotion.reconstruct(rows,motionPath.length):[]]));
}
function syncRaceClock(){
  const lap=+$('#r-lap').value;
  if(feedLap!==lap){feedLap=lap;raceClock=feedBoundaries.find(b=>b.lap===lap)?.time??RMOTION?.start_s??null;}
}
function advanceRaceClock(dt){
  if(!RREPLAY||raceClock===null)return;
  raceClock+=dt/1000*(+$('#c-speed').value);
  const end=feedBoundaries.at(-1)?.time??RMOTION?.end_s;
  if(raceClock>=end){
    if($('#c-loop')?.checked){missionTicket=null;feedLap=null;$('#r-lap').value=4;drawReplay();return;}
    raceClock=end;if(playback)$('#r-play').click();
  }
  const latest=feedBoundaries.filter(b=>b.time<=raceClock).at(-1);
  if(latest&&latest.lap!==feedLap){feedLap=latest.lap;$('#r-lap').value=latest.lap;drawReplay();}
}
function formatRaceTime(t){
  if(!isNumber(t))return '—';
  const seconds=Math.max(0,t-(RMOTION?.start_s||0));
  return `${String(Math.floor(seconds/3600)).padStart(2,'0')}:${String(Math.floor(seconds%3600/60)).padStart(2,'0')}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;
}
function updateFeedSamples(){
  feedSamples=Object.fromEntries(Object.entries(motionRows).map(([d,rows])=>[d,PitwallMotion.sample(rows,raceClock,motionPath)]));
}
function paintFeedReadouts(){
  const driver=$('#i-driver').value,s=feedSamples[driver],gap=PitwallStrategy.trafficAt(feedSamples,driver,RREPLAY?.circuit?.length_m);
  $('#f-clock').textContent=formatRaceTime(raceClock);
  const completed=RREPLAY?.laps_data.filter(r=>r.driver===driver&&isNumber(r.completed_s)&&r.completed_s<=raceClock).sort((a,b)=>b.lap-a.lap)[0];
  $('#f-lap-basis').textContent=`${driver} CLOCK L${completed?.lap??'—'} / ARCHIVE CURSOR L${feedLap??'—'}`;
  $('#f-source').textContent=RMOTION?`RECORDED RACE / RECONSTRUCTED MOTION / ${Object.values(feedSamples).filter(v=>v?.ontrack).length} CARS`:'POSITION FEED UNAVAILABLE';
  $('#f-speed').textContent=s&&isNumber(s.speed)?Math.round(s.speed):'—';
  $('#f-gear').textContent=s&&isNumber(s.gear)?s.gear:'—';
  $('#f-throttle').style.width=Math.max(0,Math.min(100,s?.throttle??0))+'%';
  $('#f-brake').style.width=s?.brake?'100%':'0%';
  $('#f-throttle-value').textContent=s&&isNumber(s.throttle)?s.throttle>100?'>100% raw':s.throttle+'%':'—';
  $('#f-throttle-value').title=s&&isNumber(s.throttle)?`Raw source ${s.throttle}%; bar saturates at 100%.`:'';
  $('#f-brake-value').textContent=s&&isNumber(s.brake)?s.brake?'ON':'OFF':'—';
  $('#f-gap').textContent=gap?.ambiguous?`Within position uncertainty / ${gap.driver}`:gap?`${gap.driver} / ~${fmt(gap.gap_s,2)}s`:'No supported forward gap';
  $('#f-gap').classList.toggle('traffic-close',!!gap&&(gap.ambiguous||gap.gap_s<1));
  $('#f-age').textContent=s?`${fmt(s.age,1)}s feed age · ${s.quality}`:'Selected car telemetry unavailable / pit lane';
  $('#c-follow').textContent=driver+' / SPEED + POSITION RECONSTRUCTION';
  drawClockForecast();
}
function positionMeasuredCars(){
  if(!circuitMap)return;
  for(const car of circuitCars){
    const s=feedSamples[car.driver],rows=motionRows[car.driver];
    car.group.setAttribute('visibility',s?.ontrack?'visible':'hidden');
    if(car.trail)car.trail.setAttribute('visibility',s?.ontrack?'visible':'hidden');
    if(car.label)car.label.setAttribute('visibility',s?.ontrack?'visible':'hidden');
    if(!s?.ontrack)continue;
    const p=circuitMap(s.x,s.y);
    const angle=Math.atan2(-s.dy,s.dx)*180/Math.PI;
    car.group.setAttribute('transform',`translate(${p[0]},${p[1]}) rotate(${angle})`);
    if(car.label){
      const overlaps=circuitCars.filter(other=>other.driver!==car.driver&&feedSamples[other.driver]?.ontrack&&Math.hypot(feedSamples[other.driver].x-s.x,feedSamples[other.driver].y-s.y)<60);
      const leader=car.selected||!overlaps.some(o=>o.selected||o.driver<car.driver);
      car.label.setAttribute('visibility',leader?'visible':'hidden');
      car.label.textContent=car.driver+(overlaps.length?' / '+overlaps.map(o=>o.driver).join(' / '):'');
      car.label.setAttribute('x',Math.max(22,Math.min(750,p[0]+17)));car.label.setAttribute('y',Math.max(26,p[1]-16));
    }
    if(car.trail){
      let points=[],previous=null;
      for(const t of Array.from({length:33},(_,i)=>4-i/8)){
        const v=PitwallMotion.sample(rows,raceClock-t,motionPath);
        if(!v?.ontrack){points=[];previous=null;continue;}
        if(previous&&(v.phase<previous.phase||v.phase-previous.phase>30))points=[];
        points.push(circuitMap(v.x,v.y).join(','));previous=v;
      }
      car.trail.setAttribute('points',points.join(' '));
    }
  }
}
