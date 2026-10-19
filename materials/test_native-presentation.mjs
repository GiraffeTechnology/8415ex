import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {validateCapture,buildPresentation} from './native-presentation.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
const PNG=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jI0kAAAAASUVORK5CYII=','base64');
function fixture(){
  const source={commit:'a'.repeat(40),tree:'b'.repeat(40)},files={},captures=[],scenarios=[];
  const names=['receipt','authorization','timeline','rollback','queue','evidence'].map(n=>'native-'+n);
  const counts={passed:1,failed:0,blocked:0,'not-run':2};
  for(let i=1;i<=6;i++){
    const id='DEMO-'+String(i).padStart(2,'0'),runId='demo-'+String(i).repeat(32);
    const route=['REG_DIRECT','REG_ELECTRONIC','REG_INTERMEDIARY'][(i-1)%3];
    const row={scenarioId:id,mainPath:route,counts,error:null};
    files['evidence/'+id+'.json']=Buffer.from(JSON.stringify({runId,source,evidenceKind:'LOCAL_SIMULATION',
      realEvidence:{provider:'NOT_RUN',chain:'NOT_RUN'},report:{scenarios:[row]}}));
    scenarios.push({scenario:id,runId,path:route,recordedCounts:counts,recordedError:null});names.push(id);
  }
  for(const name of names){files['screens/'+name+'.png']=Buffer.from(PNG);
    captures.push({entry:name,HTTP:200,pngSHA256:hash(PNG),observedUTC:'2026-01-01T00:00:00Z'});}
  for(const name of ['start','end']) files['evidence/native-'+name+'.json']=Buffer.from(JSON.stringify({source}));
  const manifest={schema:'8415ex-native-browser-materials/1',source,
    contentKind:'ACTUAL_BROWSER_SCREENSHOTS_OF_LOCAL_SIMULATION',files:{},captures,scenarios,
    finishedUTC:'2026-01-01T00:00:01Z',video:'NOT_RUN'};
  for(const [path,b] of Object.entries(files))manifest.files[path]={bytes:b.length,sha256:hash(b)};
  return {files,manifest};
}
function replaceRecord(c,path,value){const b=Buffer.from(JSON.stringify(value));c.files[path]=b;c.manifest.files[path]={bytes:b.length,sha256:hash(b)};}

test('retains all six runs and four original count names',()=>{
  const v=validateCapture(fixture()); assert.equal(v.scenarios.length,6);
  assert.equal(v.screenshots.length,12); assert.equal(v.scenarios[0].counts['not-run'],2);
});
test('rejects missing screenshot and changed captured bytes',()=>{
  let c=fixture();delete c.files['screens/native-receipt.png'];assert.throws(()=>validateCapture(c));
  c=fixture();c.files['screens/native-receipt.png']=Buffer.from('changed');assert.throws(()=>validateCapture(c));
});
test('rejects mixed runtime source and real evidence promotion',()=>{
  let c=fixture();let path='evidence/DEMO-01.json',r=JSON.parse(c.files[path]);r.source.tree='c'.repeat(40);
  replaceRecord(c,path,r);assert.throws(()=>validateCapture(c));
  c=fixture();r=JSON.parse(c.files[path]);r.realEvidence.chain='PASS';replaceRecord(c,path,r);assert.throws(()=>validateCapture(c));
});
test('rejects duplicate run and altered scenario count summary',()=>{
  let c=fixture();c.manifest.scenarios[1].runId=c.manifest.scenarios[0].runId;assert.throws(()=>validateCapture(c));
  c=fixture();c.manifest.scenarios[0].recordedCounts={passed:99,failed:0,blocked:0,'not-run':2};assert.throws(()=>validateCapture(c));
});
test('prepares fifteen editable slide objects with no acceptance promotion',async()=>{
  const slides=[];const api={Presentation:{create(){return {slides:{items:slides,add(){const s={background:{},speakerNotes:{},
    shapes:{add(){return {set text(value){this.value=value;},get text(){return this.surface??={style:{}};}};}},images:{add(){}}};slides.push(s);return s;}}};}},
    PresentationFile:{async exportPptx(){return {kind:'MOCK_ONLY'};}}};
  const result=await buildPresentation(fixture(),{fontFamily:'Verified Test Font',artifactTool:api});
  assert.equal(slides.length,15);assert.equal(result.manifest.finalAcceptance,'NOT_RUN');
  assert.equal(result.manifest.visualQA,'NOT_RUN');assert.match(slides[7].speakerNotes.text,/demo-1{32}/);
});
test('missing verified font refuses before renderer import',async()=>{
  await assert.rejects(buildPresentation(fixture()),/font family/);
});
