import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {buildFilm} from './native-film.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
function fixture(){
  const source={commit:'a'.repeat(40),tree:'b'.repeat(40)},files={},captures=[],scenarios=[];
  // Synthetic container headers exercise contract checks, never playback acceptance.
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jI0kAAAAASUVORK5CYII=','base64');
  const counts={passed:1,failed:0,blocked:0,'not-run':2};
  const names=['receipt','authorization','timeline','rollback','queue','evidence'].map(n=>'native-'+n);
  for(let i=1;i<=6;i++){
    const id='DEMO-'+String(i).padStart(2,'0'),runId='demo-'+String(i).repeat(32),path='REG_DIRECT';
    const record={source,runId,evidenceKind:'LOCAL_SIMULATION',realEvidence:{chain:'NOT_RUN'},
      report:{scenarios:[{scenarioId:id,mainPath:path,counts,error:null}]}};
    files['evidence/'+id+'.json']=Buffer.from(JSON.stringify(record));
    scenarios.push({scenario:id,runId,path,recordedCounts:counts});names.push(id);
  }
  for(const [i,name] of names.entries()){
    files['screens/'+name+'.png']=Buffer.from(png);
    captures.push({entry:name,HTTP:200,pngSHA256:hash(png),observedUTC:new Date(Date.UTC(2026,0,1,0,0,i+1)).toISOString()});
  }
  for(const n of ['start','end'])files['evidence/native-'+n+'.json']=Buffer.from(JSON.stringify({source}));
  const webm=Buffer.from([26,69,223,163,0]);files['video/browser-capture.webm']=webm;
  const manifest={schema:'8415ex-native-browser-materials/1',source,captures,scenarios,
    contentKind:'ACTUAL_BROWSER_SCREENSHOTS_OF_LOCAL_SIMULATION',finishedUTC:'2026-01-01T00:00:13Z',files:{},
    video:{kind:'EXISTING_BROWSER_CONTEXT_RECORDING',path:'video/browser-capture.webm',bytes:webm.length,sha256:hash(webm)}};
  for(const [path,b]of Object.entries(files))manifest.files[path]={bytes:b.length,sha256:hash(b)};
  return {files,manifest};
}
const timing=()=>({recordingStartedUTC:'2026-01-01T00:00:00Z',recordingFinishedUTC:'2026-01-01T00:00:20Z',mediaDurationMs:20000,clockEvidenceRef:'fixture-clock-1'});

test('requires original finalized recording',()=>{const c=fixture();c.manifest.video='NOT_RUN';assert.throws(()=>buildFilm(c,timing()));});
test('does not invent a recording start or duration',()=>{assert.throws(()=>buildFilm(fixture()));});
test('preserves bytes and emits six source-bound chapter cues',()=>{
  const c=fixture(),result=buildFilm(c,timing());
  assert.deepEqual(result.files['browser-capture.webm'],new Uint8Array(c.files['video/browser-capture.webm']));
  assert.equal(result.manifest.chapters.length,6);assert.equal(result.manifest.playbackQA,'NOT_RUN');
  assert.equal(result.manifest.finalAcceptance,'NOT_RUN');
  assert.match(new TextDecoder().decode(result.files['chapters.vtt']),/00:00:07\.000 --> 00:00:08\.000/);
  assert.match(new TextDecoder().decode(result.files['index.html']),/LOCAL SIMULATION/);
});
test('rejects observations outside measured recording',()=>{const t=timing();t.mediaDurationMs=5000;assert.throws(()=>buildFilm(fixture(),t));});
test('rejects altered original video bytes',()=>{const c=fixture();c.files['video/browser-capture.webm'][4]=1;assert.throws(()=>buildFilm(c,timing()));});
test('rejects reverse scenario timing',()=>{const c=fixture();c.manifest.captures.find(s=>s.entry==='DEMO-02').observedUTC='2026-01-01T00:00:06Z';assert.throws(()=>buildFilm(c,timing()));});
