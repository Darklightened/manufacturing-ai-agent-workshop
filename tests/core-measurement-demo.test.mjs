import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {compileCompany,createSession,advance,markDelivered,answerQuestion,reopenQuestion,setRange,summarize,validateSession,makeReport} from '../packages/core/core.mjs';

// Author-written classroom examples. Numeric comparisons are real, not OCR evaluation.
function pack(precision=false) {
  const names=['외경','전체 길이','플랜지 두께'],ids=['M-OD','M-LENGTH','M-FLANGE'],tasks=['diameter','length','flange'];
  const specimenId=precision?'EDU-P-001':'EDU-S-001';
  const limits=precision?[['26.25','26.35'],['39.99','40.01'],['5.75','5.85']]:[['26.10','26.50'],['39.90','40.10'],['5.70','5.90']];
  const criteria=ids.map((id,i)=>({id,taskId:tasks[i],label:names[i],target:specimenId,kind:'range',unit:'mm',lower:limits[i][0],upper:limits[i][1],allowWorker:i===2}));
  return {id:precision?'precision-unit':'measure-unit',version:'teaching-v1',title:'플랜지 부시 검사',companyId:'edu-measure',companyName:'다온정밀',processId:precision?'MEAS-P':'MEAS-S',mode:'demo',demoKind:'measurement',
    tasks:tasks.map((id,i)=>({id,label:names[i]})),criteria,
    inspection:{productId:precision?'BSH-2630-P':'BSH-2630',productName:precision?'플랜지 부시 정밀형':'플랜지 부시 표준형',drawingId:precision?'DR-BSH-2630-P':'DR-BSH-2630',drawingRevision:'A',specimenId,drawing:'assets/drawing.svg',
      features:ids.map((criterionId,i)=>({criterionId,code:['A','B','C'][i],label:names[i],nominal:['26.30','40.00','5.80'][i],instrument:['디지털 캘리퍼스','높이 게이지','디지털 마이크로미터'][i],lower:limits[i][0],upper:limits[i][1],unit:'mm'}))},
    checkpoints:tasks.map((taskId,i)=>({id:`m${i+1}`,time:10*(i+1),taskId,target:specimenId,origin:'authored_demo',image:`assets/m${i+1}.svg`,label:names[i],assessments:[{criterionId:ids[i],verdict:i===2?'unknown':'met',unit:'mm',raw:i===2?'5.?8 mm':`${['26.30','40.02'][i]} mm`,...(i===2?{question:'표시가 가려져 있습니다. 플랜지 두께를 확인해 주세요.'}:{value:['26.30','40.02'][i]}),reason:i===2?'표시 일부가 가려져 있습니다.':'준비된 계측 장면에서 값을 기록했습니다.'}]}))};
}
const scenario=pack();
const pdf=s=>`company_id: ${s.companyId}\nprocess_id: ${s.processId}\nproduct_id: ${s.inspection.productId}\ndrawing_id: ${s.inspection.drawingId}\ndrawing_revision: ${s.inspection.drawingRevision}\nspecimen_id: ${s.inspection.specimenId}\n`+s.tasks.map(t=>`task_id: ${t.id}`).join('\n');
const csv=s=>'id,taskId,label,target,kind,unit,lower,upper,allowWorker\n'+s.criteria.map(c=>[c.id,c.taskId,c.label,c.target,c.kind,c.unit,c.lower,c.upper,c.allowWorker].join(',')).join('\n');
const fresh=(s=scenario)=>createSession(s,compileCompany(pdf(s),csv(s),s));
const full=(s=scenario)=>advance(fresh(s),s,s.checkpoints.length-1);
const active=s=>s.questions.find(q=>q.criterionId==='M-FLANGE'&&!['resolved','superseded'].includes(q.state));
function answer(s,value='5.78',unit='mm',extra={}) {
  const q=active(s);return answerQuestion(markDelivered(s,q.id),q.id,{target:q.target,value,unit,text:`작업자가 ${value} ${unit}로 확인했습니다.`,...extra});
}

test('Measurement compiler binds actual product, drawing revision, specimen and feature definitions',()=>{
  const b=compileCompany(pdf(scenario),csv(scenario),scenario);assert.deepEqual(b.inspection,scenario.inspection);
  for(const key of ['product_id','drawing_id','drawing_revision','specimen_id']) {
    const wrong=pdf(scenario).replace(new RegExp(`${key}: [^\\n]+`),`${key}: WRONG`);
    assert.throws(()=>compileCompany(wrong,csv(scenario),scenario),/제품·도면·개정·시료/);
    assert.throws(()=>compileCompany(pdf(scenario).replace(new RegExp(`${key}: [^\\n]+\\n?`),''),csv(scenario),scenario),/제품·도면·개정·시료/);
  }
});
test('Measurement contract rejects wrong feature maps, units, range definitions and specimens',()=>{
  for(const change of [s=>s.inspection.features[0].criterionId='missing',s=>s.inspection.features[1].code='A',s=>s.inspection.features[0].unit='cm',s=>s.inspection.features[0].lower='20',s=>s.criteria[0].target='other',s=>s.inspection.drawing='https://remote/drawing.svg']) {
    const bad=structuredClone(scenario);change(bad);assert.throws(()=>fresh(bad));
  }
  const bad=structuredClone(scenario);bad.checkpoints[0].target='other';assert.throws(()=>fresh(bad),/시료/);
});
test('A bundle or session cannot be transferred to another product, drawing, revision or feature',()=>{
  const base=fresh(),forgedBundle=structuredClone(base.bundle);forgedBundle.inspection.productId='other';
  assert.throws(()=>createSession(scenario,forgedBundle),/연결/);
  for(const edit of [s=>s.inspection.productId='other',s=>s.inspection.drawingId='other',s=>s.inspection.drawingRevision='B',s=>s.inspection.specimenId='other',s=>s.inspection.features[0].code='D',s=>s.inspection.drawing='other.svg']) {
    const changed=structuredClone(scenario);edit(changed);assert.throws(()=>advance(base,changed),/버전/);
  }
});
test('Measurement progression records two values, then exactly one uncertain feature question',()=>{
  let s=fresh();assert.equal(summarize(s,scenario).not_due,3);
  s=advance(s,scenario,1);assert.equal(s.questions.length,0);assert.equal(summarize(s,scenario).met,2);
  s=advance(s,scenario,2);assert.equal(s.questions.length,1);assert.equal(summarize(s,scenario).unknown,1);
  assert.equal(s.assessments['M-FLANGE'].measurement.raw,'5.?8 mm');assert.equal(s.assessments['M-FLANGE'].measurement.valid,false);
  assert.equal(s.assessments['M-OD'].measurement.value,'26.30');assert.equal(s.assessments['M-OD'].origin,'authored_demo');
  assert.deepEqual(active(s).binding,s.assessments['M-FLANGE'].binding);assert.equal(active(s).binding.featureCode,'C');
  assert.equal(summarize(s,scenario).pass,false);assert.equal(validateSession(s,scenario),true);
});
test('A scripted met never overrules numeric tolerance: precision product length fails',()=>{
  const p=pack(true),s=full(p);assert.equal(s.assessments['M-LENGTH'].rawExampleVerdict,'met');
  assert.equal(s.assessments['M-LENGTH'].verdict,'violated');assert.equal(s.assessments['M-LENGTH'].measurement.value,'40.02');
  const done=answer(s);assert.equal(summarize(done,p).met,2);assert.equal(summarize(done,p).violated,1);assert.equal(summarize(done,p).pass,false);
  assert.equal(validateSession(done,p),true);
});
test('Unknown, malformed and wrong-unit authored candidates never become numeric approvals',()=>{
  for(const mutate of [raw=>raw.value='5.?8',raw=>{raw.value='5.78';raw.unit='cm';raw.verdict='met';},raw=>{raw.value='5.78';raw.verdict='unknown';}]) {
    const s=structuredClone(scenario);mutate(s.checkpoints[2].assessments[0]);const state=full(s);
    assert.equal(state.assessments['M-FLANGE'].verdict,'unknown');assert.equal(state.assessments['M-FLANGE'].measurement.valid,false);
  }
});
test('Worker measurement requires delivered question and matching target, position and exact unit',()=>{
  const s=full(),q=active(s),good={target:q.target,value:'5.78',unit:'mm'};
  assert.throws(()=>answerQuestion(s,q.id,good),/전달/);const d=markDelivered(s,q.id);
  for(const bad of [{target:'other'},{unit:'cm'},{unit:'MM'},{value:'5.?8'},{featureCode:'B'},{productId:'WRONG'},{drawingRevision:'B'}]) assert.throws(()=>answerQuestion(d,q.id,{...good,...bad}));
  assert.equal(s.assessments['M-FLANGE'].measurement.valid,false);
});
test('Positive numeric reply completes all checks while preserving raw candidate, scope and source',()=>{
  const initial=full(),raw=structuredClone(initial.assessments['M-FLANGE'].rawProposal),done=answer(initial),r=done.assessments['M-FLANGE'];
  assert.equal(summarize(done,scenario).pass,true);assert.equal(summarize(done,scenario).met,3);
  assert.equal(r.measurement.value,'5.78');assert.equal(r.measurement.raw,'5.?8 mm');assert.equal(r.origin,'worker_confirmed');
  assert.equal(r.rawExampleVerdict,'unknown');assert.deepEqual(r.rawProposal,raw);assert.equal(r.workerConfirmation.value,'5.78');
  assert.equal(r.workerConfirmation.binding.featureCode,'C');assert.equal(r.modelVerdict,undefined);assert.equal(r.receipt,undefined);assert.equal(validateSession(done,scenario),true);
});
test('578 is recorded as 578, not moved into the allowed range by decimal normalization',()=>{
  const done=answer(full(),'578'),r=done.assessments['M-FLANGE'];assert.equal(r.measurement.value,'578');
  assert.equal(r.verdict,'violated');assert.equal(r.measurement.raw,'5.?8 mm');assert.equal(validateSession(done,scenario),true);
  assert.match(makeReport(done,scenario),/578/);assert.match(makeReport(done,scenario),/허용 범위를 벗어난/);
});
test('Changing a range rechecks a fixed numeric value and cannot resolve an uncertain candidate',()=>{
  const pending=setRange(full(),'M-FLANGE','0','10000');assert.equal(pending.assessments['M-FLANGE'].verdict,'unknown');
  assert.equal(pending.assessments['M-FLANGE'].measurement.valid,false);assert.equal(summarize(pending,scenario).pass,false);
  const done=answer(full()),changed=setRange(done,'M-OD','26.10','26.20');assert.equal(changed.assessments['M-OD'].verdict,'violated');
  assert.equal(changed.assessments['M-OD'].measurement.value,'26.30');assert.equal(changed.bundle.inspection.features[0].upper,'26.50');
  assert.equal(changed.bundle.inspection.drawingRevision,'A');assert.equal(changed.initialBundle.criteria[0].upper,'26.50');
  assert.equal(summarize(setRange(changed,'M-OD','26.10','26.50'),scenario).pass,true);assert.equal(validateSession(changed,scenario),true);
});
test('Exact decimal boundary is inclusive and an extra significant digit outside is rejected',()=>{
  assert.equal(answer(full(),'5.70').assessments['M-FLANGE'].verdict,'met');
  assert.equal(answer(full(),'5.90').assessments['M-FLANGE'].verdict,'met');
  assert.equal(answer(full(),'5.900000000000000001').assessments['M-FLANGE'].verdict,'violated');
});
test('Correcting a numeric reply retains both answers, requires delivery again and leaves a pending check',()=>{
  let s=answer(full(),'578');const first=active(s);assert.equal(first,undefined);
  s=reopenQuestion(s,'M-FLANGE');assert.equal(summarize(s,scenario).pass,false);assert.equal(s.questions.length,2);
  assert.deepEqual(reopenQuestion(s,'M-FLANGE'),s);const q=active(s);
  assert.throws(()=>answerQuestion(s,q.id,{target:q.target,value:'5.78',unit:'mm'}),/전달/);
  s=answer(s,'5.78');assert.equal(summarize(s,scenario).pass,true);assert.equal(s.questions[0].answers[0].value,'578');
  assert.equal(s.questions[1].answers[0].value,'5.78');assert.ok(s.assessments['M-FLANGE'].history.some(r=>r.measurement.value==='578'));
  assert.equal(validateSession(s,scenario),true);
});
test('Measurement journal rejects edits to value, unit, feature, product and worker reply',()=>{
  const s=answer(full());assert.equal(validateSession(JSON.parse(JSON.stringify(s)),scenario),true);
  for(const mutate of [x=>x.assessments['M-FLANGE'].measurement.value='5.80',x=>x.assessments['M-FLANGE'].measurement.raw='5.78 mm',x=>x.assessments['M-OD'].binding.featureCode='B',x=>x.bundle.inspection.productId='WRONG',x=>x.questions[0].answers[0].value='5.90']) {
    const bad=structuredClone(s);mutate(bad);assert.throws(()=>validateSession(bad,scenario),/원장/);
  }
});
test('Measurement report includes drawing, numeric criteria, raw/confirmed values and distinct changed limits',()=>{
  const s=setRange(answer(full()),'M-LENGTH','39.90','40.01');
  const report=makeReport(s,scenario),inspection=makeReport(s,scenario,{inspection:true});
  assert.match(report,/<h1>계측 검사 보고서<\/h1>/);assert.match(inspection,/<h1>치수 검수조서<\/h1>/);
  for(const html of [report,inspection]) {
    assert.match(html,/BSH-2630/);assert.match(html,/DR-BSH-2630/);assert.match(html,/개정 A/);assert.match(html,/EDU-S-001/);
    assert.match(html,/5\.\?8 mm/);assert.match(html,/5\.78/);assert.match(html,/39\.90–40\.10 mm/);assert.match(html,/39\.90–40\.01 mm/);
    assert.match(html,/도면 기준/);assert.match(html,/실습 적용 기준 · 변경됨/);assert.match(html,/assets\/drawing.svg/);
    assert.equal((html.match(/<img /g)??[]).length,4);assert.match(html,/강의용 예시/);assert.doesNotMatch(html,/저장된 실제 모델 응답/);
    const visible=html.replace(/<details[\s\S]*?<\/details>/g,'');assert.ok(!visible.includes(s.id));assert.match(html,/worker_confirmed/);
  }
});
test('Report uses only observed scenes and escapes a worker answer',()=>{
  const one=advance(fresh(),scenario,0);assert.equal((makeReport(one,scenario).match(/<img /g)??[]).length,2);
  const s=answer(full(),'5.78','mm',{text:'확인 <script>alert(1)</script>'}),html=makeReport(s,scenario);
  assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>alert/);
  const pending=reopenQuestion(s,'M-FLANGE');assert.doesNotMatch(makeReport(pending,scenario),/세 곳의 치수 확인을 마쳤습니다/);
});
test('Shipped standard and precision products compile actual PDF text and CSV, preserving distinct drawings and outcomes',()=>{
  const root=new URL('../',import.meta.url),products=[];
  for(const sid of ['measurement_demo','measurement_precision_demo']) {
    const dir=new URL(`scenarios/${sid}/`,root),p=JSON.parse(readFileSync(new URL('scenario.json',dir),'utf8'));
    const text=readFileSync(new URL('SOP.extracted.txt',dir),'utf8'),rules=readFileSync(new URL('criteria.csv',dir),'utf8');
    assert.ok(existsSync(new URL('SOP.pdf',dir)));assert.ok(existsSync(new URL(p.inspection.drawing,root)));
    assert.ok(p.checkpoints.every(cp=>existsSync(new URL(cp.image,root))));
    let s=createSession(p,compileCompany(text,rules,p));s=advance(s,p,2);assert.equal(s.questions.length,1);
    assert.equal(s.assessments['M-FLANGE'].measurement.valid,false);s=answer(s,'5.78');
    const summary=summarize(s,p);assert.equal(summary.total,3);assert.equal(summary.openQuestions,0);
    assert.equal(summary.met,sid==='measurement_demo'?3:2);assert.equal(summary.violated,sid==='measurement_demo'?0:1);
    assert.equal(validateSession(s,p),true);assert.match(makeReport(s,p,{inspection:true}),/치수 검수조서/);products.push({p,s});
  }
  assert.notEqual(products[0].p.inspection.productId,products[1].p.inspection.productId);
  assert.notEqual(products[0].p.inspection.specimenId,products[1].p.inspection.specimenId);
  assert.notEqual(products[0].p.inspection.drawingId,products[1].p.inspection.drawingId);
  assert.throws(()=>validateSession(products[0].s,products[1].p),/버전/);
});
