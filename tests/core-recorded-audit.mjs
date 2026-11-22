/** CPU audit of an existing real capture; does not invoke a model or replace its outcomes. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {bindRecording,compileCompany,createSession,advance,markDelivered,answerQuestion,setWorkerPolicy,summarize,validateSession,makeReport} from '../packages/core/core.mjs';

const root=fileURLToPath(new URL('../',import.meta.url));
const load=p=>readFileSync(resolve(root,p));
const sha=b=>createHash('sha256').update(b).digest('hex');
const pack=JSON.parse(load('recordings/electronics_v1/pack.json'));
const base=JSON.parse(load('scenarios/electronics/scenario.json'));
const before=JSON.stringify(pack),steps=[];let files=0,transmittedImages=0;
for(const pin of Object.values(pack.sourcePins)) {assert.equal(sha(load(pin.path)),pin.sha256);files++;}
for(const entry of pack.entries) {
  const receipt=entry.receipt,requestBytes=load(receipt.requestPath),responseBytes=load(receipt.responsePath);
  assert.equal(sha(requestBytes),receipt.requestSha256);assert.equal(sha(responseBytes),receipt.responseSha256);files+=2;
  const request=JSON.parse(requestBytes),response=JSON.parse(responseBytes);
  const images=request.messages.flatMap(m=>Array.isArray(m.content)?m.content:[]).filter(c=>c.type==='image_url');
  assert.equal(images.length,entry.inputImages.length);
  for(const [i,image] of entry.inputImages.entries()) {
    assert.equal(sha(load(image.path)),image.sha256);files++;
    assert.equal(sha(Buffer.from(images[i].image_url.url.split(',')[1],'base64')),image.sha256);transmittedImages++;
  }
  if(entry.output!==null) {
    assert.equal(response.model,pack.model);assert.equal(response.choices[0].finish_reason,'stop');
    assert.equal(response.choices[0].message.content,entry.responseContent);
    assert.deepEqual(JSON.parse(entry.responseContent),entry.output);
  }
}
const scenario=bindRecording(base,pack),bundle=compileCompany(load('scenarios/electronics/SOP.extracted.txt').toString(),load('scenarios/electronics/criteria.csv').toString(),scenario);
let session=createSession(scenario,bundle);
for(let i=0;i<scenario.checkpoints.length;i++) {
  session=advance(session,scenario,i);assert.equal(validateSession(session,scenario),true);
  const summary=summarize(session,scenario),cp=scenario.checkpoints[i];
  steps.push({checkpointId:cp.id,time:cp.time,expectedTask:cp.taskId,observedTask:cp.observedTaskId,phase:cp.observedPhase,
    counts:summary.counts,openQuestions:summary.openQuestions,rows:summary.rows.map(r=>({criterionId:r.criterionId,raw:r.rawProposal,modelVerdict:r.modelVerdict,verdict:r.verdict,evidenceId:r.evidenceId,evidenceTime:r.sourceTime,applicabilityConflict:r.applicabilityConflict}))});
}
const eligible=summarize(session,scenario).rows.find(r=>r.verdict==='unknown'&&r.modelVerdict==='unknown'&&!r.inferenceFailure&&!r.applicabilityConflict);
const interactions=[];
if(eligible) {
  const criterionId=eligible.criterionId,q=session.questions.find(q=>q.criterionId===criterionId&&!['resolved','superseded'].includes(q.state));
  assert.ok(q);
  let answered=markDelivered(session,q.id);
  assert.throws(()=>answerQuestion(answered,q.id,{target:'wrong-target',confirmation:'met',text:'wrong object'}));
  answered=answerQuestion(answered,q.id,{target:q.target,confirmation:'met',text:'강의 검수용 입력: 해당 대상의 조건을 직접 확인했다고 가정합니다.'});
  assert.equal(answered.assessments[criterionId].verdict,'unknown');
  const allowed=setWorkerPolicy(answered,criterionId,'worker_attestation');assert.equal(allowed.assessments[criterionId].verdict,'met');
  const reverted=setWorkerPolicy(allowed,criterionId,'visual_only');assert.equal(reverted.assessments[criterionId].verdict,'unknown');
  let negative=setWorkerPolicy(session,criterionId,'worker_attestation');negative=markDelivered(negative,q.id);
  negative=answerQuestion(negative,q.id,{target:q.target,confirmation:'violated',text:'강의 검수용 입력: 해당 조건의 불일치를 직접 확인했다고 가정합니다.'});
  assert.equal(negative.assessments[criterionId].verdict,'violated');
  for(const [condition,s]of [['visual_only_with_answer',answered],['worker_attestation_positive',allowed],['revert_visual_only',reverted],['worker_attestation_negative',negative]]) {
    assert.equal(validateSession(s,scenario),true);
    assert.deepEqual(s.assessments[criterionId].rawProposal,session.assessments[criterionId].rawProposal);
    assert.notEqual(makeReport(s,scenario),makeReport(session,scenario));
    interactions.push({condition,criterionId,verdict:s.assessments[criterionId].verdict,origin:s.assessments[criterionId].origin,counts:summarize(s,scenario).counts});
  }
}
assert.equal(JSON.stringify(pack),before);
const result={schema:'seminar.actual-recording-core-audit.v1',status:'passed',recordingId:pack.id,model:pack.model,
  modelCallsDuringAudit:0,acceptedRecordedCalls:pack.entries.filter(e=>e.output!==null).length,failedRecordedCalls:pack.entries.filter(e=>e.output===null).length,
  actualAssessmentRows:pack.entries.reduce((n,e)=>n+(e.output?.assessments.length??0),0),fileHashChecks:files,actualTransmittedImageChecks:transmittedImages,
  defaultFinal:summarize(session,scenario).counts,steps,interactions,independentAccuracyAssessed:false};
console.log(JSON.stringify(result,null,2));
