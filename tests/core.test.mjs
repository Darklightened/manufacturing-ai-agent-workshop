import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseCsv,compileCompany,createSession,advance,markDelivered,answerQuestion,setRange,summarize,makeReport,validateSession} from '../packages/core/core.mjs';

const scenario={id:'test',title:'테스트 실습',companyId:'edu-dynin',processId:'PROC',mode:'fixture',tasks:[{id:'A',label:'조립'},{id:'B',label:'측정'}],criteria:[
  {id:'joint',taskId:'A',label:'연결부 확인',target:'object',kind:'visual',allowWorker:false},
  {id:'size',taskId:'B',label:'측정값',target:'gauge',kind:'range',unit:'mm',lower:'0.1',upper:'0.3',allowWorker:true}
],checkpoints:[
  {id:'c0',time:1,taskId:'A',target:'object',origin:'authored_fixture',image:'frame.jpg',assessments:[{criterionId:'joint',verdict:'unknown',reason:'손에 가림'}]},
  {id:'c1',time:5,taskId:'A',target:'object',origin:'authored_fixture',image:'frame2.jpg',assessments:[{criterionId:'joint',verdict:'met',reason:'교육용 확인'}]},
  {id:'c2',time:8,taskId:'B',target:'gauge',origin:'authored_fixture',image:'gauge.jpg',assessments:[{criterionId:'size',verdict:'unknown',raw:'03',reason:'소수점 모호'}]}
]};
const pdf='company_id: edu-dynin process_id: PROC task_id: A task_id: B';
const csv='id,taskId,label,target,kind,unit,lower,upper,allowWorker\njoint,A,연결부 확인,object,visual,,,,false\nsize,B,측정값,gauge,range,mm,0.1,0.3,true';
const bundle=()=>compileCompany(pdf,csv,scenario);
const fresh=()=>createSession(scenario,bundle());
const ready=()=>{let s=advance(fresh(),scenario,2); return markDelivered(s,s.questions.find(q=>q.criterionId==='size').id,'screen');};

test('CSV handles BOM, CRLF, quoted commas and escaped quotes',()=>{
  assert.deepEqual(parseCsv('\uFEFFid,label\r\na,"hello, ""world"""\r\n'),[{id:'a',label:'hello, "world"'}]);
});
test('CSV rejects unclosed quotes and mismatched columns',()=>{
  assert.throws(()=>parseCsv('id,label\na,"missing'));
  assert.throws(()=>parseCsv('id,label\na,b,c'));
});
test('Actual PDF token mismatch and missing CSV columns reject compilation',()=>{
  assert.throws(()=>compileCompany(pdf.replace('PROC','WRONG'),csv,scenario));
  assert.throws(()=>compileCompany('company_id: another process_id: PROC',csv,scenario));
  assert.throws(()=>compileCompany(pdf,csv.replace('allowWorker','foo'),scenario));
});
test('Compiler rejects duplicate and unknown criteria and policy drift',()=>{
  assert.throws(()=>compileCompany(pdf,csv+'\njoint,A,duplicate,object,visual,,,,false',scenario));
  assert.throws(()=>compileCompany(pdf,csv.replace('joint,A','other,A'),scenario));
  assert.throws(()=>compileCompany(pdf,csv.replace('visual,,,,false','visual,,,,true'),scenario));
});
test('Semantic relabeling and unrecognized columns cannot reuse an old fixture verdict',()=>{
  assert.throws(()=>compileCompany(pdf,csv.replace('연결부 확인','체결 토크 합격'),scenario),/이름 변경/);
  const withExtra=csv.split('\n').map((line,i)=>line+(i===0?',expected':',torque-approved')).join('\n');
  assert.throws(()=>compileCompany(pdf,withExtra,scenario),/지원하지 않는 CSV 열/);
  assert.throws(()=>compileCompany(pdf,csv.replace('visual,,,,false','visual,Nm,,,false'),scenario),/단위/);
  assert.throws(()=>compileCompany(pdf,csv.replace('visual,,,,false','visual,,5,10,false'),scenario),/수치 범위/);
  assert.equal(compileCompany(pdf,csv.replace('0.1,0.3','0.2,0.4'),scenario).criteria[1].lower,'0.2');
});
test('Invalid ranges and nonfinite numbers reject',()=>{
  assert.throws(()=>compileCompany(pdf,csv.replace('0.1,0.3','0.5,0.3'),scenario));
  assert.throws(()=>compileCompany(pdf,csv.replace('0.1,0.3','NaN,0.3'),scenario));
  assert.throws(()=>setRange(fresh(),'size','1e2','1e3'));
});
test('Compilation is deterministic and retains parsed source evidence',()=>{
  assert.deepEqual(bundle(),bundle()); assert.equal(bundle().sourceCsv,csv);
  assert.equal(bundle().criteria[1].upper,'0.3');
});
test('Before observations all rules not due, no false pass',()=>{
  const x=summarize(fresh(),scenario); assert.equal(x.not_due,2);assert.equal(x.pass,false);
});
test('Advancing one checkpoint records only causal evidence and preserves input',()=>{
  const s=fresh(),n=advance(s,scenario);assert.equal(s.position,-1);assert.equal(n.position,0);
  assert.equal(n.assessments.joint.verdict,'unknown');assert.equal(n.assessments.size,undefined);
  assert.equal(n.questions.length,1);assert.equal(n.questions[0].state,'created');
});
test('Duplicate checkpoint is idempotent, rewind rejects, jumping processes intermediate records',()=>{
  const s=advance(fresh(),scenario,1);assert.deepEqual(advance(s,scenario,1),s);
  assert.throws(()=>advance(s,scenario,0));assert.equal(s.events.filter(e=>e.type==='checkpoint').length,2);
  assert.equal(s.assessments.joint.history.length,1);assert.equal(s.questions[0].resolvedAt,5);
});
test('Answers require delivery and correct target',()=>{
  const s=advance(fresh(),scenario,0),q=s.questions[0];
  assert.throws(()=>answerQuestion(s,q.id,{target:'object',text:'확인'}));
  const d=markDelivered(s,q.id,'screen');
  assert.throws(()=>answerQuestion(d,q.id,{target:'wrong',text:'확인'}));
});
test('Worker statement alone does not validate a visual criterion',()=>{
  let s=advance(fresh(),scenario,0);s=markDelivered(s,s.questions[0].id,'screen');
  s=answerQuestion(s,s.questions[0].id,{target:'object',text:'확인했습니다'});
  assert.equal(s.assessments.joint.verdict,'unknown');assert.equal(s.questions[0].state,'answered');
  assert.equal(summarize(s,scenario).pass,false);assert.equal(validateSession(s,scenario),true);
});
test('Later evidence resolves at later time and stale answer rejects',()=>{
  let s=advance(fresh(),scenario,0);const q=s.questions[0];s=advance(s,scenario,1);
  assert.equal(s.questions[0].state,'resolved');assert.equal(s.questions[0].resolvedAt,5);
  assert.throws(()=>answerQuestion(s,q.id,{target:'object',text:'뒤늦은 답변'}));
});
test('Video end is not complete physical compliance',()=>{
  const s=advance(fresh(),scenario,2),r=summarize(s,scenario);
  assert.equal(s.completed,true);assert.equal(r.pass,false);assert.equal(r.unknown,1);
});
test('Measurement requires exact unit and does not move decimal to fit range',()=>{
  let s=ready();const q=s.questions.find(q=>q.criterionId==='size');
  assert.throws(()=>answerQuestion(s,q.id,{target:'gauge',value:'0.3',unit:'cm'}));
  s=answerQuestion(s,q.id,{target:'gauge',value:'300',unit:'mm'});
  assert.equal(s.assessments.size.verdict,'violated');assert.equal(s.assessments.size.measurement.value,'300');
  assert.equal(s.assessments.size.measurement.raw,'03');assert.equal(s.assessments.size.origin,'worker_confirmed');
});
test('Decimal boundary is exact and large values retain exact ordering',()=>{
  let s=ready();const q=s.questions.find(q=>q.criterionId==='size');
  s=answerQuestion(s,q.id,{target:'gauge',value:'0.3000000000000000001',unit:'mm'});
  assert.equal(s.assessments.size.verdict,'violated');
  s=setRange(s,'size','0.1','0.3000000000000000001');assert.equal(s.assessments.size.verdict,'met');
  assert.equal(summarize(s,scenario).pass,true);assert.equal(s.initialBundle.criteria[1].upper,'0.3');
});
test('Rule changes preserve history and cannot turn unclear input into valid reading',()=>{
  const s=setRange(ready(),'size','0','100');assert.equal(s.assessments.size.verdict,'unknown');
  assert.equal(s.assessments.size.measurement.valid,false);assert.equal(validateSession(s,scenario),true);
});
test('Journal import validates replay and rejects forged statuses or future evidence',()=>{
  const s=ready();assert.equal(validateSession(JSON.parse(JSON.stringify(s)),scenario),true);
  const edited=structuredClone(s);edited.assessments.size.verdict='met';assert.throws(()=>validateSession(edited,scenario));
  const future=structuredClone(s);future.events[0].time=999;assert.throws(()=>validateSession(future,scenario));
});
test('Changed scenario input prevents stale import',()=>{
  const s=ready(),changed=structuredClone(scenario);changed.checkpoints[0].image='different.jpg';
  assert.throws(()=>validateSession(s,changed));
});
test('Report escapes student input, labels fixtures, and excludes unsafe image schemes',()=>{
  let s=advance(fresh(),scenario,0);s=markDelivered(s,s.questions[0].id);
  s=answerQuestion(s,s.questions[0].id,{target:'object',text:'<img src=x onerror=alert(1)>'});
  const report=makeReport(s,scenario);assert.match(report,/교육용 입력/);assert.match(report,/&lt;img/);
  assert.ok(!report.includes('<img src=x onerror'));
  s.assessments.joint.image='javascript:alert(1)';assert.ok(!makeReport(s,scenario).includes('src="javascript:'));
});
test('Rework creates new attempt and retains earlier assessment history',()=>{
  const custom=structuredClone(scenario);custom.checkpoints.splice(2,0,{id:'rework',time:6,taskId:'A',target:'object',origin:'authored_fixture',image:'rework.jpg',invalidate:['joint'],assessments:[{criterionId:'joint',verdict:'unknown',reason:'재체결 필요'}]});
  let s=createSession(custom,compileCompany(pdf,csv,custom));s=advance(s,custom,2);
  assert.equal(s.assessments.joint.attempt,2);assert.equal(s.assessments.joint.verdict,'unknown');
  assert.ok(s.assessments.joint.history.some(x=>x.verdict==='met'));
  assert.equal(s.questions.at(-1).attempt,2);assert.equal(validateSession(s,custom),true);
});

test('Invalidation cannot target another object or an unobserved criterion',()=>{
  const custom=structuredClone(scenario);
  custom.checkpoints[0].invalidate=['size'];
  assert.throws(()=>advance(createSession(custom,compileCompany(pdf,csv,custom)),custom,0));
  custom.checkpoints[0].invalidate=['joint'];
  assert.throws(()=>advance(createSession(custom,compileCompany(pdf,csv,custom)),custom,0));
});
test('Source time and duplicate proposal identities are validated',()=>{
  const custom=structuredClone(scenario);custom.checkpoints[0].sourceTime=-1;
  assert.throws(()=>createSession(custom,bundle()));
  custom.checkpoints[0].sourceTime=0;custom.checkpoints[0].assessments.push(custom.checkpoints[0].assessments[0]);
  assert.throws(()=>createSession(custom,bundle()));
});
test('Report preserves raw string and worker value with distinct origin',()=>{
  let s=ready();const q=s.questions.find(q=>q.criterionId==='size');
  s=answerQuestion(s,q.id,{target:'gauge',value:'0.30',unit:'mm'});
  s=setRange(s,'size','0','0.2');
  const report=makeReport(s,scenario);
  assert.match(report,/초기 판독 문자열: 03/);assert.match(report,/0.30 mm/);
  assert.match(report,/작업자 확인값/);assert.match(report,/이전 판정과 원시 기록/);
  assert.equal(s.assessments.size.rawProposal.raw,'03');
});
test('Actual workshop packs compile and replay with no inference',()=>{
  for(const id of ['electronics','electronics_error','instruments','mechanical','maintenance']) {
    const dir=new URL(`../scenarios/${id}/`,import.meta.url);
    const actual=JSON.parse(readFileSync(new URL('scenario.json',dir),'utf8'));
    const b=compileCompany(readFileSync(new URL('SOP.extracted.txt',dir),'utf8'),readFileSync(new URL('criteria.csv',dir),'utf8'),actual);
    let s=createSession(actual,b);s=advance(s,actual,actual.checkpoints.length-1);
    assert.equal(validateSession(JSON.parse(JSON.stringify(s)),actual),true);
    assert.equal(s.mode,'fixture');assert.equal(summarize(s,actual).pass,false);
    if(id==='instruments') {
      assert.equal(s.assessments['I-DIGITAL'].measurement.value,'26.30');
      assert.equal(s.assessments['I-VERNIER'].time,20);
      assert.equal(s.assessments['I-VERNIER'].sourceTime,12.256);
      assert.match(makeReport(s,actual),/교육용 진행 지점/);
    }
    if(id==='maintenance') {
      assert.equal(s.events.filter(e=>e.type==='invalidated').length,1);
      assert.equal(s.assessments['R-CURRENT'].attempt,2);
      assert.equal(s.assessments['R-CURRENT'].verdict,'unknown');
      assert.equal(s.assessments['R-CURRENT'].history[0].verdict,'met');
      assert.match(makeReport(s,actual),/이전 시도/);
    }
  }
});
