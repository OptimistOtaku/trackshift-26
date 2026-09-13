/** Build the current jury deck from the same evidence files as the console. */
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const runtime=process.env.PITWALL_RUNTIME_ROOT||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
process.env.RUNTIME_NODE_MODULES=path.join(runtime,'node/node_modules');
process.env.RUNTIME_NODE=path.join(runtime,'node/bin/node.exe');
process.env.RUNTIME_PYTHON=path.join(runtime,'python/python.exe');
const skill=process.env.PITWALL_PRESENTATIONS_SKILL||path.join(os.homedir(),'.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations');
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(path.join(runtime,'node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const build=path.join(root,'.build/jury-updated'),out=path.join(root,'artifacts/submission');
await fs.mkdir(build,{recursive:true});await fs.mkdir(out,{recursive:true});
const read=async name=>JSON.parse(await fs.readFile(path.join(root,'artifacts/demo',name),'utf8'));
const [pace,decision,race]=await Promise.all(['clock/report.json','decision-clock/report.json','clock/R11.json'].map(read));
const state=race.snapshots.find(s=>s.driver==='NOR'&&s.lap===25),f=state.forecasts.find(f=>f.horizon===3);
const result=race.evaluation.find(e=>e.driver==='NOR'&&e.issued_lap===25&&e.horizon===3);

const presentation=Presentation.create({slideSize:{width:1280,height:720}});
const palette={bg:'#0A0E0D',ink:'#EDF0ED',dim:'#A6B0A7',lime:'#E6FC74',orange:'#E4A06D'};
const family='Bahnschrift';
function text(slide,value,x,y,w,h,size=28,color=palette.ink,bold=false){
  const t=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  t.text=value;t.text.style={typeface:family,fontSize:size,bold,color,autoFit:'none'};return t;
}
function slide(title,notes){
  const s=presentation.slides.add();s.background.fill=palette.bg;
  if(title)text(s,title,64,54,1152,74,46,palette.ink,true);
  s.speakerNotes.textFrame.setText(notes);return s;
}
let s=slide('', 'PITWALL, TrackShift 2026. Team: Handsome Squidward. Members: Aditya and Ruhani. Updated 13 September 2026. This presentation uses the current timestamp-aligned pace model and deployed tyre-response model. Historical replay and conditional strategy scenarios do not establish physical wear or an optimal pit lap.');
text(s,'PITWALL',64,105,1100,130,106,palette.lime,true);
text(s,'Tyre degradation intelligence',70,270,1080,75,49);
text(s,'Pace forecasts and inspectable pit scenarios',70,373,1120,68,34,palette.dim);
text(s,'Team Handsome Squidward',70,493,1100,63,39,palette.lime,true);
text(s,'Aditya and Ruhani',70,567,1060,48,29);
text(s,'TrackShift 2026  /  13 September 2026',70,635,1060,38,23,palette.dim);
s=slide('Tyre wear is hidden inside lap pace','Source: artifacts/demo/model.json → degradation_curves.practice.compounds.HARD. Slopes evaluated at tyre age 10. Historical research artifacts predate the replay traffic correction. The practice-to-race transfer failed; these are identification evidence, not deployed physical wear estimates.');
text(s,'Fuel  +  tyres  +  traffic  +  track evolution',64,175,1152,66,36,palette.dim);
text(s,'−0.154',64,289,480,112,79,palette.orange);
text(s,'Naive HARD slope / s per lap',70,410,500,45,27);
text(s,'+0.063',680,289,480,112,79,palette.lime);
text(s,'After confounder correction',686,410,530,45,27);
text(s,'A plausible practice curve still failed the race-transfer test.\nWe validate race forecasting and stop scenarios separately.',64,520,1152,96,28);
text(s,'Historical research at tyre age 10; not a direct physical wear sensor.',64,651,1152,32,20,palette.dim);
s=slide('Forecast verification on the driver clock', 'Source: artifacts/demo/clock/R11.json. NOR lap 25, horizon 3, target lap 28. Issue timestamp 5407.546 s, target completion 5663.613 s. Current forecast 85.018732 s, actual 85.071 s, persistence 84.973 s. This updates the same example used in the prior deck rather than selecting a different result. One example is a demonstration, not aggregate accuracy evidence. In the app, choose Hungary and Norris, lock a three-lap forecast, then let recorded replay reveal the target.');
text(s,'HUNGARY / NOR / LAP 25 TO LAP 28',64,163,1152,48,25,palette.dim);
for(const [x,label,value] of [[64,'LOCKED FORECAST',f.pace_s.toFixed(3)+'s'],[480,'ACTUAL LAP',result.actual_s.toFixed(3)+'s'],[883,'ABSOLUTE ERROR',Math.abs(f.pace_s-result.actual_s).toFixed(3)+'s']]){
  text(s,label,x,273,350,36,21,palette.dim);text(s,value,x,321,350,95,65,palette.lime);
}
text(s,`Persistence error: ${Math.abs(result.baseline_s-result.actual_s).toFixed(3)}s. The lock preserves the issued prediction.`,64,465,1152,80,29);
text(s,'Actuals appear only after target completion. Recorded replay, with one clock\nfor the circuit, forecasts and stop scenarios.',64,587,1152,85,26,palette.dim);
s=slide('Fresh-tyre response now uses measured context', 'Sources: artifacts/demo/decision-clock/report.json and docs/TYRE_RESPONSE_UPGRADE.md. Model environment_a256_normalized uses regularized ridge regression, a saturating age basis, compounds, pace state, race progress, track temperature and observed traffic, including age/temperature interactions and missing-input flags. Selection uses R04-R08 and fits use earlier races. Evaluation uses 107 supported stops in reused R09-R12. Current RMSE 0.671706 s, previous architecture 0.764444 s, mean 0.761195 s. Lower error versus previous architecture is 12.131515%. Event-bootstrap 95% gain interval versus mean is -0.035829% to 21.750066%, narrowly including zero. Wide response intervals and residual confounding remain.');
text(s,'Tyre age and compounds, recent pace and race progress',64,172,1152,54,32);
text(s,'Track temperature and observed traffic enter the model',64,242,1152,60,32,palette.lime);
text(s,decision.rmse_s.toFixed(3)+'s',64,351,520,115,88,palette.lime);
text(s,'Stop-recovery RMSE / 107 stops',70,481,550,48,27);
text(s,decision.improvement_vs_previous_pct.toFixed(1)+'%',730,351,470,115,88,palette.lime);
text(s,'Lower error than previous model',735,481,480,70,27);
text(s,'The same response powers compound comparison and pit scenarios.\nUncertainty remains wide. Physical tyre wear remains unmeasured.',64,575,1152,95,28,palette.dim);
s=slide('Current models improve on their baselines','Sources: artifacts/demo/clock/report.json and artifacts/demo/decision-clock/report.json. Pace RMSE 0.745595 s versus persistence 0.843650 s, 11.622706% lower, 6831 scored of 9062 issued forecasts. Pace nominal 90% interval empirical coverage is 92.5487%. Stop-recovery RMSE 0.671706 s versus historical mean 0.761195 s, 11.756479% lower, 107 supported stops. Both use reused R09-R12 evaluation races and earlier-race fits. Stop-response selection uses development R04-R08. Pace event-bootstrap improvement interval is 8.744469% to 15.413975%. Stop-response gain interval is -0.035829% to 21.750066%, narrowly including zero. The two targets have different populations and must not be pooled. RMSE means root mean squared error, measured in seconds.');
const chart=s.charts.add('bar',{position:{left:64,top:176,width:820,height:370},categories:['Pace forecast','Stop recovery'],series:[{name:'PITWALL',values:[pace.rmse_s,decision.rmse_s],fill:palette.lime},{name:'Baseline',values:[pace.baseline_rmse_s,decision.baseline_rmse_s],fill:'#69776A'}],barOptions:{direction:'column',grouping:'clustered',gapWidth:140},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:20,fill:palette.ink}},chartFill:palette.bg,plotAreaFill:palette.bg,chartLine:{fill:'none',width:0},plotAreaLine:{fill:'none',width:0},xAxis:{textStyle:{fontSize:21,fill:palette.ink},majorGridlines:null},yAxis:{min:0,max:1,majorUnit:0.25,numberFormatCode:'0.0"s"',textStyle:{fontSize:19,fill:palette.dim},majorGridlines:{fill:'#2B352B',width:1}},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.000',textStyle:{fontSize:19,fill:palette.ink}}});
applyPresentationChartFont(chart,{fontFamily:family});
[[pace.rmse_s,decision.rmse_s],[pace.baseline_rmse_s,decision.baseline_rmse_s]].forEach((values,i)=>values.forEach((value,j)=>{
  const label=chart.series.getItemAt(i).dataLabelOverrides.add(j);label.text=value.toFixed(3)+'s';label.position='outEnd';
  label.textStyle.typeface=family;label.textStyle.fontSize=19;label.textStyle.fill=palette.ink;
}));
text(s,pace.improvement_pct.toFixed(1)+'%',925,203,290,100,66,palette.lime);text(s,'less pace RMSE',930,303,290,48,24);
text(s,decision.improvement_pct.toFixed(1)+'%',925,390,290,100,66,palette.lime);text(s,'less stop-recovery RMSE',930,491,295,68,24);
text(s,`${pace.n.toLocaleString()} scored pace forecasts and ${decision.n} stops. Four reused evaluation races.`,64,576,1152,46,25);
text(s,'RMSE in seconds, lower is better. Pace baseline: persistence. Stop baseline: historical mean.\nExploratory stop-response gain: the 95% event-bootstrap interval narrowly includes zero.',64,636,1152,66,20,palette.dim);
s=slide('An inspectable pit-planning workflow','Sources: docs/PRODUCT_OPERATIONS.md, docs/CATEGORY_ASSESSMENT.md and demo_fallback/index.html. Demonstrate the current main console: Watch comparison 10x, forecast/actual pairing and audit lock; Plan stop & rejoin, supported compound inventory, observed pit loss and optional traffic/decay inputs; projected neighbours and named rival scenarios. Future traffic and tyre decay are assumptions. Rejoin is conditional and excludes unsupported cars. Prospective independent evaluation and external live integration remain next steps. Team Handsome Squidward: Aditya and Ruhani.');
text(s,'01   Compare each issued forecast with the arriving lap',64,173,1152,66,33,palette.lime);
text(s,'02   Compare fresh compounds and inspect stop cost',64,272,1152,66,33,palette.lime);
text(s,'03   Check rejoin neighbours and stress extra traffic',64,371,1152,66,33,palette.lime);
text(s,'Historical replay with explicit assumptions and uncertainty.\nPhysical tyre life and realized positions gained remain unvalidated.',64,490,1152,102,29);
text(s,'Handsome Squidward  /  Aditya and Ruhani',64,634,1152,44,26,palette.dim);
await (await PresentationFile.exportPptx(presentation)).save(path.join(build,'candidate.pptx'));
for(let i=0;i<presentation.slides.items.length;i++){
  const image=await presentation.export({slide:presentation.slides.items[i],format:'png',scale:1});
  await fs.writeFile(path.join(build,`slide-${i+1}.png`),new Uint8Array(await image.arrayBuffer()));
}
const finalPath=path.join(out,'PITWALL_Handsome_Squidward_Updated.pptx');
const finalized=await finalizePresentation({workspaceDir:root,candidatePath:path.join(build,'candidate.pptx'),finalPath,
  pythonExecutable:path.join(runtime,'python/python.exe'),integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
  explicitTotalSlideCount:6,requiredNativeChartOwnerSlides:[5],materializeLiteralChartWorkbooks:true,
  fontPolicy:{basis:'design',families:[family]},verifyArtifactToolImport:true,receiptPath:path.join(build,'final-validation.json')});
const finalDeck=await PresentationFile.importPptx(await FileBlob.load(finalPath));
for(let i=0;i<finalDeck.slides.items.length;i++){
  const image=await finalDeck.export({slide:finalDeck.slides.items[i],format:'png',scale:1});
  await fs.writeFile(path.join(build,`final-slide-${i+1}.png`),new Uint8Array(await image.arrayBuffer()));
}
console.log('Validated deck: '+finalized.finalPath);
