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
const build=path.join(root,'.build/jury'),out=path.join(root,'artifacts/submission');
await fs.mkdir(build,{recursive:true});await fs.mkdir(out,{recursive:true});
const read=async name=>JSON.parse(await fs.readFile(path.join(root,'artifacts/demo',name),'utf8'));
const [pace,battle,decision,race]=await Promise.all(['intelligence/report.json','intelligence/battle_report.json','intelligence/decision_report.json','intelligence/R11.json'].map(read));
const state=race.snapshots.find(s=>s.driver==='NOR'&&s.lap===25),f=state.forecasts.find(f=>f.horizon===3);
const result=race.evaluation.find(e=>e.driver==='NOR'&&e.issued_lap===25&&e.horizon===3);
const step=state.stop_scenarios.HARD,b=state.battles.find(b=>b.horizon===3),margin=3*step.step_s-b.predicted_loss_s-1.5-.7;
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
let s=slide('', 'PITWALL / TrackShift 2026. Present the app using Present to jury. This deck accompanies the working local demo; all metrics come from artifacts/demo/intelligence/*.json. Do not claim a validated optimal pit lap or places gained.');
text(s,'PITWALL',64,115,1100,130,106,palette.lime,true);
text(s,'Tyre degradation intelligence',70,288,1080,75,49);
text(s,'Forecast the pace risk.\nPrice the response.',70,400,1080,130,40,palette.dim);
text(s,'Aditya & Ruhani  /  TrackShift 2026',70,626,1060,36,23,palette.dim);
s=slide('Tyre wear is hidden inside lap pace','Source: artifacts/demo/model.json → degradation_curves.practice.compounds.HARD. Slopes evaluated at tyre age 10. Historical research artifacts predate the replay traffic correction. The practice-to-race transfer failed; these are identification evidence, not deployed physical wear estimates.');
text(s,'Fuel  +  tyres  +  traffic  +  track evolution',64,175,1152,66,36,palette.dim);
text(s,'−0.154',64,289,480,112,79,palette.orange);
text(s,'Naive HARD slope / s per lap',70,410,500,45,27);
text(s,'+0.063',680,289,480,112,79,palette.lime);
text(s,'After confounder correction',686,410,530,45,27);
text(s,'A plausible practice curve still failed the race-transfer test.\nWe validate race forecasting and stop scenarios separately.',64,520,1152,96,28);
text(s,'Historical research at tyre age 10; not a direct physical wear sensor.',64,651,1152,32,20,palette.dim);
s=slide('Lock the forecast. Then reveal the lap.', 'Source: artifacts/demo/intelligence/R11.json. Snapshot NOR / lap 25 / horizon 3; target lap 28. Demo example uses the pre-existing default cursor, not a search for best error. Prediction 85.066332; actual 85.071; persistence 84.973. One example is not an accuracy claim. In app: Present to jury → Predict & verify → Advance to lap 28 & score.');
text(s,'HUNGARY / NOR / LAP 25 → LAP 28',64,163,1152,48,25,palette.dim);
for(const [x,label,value] of [[64,'LOCKED FORECAST',f.pace_s.toFixed(3)+'s'],[480,'ACTUAL LAP',result.actual_s.toFixed(3)+'s'],[883,'ABSOLUTE ERROR',Math.abs(f.pace_s-result.actual_s).toFixed(3)+'s']]){
  text(s,label,x,273,350,36,21,palette.dim);text(s,value,x,321,350,95,65,palette.lime);
}
text(s,`Persistence error: ${Math.abs(result.baseline_s-result.actual_s).toFixed(3)}s. The forecast stays fixed as replay advances.`,64,465,1152,80,29);
text(s,'One historical example. The next benchmark includes every scored evaluation forecast.',64,613,1152,66,23,palette.dim);
s=slide('Traffic can erase the undercut margin','Sources: artifacts/demo/intelligence/R11.json stop_scenarios.HARD and battles[horizon=3] at NOR lap25. Scenario: 1.5s gap, 0.7s warm-up, equal service, zero extra degradation, both cars stop. Central margin = 3*1.315561 - 0.078218 -1.5 -0.7 =1.668465s. Adding 2s total rejoin traffic gives -0.331535s. Combined stress radius =3*2.032157 +2.497010 =8.593481s. Conditional arithmetic, no validated overtake claim.');
text(s,`${(3*step.step_s).toFixed(2)}s tyre benefit − ${b.predicted_loss_s.toFixed(2)}s rival pace − 1.50s gap − 0.70s warm-up`,64,166,1152,90,29,palette.dim);
text(s,'+'+margin.toFixed(2)+'s',64,310,500,115,91,palette.lime);
text(s,'Central margin / clean rejoin',70,445,520,48,27);
text(s,(margin-2).toFixed(2)+'s',705,310,500,115,91,palette.orange);
text(s,'With 2s of rejoin traffic',710,445,505,48,27);
text(s,'Both stress ranges cross zero. The tool exposes a fragile attack\ninstead of inventing a confident pit command.',64,552,1152,85,29);
text(s,'Both cars stop; shared pit transit cancels. Costs and inventory require engineer input.',64,661,1152,30,19,palette.dim);
s=slide('Measured improvement against baselines','Sources: artifacts/demo/intelligence/report.json and battle_report.json. Pace RMSE on 6831 forecasts; relative-time RMSE on3128 forecasts. All later-race results use earlier-race fits. Architectures selected using development events; R09-R12 are reused evaluation events. Forecasts assume same-stint green running.');
const chart=s.charts.add('bar',{position:{left:64,top:176,width:820,height:370},categories:['Pace forecast','Rival-time forecast'],series:[{name:'PITWALL',values:[pace.rmse_s,battle.rmse_s],fill:palette.lime},{name:'Baseline',values:[pace.baseline_rmse_s,battle.baseline_rmse_s],fill:'#69776A'}],barOptions:{direction:'column',grouping:'clustered',gapWidth:140},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:20,fill:palette.ink}},chartFill:palette.bg,plotAreaFill:palette.bg,chartLine:{fill:'none',width:0},plotAreaLine:{fill:'none',width:0},xAxis:{textStyle:{fontSize:21,fill:palette.ink},majorGridlines:null},yAxis:{min:0,max:3,majorUnit:1,numberFormatCode:'0.0"s"',textStyle:{fontSize:19,fill:palette.dim},majorGridlines:{fill:'#2B352B',width:1}},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.000',textStyle:{fontSize:19,fill:palette.ink}}});
applyPresentationChartFont(chart,{fontFamily:family});
[[pace.rmse_s,battle.rmse_s],[pace.baseline_rmse_s,battle.baseline_rmse_s]].forEach((values,i)=>values.forEach((value,j)=>{
  const label=chart.series.getItemAt(i).dataLabelOverrides.add(j);label.text=value.toFixed(3)+'s';label.position='outEnd';
  label.textStyle.typeface=family;label.textStyle.fontSize=19;label.textStyle.fill=palette.ink;
}));
text(s,pace.improvement_pct.toFixed(1)+'%',925,203,290,100,66,palette.lime);text(s,'less pace RMSE',930,303,290,48,24);
text(s,battle.improvement_pct.toFixed(1)+'%',925,390,290,100,66,palette.lime);text(s,'less rival-time RMSE',930,491,295,68,24);
text(s,`${pace.n.toLocaleString()} pace and ${battle.n.toLocaleString()} rival forecasts. Four reused evaluation races.`,64,589,1152,49,25);
text(s,`Stop-step RMSE ${decision.rmse_s.toFixed(3)}s vs ${decision.baseline_rmse_s.toFixed(3)}s: too small a gain to claim optimal pit strategy.`,64,652,1152,40,21,palette.dim);
s=slide('A decision aid the engineer can inspect','Sources: current local application demo_fallback/index.html; docs/JURY_PRESENTATION.md; artifacts/demo/intelligence/*.json. Use the app four-chapter walkthrough. Strong claims are forecast accuracy and inspectable scenario arithmetic; physical tyre life, actual race time saved and positions won remain unproven.');
text(s,'01   Predict and verify the next laps',64,197,1152,65,34,palette.lime);
text(s,'02   Stress the undercut with traffic and rival response',64,301,1152,92,34,palette.lime);
text(s,'03   Inspect the baseline, coverage and model limits',64,421,1152,65,34,palette.lime);
text(s,'Measured forecast advantage. Transparent strategy assumptions.\nGrounded engineer briefing. Offline replay.',64,544,1152,100,29);
text(s,'Open the app → Present to jury',64,660,1152,32,23,palette.dim);
await (await PresentationFile.exportPptx(presentation)).save(path.join(build,'candidate.pptx'));
for(let i=0;i<presentation.slides.items.length;i++){
  const image=await presentation.export({slide:presentation.slides.items[i],format:'png',scale:1});
  await fs.writeFile(path.join(build,`slide-${i+1}.png`),new Uint8Array(await image.arrayBuffer()));
}
const finalPath=path.join(out,'PITWALL_Jury_Final.pptx');
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
