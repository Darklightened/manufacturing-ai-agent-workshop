import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {compileCompany} from '../packages/core/core.mjs';
import * as State from '../packages/company-build/state.mjs';
import {CompanyBuilder} from '../packages/company-build/ui.mjs';
const scenario=JSON.parse(fs.readFileSync(new URL('../scenarios/electronics_demo/scenario.json',import.meta.url)));
const bundle=compileCompany(fs.readFileSync(new URL('../scenarios/electronics_demo/SOP.extracted.txt',import.meta.url),'utf8'),fs.readFileSync(new URL('../scenarios/electronics_demo/criteria.csv',import.meta.url),'utf8'),scenario);
function candidate(failure){
 let invalidated=false,accepted=false,finished=false;
 const ui=new CompanyBuilder({isVisible:()=>false,begin:()=>({}),finish:()=>{finished=true;},invalidate:()=>{invalidated=true;},loadSQL:async()=>{throw new Error('SQLite unavailable');},accept:async()=>{accepted=true;throw new Error('host adoption failed');},save:async()=>{}});
 ui.state=State.correctTask(State.prepareReview(State.startBuild(State.makeBuildState([{name:'example.csv',size:10}])),bundle),'battery','원문 대조');ui.db={close(){}};
 if(failure==='accept')ui.rebuildDb=async()=>{};
 return {ui,status:()=>({invalidated,accepted,finished})};
}
test('SQLite completion failure rolls back reviewed phase and never marks ontology accepted',async()=>{
 const {ui,status}=candidate('sql'),before=structuredClone(ui.state);
 await assert.rejects(()=>ui.finishReview(),/SQLite unavailable/);
 assert.deepEqual(ui.state,before);assert.equal(ui.approved,false);assert.equal(ui.db,null);assert.deepEqual(status(),{invalidated:true,accepted:false,finished:true});
});
test('host bundle adoption failure preserves learner correction but rejects completion',async()=>{
 const {ui,status}=candidate('accept'),before=structuredClone(ui.state);
 await assert.rejects(()=>ui.finishReview(),/host adoption failed/);
 assert.deepEqual(ui.state,before);assert.equal(ui.approved,false);assert.equal(State.canCompleteReview(ui.state),true);assert.deepEqual(status(),{invalidated:true,accepted:true,finished:true});
});
test('review cannot complete before SQLite is available',async()=>{
 const {ui,status}=candidate('sql');ui.db=null;
 await assert.rejects(()=>ui.finishReview(),/SQLite DB/);assert.equal(ui.approved,false);assert.deepEqual(status(),{invalidated:false,accepted:false,finished:false});
});
