/* One timestamp, actual model outputs, explicit stop/traffic arithmetic. */
(function(root){
  const S=typeof module!=='undefined'?require('./strategy-engine'):root.PitwallStrategy;
  const finite=Number.isFinite;
  function stateAt(payload,replay,driver,time){
    if(!payload||payload.round!==replay.round||!finite(time))return null;
    const row=replay.laps_data.filter(r=>r.driver===driver&&finite(r.completed_s)&&r.completed_s<=time).sort((a,b)=>b.completed_s-a.completed_s)[0];
    if(!row||row.track_status!=='1'||row.in_lap||row.out_lap||time-row.completed_s>180)return null;
    const state=payload.snapshots.find(s=>s.driver===driver&&s.lap===row.lap&&s.issued_s<=time);
    return state?{...state,row}:null;
  }
  function arrival(state,target){
    if(!state)return null;
    const h=target-state.lap;
    if(h===0)return {time:state.row.completed_s,radius:0,h};
    if(h<1||h>5)return null;
    const total=S.totalPace(state,h);
    if(!finite(total))return null;
    const radii=Array.from({length:h},(_,i)=>{
      const k=i+1,f=state.forecasts.find(f=>f.horizon===k);
      if(f)return finite(f.upper_s)?f.upper_s-f.pace_s:null;
      const a=state.forecasts.find(f=>f.horizon===k-1),b=state.forecasts.find(f=>f.horizon===k+1);
      return finite(a?.upper_s)&&finite(b?.upper_s)?((a.upper_s-a.pace_s)+(b.upper_s-b.pace_s))/2:null;
    });
    return {time:state.row.completed_s+total,radius:radii.every(finite)?radii.reduce((a,b)=>a+b,0):null,h};
  }
  function plan({replay,pace,pit,time,driver,compound,pitLoss,trafficLoss,decay,inventory,responseLaps=3}){
    if(![pitLoss,trafficLoss,decay,time].every(finite)||Math.min(pitLoss,trafficLoss,decay)<0)return {status:'invalid'};
    const own=stateAt(pace,replay,driver,time),tyres=stateAt(pit,replay,driver,time);
    const supported=s=>s?.supported&&!s.extrapolating&&s.training_stops>=5&&finite(s.step_s)&&finite(s.radius_s);
    const step=tyres?.stop_scenarios[compound];
    if(!own||!tyres||!supported(step)||!inventory.includes(compound))return {status:'unsupported'};
    const others=replay.drivers.filter(d=>d!==driver).map(d=>stateAt(pace,replay,d,time)).filter(Boolean);
    const choices=Object.entries(tyres.stop_scenarios).filter(([c,s])=>inventory.includes(c)&&supported(s)).map(([c,s])=>({compound:c,...s,net5:5*s.step_s-pitLoss-trafficLoss-10*decay})).sort((a,b)=>b.net5-a.net5);
    const windows=[];
    for(let delay=0;delay<4;delay++){
      const target=own.lap+delay+1,a=arrival(own,target);
      if(!a)continue;
      const field=others.map(s=>({driver:s.driver,a:arrival(s,target)})).filter(s=>s.a);
      const ordered=field.map(s=>({driver:s.driver,delta:s.a.time-a.time-pitLoss})).sort((a,b)=>a.delta-b.delta);
      const front=ordered.filter(r=>r.delta<0).at(-1),back=ordered.find(r=>r.delta>=0);
      windows.push({delay,lap:own.lap+delay,reference_lap:target,ahead:front?{driver:front.driver,gap_s:-front.delta}:null,
        behind:back?{driver:back.driver,gap_s:back.delta}:null,covered:field.length+1,total:replay.drivers.length,baselines:0,
        trafficRisk:front?Math.max(0,2.5+front.delta):0,net5:(5-delay)*step.step_s-pitLoss-trafficLoss-decay*(5-delay)*(4-delay)/2});
    }
    if(![3,5].includes(responseLaps))return {status:'invalid'};
    const target=own.lap+responseLaps,a=arrival(own,target),attacks=[];
    if(a)for(const other of others){
      const b=arrival(other,target);if(!b||other.row.position>=own.row.position)continue;
      // Shared future timing line aligns cars whose latest observed lap differs.
      const relative=a.time-b.time,margin=responseLaps*step.step_s-relative-trafficLoss-decay*responseLaps*(responseLaps-1)/2;
      const radius=finite(a.radius)&&finite(b.radius)?a.radius+b.radius+responseLaps*step.radius_s:null;
      attacks.push({driver:other.driver,margin_s:margin,radius_s:radius,relative_s:relative,
        gap_s:null,target_lap:target,basis:`Clock forecasts aligned at L${target}; both stops have equal pit loss`});
    }
    attacks.sort((a,b)=>a.relative_s-b.relative_s);
    return {status:'ready',lap:own.lap,issued_s:own.issued_s,inputs:tyres.inputs,own,choices,step,windows,attacks:attacks.slice(0,4),
      current_pace_s:S.paceAt(own,1),new_tyre_pace_s:S.paceAt(own,1)-step.step_s,
      recovery_laps:step.step_s>0?(pitLoss+trafficLoss)/step.step_s:null,
      preferred:windows.slice().sort((a,b)=>a.trafficRisk-b.trafficRisk||b.net5-a.net5)[0]};
  }
  const api={stateAt,arrival,plan};if(typeof module!=='undefined')module.exports=api;else root.PitwallLive=api;
})(typeof window!=='undefined'?window:this);
