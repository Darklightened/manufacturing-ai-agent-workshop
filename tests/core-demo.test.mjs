import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {compileCompany,createSession,advance,markDelivered,answerQuestion,reopenQuestion,setWorkerPolicy,summarize,validateSession,makeReport} from '../packages/core/core.mjs';

// Authored test story: these outcomes are teaching inputs, never model measurements.
const taskIds=['preparation','circuit','propeller','battery','switch','final'];
const ids=['E-PREP','E-CONNECTION','E-PROPELLER','E-BATTERY','E-SWITCH','E-FINAL'];
const scenario={id:'demo-unit',title:'전자 조립 강의용 예시',companyId:'edu-demo',processId:'ELEC-DEMO',mode:'demo',
  tasks:taskIds.map((id,i)=>({id,label:['부품 준비','회로 연결','프로펠러 장착','배터리 삽입','스위치 확인','최종 외관'][i]})),
  criteria:ids.map((id,i)=>({id,taskId:taskIds[i],label:`검사 ${i+1}`,target:'circuit-board',kind:'visual',unit:'',lower:'',upper:'',allowWorker:id==='E-BATTERY'})),
  checkpoints:taskIds.map((taskId,i)=>({id:`e${i+1}`,time:10*(i+1),sourceTime:10*(i+1),taskId,target:'circuit-board',
    origin:'authored_demo',image:`assets/scene-${i+1}.jpg`,assessments:i===2?[]:i===3?[
      {criterionId:'E-PROPELLER',verdict:'met',reason:'장착된 프로펠러를 보여주는 예시 장면'},
      {criterionId:'E-BATTERY',verdict:'unknown',reason:'손에 가려 극성이 보이지 않습니다.',question:'배터리 두 개의 방향이 홀더 표시와 맞나요?'}
    ]:[{criterionId:ids[i],verdict:'met',reason:'단계별 확인을 설명하는 강의용 관찰'}]}))};
const pdf=`company_id: edu-demo process_id: ELEC-DEMO ${taskIds.map(id=>`task_id: ${id}`).join(' ')}`;
const csv='id,taskId,label,target,kind,unit,lower,upper,allowWorker\n'+scenario.criteria.map(c=>[c.id,c.taskId,c.label,c.target,c.kind,c.unit,c.lower,c.upper,c.allowWorker].join(',')).join('\n');
const fresh=(s=scenario)=>createSession(s,compileCompany(pdf,csv,s));
const active=s=>s.questions.find(q=>q.criterionId==='E-BATTERY'&&!['resolved','superseded'].includes(q.state));
function confirm(s,confirmation='met',text='배터리 두 개의 + / − 방향을 직접 확인했습니다.') {
  const q=active(s);s=markDelivered(s,q.id,'screen');
  return answerQuestion(s,q.id,{target:q.target,confirmation,text});
}

test('Demo compiles document inputs deterministically and keeps all required meanings',()=>{
  const s=fresh();assert.equal(s.mode,'demo');assert.equal(s.bundle.sourceText,pdf);assert.equal(s.bundle.sourceCsv,csv);
  assert.deepEqual(s.bundle,compileCompany(pdf,csv,scenario));assert.equal(s.bundle.criteria.length,6);
  assert.throws(()=>compileCompany(pdf,csv.replace('검사 4','검사 생략'),scenario),/이름 변경/);
  assert.throws(()=>compileCompany(pdf,csv.replace('visual,,,,true','visual,,,,false'),scenario),/정책/);
});
test('Demo rejects falsely claimed recorded origin or a fabricated model receipt',()=>{
  const wrong=structuredClone(scenario);wrong.checkpoints[0].origin='recorded_model';assert.throws(()=>fresh(wrong),/출처/);
  const fake=structuredClone(scenario);fake.checkpoints[0].recording={receipt:{id:'fake'}};assert.throws(()=>fresh(fake),/식별 기록/);
});
test('Six-step teaching story has no premature question and one battery question at its visible stage',()=>{
  let s=fresh();assert.equal(summarize(s,scenario).not_due,6);
  s=advance(s,scenario,2);assert.equal(s.questions.length,0);assert.equal(summarize(s,scenario).met,2);
  assert.equal(s.assessments['E-PROPELLER'],undefined);assert.equal(s.assessments['E-BATTERY'],undefined);
  s=advance(s,scenario,3);assert.equal(s.questions.length,1);assert.equal(active(s).criterionId,'E-BATTERY');
  assert.equal(s.assessments['E-PROPELLER'].verdict,'met');assert.equal(s.assessments['E-PROPELLER'].checkpointId,'e4');
  assert.match(active(s).text,/배터리 두 개/);assert.equal(active(s).allowWorker,true);
  assert.equal(validateSession(s,scenario),true);
});
test('Demo cross-task evidence can finish an earlier task but cannot certify a future task or other target',()=>{
  const future=structuredClone(scenario);future.checkpoints[0].assessments.push({criterionId:'E-FINAL',verdict:'met'});
  assert.throws(()=>advance(fresh(future),future,0),/시작하지 않은/);
  const wrong=structuredClone(scenario);wrong.checkpoints[0].assessments[0].target='other-board';
  assert.throws(()=>advance(fresh(wrong),wrong,0),/대상/);
});
test('Positive worker answer resolves the one intended hold and six final checks pass',()=>{
  let s=advance(fresh(),scenario,3);const raw=JSON.stringify(s.assessments['E-BATTERY'].rawProposal);
  s=confirm(s);assert.equal(s.assessments['E-BATTERY'].verdict,'met');assert.equal(summarize(s,scenario).pass,false);
  s=advance(s,scenario,5);const out=summarize(s,scenario);assert.equal(out.pass,true);assert.equal(out.met,6);assert.equal(out.openQuestions,0);
  const row=s.assessments['E-BATTERY'];assert.equal(row.rawExampleVerdict,'unknown');assert.equal(JSON.stringify(row.rawProposal),raw);
  assert.equal(row.origin,'worker_confirmed');assert.equal(row.modelVerdict,undefined);assert.equal(row.receipt,undefined);
  assert.equal(validateSession(s,scenario),true);
});
test('Finishing the video without an answer retains a hold rather than inventing success',()=>{
  const s=advance(fresh(),scenario,5),out=summarize(s,scenario);assert.equal(out.met,5);assert.equal(out.unknown,1);
  assert.equal(out.pass,false);assert.equal(out.openQuestions,1);assert.equal(s.questions[0].answers.length,0);
});
test('Negative answer remains a discrepancy after subsequent stages and final report',()=>{
  let s=confirm(advance(fresh(),scenario,3),'violated','한 개를 반대로 넣었습니다.');s=advance(s,scenario,5);
  assert.equal(summarize(s,scenario).violated,1);assert.equal(summarize(s,scenario).pass,false);
  assert.equal(s.assessments['E-BATTERY'].origin,'worker_confirmed');assert.match(makeReport(s,scenario),/한 개를 반대로 넣었습니다/);
  assert.equal(validateSession(s,scenario),true);
});
test('A later positive scripted head cannot silently overwrite a negative worker statement',()=>{
  const next=structuredClone(scenario);next.checkpoints[5].assessments.push({criterionId:'E-BATTERY',verdict:'met',reason:'마지막 장면에서 상태가 좋아 보이는 예시'});
  let s=confirm(advance(fresh(next),next,3),'violated','방향 불일치');s=advance(s,next,5);
  assert.equal(s.assessments['E-BATTERY'].rawExampleVerdict,'met');assert.equal(s.assessments['E-BATTERY'].verdict,'violated');
  assert.equal(s.assessments['E-BATTERY'].workerConfirmation.text,'방향 불일치');assert.equal(validateSession(s,next),true);
});
test('Strict policy restores the raw unknown; reallowing worker confirmation restores the saved answer',()=>{
  let s=advance(confirm(advance(fresh(),scenario,3)),scenario,5);const raw=JSON.stringify(s.assessments['E-BATTERY'].rawProposal);
  const originalCriteria=s.initialBundle.criteria;
  s=setWorkerPolicy(s,'E-BATTERY','visual_only');assert.equal(s.assessments['E-BATTERY'].verdict,'unknown');assert.equal(summarize(s,scenario).pass,false);
  assert.equal(s.assessments['E-BATTERY'].workerConfirmation.confirmation,'met');assert.equal(active(s).allowWorker,false);
  s=setWorkerPolicy(s,'E-BATTERY','worker_attestation');assert.equal(summarize(s,scenario).pass,true);
  assert.equal(JSON.stringify(s.assessments['E-BATTERY'].rawProposal),raw);assert.equal(s.assessments['E-BATTERY'].rawExampleVerdict,'unknown');
  assert.deepEqual(s.bundle.criteria.map(({allowWorker,...r})=>r),originalCriteria.map(({allowWorker,...r})=>r));
  assert.ok(s.assessments['E-BATTERY'].history.some(r=>r.origin==='worker_confirmed'));
  assert.equal(new Set(s.questions.map(q=>q.id)).size,s.questions.length);assert.equal(validateSession(s,scenario),true);
});
test('Policy changes without an answer do not resolve unknown; unstated confirmations remain unknown',()=>{
  let s=advance(fresh(),scenario,3);s=setWorkerPolicy(s,'E-BATTERY','visual_only');s=setWorkerPolicy(s,'E-BATTERY','worker_attestation');
  assert.equal(s.assessments['E-BATTERY'].verdict,'unknown');s=confirm(s,'unknown','아직 확인하지 못했습니다.');
  assert.equal(s.assessments['E-BATTERY'].verdict,'unknown');assert.equal(active(s).state,'answered');assert.equal(validateSession(s,scenario),true);
});
test('Demo answers require delivery, exact target, valid explicit confirmation and text',()=>{
  const s=advance(fresh(),scenario,3),q=active(s);
  assert.throws(()=>answerQuestion(s,q.id,{target:q.target,confirmation:'met',text:'확인'}),/전달/);
  const d=markDelivered(s,q.id,'audio');assert.throws(()=>answerQuestion(d,q.id,{target:'wrong',confirmation:'met',text:'확인'}),/대상/);
  assert.throws(()=>answerQuestion(d,q.id,{target:q.target,confirmation:'approved',text:'확인'}),/명시적/);
  assert.throws(()=>answerQuestion(d,q.id,{target:q.target,confirmation:'met',text:' '}),/내용/);
});
test('Correcting an answer requires a fresh question and retains both replies and old verdicts',()=>{
  let s=advance(confirm(advance(fresh(),scenario,3),'violated','배터리 방향이 다릅니다.'),scenario,5);const oldId=s.questions[0].id;
  s=reopenQuestion(s,'E-BATTERY');assert.equal(s.questions.length,2);assert.notEqual(active(s).id,oldId);assert.equal(summarize(s,scenario).pass,false);
  assert.deepEqual(reopenQuestion(s,'E-BATTERY'),s);const q=active(s);
  assert.throws(()=>answerQuestion(s,q.id,{target:q.target,confirmation:'met',text:'다시 확인'}),/전달/);
  s=confirm(s,'met','방향을 수정한 뒤 두 개 모두 확인했습니다.');assert.equal(summarize(s,scenario).pass,true);
  assert.equal(s.questions[0].answers[0].text,'배터리 방향이 다릅니다.');assert.match(s.questions[1].answers[0].text,/수정한 뒤/);
  assert.ok(s.assessments['E-BATTERY'].history.some(r=>r.verdict==='violated'));assert.equal(validateSession(s,scenario),true);
});
test('Demo report identifies authored examples, exact worker text, source images, policy and history',()=>{
  let s=advance(confirm(advance(fresh(),scenario,3),'met','두 개 모두 확인 <script>alert(1)</script>'),scenario,5);
  s=setWorkerPolicy(s,'E-BATTERY','visual_only');s=setWorkerPolicy(s,'E-BATTERY','worker_attestation');const report=makeReport(s,scenario);
  assert.match(report,/강의용 예시/);assert.match(report,/최초 예시 판정: 확인 필요/);assert.match(report,/작업자 확인: 충족/);
  assert.match(report,/worker_attestation/);assert.match(report,/assets\/scene-4.jpg/);assert.match(report,/&lt;script&gt;/);
  assert.doesNotMatch(report,/<script>alert/);assert.doesNotMatch(report,/실제 모델 원본 응답과 식별 기록|요청 SHA256|저장된 실제 모델 응답 재생/);
});
test('Demo journal import rejects changed raw examples, forged answers and missing required rules',()=>{
  const s=advance(confirm(advance(fresh(),scenario,3)),scenario,5);assert.equal(validateSession(JSON.parse(JSON.stringify(s)),scenario),true);
  for(const edit of [x=>x.assessments['E-BATTERY'].rawExampleVerdict='met',x=>x.assessments['E-BATTERY'].workerConfirmation.text='조작된 답변',x=>x.bundle.criteria.pop(),x=>x.questions[0].answers[0].confirmation='violated']) {
    const changed=structuredClone(s);edit(changed);assert.throws(()=>validateSession(changed,scenario),/원장/);
  }
  const changed=structuredClone(scenario);changed.checkpoints[3].assessments[1].reason='다른 예시 관찰';assert.throws(()=>validateSession(s,changed),/버전/);
});
test('Published electronics teaching pack compiles its real PDF text and CSV and completes all six checks',()=>{
  const root=new URL('../',import.meta.url),dir=new URL('scenarios/electronics_demo/',root);
  const pack=JSON.parse(readFileSync(new URL('scenario.json',dir),'utf8'));
  const text=readFileSync(new URL('SOP.extracted.txt',dir),'utf8'),rules=readFileSync(new URL('criteria.csv',dir),'utf8');
  assert.equal(pack.mode,'demo');assert.equal(pack.criteria.length,6);assert.equal(pack.checkpoints.length,6);
  assert.ok(existsSync(new URL('SOP.pdf',dir)));assert.ok(pack.checkpoints.every(cp=>existsSync(new URL(cp.image,root))));
  let s=createSession(pack,compileCompany(text,rules,pack));s=advance(s,pack,2);assert.equal(s.questions.length,0);
  s=advance(s,pack,3);assert.equal(s.questions.length,1);s=confirm(s);s=advance(s,pack,5);
  assert.equal(summarize(s,pack).met,6);assert.equal(summarize(s,pack).pass,true);assert.equal(validateSession(s,pack),true);
  assert.equal(s.assessments['E-PROPELLER'].sourceTime,99.726);assert.equal(s.assessments['E-BATTERY'].rawExampleVerdict,'unknown');
  assert.match(makeReport(s,pack),/강의용 예시/);
});
test('Teaching report and inspection expose the same result while hiding technical identity only in details',()=>{
  const s=advance(confirm(advance(fresh(),scenario,3)),scenario,5);
  const report=makeReport(s,scenario),inspection=makeReport(s,scenario,{inspection:true});
  assert.match(report,/<h1>조립 작업 보고서<\/h1>/);assert.match(inspection,/<h1>조립 검수조서<\/h1>/);
  for(const html of [report,inspection]) {
    assert.match(html,/모든 검사 항목을 확인했습니다/);assert.equal((html.match(/<img /g)??[]).length,6);
    assert.match(html,/<th>검사 항목<\/th><th>결과<\/th><th>판정 출처<\/th><th>확인 내용<\/th>/);
    const visible=html.replace(/<details[\s\S]*?<\/details>/g,'');
    assert.ok(!visible.includes(s.id));assert.ok(!visible.includes(s.scenarioFingerprint));assert.ok(!visible.includes(s.initialBundle.version));
    assert.match(visible,/배터리 두 개의 \+ \/ − 방향을 직접 확인했습니다/);
    assert.ok(html.includes(s.id));assert.ok(html.includes(s.scenarioFingerprint));assert.ok(html.includes(s.initialBundle.version));
    assert.doesNotMatch(html,/<details[^>]*\sopen(?:\s|>)/);
    const technical=html.match(/<details class="technical-details">([\s\S]*?)<\/details>/)[1];
    const raw=[...technical.matchAll(/<pre>([\s\S]*?)<\/pre>/g)].at(-1)[1];
    const decoded=raw.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
    assert.deepEqual(JSON.parse(decoded),s);
  }
});
test('Report changes with strict policy, negative answer and pending reconfirmation without leaking future photos',()=>{
  const before=advance(fresh(),scenario,3);assert.equal((makeReport(before,scenario).match(/<img /g)??[]).length,4);
  const done=advance(confirm(before),scenario,5),strict=setWorkerPolicy(done,'E-BATTERY','visual_only');
  assert.match(makeReport(strict,scenario),/추가 확인이 남아 있습니다/);
  assert.match(makeReport(strict,scenario),/답변은 기록했으며, 시각 증거만 인정하는 현재 기준/);
  const requested=reopenQuestion(done,'E-BATTERY');assert.match(makeReport(requested,scenario),/이전 작업자 답변 · 재확인 요청 중/);
  assert.doesNotMatch(makeReport(requested,scenario),/모든 검사 항목을 확인했습니다/);
  const negative=confirm(requested,'violated','반대로 들어가 있습니다.');
  assert.match(makeReport(negative,scenario),/기준과 다른 항목이 있습니다/);
  assert.match(makeReport(negative,scenario,{inspection:true}),/반대로 들어가 있습니다/);
});
