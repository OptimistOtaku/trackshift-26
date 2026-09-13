/* Pure, causal scenario calculations. Every forecast is supplied at the issue lap. */
(function(root){
  const finite=x=>typeof x==='number'&&Number.isFinite(x);
  const median=a=>{const v=[...a].sort((x,y)=>x-y),n=v.length;return n?(v[Math.floor((n-1)/2)]+v[Math.floor(n/2)])/2:null;};
  function sampleAt(rows,time){
    let lo=0,hi=rows.length;
    while(lo<hi){const m=(lo+hi)>>1;if(rows[m][0]<=time)lo=m+1;else hi=m;}
    const i=lo-1,last=rows[i];
    if(!last||time-last[0]+last[9]>2.5)return null;
    // Render at t-1s, using only samples already received at t.
    const old=rows[i-1],mix=old&&last[0]-old[0]<=2?Math.max(0,Math.min(1,(time-1-old[0])/(last[0]-old[0]))):1;
    return {t:last[0],x:old?old[1]+mix*(last[1]-old[1]):last[1],y:old?old[2]+mix*(last[2]-old[2]):last[2],arc:last[3],speed:last[4],gear:last[5],throttle:last[6],brake:last[7],ontrack:!!last[8],age:time-last[0]+last[9]};
  }
  function boundaryTimes(replay){
    const values=new Map();
    for(const row of replay.laps_data)if(finite(row.completed_s))values.set(row.lap,Math.max(values.get(row.lap)||0,row.completed_s));
    let previous=0;
    return [...values].sort((a,b)=>a[0]-b[0]).map(([lap,time])=>({lap,time:previous=Math.max(time,previous)}));
  }
  function trafficAt(samples,driver,length){
    const own=samples[driver];
    if(!own?.ontrack||!finite(own.arc)||!finite(own.speed)||own.speed<30)return null;
    if(!finite(length)||length<=0)return null;
    const overlap=Object.entries(samples).find(([d,s])=>d!==driver&&s?.ontrack&&finite(s.arc)&&
      (Math.hypot(s.x-own.x,s.y-own.y)<10||Math.min(Math.abs(s.arc-own.arc),1-Math.abs(s.arc-own.arc))*length<15));
    if(overlap)return {ambiguous:true,driver:overlap[0],basis:'Position samples overlap within one metre; no gap inferred'};
    const cars=Object.entries(samples).filter(([d,s])=>d!==driver&&s?.ontrack&&finite(s.arc))
      .map(([d,s])=>({driver:d,distance:((s.arc-own.arc+1)%1)*length,uncertainty:(own.uncertainty_m||0)+(s.uncertainty_m||0)})).sort((a,b)=>a.distance-b.distance);
    if(cars.length&&cars[0].distance<=cars[0].uncertainty)return {...cars[0],ambiguous:true,basis:'Reconstructed position ranges overlap'};
    return cars.length?{...cars[0],gap_s:cars[0].distance/(own.speed/3.6),basis:'Projected distance / current speed; approximate physical gap'}:null;
  }
  function paceAt(state,k){
    if(!state||!Number.isInteger(k)||k<1||k>5)return null;
    const exact=state.forecasts.find(f=>f.horizon===k);
    if(exact)return finite(exact.pace_s)?exact.pace_s:null;
    const a=state.forecasts.find(f=>f.horizon===k-1),b=state.forecasts.find(f=>f.horizon===k+1);
    return a&&b?(a.pace_s+b.pace_s)/2:null;
  }
  function totalPace(state,h){
    const values=Array.from({length:h},(_,i)=>paceAt(state,i+1));
    return values.every(finite)?values.reduce((a,b)=>a+b,0):null;
  }
  function supported(step){return !!step&&step.supported&&!step.extrapolating&&step.training_stops>=5&&finite(step.step_s)&&finite(step.radius_s);}
  function pitLossAt(replay,lap){
    const done=replay.laps_data.filter(r=>r.lap<=lap),costs=[];
    const usable=r=>r&&r.track_status==='1'&&!r.in_lap&&!r.out_lap&&finite(r.lap_time_s);
    for(const entry of done.filter(r=>r.in_lap&&r.track_status==='1')){
      const own=done.filter(r=>r.driver===entry.driver),get=k=>own.find(r=>r.lap===k);
      const out=get(entry.lap+1),pre=[get(entry.lap-2),get(entry.lap-1)],post=[get(entry.lap+2),get(entry.lap+3),get(entry.lap+4)];
      if(!out?.out_lap||out.track_status!=='1'||!finite(entry.lap_time_s)||!finite(out.lap_time_s)||!pre.every(usable)||!post.every(usable))continue;
      const value=entry.lap_time_s+out.lap_time_s-median(pre.map(r=>r.lap_time_s))-median(post.map(r=>r.lap_time_s));
      if(value>=10&&value<=40)costs.push(value);
    }
    return {n:costs.length,median_s:median(costs),spread_s:costs.length?median(costs.map(v=>Math.abs(v-median(costs)))):null};
  }
  function plan({replay,intel,lap,driver,compound,pitLoss,trafficLoss,decay,inventory}){
    if(![pitLoss,trafficLoss,decay].every(finite)||pitLoss<0||trafficLoss<0||decay<0)return {status:'invalid'};
    const state=intel.snapshots.find(s=>s.driver===driver&&s.lap===lap);
    const rows=replay.laps_data.filter(r=>r.lap===lap&&finite(r.completed_s)&&finite(r.position));
    const own=rows.find(r=>r.driver===driver),step=state?.stop_scenarios?.[compound];
    if(!own||own.track_status!=='1'||own.in_lap||own.out_lap||!supported(step)||!inventory.includes(compound))return {status:'unsupported'};
    const choices=Object.entries(state.stop_scenarios).filter(([c,s])=>inventory.includes(c)&&supported(s))
      .map(([c,s])=>({compound:c,...s,net5:5*s.step_s-pitLoss-trafficLoss-10*decay})).sort((a,b)=>b.net5-a.net5);
    const own5=totalPace(state,5);
    if(!finite(own5))return {status:'unsupported'};
    const competitors=rows.filter(r=>r.driver!==driver&&r.track_status==='1'&&!r.in_lap&&!r.out_lap)
      .map(r=>({...r,state:intel.snapshots.find(s=>s.driver===r.driver&&s.lap===lap)}));
    const windows=[];
    for(let delay=0;delay<=3;delay++){
      const elapsed=delay?totalPace(state,delay):0;
      if(!finite(elapsed))continue;
      const field=competitors.map(r=>{const predicted=delay?totalPace(r.state,delay):0;return {driver:r.driver,offset:r.completed_s-own.completed_s,
        fallback:delay>0&&!finite(predicted),elapsed:finite(predicted)?predicted:finite(r.lap_time_s)?delay*r.lap_time_s:null};}).filter(r=>finite(r.elapsed));
      const projected=field.map(r=>({driver:r.driver,delta:r.offset+r.elapsed-elapsed-pitLoss})).sort((a,b)=>a.delta-b.delta);
      const ahead=projected.filter(r=>r.delta<0).at(-1),behind=projected.find(r=>r.delta>=0);
      windows.push({delay,lap:lap+delay,position:projected.filter(r=>r.delta<0).length+1,
        ahead:ahead?{driver:ahead.driver,gap_s:-ahead.delta}:null,behind:behind?{driver:behind.driver,gap_s:behind.delta}:null,
        covered:field.length+1,total:rows.length,baselines:field.filter(r=>r.fallback).length,trafficRisk:ahead?Math.max(0,2.5+ahead.delta):0,
        net5:(5-delay)*step.step_s-pitLoss-trafficLoss-decay*(5-delay)*(4-delay)/2});
    }
    const attacks=competitors.filter(r=>r.position<own.position).slice(-4).map(r=>{
      const gap=own.completed_s-r.completed_s,other=totalPace(r.state,3);
      if(!finite(other)||gap<0)return null;
      const learned=state.battles?.find(b=>b.rival===r.driver&&b.horizon===3);
      const relative=learned?.predicted_loss_s??totalPace(state,3)-other;
      const ownRadius=state.forecasts.find(f=>f.horizon===3)?.upper_s-state.forecasts.find(f=>f.horizon===3)?.pace_s;
      const otherRadius=r.state?.forecasts.find(f=>f.horizon===3)?.upper_s-r.state?.forecasts.find(f=>f.horizon===3)?.pace_s;
      const relRadius=learned?.radius_s??(finite(ownRadius)&&finite(otherRadius)?3*(ownRadius+otherRadius):null);
      const margin=3*step.step_s-relative-gap-trafficLoss-3*decay;
      const radius=finite(relRadius)?3*step.radius_s+relRadius:null;
      return {driver:r.driver,gap_s:gap,relative_s:relative,margin_s:margin,radius_s:radius,
        basis:learned?'Learned adjacent-rival model':'Integrated lap forecasts; no learned correction'};
    }).filter(Boolean);
    return {status:'ready',choices,step,windows,attacks,
      recovery_laps:step.step_s>0?(pitLoss+trafficLoss)/step.step_s:null,
      preferred:windows.slice().sort((a,b)=>a.trafficRisk-b.trafficRisk||b.net5-a.net5)[0]};
  }
  const api={sampleAt,boundaryTimes,trafficAt,paceAt,totalPace,pitLossAt,plan};
  if(typeof module!=='undefined')module.exports=api;else root.PitwallStrategy=api;
})(typeof window!=='undefined'?window:this);
