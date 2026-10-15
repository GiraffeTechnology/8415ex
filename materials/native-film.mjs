/** Film delivery preparation from the original finalized browser recording. */
import {createHash} from 'node:crypto';
import {validateCapture} from './native-presentation.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
const check=(v,message)=>{if(!v)throw new Error(message);};
const text=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const encoder=new TextEncoder();
const TITLES=['Single transfer and collection','Independent prefix release','B refusal and full suffix recovery',
  'C refusal with the completed prefix preserved','Recovery with an exhausted gas budget','Trading cutoff and collection'];
function utc(value){
  check(typeof value==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value),'explicit UTC recording time required');
  const time=Date.parse(value);check(Number.isFinite(time),'valid UTC recording time required');return time;
}
function stamp(ms){
  const value=Math.floor(ms),h=Math.floor(value/3600000),m=Math.floor(value/60000)%60,s=Math.floor(value/1000)%60;
  return [h,m,s].map(x=>String(x).padStart(2,'0')).join(':')+'.'+String(value%1000).padStart(3,'0');
}
/** timing must come from the original recording context and measured media.
 * Hashes and plausible timing are consistency checks, never independent proof.
 * This function neither probes/transcodes nor opens a path or browser. */
export function buildFilm(captured,timing){
  const v=validateCapture(captured),m=captured.manifest,video=m.video;
  check(video&&typeof video==='object'&&video.kind==='EXISTING_BROWSER_CONTEXT_RECORDING','finalized original browser recording required');
  check(video.path==='video/browser-capture.webm','original recording member required');
  const data=captured.files[video.path];
  check(data instanceof Uint8Array&&data.length>=4&&data.length<=64*1024*1024,'bounded WebM bytes required');
  check(Buffer.from(data.subarray(0,4)).equals(Buffer.from([26,69,223,163])),'WebM container marker required');
  check(video.bytes===data.length&&video.sha256===hash(data),'finalized recording hash mismatch');
  check(timing&&typeof timing==='object'&&Object.keys(timing).sort().join(',')===
    'clockEvidenceRef,mediaDurationMs,recordingFinishedUTC,recordingStartedUTC','complete original recording timing required');
  check(typeof timing.clockEvidenceRef==='string'&&/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(timing.clockEvidenceRef),'non-secret original clock evidence reference required');
  check(Number.isSafeInteger(timing.mediaDurationMs)&&timing.mediaDurationMs>0&&timing.mediaDurationMs<=86400000,'measured bounded media duration required');
  const start=utc(timing.recordingStartedUTC),end=utc(timing.recordingFinishedUTC);
  check(end>start&&timing.mediaDurationMs<=end-start,'recording clock and measured duration disagree');
  const chapters=v.scenarios.map((s,i)=>{
    const shot=v.screenshots.find(x=>x.entry===s.id),offset=utc(shot.observedUTC)-start;
    check(offset>=0&&offset<timing.mediaDurationMs&&utc(shot.observedUTC)<=end,'scenario screenshot is outside original recording');
    return {id:s.id,title:TITLES[i],runId:s.runId,route:s.route,counts:s.counts,
      observedUTC:shot.observedUTC,offsetMs:offset,recordedError:s.hasRecordedError};
  });
  check(chapters.every((c,i)=>i===0||c.offsetMs>chapters[i-1].offsetMs),'chronological distinct scenario observations required');
  const cues=chapters.map((c,i)=>{
    const endMs=i+1<chapters.length?chapters[i+1].offsetMs:timing.mediaDurationMs;
    return c.id+'\n'+stamp(c.offsetMs)+' --> '+stamp(endMs)+'\n'+c.id+' '+c.title+'\nLOCAL SIMULATION. '+c.route+'.\n';
  });
  const source={schema:'8415ex-native-film/1',source:v.source,inputManifestSHA256:v.manifestSHA256,
    video:{path:'browser-capture.webm',bytes:data.length,sha256:hash(data)},timing:{...timing},chapters,
    timingVerification:'HOST_RECORD_REQUIRED_NOT_INDEPENDENTLY_VERIFIED',
    playbackQA:'NOT_RUN',contentQA:'NOT_RUN',providerSigningChain:'NOT_RUN',deployment:'NOT_RUN',finalAcceptance:'NOT_RUN'};
  const links=chapters.map(c=>'<li><button type="button" data-offset="'+String(c.offsetMs/1000)+'">'+
    text(c.id+' '+c.title)+'</button><p>'+text(c.route+' / '+c.runId)+'<br>'+text(JSON.stringify(c.counts))+
    (c.recordedError?' / Scenario recorded an error.':'')+'</p></li>').join('');
  const html='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
    '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; media-src \'self\'; style-src \'unsafe-inline\'; script-src \'unsafe-inline\'">'+
    '<title>8415EX browser demonstration</title><style>body{font:18px system-ui;max-width:1120px;margin:30px auto;padding:20px;color:#142738}video{width:100%}button{font:inherit;text-align:left;padding:8px}p{overflow-wrap:anywhere}li{margin:20px 0}</style>'+
    '<h1>8415EX browser demonstration</h1><p>LOCAL SIMULATION. Registrars, accounts and assets are synthetic. No real institutional cooperation is implied.</p>'+
    '<video id="film" controls preload="metadata"><source src="browser-capture.webm" type="video/webm"><track kind="captions" src="chapters.vtt" srclang="en" label="English" default></video>'+
    '<p>The video retains the original browser recording bytes. Chapters locate screenshot observation times. They do not assert when the underlying operation began.</p>'+
    '<p>Playback, content review, provider signing, Sepolia transactions and deployment acceptance: NOT_RUN.</p><ol>'+links+'</ol>'+
    '<h2>Source</h2><p>Commit '+text(v.source.commit)+'<br>Tree '+text(v.source.tree)+'</p>'+
    '<p><a href="source.json">Source, recording hash and timing reference</a></p>'+
    '<script>const video=document.getElementById("film");document.querySelectorAll("button[data-offset]").forEach(button=>button.addEventListener("click",()=>{video.currentTime=Number(button.dataset.offset);video.play().catch(()=>{});}));</script></html>';
  const files={'browser-capture.webm':new Uint8Array(data),'index.html':encoder.encode(html),
    'chapters.vtt':encoder.encode('WEBVTT\n\n'+cues.join('\n')),'source.json':encoder.encode(JSON.stringify(source,null,2)+'\n')};
  return {files,manifest:{...source,files:Object.fromEntries(Object.entries(files).map(([path,b])=>[path,{bytes:b.length,sha256:hash(b)}]))}};
}
