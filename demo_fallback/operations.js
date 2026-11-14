let operationsReady=false,pitLossManual=false;
function initOperations(){
  operationsReady=true;
  for(const id of ['o-compound','o-pitloss','o-traffic','o-decay','o-hard','o-medium','o-soft'])$('#'+id).addEventListener('input',()=>{if(id==='o-pitloss')pitLossManual=true;syncPlannerInventory();drawOperations();});
  $('#o-auto').onclick=()=>{pitLossManual=false;$('#o-traffic').value=0;$('#o-decay').value=0;drawOperations();};
  $('#o-apply').onclick=()=>{
    $('#m-compound').value=$('#o-compound').value;
    setMissionView('undercut');$('#mission-undercut').scrollIntoView({block:'center',behavior:reducedMotion.matches?'instant':'smooth'});
    $('#o-applied').textContent='Same clock inputs loaded: tyre response, integrated forecasts, pit loss and traffic.';
  };
  $('#o-focus').onclick=()=>{document.body.classList.toggle('focus-console');$('#o-focus').textContent=document.body.classList.contains('focus-console')?'Exit focus ↙':'Focus console ↗';};
}
function clearOperations(message){
  if(!operationsReady)return;
  for(const id of ['o-summary','o-feedback','o-call','o-tyre-value','o-choices','o-windows','o-rejoin','o-targets','o-provenance','o-tactical','o-recovery','o-recovery-note','o-pit-source','o-driver-call','o-status','t-model-inputs'])$('#'+id).textContent=message;
  $('#o-apply').disabled=true;
}

function syncPlannerInventory(){
  const available=['HARD','MEDIUM','SOFT'].filter(c=>$('#o-'+c.toLowerCase()).checked);
  for(const id of ['o-compound','m-compound']){
    const select=$('#'+id);
    for(const option of select.options)option.disabled=!available.includes(option.value);
    if(available.length&&!available.includes(select.value))select.value=available[0];
    select.disabled=!available.length;
  }
}
