/** Editable presentation from the original browser collector. No I/O or runtime launch. */
import {createHash} from 'node:crypto';
const NATIVE=['receipt','authorization','timeline','rollback','queue','evidence'];
const SCENARIOS=Array.from({length:6},(_,i)=>`DEMO-${String(i+1).padStart(2,'0')}`);
const hash=b=>createHash('sha256').update(b).digest('hex');
const fail=message=>{throw new Error(message);};
const check=(ok,message)=>{if(!ok)fail(message);};
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const identity=s=>object(s)&&['commit','tree'].every(k=>typeof s[k]==='string'&&/^[a-f0-9]{40}$/.test(s[k]));
const same=(a,b)=>identity(a)&&identity(b)&&a.commit===b.commit&&a.tree===b.tree;
const bytes=v=>v instanceof Uint8Array;
const json=b=>JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(b));
function imageSize(b){
  check(b.length>=24&&Buffer.from(b.subarray(0,8)).equals(Buffer.from([137,80,78,71,13,10,26,10])),'PNG required');
  check(Buffer.from(b.subarray(12,16)).toString('ascii')==='IHDR','PNG dimensions required');
  const d=new DataView(b.buffer,b.byteOffset,b.byteLength),w=d.getUint32(16),h=d.getUint32(20);
  check(w>0&&h>0&&w<=16384&&h<=16384&&w*h<=32000000,'bounded screenshot dimensions required');
  return {width:w,height:h};
}
function countSummary(raw){
  check(object(raw)&&Object.keys(raw).sort().join(',')==='blocked,failed,not-run,passed','original four scenario counts required');
  return Object.fromEntries(['passed','failed','blocked','not-run'].filter(k=>Object.hasOwn(raw,k)).map(k=>{
    check(Number.isSafeInteger(raw[k])&&raw[k]>=0,'integer recorded count required'); return[k,raw[k]];
  }));
}
export function validateCapture(captured){
  check(object(captured)&&object(captured.files)&&object(captured.manifest),'original capture object required');
  const {files,manifest:m}=captured;
  check(m.schema==='8415ex-native-browser-materials/1'&&identity(m.source),'capture source identity required');
  check(m.contentKind==='ACTUAL_BROWSER_SCREENSHOTS_OF_LOCAL_SIMULATION','actual browser capture kind required');
  check(object(m.files)&&Array.isArray(m.captures)&&Array.isArray(m.scenarios),'complete manifest required');
  check(Object.keys(files).length===Object.keys(m.files).length,'all capture files must be accounted');
  let total=0;
  for(const [path,data] of Object.entries(files)){
    check(/^(screens\/[A-Za-z0-9-]+\.png|evidence\/[A-Za-z0-9-]+\.json|video\/browser-capture\.webm)$/.test(path),'unexpected capture member');
    check(bytes(data)&&data.length>0&&data.length<=64*1024*1024,'bounded capture bytes required');
    total+=data.length;
    check(object(m.files[path])&&m.files[path].bytes===data.length&&m.files[path].sha256===hash(data),'capture member hash mismatch');
  }
  check(total<=64*1024*1024,'capture total limit exceeded');
  const names=[...NATIVE.map(n=>'native-'+n),...SCENARIOS];
  check(m.captures.length===names.length&&new Set(m.captures.map(c=>c.entry)).size===names.length,'twelve distinct screenshots required');
  const screenshots=names.map(entry=>{
    const c=m.captures.find(c=>c.entry===entry),path='screens/'+entry+'.png',b=files[path];
    check(object(c)&&c.HTTP===200&&bytes(b)&&b.length<=8*1024*1024,'complete HTTP200 screenshot required');
    check(c.pngSHA256===hash(b),'screenshot observation hash mismatch');
    return {entry,path,data:b,size:imageSize(b),observedUTC:c.observedUTC};
  });
  for(const path of ['evidence/native-start.json','evidence/native-end.json']){
    check(bytes(files[path])&&same(json(files[path]).source,m.source),'native source changed or missing');
  }
  check(m.scenarios.length===6&&new Set(m.scenarios.map(s=>s.scenario)).size===6,'six distinct scenario records required');
  const scenarios=SCENARIOS.map(id=>{
    const brief=m.scenarios.find(s=>s.scenario===id),path='evidence/'+id+'.json';
    check(object(brief)&&bytes(files[path]),'scenario record missing');
    const raw=json(files[path]),rows=raw.report?.scenarios;
    check(same(raw.source,m.source)&&raw.evidenceKind==='LOCAL_SIMULATION','scenario source or evidence kind mismatch');
    check(typeof raw.runId==='string'&&/^demo-[a-f0-9]{32}$/.test(raw.runId)&&raw.runId===brief.runId,'scenario run identity mismatch');
    check(Array.isArray(rows)&&rows.length===1&&rows[0].scenarioId===id,'scenario identity mismatch');
    check(['REG_DIRECT','REG_ELECTRONIC','REG_INTERMEDIARY'].includes(rows[0].mainPath)&&rows[0].mainPath===brief.path,'original route mismatch');
    check(object(raw.realEvidence)&&Object.keys(raw.realEvidence).length>0&&Object.values(raw.realEvidence).every(v=>v==='NOT_RUN'),'local evidence cannot claim real acceptance');
    const counts=countSummary(rows[0].counts);
    check(JSON.stringify(counts)===JSON.stringify(countSummary(brief.recordedCounts)),'scenario count summary mismatch');
    return {id,path,runId:raw.runId,route:rows[0].mainPath,counts,hasRecordedError:rows[0].error!=null};
  });
  check(new Set(scenarios.map(s=>s.runId)).size===6,'scenario run identities must be distinct');
  return {source:{...m.source},screenshots,scenarios,
    captureFinishedUTC:m.finishedUTC,video:m.video,
    manifestSHA256:hash(Buffer.from(JSON.stringify(m)))};
}

const TITLES={receipt:'Whole warehouse receipt',authorization:'Wallet authorization scope',
  timeline:'Trade and registration timeline',rollback:'Suffix recovery',queue:'Pending operations',evidence:'Run evidence'};
const DEMO_TITLES=['Single transfer and collection','Independent prefix release','B refusal and full suffix recovery',
  'C refusal with the completed prefix preserved','Recovery with an exhausted gas budget','Trading cutoff and collection'];
function text(slide,value,box,font,size=24,bold=false){
  const shape=slide.shapes.add({geometry:'textbox',position:box,fill:'none',line:{fill:'none',width:0}});
  shape.text=value;
  shape.text.style={fontFamily:font,fontSize:size,bold,color:'#142738'};
  return shape;
}
function baseSlide(p,title,font){
  const slide=p.slides.add(); slide.background.fill='#FFFFFF';
  text(slide,title,{left:64,top:30,width:1152,height:72},font,36,true);
  return slide;
}
function photo(slide,item){
  const frame={left:64,top:122,width:1152,height:470};
  const scale=Math.min(frame.width/item.size.width,frame.height/item.size.height);
  const width=item.size.width*scale,height=item.size.height*scale;
  slide.images.add({blob:item.data.buffer.slice(item.data.byteOffset,item.data.byteOffset+item.data.byteLength),
    contentType:'image/png',alt:'Actual browser capture: '+item.entry,fit:'contain',
    position:{left:frame.left+(frame.width-width)/2,top:frame.top+(frame.height-height)/2,width,height}});
}
/** Pure preparation. The authorized QA host supplies captured bytes and a verified font.
 * Dependency import happens only when this function runs. No install, filesystem,
 * browser, provider or runtime creation is performed here. */
export async function buildPresentation(captured,{fontFamily,artifactTool}={}){
  check(typeof fontFamily==='string'&&/^[A-Za-z0-9 ,.-]{1,80}$/.test(fontFamily),'explicit verified font family required');
  const v=validateCapture(captured);
  const api=artifactTool??await import('@oai/artifact-tool');
  check(typeof api.Presentation?.create==='function'&&typeof api.PresentationFile?.exportPptx==='function','original artifact-tool API required');
  const p=api.Presentation.create({slideSize:{width:1280,height:720}});
  const sourceNote='Runtime commit '+v.source.commit+'\nTree '+v.source.tree+'\nCapture manifest SHA256 '+v.manifestSHA256;
  let slide=baseSlide(p,'8415EX local browser demonstration',fontFamily);
  text(slide,'One NFT represents one whole warehouse receipt.\nOwner, registered holder and each segment payment remain separate.\nThe following images come from the original local workbench browser capture.',
    {left:64,top:160,width:1152,height:230},fontFamily,28);
  text(slide,'LOCAL SIMULATION\nRegistrars and accounts are synthetic. No institutional cooperation is implied.\nProvider signing, Sepolia execution and production acceptance: NOT_RUN',
    {left:64,top:430,width:1152,height:180},fontFamily,24);
  slide.speakerNotes.text=sourceNote;
  for(const name of NATIVE){
    const item=v.screenshots.find(s=>s.entry==='native-'+name);
    slide=baseSlide(p,TITLES[name],fontFamily); photo(slide,item);
    text(slide,'Actual browser view of the local simulation. Real provider and chain acceptance remain NOT_RUN.',
      {left:64,top:615,width:1152,height:70},fontFamily,20);
    slide.speakerNotes.text=sourceNote+'\nCapture '+item.path+'\nPNG SHA256 '+hash(item.data)+'\nObserved '+String(item.observedUTC);
  }
  for(const [i,scenario] of v.scenarios.entries()){
    const item=v.screenshots.find(s=>s.entry===scenario.id);
    slide=baseSlide(p,scenario.id+': '+DEMO_TITLES[i],fontFamily); photo(slide,item);
    const counts=Object.entries(scenario.counts).map(([k,n])=>k+' '+n).join(', ');
    text(slide,'LOCAL SIMULATION. '+scenario.route+'. Recorded counts: '+counts+'.'+
      (scenario.hasRecordedError?' The scenario recorded an error.':''),
      {left:64,top:610,width:1152,height:80},fontFamily,19);
    slide.speakerNotes.text=sourceNote+'\nScenario '+scenario.id+'\nRun '+scenario.runId+
      '\nEvidence '+scenario.path+'\nScreenshot '+item.path+'\nPNG SHA256 '+hash(item.data)+
      '\nRecorded counts are retained observations, not independent QA acceptance.';
  }
  slide=baseSlide(p,'Evidence and remaining acceptance',fontFamily);
  text(slide,'Actual browser screenshots document a local simulation.\nThe source and scenario run identities remain attached to each image.\nWallet signing, the specified Sepolia asset and deployed operation require separate evidence.\nRendering, PowerPoint opening and visual review remain independent QA work.',
    {left:64,top:150,width:1152,height:300},fontFamily,28);
  const video=object(v.video)&&v.video.kind==='EXISTING_BROWSER_CONTEXT_RECORDING'
    ?'The original browser video bytes were collected. Playback and content acceptance remain separate.'
    :'A completed browser recording is not present in this capture.';
  text(slide,video,{left:64,top:500,width:1152,height:120},fontFamily,24);
  slide.speakerNotes.text=sourceNote;
  slide=baseSlide(p,'Runtime source and capture identity',fontFamily);
  text(slide,'Commit\n'+v.source.commit+'\n\nTree\n'+v.source.tree,
    {left:64,top:150,width:1152,height:240},fontFamily,24);
  text(slide,'Capture manifest SHA256\n'+v.manifestSHA256+'\n\nCapture finished UTC\n'+String(v.captureFinishedUTC),
    {left:64,top:420,width:1152,height:225},fontFamily,20);
  slide.speakerNotes.text=sourceNote;
  const manifest={schema:'8415ex-native-presentation/1',source:v.source,
    inputManifestSHA256:v.manifestSHA256,slides:15,contentKind:'LOCAL_BROWSER_SIMULATION',
    fontPolicy:{basis:'design',families:[fontFamily]},rendering:'NOT_RUN',visualQA:'NOT_RUN',
    powerPointOpen:'NOT_RUN',providerSigningChain:'NOT_RUN',deployment:'NOT_RUN',
    finalAcceptance:'NOT_RUN',scenarioRuns:v.scenarios.map(s=>({id:s.id,runId:s.runId,route:s.route,counts:s.counts}))};
  return {presentation:p,manifest,exportPptx:()=>api.PresentationFile.exportPptx(p)};
}
/** Render only when the independent Linux QA host calls this explicitly. */
export async function renderSlides(prepared){
  const previews=[];
  for(const [i,slide] of prepared.presentation.slides.items.entries()){
    const png=await prepared.presentation.export({slide,format:'png',scale:1});
    previews.push({slide:i+1,blob:png});
  }
  return previews;
}
