import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import * as C from '../packages/core/core.mjs';
const root=new URL('../',import.meta.url);
function scenario(id='measurement_input_demo'){return JSON.parse(readFileSync(new URL(`scenarios/${id}/scenario.json`,root),'utf8'));}
function fresh(p=scenario()){const dir=`scenarios/${p.id}/`;return C.createSession(p,C.compileCompany(readFileSync(new URL(dir+'SOP.extracted.txt',root),'utf8'),readFileSync(new URL(dir+'criteria.csv',root),'utf8'),p));}
const question=(s,id)=>s.questions.find(q=>q.criterionId===id&&!['resolved','superseded'].includes(q.state));
function record(s,p,index,value){s=C.advance(s,p,index);const id=p.criteria[index].id;s=C.requestMeasurementConfirmation(s,id);const q=question(s,id);s=C.markDelivered(s,q.id,'screen');return C.answerQuestion(s,q.id,{target:q.target,value,unit:'mm',...q.binding});}
function all(p=scenario()){let s=C.setInspectionDetails(fresh(p),{inspector:'홍길동',lot:'LOT-20261123-01'});for(const [i,v] of ['26.30','40.02','5.78'].entries())s=record(s,p,i,v);return s;}

test('Versioned LAB2 inputs compile real documents and retain all original scene indications',()=>{
 for(const sid of ['measurement_input_demo','measurement_input_precision_demo']){
  const p=scenario(sid),s=fresh(p);assert.equal(p.measurementEntry,'worker_input');assert.equal(p.mode,'demo');
  assert.deepEqual(p.criteria.map(c=>c.allowWorker),[true,true,true]);assert.deepEqual(p.checkpoints.map(c=>c.assessments[0].raw),['26.30 mm','40.02 mm','5.?8 mm']);
  assert.ok(p.checkpoints.every(c=>c.origin==='authored_demo'&&existsSync(new URL(c.image,root))));
  assert.ok(existsSync(new URL(`scenarios/${sid}/SOP.pdf`,root)));assert.ok(s.bundle.sourceText.replace(/\s+/g,' ').includes('검사 로트'));
  assert.equal(p.variants.length,1);assert.match(p.variants[0].id,/^measurement_input/);assert.equal(C.validateSession(s,p),true);
 }
});

test('Current observed allowed measurement can request first input and active request is idempotent',()=>{
 const p=scenario(),s=fresh(p);assert.throws(()=>C.requestMeasurementConfirmation(s,'M-OD'),/관찰/);
 const observed=C.advance(s,p,0),raw=structuredClone(observed.assessments['M-OD']);
 const requested=C.requestMeasurementConfirmation(observed,'M-OD');assert.equal(requested.questions.length,1);
 assert.deepEqual(requested.assessments['M-OD'],raw);assert.deepEqual(C.requestMeasurementConfirmation(requested,'M-OD'),requested);
 assert.equal(C.summarize(requested,p).openQuestions,1);assert.equal(C.summarize(requested,p).pass,false);assert.throws(()=>C.requestMeasurementConfirmation(requested,'M-LENGTH'),/관찰/);
 const old=scenario('measurement_demo');assert.throws(()=>C.requestMeasurementConfirmation(C.advance(fresh(old),old,0),'M-OD'),/허용/);
 assert.equal(C.validateSession(requested,p),true);
});

test('Direct input requires delivery, exact unit, product, drawing, specimen and feature binding',()=>{
 const p=scenario();let s=C.requestMeasurementConfirmation(C.advance(fresh(p),p,0),'M-OD'),q=question(s,'M-OD');
 const good={target:q.target,value:'26.30',unit:'mm',...q.binding};
 assert.throws(()=>C.answerQuestion(s,q.id,good),/전달/);s=C.markDelivered(s,q.id,'screen');
 for(const bad of [{target:'other'},{unit:'cm'},{unit:'MM'},{productId:'BSH-2630-P'},{drawingId:'WRONG'},{drawingRevision:'B'},{specimenId:'WRONG'},{featureCode:'B'}])assert.throws(()=>C.answerQuestion(s,q.id,{...good,...bad}));
 for(const value of ['','26.?0','26,30','2.63e1','26.30 mm','NaN','Infinity','0x1A','26.30.0'])assert.throws(()=>C.answerQuestion(s,q.id,{...good,value}),/10진수/);
 assert.equal(s.assessments['M-OD'].measurement.value,'26.30');assert.equal(s.assessments['M-OD'].origin,'authored_demo');
});

test('A/B/C typed values are worker-confirmed with source indications retained and reproducible outcomes',()=>{
 const p=scenario(),s=all(p);assert.equal(C.summarize(s,p).pass,true);
 assert.deepEqual(p.criteria.map(c=>s.assessments[c.id].origin),['worker_confirmed','worker_confirmed','worker_confirmed']);
 assert.deepEqual(p.criteria.map(c=>s.assessments[c.id].measurement.raw),['26.30 mm','40.02 mm','5.?8 mm']);
 assert.equal(s.questions.length,3);assert.ok(s.questions.every(q=>q.state==='resolved'&&q.deliveredChannels.includes('screen')));
 assert.equal(C.validateSession(s,p),true);const precision=scenario('measurement_input_precision_demo'),ps=all(precision);
 assert.equal(C.summarize(ps,precision).violated,1);assert.equal(ps.assessments['M-LENGTH'].verdict,'violated');
 assert.throws(()=>C.validateSession(s,precision),/버전/);
});

test('Out-of-range typed values never undergo automatic decimal correction',()=>{
 const p=scenario();let s=record(fresh(p),p,0,'2630');assert.equal(s.assessments['M-OD'].measurement.value,'2630');
 assert.equal(s.assessments['M-OD'].measurement.raw,'26.30 mm');assert.equal(s.assessments['M-OD'].verdict,'violated');
 s=C.setRange(s,'M-OD','26.10','26.50');assert.equal(s.assessments['M-OD'].measurement.value,'2630');assert.equal(C.validateSession(s,p),true);
});

test('Re-entry preserves every old answer, raw indication and previous verdict in visible reports',()=>{
 const p=scenario();let s=record(fresh(p),p,0,'2630');s=record(s,p,0,'26.30');s=record(s,p,1,'40.02');s=record(s,p,2,'5.78');
 assert.equal(s.questions.length,4);assert.deepEqual(s.questions.filter(q=>q.criterionId==='M-OD').flatMap(q=>q.answers.map(a=>a.value)),['2630','26.30']);
 assert.ok(s.assessments['M-OD'].history.some(r=>r.measurement.value==='2630'));assert.equal(C.validateSession(s,p),true);
 const html=C.makeReport(s,p,{inspection:true}).replace(/<details[\s\S]*?<\/details>/g,'');assert.match(html,/기록한 확인값: 2630 mm/);assert.match(html,/기록한 확인값: 26\.30 mm/);
});

test('Inspector and lot are optional, bounded, replayed, escaped and fixed before observations',()=>{
 const p=scenario(),blank=fresh(p);assert.ok(!Object.hasOwn(blank,'inspectionDetails'));
 const values={inspector:' 홍길동 <script>alert(1)</script> ',lot:' LOT-01<&> '};const s=C.setInspectionDetails(blank,values);
 assert.deepEqual(s.inspectionDetails,{inspector:values.inspector.trim(),lot:values.lot.trim()});assert.deepEqual(C.setInspectionDetails(s,s.inspectionDetails),s);
 for(const bad of [{inspector:'',lot:'x'},{inspector:'x'.repeat(81),lot:'x'},{inspector:'x',lot:'x'.repeat(65)},{inspector:'x\ny',lot:'x'},{inspector:'x',lot:'x',other:1},{inspector:2,lot:'x'}])assert.throws(()=>C.setInspectionDetails(blank,bad));
 assert.throws(()=>C.setInspectionDetails(C.advance(s,p,0),{inspector:'다른 사람',lot:'LOT-02'}),/시작하기 전에/);
 const html=C.makeReport(s,p,{inspection:true});assert.match(html,/검사자 · 수강생 입력/);assert.match(html,/검사 로트 · 수강생 입력/);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>alert/);assert.equal(C.validateSession(s,p),true);
});

test('Metadata, raw input, reply and command tampering fail ledger replay',()=>{
 const p=scenario(),s=all(p);for(const edit of [x=>x.inspectionDetails.lot='wrong',x=>x.assessments['M-OD'].measurement.raw='26.20 mm',x=>x.questions[0].answers[0].value='26.40',x=>x.commands[0].details.inspector='other',x=>x.commands=x.commands.filter(c=>c.type!=='measurement_confirmation')]){
  const bad=structuredClone(s);edit(bad);assert.throws(()=>C.validateSession(bad,p));
 }
 const changed=structuredClone(p);changed.measurementEntry='automatic';assert.throws(()=>C.validateSession(s,changed),/버전/);
});

test('Pre-change saved original measurement sessions restore exactly without metadata fields',()=>{
 const legacy=JSON.parse(readFileSync(new URL('fixtures/measurement_legacy_sessions.json',import.meta.url),'utf8'));
 for(const s of legacy){assert.ok(!Object.hasOwn(s,'inspectionDetails'));assert.equal(C.validateSession(s,scenario(s.scenarioId)),true);}
});
