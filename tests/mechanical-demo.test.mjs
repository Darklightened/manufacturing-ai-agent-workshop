import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import * as Core from '../packages/core/core.mjs';
import {stageGate,restoredStage} from '../packages/mechanical-flow/ui.mjs';
const root = new URL('../',import.meta.url);
const read = file => readFileSync(new URL(file,root),'utf8');
const scenario = JSON.parse(read('scenarios/mechanical_demo/scenario.json'));
const text = read('scenarios/mechanical_demo/SOP.extracted.txt');
const csv = read('scenarios/mechanical_demo/criteria.csv');
const fresh = () => Core.createSession(scenario,Core.compileCompany(text,csv,scenario));
function answer(session,confirmation='met') {
  const q = session.questions.find(q => !['resolved','superseded'].includes(q.state));
  session = Core.markDelivered(session,q.id,'screen');
  return Core.answerQuestion(session,q.id,{target:q.target,confirmation,text:{met:'핀을 제자리에 끼운 것을 확인했습니다',violated:'핀이 제대로 끼워지지 않았습니다',unknown:'아직 확인할 수 없습니다'}[confirmation]});
}

test('Mechanical teaching pack compiles actual extracted PDF and CSV with six scoped criteria',() => {
  const session = fresh();
  assert.equal(session.bundle.criteria.length,6);
  assert.equal(session.bundle.source,'parsed_pdf_csv');
  assert.deepEqual(session.bundle.tasks.map(t => t.id),['chassis','bracket','axle','final']);
  assert.equal(session.bundle.criteria.filter(c => c.allowWorker).length,1);
  assert.equal(session.bundle.criteria.find(c => c.allowWorker).id,'MD-PIN');
  assert.match(text,/강의용/);
  assert.equal(Core.validateSession(session,scenario),true);
});

test('Source stages are contiguous, evidence is causal, all media exist, only one intended unknown',() => {
  assert.deepEqual(scenario.checkpoints.map(c => [c.sourceStart,c.sourceEnd]),[[0,70],[70,90],[90,178],[178,184.4]]);
  assert.deepEqual(scenario.checkpoints.map(c => c.sourceTime),[69,89,177,183]);
  let unknown = 0;
  for(const cp of scenario.checkpoints) {
    assert.equal(cp.origin,'authored_demo');assert.equal(cp.time,cp.sourceEnd);
    assert.ok(cp.sourceTime >= cp.sourceStart && cp.sourceTime <= cp.sourceEnd);
    assert.ok(existsSync(new URL(cp.image,root)));assert.ok(existsSync(new URL(cp.videoPath,root)));
    for(const a of cp.assessments) if(a.verdict === 'unknown') { unknown++;assert.equal(a.criterionId,'MD-PIN');assert.match(a.question,/接|핀/); }
  }
  assert.equal(unknown,1);
  assert.equal(scenario.mode,'demo');assert.equal(scenario.media.codec,'vp9');
});

test('Bracket gate requires explicit delivered worker response; no silent skip into axle stage',() => {
  let session = fresh();assert.equal(stageGate(session,scenario,0),false);
  session = Core.advance(session,scenario,0);assert.equal(stageGate(session,scenario,0),true);
  assert.equal(stageGate(session,scenario,1),false);assert.equal(session.questions.length,0);
  session = Core.advance(session,scenario,1);assert.equal(stageGate(session,scenario,1),false);
  const question = session.questions[0];assert.equal(question.criterionId,'MD-PIN');
  assert.throws(() => Core.answerQuestion(session,question.id,{target:question.target,confirmation:'met',text:'확인'}),/먼저/);
  session = answer(session);assert.equal(stageGate(session,scenario,1),true);
  assert.equal(session.assessments['MD-PIN'].rawExampleVerdict,'unknown');
  assert.equal(session.assessments['MD-PIN'].origin,'worker_confirmed');
  assert.equal(Core.validateSession(session,scenario),true);
});

test('Negative and unknown answers hold progression; later authored video cannot clear them',() => {
  for(const verdict of ['violated','unknown']) {
    let session = answer(Core.advance(fresh(),scenario,1),verdict);
    assert.equal(stageGate(session,scenario,1),false);
    session = Core.advance(session,scenario,3); // Even an imported full timeline keeps a hold.
    assert.equal(Core.summarize(session,scenario).pass,false);
    assert.equal(stageGate(session,scenario,3),false);
    assert.equal(session.assessments['MD-PIN'].verdict,verdict);
    assert.equal(Core.validateSession(session,scenario),true);
  }
});

test('Completed walkthrough has six checks, four photographs and separate original observation and answer',() => {
  let session = answer(Core.advance(fresh(),scenario,1));
  session = Core.advance(session,scenario,3);
  assert.equal(Core.summarize(session,scenario).met,6);assert.equal(Core.summarize(session,scenario).pass,true);
  assert.equal(stageGate(session,scenario,3),true);
  const html = Core.makeReport(session,scenario,{inspection:true});
  for(const cp of scenario.checkpoints) assert.ok(html.includes(cp.image));
  assert.match(html,/핀을 제자리에 끼운 것을 확인했습니다/);
  assert.match(html,/최초 예시 판정: 확인 필요/);
  assert.match(html,/강의용 예시/);
  assert.equal(Core.validateSession(session,scenario),true);
});

test('Policy review and re-confirmation reopen a previously passed gate without erasing history',() => {
  let session = answer(Core.advance(fresh(),scenario,1));
  session = Core.setWorkerPolicy(session,'MD-PIN','visual_only');
  assert.equal(stageGate(session,scenario,1),false);assert.equal(session.assessments['MD-PIN'].workerConfirmation.confirmation,'met');
  session = Core.setWorkerPolicy(session,'MD-PIN','worker_attestation');assert.equal(stageGate(session,scenario,1),true);
  session = Core.reopenQuestion(session,'MD-PIN');assert.equal(stageGate(session,scenario,1),false);
  session = answer(session,'violated');assert.equal(stageGate(session,scenario,1),false);
  session = Core.reopenQuestion(session,'MD-PIN');session = answer(session,'met');assert.equal(stageGate(session,scenario,1),true);
  assert.ok(session.questions.flatMap(q => q.answers).some(a => a.confirmation === 'violated'));
  assert.equal(Core.validateSession(session,scenario),true);
});

test('Restore and repeated completed boundary preserve the same Core ledger; stage metadata is immutable',() => {
  const session = Core.advance(fresh(),scenario,0);
  assert.equal(restoredStage(session,scenario),0);
  assert.deepEqual(Core.advance(session,scenario,0),session);
  assert.equal(Core.validateSession(JSON.parse(JSON.stringify(session)),scenario),true);
  const changed = structuredClone(scenario);changed.checkpoints[0].sourceEnd = 69;
  assert.throws(() => Core.validateSession(session,changed),/시나리오|버전|계약/);
  assert.equal(restoredStage(fresh(),scenario),0);
});
