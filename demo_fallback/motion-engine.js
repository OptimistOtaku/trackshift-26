/* Causal track-constrained reconstruction. Never lerp XY across a corner. */
(function(root){
  const finite=Number.isFinite,wrap=x=>((x%1)+1)%1,clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  function geometry(points,length){
    if(!points?.length||!finite(length)||length<=0)return null;
    const segments=points.map((a,i)=>{const b=points[(i+1)%points.length];return Math.hypot(b[0]-a[0],b[1]-a[1]);});
    const total=segments.reduce((a,b)=>a+b,0),ends=[];let sum=0;
    segments.forEach(v=>{sum+=v;ends.push(sum/total);});
    return {length,point(arc){
      const f=wrap(arc);let lo=0,hi=ends.length-1;
      while(lo<hi){const m=(lo+hi)>>1;if(ends[m]<f)lo=m+1;else hi=m;}
      const start=lo?ends[lo-1]:0,u=(f-start)/(ends[lo]-start||1),a=points[lo],b=points[(lo+1)%points.length];
      return {x:a[0]+u*(b[0]-a[0]),y:a[1]+u*(b[1]-a[1]),dx:b[0]-a[0],dy:b[1]-a[1]};
    }};
  }
  function reconstruct(rows,length){
    const out=[];let state=null,raw=null;
    for(const r of rows){
      const t=r[0],ontrack=!!r[8]&&finite(r[3]),speed=finite(r[4])?clamp(r[4]/3.6,0,110):null;
      const dt=state?t-state.t:0;
      if(!state||dt<=0||dt>2||!ontrack||!state.ontrack||speed===null){
        state={t,phase:(r[3]||0)*length,target:(r[3]||0)*length,ontrack:ontrack&&speed!==null,speed:speed||0,uncertainty:25,quality:'anchor'};
        raw=ontrack?{t,x:r[1],y:r[2],arc:r[3]}:null;
      }else{
        const base=(state.speed+speed)/2*dt,predicted=state.phase+base;
        let target=state.target+base,quality='speed reconstruction',rawAge=raw?t-raw.t:0;
        if(raw&&(raw.x!==r[1]||raw.y!==r[2])){
          const elapsed=t-raw.t,forward=wrap(r[3]-raw.arc)*length;
          const plausible=forward<=125*elapsed+35||forward>length-25;
          if(plausible){
            const error=(wrap(r[3]-wrap(predicted/length)+.5)-.5)*length;
            if(Math.abs(error)<Math.max(400,125*elapsed)){
              target=predicted+error;quality='position corrected';
              raw={t,x:r[1],y:r[2],arc:r[3]};rawAge=0;
            }else quality='position rejected';
          }else quality='position rejected';
        }
        const correction=clamp((target-predicted)*.18,-Math.min(base*.35,20*dt),Math.min(base*.35,20*dt));
        state={t,phase:state.phase+clamp(base+correction,0,110*dt),target,ontrack,speed,
          uncertainty:Math.max(20,Math.abs(target-predicted),Math.min(rawAge,15)*speed*.2),quality};
      }
      out.push({...state,source:r});
    }
    return out;
  }
  function sample(rows,time,path){
    if(!path||!finite(time))return null;
    let lo=0,hi=rows.length;while(lo<hi){const m=(lo+hi)>>1;if(rows[m].t<=time)lo=m+1;else hi=m;}
    const i=lo-1,b=rows[i],a=rows[i-1];
    if(!b||time-b.t+b.source[9]>2.5||!b.ontrack)return null;
    // One-second render buffer. Both endpoints have arrived at the session clock.
    const valid=a?.ontrack&&b.t-a.t<=2;
    const u=valid?clamp((time-1-a.t)/(b.t-a.t),0,1):1;
    const phase=valid?a.phase+u*(b.phase-a.phase):b.phase,arc=wrap(phase/path.length),p=path.point(arc);
    return {...p,t:b.t,phase,arc,speed:b.source[4],gear:b.source[5],throttle:b.source[6],brake:b.source[7],
      ontrack:true,age:time-b.t+b.source[9],uncertainty_m:Math.max(a?.uncertainty||0,b.uncertainty),quality:b.quality,reconstructed:true};
  }
  const api={geometry,reconstruct,sample};if(typeof module!=='undefined')module.exports=api;else root.PitwallMotion=api;
})(typeof window!=='undefined'?window:this);
