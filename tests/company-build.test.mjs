import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as State from '../packages/company-build/state.mjs';
import * as Core from '../packages/core/core.mjs';
const path=new URL('../scenarios/electronics_demo/',import.meta.url);
const scenario=JSON.parse(readFileSync(new URL('scenario.json',path),'utf8'));
const canonical=()=>Core.compileCompany(readFileSync(new URL('SOP.extracted.txt',path),'utf8'),readFileSync(new URL('criteria.csv',path),'utf8'),scenario);
const files=[{webkitRelativePath:'다온에듀테크/작업지시서.pdf',name:'작업지시서.pdf',size:42,type:'application/pdf'},
 {webkitRelativePath:'다온에듀테크/검사기준.csv',name:'검사기준.csv',size:32,type:'text/csv'}];
const fresh=()=>State.makeBuildState(files);
const draft=()=>State.prepareReview(State.startBuild(fresh()),canonical());
const finish=()=>State.completeReview(State.correctTask(draft(),'battery'));

test('Folder metadata strips file payloads and preserves Unicode, distinct nested paths and selection',()=>{
 const source=[...files,{name:'작업지시서.pdf',webkitRelativePath:'다른회사/작업지시서.pdf',size:0,secret:'not saved'}];
 const s=State.makeBuildState(source);assert.equal(s.files.length,3);assert.equal(s.files[0].path,files[0].webkitRelativePath);
 assert.ok(s.files.every(f=>f.selected));assert.equal(s.files[2].secret,undefined);assert.equal(s.phase,'selection');
 assert.equal(State.makeBuildState().phase,'upload');assert.equal(State.makeBuildState([{path:'회사/기준.csv',selected:false}]).files[0].selected,false);
});
test('Folder rejects unsafe/duplicate paths and malformed metadata before adoption',()=>{
 for(const path of ['../x','회사/../x','/absolute','C:/private','회사//x','회사/\u0000.pdf'])assert.throws(()=>State.makeBuildState([{path}]),/경로/);
 assert.throws(()=>State.makeBuildState([{path:'회사/x'},{path:'회사/x'}]),/중복/);
 assert.throws(()=>State.makeBuildState([{path:'회사/x',size:-1}]),/크기/);
});
test('No selected file cannot build; choosing any subset still uses the same explicit teaching source',()=>{
 const empty=State.setAllSelected(fresh(),false);assert.throws(()=>State.startBuild(empty),/한 개 이상/);
 const one=State.setFileSelected(empty,empty.files[1].id,true);const s=State.prepareReview(State.startBuild(one),canonical());
 assert.equal(s.files.filter(f=>f.selected).length,1);assert.deepEqual(s.canonicalBundle,canonical());
 assert.equal(s.events.find(e=>e.type==='build_started').resultPolicy,'fixed_electronics_teaching_template');
});
test('Draft changes exactly battery mapping and does not mutate original inputs or canonical source',()=>{
 const s=State.startBuild(fresh()),b=canonical(),old=JSON.stringify({s,b});const d=State.prepareReview(s,b);
 assert.equal(JSON.stringify({s,b}),old);assert.equal(d.draftBundle.criteria.find(c=>c.id==='E-BATTERY').taskId,'circuit');
 assert.equal(d.canonicalBundle.criteria.find(c=>c.id==='E-BATTERY').taskId,'battery');
 const repaired=structuredClone(d.draftBundle);repaired.criteria.find(c=>c.id==='E-BATTERY').taskId='battery';assert.deepEqual(repaired,b);
 assert.equal(d.issue.origin,'authored_demo');
});
test('Review gates reject skip, wrong known task and unknown task; correction history retains wrong attempts',()=>{
 const d=draft();assert.equal(State.canCompleteReview(d),false);assert.throws(()=>State.completeReview(d),/修正|수정/);
 assert.throws(()=>State.reviewedBundle(d),/완료/);assert.throws(()=>State.correctTask(d,'missing'),/등록/);
 const wrong=State.correctTask(d,'final');assert.equal(State.canCompleteReview(wrong),false);assert.throws(()=>State.completeReview(wrong),/수정/);
 const good=State.correctTask(wrong,'battery');assert.ok(State.canCompleteReview(good));
 const attempts=good.events.filter(e=>e.type==='task_mapping_reviewed');assert.deepEqual(attempts.map(e=>e.accepted),[false,true]);
 assert.equal(d.draftBundle.criteria.find(c=>c.id==='E-BATTERY').taskId,'circuit');
});
test('Reviewed bundle is exactly compiler output and compatible with strict existing session validation',()=>{
 const done=finish(),b=State.reviewedBundle(done);assert.deepEqual(b,canonical());
 const session=Core.createSession(scenario,b);assert.equal(Core.validateSession(session,scenario),true);
 b.criteria[0].label='outside mutation';assert.deepEqual(State.reviewedBundle(done),canonical());
});
test('Folder or file selection changes invalidate completed approval and archive prior draft and review',()=>{
 const original=finish(),changed=State.setFileSelected(original,original.files[0].id,false);
 assert.equal(changed.phase,'selection');assert.equal(changed.canonicalBundle,null);assert.equal(changed.archives.length,1);
 assert.equal(changed.archives[0].phase,'ontology');assert.equal(changed.archives[0].issue.resolved,true);
 assert.equal(original.archives.length,0);assert.throws(()=>State.reviewedBundle(changed),/완료/);
 const replaced=State.replaceFiles(original,[{path:'다른회사/x.txt'}]);assert.equal(replaced.files.length,1);assert.equal(replaced.issue,null);assert.equal(replaced.archives[0].reason,'folder_replaced');
});
test('Selecting unchanged metadata does not erase a valid review',()=>{
 const s=finish();assert.deepEqual(State.setAllSelected(s,true),s);assert.deepEqual(State.setFileSelected(s,s.files[0].id,true),s);
});
test('Interrupted processing returns to selection and records interruption instead of claiming completion',()=>{
 const running=State.startBuild(fresh()),restored=State.restoreBuildState(JSON.parse(JSON.stringify(running)),scenario);
 assert.equal(restored.phase,'selection');assert.equal(restored.canonicalBundle,null);assert.equal(restored.events.at(-1).type,'build_interrupted');
 assert.equal(restored.archives[0].phase,'processing');assert.equal(running.phase,'processing');
});
test('Refresh restores reviewed work and preserves editable-but-unresolved wrong attempt',()=>{
 for(const s of [fresh(),draft(),State.correctTask(draft(),'propeller'),finish()])assert.deepEqual(State.restoreBuildState(JSON.parse(JSON.stringify(s)),scenario),s);
});
test('Restore rejects altered source, unrelated draft edits, invalid metadata and fabricated completed flags',()=>{
 const done=finish();const mutate=fn=>{const s=structuredClone(done);fn(s);assert.throws(()=>State.restoreBuildState(s,scenario));};
 mutate(s=>{s.canonicalBundle.criteria[0].label='tampered';});
 mutate(s=>{s.draftBundle.criteria[0].allowWorker=true;});
 mutate(s=>{s.files[0].path='../private';});
 mutate(s=>{s.events=[];});
 const pending=draft();pending.phase='ontology';pending.issue.resolved=true;assert.throws(()=>State.restoreBuildState(pending,scenario));
 assert.throws(()=>State.restoreBuildState(done,{...scenario,id:'another'}),/시나리오/);
});
test('Review rejects an altered supported canonical contract and unrelated exercises',()=>{
 const s=State.startBuild(fresh()),bad=canonical();bad.criteria.find(c=>c.id==='E-BATTERY').taskId='switch';
 assert.throws(()=>State.prepareReview(s,bad),/원본 작업/);assert.throws(()=>State.prepareReview(s,{...canonical(),companyId:'other'}),/전자 조립/);
});

test('Learner review note is optional, bounded and preserved with every correction attempt',()=>{
 const d=draft(),good=State.correctTask(d,'battery','  SOP의 배터리 삽입 단계와 대조  ');
 assert.equal(good.events.at(-1).note,'SOP의 배터리 삽입 단계와 대조');
 assert.equal(State.correctTask(d,'circuit').events.at(-1).note,'');
 assert.throws(()=>State.correctTask(d,'battery',false),/메모/);
 assert.throws(()=>State.correctTask(d,'battery','x'.repeat(1001)),/메모/);
});
