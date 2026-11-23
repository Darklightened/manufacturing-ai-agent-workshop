import {PLAN} from '../packages/worker-flow/plan.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileCompany} from '../packages/core/core.mjs';
import * as W from '../packages/worker-flow/state.mjs';
import {buildInspectionRecord,renderInspectionHTML,makeInspectionDocx} from '../packages/worker-flow/report.mjs';

const scenario=JSON.parse(readFileSync(new URL('../scenarios/electronics_demo/scenario.json',import.meta.url)));
const source=readFileSync(new URL('../scenarios/electronics_demo/criteria.csv',import.meta.url),'utf8');
const text=['company_id: '+scenario.companyId,'process_id: '+scenario.processId,...scenario.tasks.map(t=>'task_id: '+t.id)].join('\n');
const bundle=compileCompany(text,source,scenario),at='2026-11-23T10:00:00.000Z';
const image='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aTN0AAAAASUVORK5CYII=';
function ready(){let s=W.createWorkerState(bundle,{id:'report-test-1',at});s=W.registerWorker(s,{name:'김민수',employeeId:'EMP-024'},at);s=W.authenticateWorker(s,{code:'6421',confirmed:true},at);s=W.selectProcess(s,bundle.processId,at);return W.startWork(s,at);}
function battery(verdict=null){let s=ready();for(let n=0;n<3;n++){s=W.observeProgress(s,1,{at});s=W.nextStage(s,at);}s=W.observeProgress(s,1,{at});if(verdict){s=W.deliverQuestion(s,s.questions[0].id,'screen',at);s=W.answerQuestion(s,s.questions[0].id,{verdict,text:verdict==='met'?'극성을 직접 확인했습니다.':'배터리 방향이 반대입니다.'},at);}return s;}
function complete(){let s=battery('met');for(let n=0;n<2;n++){s=W.nextStage(s,at);s=W.observeProgress(s,1,{at});}return s;}
function args(state){return {state,bundle,scenario,images:Object.fromEntries(state.checks.filter(c=>c.imagePath).map(c=>[c.imagePath,image]))};}
function zipEntries(bytes){const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),entries=new Map();let offset=0;while(v.getUint32(offset,true)===0x04034b50){const method=v.getUint16(offset+8,true),size=v.getUint32(offset+18,true),nameLen=v.getUint16(offset+26,true),extraLen=v.getUint16(offset+28,true);assert.equal(method,0);const name=new TextDecoder().decode(bytes.slice(offset+30,offset+30+nameLen)),begin=offset+30+nameLen+extraLen;entries.set(name,bytes.slice(begin,begin+size));offset=begin+size;}assert.equal(v.getUint32(offset,true),0x02014b50);assert.equal(v.getUint32(bytes.length-22,true),0x06054b50);assert.equal(v.getUint16(bytes.length-12,true),entries.size);return entries;}
const decode=(files,path)=>new TextDecoder().decode(files.get(path));

test('inspection projection keeps 18 checks, six source criteria, raw unknown and worker-confirmed outcome distinct',()=>{
 const r=buildInspectionRecord(args(complete()));assert.equal(r.rows.length,18);assert.equal(r.stages.length,6);assert.equal(r.resultCode,'complete');assert.equal(new Set(r.rows.map(c=>c.criterionId)).size,6);assert.equal(r.summary.passedStages,6);
 const battery=r.rows.find(c=>c.id==='W-BATTERY-03');assert.equal(battery.raw,'확인 필요');assert.equal(battery.verdict,'충족');assert.equal(battery.origin,'작업자 확인');assert.equal(r.questions[0].answers[0].text,'극성을 직접 확인했습니다.');assert.equal(r.events.filter(e=>e.type==='agent_pass').length,6);assert.equal(r.identifiers.operator,'김민수');assert.match(r.identifiers.authentication,/교육용 화면 인증/);
});
test('evidence captions use original still time instead of authored observation threshold',()=>{
 const s=W.observeProgress(ready(),PLAN[0].checks[0].threshold,{at}),r=buildInspectionRecord(args(s));assert.equal(r.evidence.length,1);assert.notEqual(r.evidence[0].sourceTime,r.evidence[0].imageTime);assert.match(r.evidence[0].caption,/0:00\.500/);assert.equal(r.rows[0].sourceTime,Number((PLAN[0].sourceStart+(PLAN[0].sourceEnd-PLAN[0].sourceStart)*PLAN[0].checks[0].threshold).toFixed(3)));
});
test('unanswered, negative and strict-policy-revoked outcomes remain held in both document projections',async()=>{
 const states=[battery(),battery('violated'),W.setEvidencePolicy(complete(),'visual_only',at)];
 for(const state of states){const a=args(state),r=buildInspectionRecord(a),html=renderInspectionHTML(a);assert.equal(r.resultCode,'held');assert.match(html,/data-final-status="held"/);assert.match(html,/保留|보류/);assert(!html.includes('data-final-status="complete"'));const files=zipEntries(await makeInspectionDocx(a));assert.match(decode(files,'word/document.xml'),/보류 · 미완료 또는 미충족 항목 존재/);}
 const r=buildInspectionRecord(args(states[2]));assert(r.events.some(e=>e.type==='agent_pass_revoked'));assert(r.events.some(e=>e.type==='agent_completion_revoked'));assert(r.rows.some(c=>c.verdictCode==='unknown'));assert.equal(r.summary.passedStages,3);
});
test('dense HTML has actual table structure, local evidence images, blank approvals and escaped worker input',()=>{
 let s=W.createWorkerState(bundle,{id:'escape-test',at});s=W.registerWorker(s,{name:'<img src=x onerror=alert(1)>',employeeId:'E<1'},at);const html=renderInspectionHTML(args(s));assert.match(html,/&lt;img src=x onerror=alert\(1\)&gt;/);assert(!html.includes('<img src=x onerror'));assert.match(html,/<table/);assert.match(html,/미서명/);assert.match(html,/미승인/);assert.match(html,/미입력/);assert.match(html,/강의용 예시/);assert.match(html,/미관찰/);
});
test('real DOCX is an OOXML ZIP with typed relationships and six embedded evidence files',async()=>{
 const data=await makeInspectionDocx(args(complete())),files=zipEntries(data);assert(data instanceof Uint8Array);assert.equal(data[0],0x50);assert.equal(data[1],0x4b);for(const part of ['[Content_Types].xml','_rels/.rels','word/document.xml','word/styles.xml','word/header1.xml','word/footer1.xml','word/_rels/document.xml.rels','docProps/core.xml'])assert(files.has(part));assert.equal([...files.keys()].filter(k=>k.startsWith('word/media/')).length,6);
 const xml=decode(files,'word/document.xml');assert.match(xml,/<w:tbl>/);assert.match(xml,/<w:tblHeader\/>/);assert.match(xml,/w:w="11906"/);assert.match(xml,/W-BATTERY-03/);assert.match(xml,/교육 기준 충족 · 검토 대기/);assert.match(xml,/미서명/);assert.match(decode(files,'word/footer1.xml'),/w:instr="PAGE"/);
 for(const [,id]of xml.matchAll(/r:embed="([^"]+)"/g))assert(decode(files,'word/_rels/document.xml.rels').includes(`Id="${id}"`));assert.equal([...xml.matchAll(/r:embed=/g)].length,6);
});
test('DOCX does not silently drop unavailable or incompatible evidence images',async()=>{
 const state=complete();await assert.rejects(()=>makeInspectionDocx({state,bundle,scenario}),/증거 사진이 없습니다/);const a=args(state),path=buildInspectionRecord(a).evidence[0].image;a.images[path]='data:image/svg+xml;base64,PHN2Zy8+';await assert.rejects(()=>makeInspectionDocx(a),/PNG\/JPEG/);
});
test('report rejects edited verdicts or mismatched criteria instead of certifying forged completion',()=>{
 const state=complete(),bad=structuredClone(state);bad.checks[0].verdict='unknown';assert.throws(()=>buildInspectionRecord(args(bad)),/기록과 검사 결과/);assert.throws(()=>buildInspectionRecord({...args(state),bundle:{...bundle,version:'different'}}),/버전/);const b=structuredClone(bundle);b.criteria[0].label='임의 기준';assert.throws(()=>buildInspectionRecord({...args(state),bundle:b}),/회사 기준/);
});


test('unobserved checks disclose no authored future finding or evidence picture',()=>{
 const r=buildInspectionRecord(args(ready()));
 assert.equal(r.evidence.length,0);
 assert(r.rows.every(row=>row.raw==='미관찰'&&row.origin==='미기록'&&row.reason==='관찰 지점에 도달하지 않음'&&row.image===null));
});
