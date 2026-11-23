import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {PLAN,PLAN_VERSION} from '../packages/worker-flow/plan.mjs';
import {planForVersion,planForState} from '../packages/worker-flow/plans.mjs';
import * as W from '../packages/worker-flow/state.mjs';
import {buildInspectionRecord} from '../packages/worker-flow/report.mjs';
const fixture=new URL('./fixtures/worker-v1-complete.json',import.meta.url);
const old=JSON.parse(readFileSync(fixture));
const provenance=JSON.parse(readFileSync(new URL('./fixtures/worker-v1-complete.provenance.json',import.meta.url)));
const scenario=JSON.parse(readFileSync(new URL('../scenarios/electronics_demo/scenario.json',import.meta.url)));
const at='2026-11-23T14:00:00.000Z';

test('preserved v1 browser record and plan retain their original bytes',()=>{
 const hash=b=>createHash('sha256').update(b).digest('hex');
 assert.equal(hash(readFileSync(fixture)),provenance.sha256);
 assert.equal(hash(readFileSync(new URL('../packages/worker-flow/plan-v1.mjs',import.meta.url))),provenance.preservedPlanSha256);
});
test('v1 saved result replays exactly under its own immutable plan',()=>{
 assert.deepEqual(W.validateWorkerState(old,old.bundle),old);
 assert.equal(planForState(old).PLAN_VERSION,'electronics-worker-tablet-v1');
 assert.equal(planForState(old).PLAN[0].sourceEnd,12);
 assert.equal(old.checks[0].sourceTime,1.2);
 const report=buildInspectionRecord({state:old,bundle:old.bundle,scenario});
 assert.equal(report.rows[0].time,'0:01.200');
 assert.equal(report.rows[0].label,old.checks[0].label);
 assert.equal(report.stages[0].sourceEnd,12);
});
test('new sessions choose the current plan while previous results stay unchanged',()=>{
 const before=JSON.stringify(old),fresh=W.createWorkerState(old.bundle,{id:'current-plan-test',at});
 assert.equal(fresh.planVersion,PLAN_VERSION);
 assert.equal(planForState(fresh).PLAN,PLAN);
 assert.equal(fresh.stages[0].sourceEnd,PLAN[0].sourceEnd);
 assert.equal(fresh.checks[0].label,PLAN[0].checks[0].label);
 assert.equal(JSON.stringify(old),before);
});
test('v1 answer policy changes and continued steps keep the v1 timeline and prior evidence',()=>{
 let state=W.setEvidencePolicy(old,'visual_only',at);
 assert.equal(state.planVersion,'electronics-worker-tablet-v1');
 assert.equal(state.stages[3].sourceStart,99.726);
 assert.equal(state.stageIndex,3);
 assert(!state.completed);
 assert.deepEqual(W.validateWorkerState(state,state.bundle),state);
 state=W.setEvidencePolicy(state,'worker_evidence',at);
 state=W.nextStage(state,at);state=W.nextStage(state,at);
 assert(state.completed);
 assert.equal(state.stages[4].sourceStart,108);
 assert.equal(state.checks[0].sourceTime,1.2);
 assert.deepEqual(W.validateWorkerState(state,state.bundle),state);
});
test('unknown versions and reinterpreting v1 records as current plans are rejected',()=>{
 assert.throws(()=>planForVersion('electronics-worker-tablet-future'));
 assert.throws(()=>W.validateWorkerState({...old,planVersion:'electronics-worker-tablet-future'}));
 if(PLAN_VERSION!==old.planVersion)assert.throws(()=>W.validateWorkerState({...old,planVersion:PLAN_VERSION}));
 const tampered=structuredClone(old);tampered.stages[0].sourceEnd=2.2;
 assert.throws(()=>W.validateWorkerState(tampered));
});
