import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compileCompany} from '../packages/core/core.mjs';
import {PLAN,CHECKS,SOURCE_DURATION,PROCESS} from '../packages/worker-flow/plan.mjs';
import * as W from '../packages/worker-flow/state.mjs';
const scenario=JSON.parse(readFileSync(new URL('../scenarios/electronics_demo/scenario.json',import.meta.url)));
const csv=readFileSync(new URL('../scenarios/electronics_demo/criteria.csv',import.meta.url),'utf8');
const pdfText=readFileSync(new URL('../scenarios/electronics_demo/SOP.extracted.txt',import.meta.url),'utf8');
const bundle=compileCompany(pdfText,csv,scenario),at='2026-11-23T10:00:00.000Z';
const create=()=>W.createWorkerState(bundle,{id:'worker-test-1',at});
function ready(){let s=create();s=W.registerWorker(s,{name:'김민수',employeeId:'EMP-024'},at);s=W.authenticateWorker(s,{code:'6421',confirmed:true},at);s=W.selectProcess(s,PROCESS.id,at);return W.startWork(s,at);}
function toBattery(){let s=ready();for(let i=0;i<3;i++){s=W.observeProgress(s,1,{at});s=W.nextStage(s,at);}return W.observeProgress(s,1,{at});}
function complete(){let s=toBattery(),q=s.questions[0];s=W.deliverQuestion(s,q.id,'screen',at);s=W.answerQuestion(s,q.id,{verdict:'met'},at);for(let i=0;i<2;i++){s=W.nextStage(s,at);s=W.observeProgress(s,1,{at});}return s;}
test('authored plan binds 18 checks to canonical six targets and causal source images',()=>{
 assert.equal(CHECKS.length,18);assert.equal(new Set(CHECKS.map(c=>c.id)).size,18);assert.equal(PLAN.length,6);
 assert(PLAN.at(-1).sourceEnd<=SOURCE_DURATION);
 for(const p of PLAN){assert.equal(p.checks.length,3);for(const c of p.checks){assert.equal(c.criterionId,p.criterionId);assert.equal(c.taskId,p.id);assert(c.imageTime<=p.sourceStart+(p.sourceEnd-p.sourceStart)*c.threshold+.001);assert.equal(c.origin,'authored_demo');}}
});
test('registration, explicit demo authentication and process selection are independent required gates',()=>{
 let s=create();assert.equal(s.setupStep,'register');assert.throws(()=>W.startWork(s,at));assert.throws(()=>W.selectProcess(s,PROCESS.id,at));
 s=W.registerWorker(s,{name:'김민수',employeeId:'EMP-024'},at);assert.equal(s.setupStep,'authenticate');assert.throws(()=>W.authenticateWorker(s,{code:'0000',confirmed:true},at));assert.throws(()=>W.authenticateWorker(s,{code:'6421',confirmed:false},at));
 s=W.authenticateWorker(s,{code:'6421',confirmed:true},at);assert.equal(s.setupStep,'process');assert.equal(s.authentication.simulation,true);assert.throws(()=>W.selectProcess(s,'FAKE',at));
 s=W.selectProcess(s,PROCESS.id,at);assert.equal(s.setupStep,'ready');s=W.startWork(s,at);assert.equal(s.started,true);assert.throws(()=>W.registerWorker(s,{name:'다른 작업자',employeeId:'OTHER'},at));
});
test('wrong source bundle and altered task mappings cannot enter worker exercise',()=>{
 assert.throws(()=>W.createWorkerState({...bundle,processId:'other'}));
 const b=structuredClone(bundle);b.criteria.find(c=>c.id==='E-BATTERY').taskId='circuit';assert.throws(()=>W.createWorkerState(b));
});
test('photos are typed image bytes, not remote URLs or executable SVGs',()=>{
 assert.throws(()=>W.registerWorker(create(),{name:'a',employeeId:'b',photo:'https://example.com/a.png'}));
 assert.throws(()=>W.registerWorker(create(),{name:'a',employeeId:'b',photo:'data:image/svg+xml;base64,AAAA'}));
 const s=W.registerWorker(create(),{name:'a',employeeId:'b',photo:'data:image/png;base64,AAAA'},at);assert.equal(s.worker.photo,'data:image/png;base64,AAAA');
});
test('video progress reveals checks in order and cannot advance future stages',()=>{
 const initial=ready();let s=W.observeProgress(initial,.1,{at});assert.equal(W.summarizeWorker(s).met,1);assert.equal(W.summarizeWorker(initial).met,0);assert.throws(()=>W.nextStage(s,at));
 assert.throws(()=>W.observeProgress(s,.5,{stageId:'battery',at}));assert.throws(()=>W.observeProgress(s,1.01,{at}));assert.throws(()=>W.observeProgress(s,NaN,{at}));assert.throws(()=>W.observeProgress(s,.05,{at}));
 s=W.observeProgress(s,.8,{at});assert.equal(W.summarizeWorker(s).met,2);s=W.observeProgress(s,1,{at});assert(s.stages[0].passed);assert.equal(W.summarizeWorker(s).canNext,true);assert(s.checks.filter(c=>c.taskId!=='preparation').every(c=>c.verdict==='not_due'));
});
test('repeated progress is idempotent and pass signal precedes worker next signal',()=>{
 let s=W.observeProgress(ready(),1,{at});assert.equal(s.events.filter(e=>e.type==='agent_pass').length,1);assert.strictEqual(W.observeProgress(s,1,{at}),s);s=W.nextStage(s,at);const pass=s.events.find(e=>e.type==='agent_pass'),next=s.events.find(e=>e.type==='worker_next');assert(pass.sequence<next.sequence);assert.equal(s.stageIndex,1);
});
test('battery ambiguity must be delivered and answered; unknown source observation survives positive reply',()=>{
 let s=toBattery();assert.equal(s.stageIndex,3);assert.equal(s.stages[3].status,'held');assert.equal(s.questions.length,1);assert.throws(()=>W.nextStage(s,at));const q=s.questions[0];assert.throws(()=>W.answerQuestion(s,q.id,{verdict:'met'},at));
 s=W.deliverQuestion(s,q.id,'voice',at);s=W.answerQuestion(s,q.id,{verdict:'met',text:'홀더 표시와 방향을 직접 대조했습니다.'},at);const row=s.checks.find(c=>c.id===q.checkId);assert.equal(row.rawVerdict,'unknown');assert.equal(row.verdict,'met');assert.equal(row.origin,'worker_confirmed');assert.equal(s.questions[0].state,'resolved');assert(s.stages[3].passed);
});
test('negative and uncertain replies keep the gate closed; correction preserves prior answers',()=>{
 let s=toBattery(),qid=s.questions[0].id;s=W.deliverQuestion(s,qid,'screen',at);s=W.answerQuestion(s,qid,{verdict:'violated'},at);assert.equal(W.summarizeWorker(s).violated,1);assert.throws(()=>W.nextStage(s,at));
 s=W.answerQuestion(s,qid,{verdict:'unknown'},at);assert.equal(W.summarizeWorker(s).unknown,1);assert.throws(()=>W.nextStage(s,at));s=W.answerQuestion(s,qid,{verdict:'met',text:'방향을 바로잡고 다시 확인했습니다.'},at);assert.equal(s.questions[0].answers.length,3);assert(s.stages[3].passed);
});
test('complete report has all checks, six pass signals and no unresolved question',()=>{
 const s=complete(),summary=W.summarizeWorker(s);assert(summary.completed);assert.equal(summary.met,18);assert.equal(summary.passedStages,6);assert.equal(summary.openQuestions.length,0);assert.equal(s.events.filter(e=>e.type==='agent_pass').length,6);assert.equal(s.events.filter(e=>e.type==='agent_complete').length,1);
});
test('strict policy revokes completion/downstream gates and preserves pass history; repair requires advancing again',()=>{
 let s=complete();const oldSignals=s.events.filter(e=>e.type==='agent_pass').length;s=W.setEvidencePolicy(s,'visual_only',at);assert.equal(s.completed,false);assert.equal(s.stageIndex,3);assert.equal(s.checks.find(c=>c.id==='W-BATTERY-03').verdict,'unknown');assert.equal(s.events.filter(e=>e.type==='agent_pass').length,oldSignals);assert.equal(s.events.filter(e=>e.type==='agent_pass_revoked').length,3);assert.throws(()=>W.nextStage(s,at));
 s=W.setEvidencePolicy(s,'worker_evidence',at);assert.equal(s.completed,false);assert.equal(s.stageIndex,3);assert.equal(s.stages[4].progress,1);assert.equal(s.stages[4].passed,false);s=W.nextStage(s,at);assert(s.stages[4].passed);assert(!s.completed);s=W.nextStage(s,at);assert(s.completed);
});
test('replay validates completed/restored progress and rejects altered decisions, commands or bundles',()=>{
 const s=complete();assert.deepEqual(W.validateWorkerState(JSON.parse(JSON.stringify(s)),bundle),s);
 for(const mutate of [x=>x.checks[0].verdict='unknown',x=>x.events.pop(),x=>x.stageIndex=0,x=>x.commands[0].payload.name='다른이름',x=>x.completed=false]){const bad=structuredClone(s);mutate(bad);assert.throws(()=>W.validateWorkerState(bad,bundle));}
 assert.throws(()=>W.validateWorkerState(s,{...bundle,version:'changed'}));
});
test('input modality stays explicit and a changed worker requires fresh authentication',()=>{
 let s=W.registerWorker(create(),{name:'첫 작업자',employeeId:'A'},at);s=W.authenticateWorker(s,{code:'6421',confirmed:true},at);s=W.registerWorker(s,{name:'두번째 작업자',employeeId:'B'},at);assert.equal(s.authentication,null);assert.equal(s.process,null);
 s=W.observeProgress(ready(),1,{source:'still_fallback',at});assert(s.checks.filter(c=>c.verdict!=='not_due').every(c=>c.inputMode==='still_fallback'));
});

test('a corrected negative answer revokes a resolved current stage without erasing the earlier pass',()=>{
 let s=toBattery(),qid=s.questions[0].id;s=W.deliverQuestion(s,qid,'screen',at);s=W.answerQuestion(s,qid,{verdict:'met'},at);assert(s.stages[3].passed);const passes=s.events.filter(e=>e.type==='agent_pass').length;
 s=W.answerQuestion(s,qid,{verdict:'violated',text:'다시 확인하니 한 개가 반대로 삽입되어 있습니다.'},at);assert.equal(s.stages[3].passed,false);assert.equal(s.questions[0].state,'unresolved');assert.equal(s.questions[0].answers.length,2);assert.equal(s.events.filter(e=>e.type==='agent_pass').length,passes);assert(s.events.some(e=>e.type==='agent_pass_revoked'&&e.stageId==='battery'));assert.throws(()=>W.nextStage(s,at));
 s=W.setEvidencePolicy(s,'visual_only',at);const row=s.checks.find(c=>c.id==='W-BATTERY-03');assert.equal(row.verdict,'violated');assert.equal(row.rawVerdict,'unknown');assert.equal(row.origin,'worker_confirmed');assert.deepEqual(W.validateWorkerState(s,bundle),s);
});
test('answers cannot be silently rebound to a later current task',()=>{
 const s=complete();assert.throws(()=>W.answerQuestion(s,s.questions[0].id,{verdict:'violated'},at));assert.equal(s.completed,true);
});
