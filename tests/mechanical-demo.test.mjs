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

test('Optional next-task guidance records a known procedure without changing inspection or progress',() => {
  const before = Core.advance(fresh(),scenario,0);
  const after = Core.requestTaskGuidance(before,scenario);
  assert.deepEqual(after.assessments,before.assessments);
  assert.deepEqual(after.questions,before.questions);
  assert.deepEqual(after.attempts,before.attempts);
  assert.equal(after.position,before.position);assert.equal(after.time,before.time);assert.equal(after.completed,before.completed);
  assert.deepEqual(Core.summarize(after,scenario),Core.summarize(before,scenario));
  const guide = after.events.at(-1);
  assert.equal(guide.type,'task_guidance');assert.equal(guide.sourceKind,'registered_procedure');
  assert.equal(guide.origin,'authored_demo_guidance');assert.equal(guide.scenarioFingerprint,after.scenarioFingerprint);
  assert.equal(guide.afterCheckpointId,'md1');assert.equal(guide.nextCheckpointId,'md2');assert.equal(guide.nextTaskId,'bracket');
  assert.match(guide.question,/다음 작업/);assert.ok(guide.answer.includes(scenario.checkpoints[1].sceneSummary));
  assert.equal(guide.scopeNote,scenario.checkpoints[1].scopeNote);
  assert.equal(guide.image,undefined);assert.equal(after.assessments['MD-BRACKET'],undefined);
  assert.equal(Core.validateSession(after,scenario),true);
  assert.deepEqual(Core.requestTaskGuidance(after,scenario),after);
});

test('Guidance follows the observed next stage, stays optional, and never resolves a held inspection',() => {
  let held = Core.advance(fresh(),scenario,1);
  const guided = Core.requestTaskGuidance(held,scenario);
  assert.equal(guided.events.at(-1).nextTaskId,'axle');
  assert.equal(guided.assessments['MD-PIN'].verdict,'unknown');
  assert.deepEqual(guided.questions,held.questions);assert.equal(stageGate(guided,scenario,1),false);
  let complete = answer(held);complete = Core.advance(complete,scenario,3);
  assert.equal(Core.summarize(complete,scenario).pass,true);
  assert.equal(complete.events.some(e => e.type === 'task_guidance'),false);
});

test('Guidance rejects unobserved, final and nonmechanical sessions and changed procedure binding',() => {
  assert.throws(() => Core.requestTaskGuidance(fresh(),scenario),/관찰 기록/);
  const fabricated = fresh();fabricated.position=0;
  assert.throws(() => Core.requestTaskGuidance(fabricated,scenario),/관찰 기록/);
  assert.throws(() => Core.requestTaskGuidance(Core.advance(fresh(),scenario,3),scenario),/마지막 단계/);
  const before = Core.advance(fresh(),scenario,0), wrong = structuredClone(scenario);
  wrong.demoKind='other';assert.throws(() => Core.requestTaskGuidance(before,wrong),/기계 조립/);
  const changed = structuredClone(scenario);changed.checkpoints[1].sceneSummary='변경된 작업 절차';
  assert.throws(() => Core.requestTaskGuidance(before,changed),/버전/);
});

test('Guidance survives exact replay and appears separately in both report forms',() => {
  let state = Core.requestTaskGuidance(Core.advance(fresh(),scenario,0),scenario);
  state = answer(Core.advance(state,scenario,1));state = Core.advance(state,scenario,3);
  assert.equal(Core.validateSession(JSON.parse(JSON.stringify(state)),scenario),true);
  for(const inspection of [false,true]) {
    const html = Core.makeReport(state,scenario,{inspection});
    assert.match(html,/작업 순서 안내/);assert.match(html,/다음 작업은 어떻게 하나요/);assert.match(html,/Agent 안내 · 등록 절차/);
    assert.match(html,/검사 확인 질문·답변이나 다음 단계의 완료 판정과 구분/);
  }
  const changed = structuredClone(state);changed.events.find(e => e.type === 'task_guidance').answer='다음 작업 완료';
  assert.throws(() => Core.validateSession(changed,scenario),/원장/);
  const changedCommand = structuredClone(state);changedCommand.commands.find(c => c.type === 'task_guidance').nextCheckpointId='md4';
  assert.throws(() => Core.validateSession(changedCommand,scenario),/원장/);
});
