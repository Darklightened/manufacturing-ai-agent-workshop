import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {bindRecording,recordingContract,compileCompany,createSession,advance,markDelivered,answerQuestion,setWorkerPolicy,summarize,validateSession,makeReport} from '../packages/core/core.mjs';

// These are explicitly synthetic protocol fixtures, never claimed to be captured model responses.
const dir=new URL('../scenarios/electronics/',import.meta.url);
const base=JSON.parse(readFileSync(new URL('scenario.json',dir),'utf8'));
const pdf=readFileSync(new URL('SOP.extracted.txt',dir),'utf8'),csv=readFileSync(new URL('criteria.csv',dir),'utf8');
function syntheticPack() {
  return {schema:'seminar.recording.v1',id:'unit-synthetic-only',scenarioId:base.id,model:'synthetic-test-double',baseContract:recordingContract(base),
    observationSchedule:base.checkpoints.map(cp=>({checkpointId:cp.id,criterionIds:base.criteria.map(c=>c.id)})),
    entries:base.checkpoints.map((cp,i)=>{
      const output={checkpointId:cp.id,observedTaskId:i===0?'propeller':cp.taskId,phase:'in_progress',summaryKo:'합성 프로토콜 검사용 출력',
        assessments:base.criteria.map((r,j)=>({criterionId:r.id,target:r.target,observation:j===4?'present':'unclear',applicability:i===0&&j>0?'not_due':'due',targetConfirmed:true,evidenceIds:[`img-${cp.id}`],reason:'검사용 원본 관찰 문자열'})),questions:[]};
      return {checkpointId:cp.id,receipt:{id:`test-${cp.id}`,model:'synthetic-test-double',requestSha256:'a'.repeat(64),responseSha256:'b'.repeat(64),requestPath:`recordings/test/${cp.id}-request.json`,responsePath:`recordings/test/${cp.id}-response.json`},
        inputImages:[{id:`img-${cp.id}`,path:cp.image,time:cp.time,sha256:'c'.repeat(64)}],output,responseContent:JSON.stringify(output)};
    })};
}
function updateOutput(pack,index,fn) {fn(pack.entries[index].output);pack.entries[index].responseContent=JSON.stringify(pack.entries[index].output);return pack;}
function setup(pack=syntheticPack(),position=base.checkpoints.length-1) {
  const scenario=bindRecording(base,pack);let session=createSession(scenario,compileCompany(pdf,csv,scenario));
  if(position>=0) session=advance(session,scenario,position);
  return {scenario,session,pack};
}
function answer(session,id='E-CONNECTION',confirmation='met') {
  const q=session.questions.find(q=>q.criterionId===id&&!['resolved','superseded'].includes(q.state));
  session=markDelivered(session,q.id);
  return answerQuestion(session,q.id,{target:'circuit-board',confirmation,text:'작업자가 해당 연결을 현장에서 확인했다고 입력함'});
}

test('Recorded binding preserves base fixtures and exact independent observed task',()=>{
  const before=JSON.stringify(base),{scenario,session}=setup(syntheticPack(),0);
  assert.equal(JSON.stringify(base),before);assert.equal(base.mode,'fixture');assert.equal(session.mode,'recorded');
  assert.equal(scenario.checkpoints[0].taskId,'circuit');assert.equal(session.events[0].observedTaskId,'propeller');
  assert.equal(session.assessments['E-CONNECTION'].receipt.id,'test-e1');
  assert.equal(session.assessments['E-CONNECTION'].rawProposal.reason,'검사용 원본 관찰 문자열');
});
test('Recording cannot be rebound to changed criterion meaning, source image or timeline',()=>{
  for(const edit of [s=>s.criteria[0].label='다른 검사',s=>s.checkpoints[0].time++,s=>s.checkpoints[0].image='other.jpg',s=>s.tasks.reverse()]) {
    const changed=structuredClone(base);edit(changed);assert.throws(()=>bindRecording(changed,syntheticPack()),/다릅니다/);
  }
});
test('Recording rejects normalized output drift, missing response, duplicate heads and forged target',()=>{
  const changed=syntheticPack();changed.entries[0].output.assessments[0].observation='present';assert.throws(()=>bindRecording(base,changed),/원본 모델 응답/);
  const missing=syntheticPack();missing.entries.pop();assert.throws(()=>bindRecording(base,missing),/모든 관찰/);
  const duplicated=updateOutput(syntheticPack(),0,o=>o.assessments[1]=o.assessments[0]);assert.throws(()=>bindRecording(base,duplicated),/검사 항목/);
  const wrong=updateOutput(syntheticPack(),0,o=>o.assessments[0].target='another-board');assert.throws(()=>bindRecording(base,wrong),/대상/);
});
test('Input evidence rejects future timestamps, absent source image and unknown citation',()=>{
  const future=syntheticPack();future.entries[0].inputImages[0].time++;assert.throws(()=>bindRecording(base,future),/미래/);
  const missing=syntheticPack();missing.entries[0].inputImages[0].path='other.jpg';assert.throws(()=>bindRecording(base,missing),/대표 장면/);
  const unknown=updateOutput(syntheticPack(),0,o=>o.assessments[0].evidenceIds=['unseen']);assert.throws(()=>bindRecording(base,unknown),/증거/);
});
test('Reported evidence follows actual cited historical frames rather than the current representative image',()=>{
  const p=syntheticPack(),earlier=structuredClone(p.entries[0].inputImages[0]);p.entries[5].inputImages.unshift(earlier);
  updateOutput(p,5,o=>o.assessments[4].evidenceIds=[earlier.id]);
  const {scenario,session}=setup(p),row=session.assessments['E-FINAL'];
  assert.equal(row.image,earlier.path);assert.equal(row.sourceTime,earlier.time);assert.equal(row.evidenceId,earlier.id);
  assert.equal(row.observationSourceTime,base.checkpoints[5].time);assert.equal(row.checkpointImage,base.checkpoints[5].image);
  assert.equal(row.evidenceKind,'cited_model_input');assert.match(makeReport(session,scenario),/인용 장면 img-e1/);
  assert.equal(validateSession(session,scenario),true);
});
test('Scheduled future criteria remain not due and do not trigger premature questions',()=>{
  const {scenario,session}=setup(syntheticPack(),0),summary=summarize(session,scenario);
  assert.equal(summary.not_due,4);assert.equal(session.questions.length,1);assert.equal(session.questions[0].criterionId,'E-CONNECTION');
  assert.equal(summary.pass,false);
});
test('A later not-due claim cannot erase a previously due obligation on the same assembly',()=>{
  const p=updateOutput(syntheticPack(),5,o=>o.assessments[0].applicability='not_due');
  const {scenario,session}=setup(p),row=session.assessments['E-CONNECTION'];
  assert.equal(row.rawProposal.applicability,'not_due');assert.equal(row.modelVerdict,'not_due');
  assert.equal(row.verdict,'unknown');assert.equal(row.applicabilityConflict,true);
  assert.equal(summarize(session,scenario).not_due,0);assert.equal(validateSession(session,scenario),true);
  const allowed=setWorkerPolicy(answer(session),'E-CONNECTION','worker_attestation');
  assert.equal(allowed.assessments['E-CONNECTION'].verdict,'unknown');
});
test('Earlier unclear applicability is not silently promoted into an established due phase',()=>{
  const p=syntheticPack();
  for(let i=0;i<6;i++) updateOutput(p,i,o=>o.assessments[0].applicability=i===5?'not_due':'unclear');
  const {session}=setup(p);
  assert.equal(session.assessments['E-CONNECTION'].dueObserved,false);
  assert.equal(session.assessments['E-CONNECTION'].applicabilityConflict,false);
  assert.equal(session.assessments['E-CONNECTION'].rawProposal.applicability,'not_due');
  assert.ok(session.questions.some(q=>q.criterionId==='E-CONNECTION'&&q.state==='created'));
});
test('Present proposal needs due applicability, identified target and cited image',()=>{
  for(const edit of [a=>a.targetConfirmed=false,a=>a.evidenceIds=[],a=>a.applicability='unclear']) {
    const p=updateOutput(syntheticPack(),5,o=>edit(o.assessments[4]));const {session}=setup(p);
    assert.equal(session.assessments['E-FINAL'].modelVerdict,'unknown');assert.equal(session.assessments['E-FINAL'].verdict,'unknown');
  }
});
test('Explicit failed response remains a failed unknown, never an authored or successful fallback',()=>{
  const p=syntheticPack();p.entries[5].output=null;p.entries[5].responseContent='truncated';p.entries[5].failure={kind:'length',message:'최대 출력 길이 도달'};
  const {scenario,session}=setup(p);
  assert.equal(summarize(session,scenario).unknown,5);assert.equal(session.assessments['E-FINAL'].inferenceFailure.kind,'length');
  assert.equal(session.assessments['E-FINAL'].origin,'recorded_model');assert.match(makeReport(session,scenario),/length/);
});
test('Recorded visual worker replies still require delivery, target and explicit status',()=>{
  const {session}=setup();const q=session.questions[0];
  assert.throws(()=>answerQuestion(session,q.id,{target:q.target,confirmation:'met',text:'확인'}),/전달/);
  const delivered=markDelivered(session,q.id);
  assert.throws(()=>answerQuestion(delivered,q.id,{target:'wrong',confirmation:'met',text:'확인'}),/대상/);
  assert.throws(()=>answerQuestion(delivered,q.id,{target:q.target,confirmation:'approved',text:'확인'}),/명시적/);
});
test('Default visual policy records positive worker assertion but does not manufacture visual evidence',()=>{
  const {scenario,session}=setup();const answered=answer(session);
  assert.equal(answered.assessments['E-CONNECTION'].verdict,'unknown');assert.equal(answered.assessments['E-CONNECTION'].origin,'recorded_model');
  assert.equal(answered.assessments['E-CONNECTION'].workerConfirmation.confirmation,'met');
  assert.equal(summarize(answered,scenario).pass,false);assert.equal(validateSession(answered,scenario),true);
});
test('Policy edit re-evaluates saved assertion, reverting restores model uncertainty and prior history',()=>{
  const {scenario,session}=setup();const answered=answer(session),raw=JSON.stringify(answered.assessments['E-CONNECTION'].rawProposal);
  const allowed=setWorkerPolicy(answered,'E-CONNECTION','worker_attestation');
  assert.equal(allowed.assessments['E-CONNECTION'].verdict,'met');assert.equal(allowed.assessments['E-CONNECTION'].origin,'worker_confirmed');
  assert.equal(allowed.assessments['E-CONNECTION'].modelVerdict,'unknown');assert.notEqual(allowed.bundle.version,answered.bundle.version);
  const reverted=setWorkerPolicy(allowed,'E-CONNECTION','visual_only');
  assert.equal(reverted.assessments['E-CONNECTION'].verdict,'unknown');assert.equal(JSON.stringify(reverted.assessments['E-CONNECTION'].rawProposal),raw);
  assert.ok(reverted.assessments['E-CONNECTION'].history.some(h=>h.origin==='worker_confirmed'));
  assert.equal(new Set(reverted.questions.map(q=>q.id)).size,reverted.questions.length);assert.equal(validateSession(reverted,scenario),true);
});
test('Explicit negative worker answer changes unknown into discrepancy under allowed policy',()=>{
  const {scenario,session}=setup();const allowed=setWorkerPolicy(session,'E-CONNECTION','worker_attestation');const failed=answer(allowed,'E-CONNECTION','violated');
  assert.equal(failed.assessments['E-CONNECTION'].verdict,'violated');assert.equal(summarize(failed,scenario).violated,1);
  assert.match(makeReport(failed,scenario),/작업자 확인값/);assert.equal(validateSession(failed,scenario),true);
});
test('Contradictory later visual evidence creates hold instead of letting worker assertion win',()=>{
  const p=updateOutput(syntheticPack(),5,o=>o.assessments[0].observation='absent');
  let {scenario,session}=setup(p,4);session=setWorkerPolicy(session,'E-CONNECTION','worker_attestation');session=answer(session);
  assert.equal(session.assessments['E-CONNECTION'].verdict,'met');session=advance(session,scenario,5);
  assert.equal(session.assessments['E-CONNECTION'].modelVerdict,'violated');assert.equal(session.assessments['E-CONNECTION'].verdict,'unknown');
  assert.equal(session.assessments['E-CONNECTION'].conflict,true);assert.equal(summarize(session,scenario).pass,false);
  assert.equal(validateSession(session,scenario),true);
});
test('Policy-only changes never resolve absent evidence and cannot silently remove required criteria',()=>{
  const {scenario,session}=setup();const changed=setWorkerPolicy(session,'E-CONNECTION','worker_attestation');
  assert.equal(changed.assessments['E-CONNECTION'].verdict,'unknown');assert.equal(changed.bundle.criteria.length,5);
  assert.throws(()=>setWorkerPolicy(changed,'E-CONNECTION','ignore'));
  assert.equal(validateSession(changed,scenario),true);
});
test('Recorded session replay rejects tampered model proposal and policy result',()=>{
  const {scenario,session}=setup();let changed=setWorkerPolicy(answer(session),'E-CONNECTION','worker_attestation');assert.equal(validateSession(changed,scenario),true);
  changed=structuredClone(changed);changed.assessments['E-CONNECTION'].rawProposal.observation='present';assert.throws(()=>validateSession(changed,scenario),/원장/);
  const forged=structuredClone(session);forged.bundle.criteria[0].allowWorker=true;assert.throws(()=>validateSession(forged,scenario),/원장/);
});
test('Recorded report distinguishes raw response, edited policy and worker result with provenance',()=>{
  const {scenario,session}=setup();const changed=setWorkerPolicy(answer(session),'E-CONNECTION','worker_attestation'),report=makeReport(changed,scenario);
  assert.match(report,/저장된 실제 모델 응답 재생/);assert.match(report,/synthetic-test-double/);
  assert.match(report,/실제 모델 원본 응답과 식별 기록/);assert.match(report,/요청 SHA256/);assert.match(report,/worker_attestation/);
  assert.match(report,/원래 제안: 확인 필요/);assert.match(report,/작업자 확인: 충족/);assert.match(report,/작업자 확인값/);
  assert.ok(!report.includes('실제 영상·사진 위에 작성된 관찰 이벤트를 적용했습니다.'));
});
