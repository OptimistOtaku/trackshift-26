/* Pure evidence contracts shared by the jury UI and Node regression tests. */
(function(root){
  const finite=v=>typeof v==='number'&&Number.isFinite(v);
  function freezeForecast(round,snapshot,horizon,baseline){
    const f=snapshot?.forecasts?.find(f=>f.horizon===horizon);
    if(!f||!finite(f.pace_s)||!finite(baseline))return null;
    return Object.freeze({round,driver:snapshot.driver,issued_lap:snapshot.lap,
      target_lap:f.target_lap,horizon,predicted_s:f.pace_s,lower_s:f.lower_s,
      upper_s:f.upper_s,baseline_s:baseline});
  }
  function resolveForecast(ticket,{round,driver,lap,evaluation}){
    if(!ticket)return {status:'empty'};
    if(round!==ticket.round||driver!==ticket.driver)return {status:'different_context'};
    if(lap<ticket.issued_lap)return {status:'before_issue'};
    if(lap<ticket.target_lap)return {status:'pending',remaining:ticket.target_lap-lap};
    const result=evaluation.find(e=>e.driver===ticket.driver&&e.issued_lap===ticket.issued_lap
      &&e.target_lap===ticket.target_lap&&e.horizon===ticket.horizon);
    if(!result||!finite(result.actual_s))return {status:'interrupted'};
    const error=Math.abs(ticket.predicted_s-result.actual_s),baselineError=Math.abs(ticket.baseline_s-result.actual_s);
    return {status:'resolved',actual_s:result.actual_s,error_s:error,baseline_error_s:baselineError,
      error_reduction_s:baselineError-error,inside_interval:finite(ticket.lower_s)&&finite(ticket.upper_s)?
        result.actual_s>=ticket.lower_s&&result.actual_s<=ticket.upper_s:null};
  }
  function scoreAtCursor(evaluation,lap,driver=null){
    const rows=evaluation.filter(e=>e.target_lap<=lap&&e.horizon===1&&(!driver||e.driver===driver)
      &&finite(e.actual_s)&&finite(e.predicted_s)&&finite(e.baseline_s));
    if(!rows.length)return {n:0,rmse_s:null,baseline_rmse_s:null,improvement_pct:null};
    const rmse=k=>Math.sqrt(rows.reduce((n,e)=>n+(e[k]-e.actual_s)**2,0)/rows.length);
    const model=rmse('predicted_s'),base=rmse('baseline_s');
    return {n:rows.length,rmse_s:model,baseline_rmse_s:base,improvement_pct:base>0?100*(1-model/base):null};
  }
  const api={freezeForecast,resolveForecast,scoreAtCursor};
  if(typeof module!=='undefined')module.exports=api;else root.PitwallEvidence=api;
})(typeof window!=='undefined'?window:this);
