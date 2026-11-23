import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import * as Core from '../core/core.mjs';
import {engineeringDrawing,formalInspectionDocument} from './index.mjs';
const load = async p => JSON.parse(await readFile(new URL(p,import.meta.url),'utf8'));
const scenario=await load('../../scenarios/measurement_input_demo/scenario.json');
const exported=await load('../../docs/measurement_input_v2/examples/session-standard.json');
const session=exported.session;
const summary=Core.summarize(session,scenario);
test('drawing places original nominal dimensions and recorded values in distinct fields',()=>{
 const svg=engineeringDrawing({inspection:scenario.inspection,assessments:session.assessments,criteria:session.bundle.criteria});
 for(const value of ['26.30','40.00','5.80','40.02','5.78','DR-BSH-2630'])assert.ok(svg.includes(value),value);
 assert.equal((svg.match(/data-feature-result=/g)||[]).length,3);
 assert.ok(svg.includes('data-drawing-feature="M-LENGTH"'));
});
test('empty, invalid and pending measurements remain unresolved rather than promoted',()=>{
 const svg=engineeringDrawing({inspection:scenario.inspection,assessments:{'M-OD':{measurement:{valid:false,value:'26.30'}}},statuses:{'M-OD':'unknown'}});
 assert.ok(svg.includes('A  확인 대기'));assert.ok(svg.includes('B  측정 전'));
 assert.ok(!svg.includes('A  26.30 mm'));
 const unresolved=engineeringDrawing({inspection:scenario.inspection,assessments:session.assessments,statuses:{'M-OD':'unknown'}});
 assert.match(unresolved,/data-drawing-feature="M-OD"[^>]*data-status="unknown"/);
});
test('value strings and metadata are XML escaped, no active markup',()=>{
 const svg=engineeringDrawing({inspection:{...scenario.inspection,productName:'<script>bad()</script>'},assessments:{'M-OD':{measurement:{valid:true,value:'<img onerror=x>',unit:'mm'}}},lot:'<unsafe>'});
 assert.ok(!svg.includes('<script>'));assert.ok(!svg.includes('<img onerror'));assert.ok(svg.includes('&lt;unsafe&gt;'));
});
test('formal report keeps photos, original reading, explicit answer and all raw history',()=>{
 const doc=formalInspectionDocument({scenario,session,summary,inspection:true});
 assert.ok(doc.includes('物品')===false);assert.ok(doc.includes('물품 검수조서'));assert.ok(doc.includes('원시 표시'));assert.ok(doc.includes('5.?8'));
 assert.ok(doc.includes('5.78'));assert.ok(doc.includes('자료 출처 및 전체 기록'));assert.ok(doc.includes('authored_demo'));
 assert.ok(doc.includes('서명 __________________'));assert.ok(!doc.includes('완전 적합함을 인정'));
 assert.equal((doc.match(/<img src=/g)||[]).length,3);
 assert.equal((doc.match(/class="inspection-paper"/g)||[]).length,4);
 assert.ok(doc.includes('&quot;questions&quot;'));assert.ok(doc.includes('&quot;commands&quot;'));
});
test('report preserves adverse status and outstanding reconfirmation',()=>{
 const changed=Core.setRange(session,'M-OD','26.10','26.25');
 const doc=formalInspectionDocument({scenario,session:changed,summary:Core.summarize(changed,scenario)});
 assert.ok(doc.includes('부적합 항목 있음'));assert.ok(doc.includes('26.10–26.25'));assert.ok(doc.includes('도면 26.10–26.50'));
 const reopened=Core.reopenQuestion(session,'M-FLANGE');
 const report=formalInspectionDocument({scenario,session:reopened,summary:Core.summarize(reopened,scenario)});
 assert.match(report,/data-drawing-feature="M-FLANGE"[^>]*data-status="unknown"/);
 assert.ok(report.includes('재확인 대기'));
});
test('question answer shows numeric value even when an explanatory memo exists',()=>{
 const withMemo=structuredClone(session);
 const question=withMemo.questions.find(q=>q.criterionId==='M-FLANGE');
 question.answers.push({value:'578',unit:'mm',text:'첫 입력',time:31});
 question.answers.push({value:'5.78',unit:'mm',text:'다시 확인',time:32});
 const doc=formalInspectionDocument({scenario,session:withMemo,summary});
 assert.ok(doc.includes('578 mm · 첫 입력'));assert.ok(doc.includes('5.78 mm · 다시 확인'));
});
test('mechanical report keeps explicit negative answer and no numeric null placeholder',async()=>{
 const s=await load('../../scenarios/mechanical_demo/scenario.json');
 const text=await readFile(new URL('../../scenarios/mechanical_demo/SOP.extracted.txt',import.meta.url),'utf8');
 const csv=await readFile(new URL('../../scenarios/mechanical_demo/criteria.csv',import.meta.url),'utf8');
 const bundle=Core.compileCompany(text,csv,s);let run=Core.createSession(s,bundle);
 for(let i=0;i<s.checkpoints.length;i++)run=Core.advance(run,s,i);
 const q=run.questions[0];run=Core.markDelivered(run,q.id,'screen');run=Core.answerQuestion(run,q.id,{target:q.target,confirmation:'violated',text:'핀이 끼워지지 않았습니다'});
 const doc=formalInspectionDocument({scenario:s,session:run,summary:Core.summarize(run,s)});
 assert.ok(doc.includes('부적합 항목 있음'));assert.ok(doc.includes('핀이 끼워지지 않았습니다'));assert.ok(!doc.includes('null  ·'));
 assert.equal((doc.match(/class="inspection-paper"/g)||[]).length,3);
 assert.equal((doc.match(/<img src=/g)||[]).length,4);
});
