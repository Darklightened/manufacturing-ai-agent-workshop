/** Pure deterministic worker exercise controller shared by UI, reports and tests. */
import {PLAN,CHECKS,PLAN_VERSION,PROCESS} from './plan.mjs';
const copy=x=>JSON.parse(JSON.stringify(x));
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const ensure=(yes,message)=>{if(!yes)throw new Error(message);};
const iso=at=>{const value=at||new Date().toISOString();ensure(typeof value==='string'&&Number.isFinite(Date.parse(value)),'기록 시각이 올바르지 않습니다.');return value;};
const text=(value,max,label)=>{ensure(typeof value==='string'&&value.trim()&&value.trim().length<=max,`${label}을(를) 입력해 주세요.`);return value.trim();};
function checkBundle(bundle){
 ensure(bundle?.companyId===PROCESS.companyId&&bundle.processId===PROCESS.id&&typeof bundle.version==='string','검토된 전자 조립 회사 기준이 필요합니다.');
 ensure(Array.isArray(bundle.tasks)&&same(bundle.tasks.map(x=>x.id),PLAN.map(x=>x.id)),'작업 순서가 전자 조립 실습과 다릅니다.');
 ensure(Array.isArray(bundle.criteria)&&bundle.criteria.length===6&&PLAN.every(p=>bundle.criteria.some(c=>c.id===p.criterionId&&c.taskId===p.id&&c.target==='circuit-board'&&c.kind==='visual')),'검사 기준의 작업·대상 연결을 확인해 주세요.');
 ensure(bundle.criteria.find(c=>c.id==='E-BATTERY')?.allowWorker===true,'배터리 작업자 확인 기준이 필요합니다.');
}
function initial(bundle,{id,at}){
 checkBundle(bundle);return {schema:'seminar.worker-flow.v1',id,createdAt:at,planVersion:PLAN_VERSION,origin:'authored_demo',bundle:copy(bundle),setupStep:'register',worker:null,authentication:null,process:null,started:false,startedAt:null,stageIndex:0,stages:PLAN.map(p=>({id:p.id,taskId:p.id,label:p.label,index:p.index,sourceStart:p.sourceStart,sourceEnd:p.sourceEnd,progress:0,status:'waiting',passed:false,passedAt:null})),checks:CHECKS.map(c=>({...copy(c),authoredVerdict:c.rawVerdict,rawVerdict:null,verdict:'not_due',observedAt:null,sourceTime:null,imagePath:null,origin:'authored_demo',workerAnswer:null})),questions:[],events:[],commands:[],completed:false,completedAt:null,policy:'worker_evidence'};
}
export function createWorkerState(bundle,options={}){const at=iso(options.at),id=options.id||globalThis.crypto?.randomUUID?.()||`worker-${Date.now()}-${Math.random().toString(16).slice(2)}`;ensure(typeof id==='string'&&id.length<=128,'작업 기록 ID가 올바르지 않습니다.');return initial(bundle,{id,at});}
function emit(s,type,at,fields={}){s.events.push({sequence:s.events.length+1,type,actor:type.startsWith('agent_')?'agent':'worker',at,...fields});}
function resultFor(row,s){if(row.rawVerdict===null)return 'not_due';if(!row.allowWorker||!row.workerAnswer)return row.rawVerdict;if(row.workerAnswer.verdict==='violated')return 'violated';return s.policy==='worker_evidence'?row.workerAnswer.verdict:row.rawVerdict;}
function reevaluate(s,at){
 for(const row of s.checks){row.verdict=resultFor(row,s);row.origin=row.workerAnswer&&row.verdict===row.workerAnswer.verdict&&(s.policy==='worker_evidence'||row.workerAnswer.verdict==='violated')?'worker_confirmed':'authored_demo';}
 for(const q of s.questions){const r=s.checks.find(x=>x.id===q.checkId);q.state=r.verdict==='met'?'resolved':q.answers.length?'unresolved':q.deliveries.length?'delivered':'created';}
 // Earlier evidence changes revoke historical pass signals without removing them.
 let firstBlocked=-1;
 for(let i=0;i<s.stages.length;i++){
  const st=s.stages[i],rows=s.checks.filter(c=>c.taskId===st.id),intrinsic=st.progress>=1&&rows.every(c=>c.verdict==='met');
  if(i<=s.stageIndex&&!intrinsic&&firstBlocked<0)firstBlocked=i;
 }
 if(firstBlocked>=0&&firstBlocked<s.stageIndex)s.stageIndex=firstBlocked;
 let prefix=true;
 for(let i=0;i<s.stages.length;i++){
  const st=s.stages[i],rows=s.checks.filter(c=>c.taskId===st.id),old=st.passed;
  st.passed=s.started&&i<=s.stageIndex&&prefix&&st.progress>=1&&rows.every(c=>c.verdict==='met');
  if(st.passed&&!old){st.passedAt=at;emit(s,'agent_pass',at,{stageId:st.id,message:`${st.label} 검사 통과. 다음 단계로 진행할 수 있습니다.`,checkIds:rows.map(c=>c.id),policy:s.policy});}
  if(!st.passed&&old){emit(s,'agent_pass_revoked',at,{stageId:st.id,message:`${st.label}의 통과 신호가 보류로 변경되었습니다.`,previousPassedAt:st.passedAt,policy:s.policy});st.passedAt=null;}
  st.status=st.passed?'passed':!s.started||i>s.stageIndex?'waiting':st.progress>=1?'held':'running';
  prefix=prefix&&st.passed;
 }
 const was=s.completed;s.completed=s.started&&s.stages.every(st=>st.passed);
 if(s.completed&&!was){s.completedAt=at;emit(s,'agent_complete',at,{message:'전체 6개 단계와 18개 확인 항목의 기록이 완료되었습니다.'});}
 if(!s.completed&&was){s.completedAt=null;emit(s,'agent_completion_revoked',at,{message:'검사 기준 또는 답변 변경으로 전체 완료 상태를 보류했습니다.'});}
}
function reduce(s,command){
 const {type,payload,at}=command;const stage=()=>s.stages[s.stageIndex];
 switch(type){
 case 'register':{
  ensure(!s.started,'작업 시작 후 작업자 정보를 바꿀 수 없습니다.');const name=text(payload.name,40,'이름'),employeeId=text(payload.employeeId,40,'작업자 번호');
  const photo=payload.photo||null;ensure(photo===null||(typeof photo==='string'&&/^data:image\/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(photo)&&photo.length<=2_000_000),'사진은 크기를 줄인 PNG·JPEG·WebP만 사용할 수 있습니다.');
  s.worker={name,employeeId,photo,registeredAt:at};s.authentication=null;s.process=null;s.setupStep='authenticate';emit(s,'worker_registered',at,{message:`작업자 ${name} (${employeeId}) 등록`,employeeId,photoAttached:!!photo});break;
 }
 case 'authenticate':
  ensure(s.worker&&!s.started,'먼저 작업자를 등록해 주세요.');ensure(payload.code==='6421'&&payload.confirmed===true,'화면 인증 코드와 본인 확인을 다시 확인해 주세요.');s.authentication={method:'training_code',verifiedAt:at,device:'작업 태블릿',simulation:true,employeeId:s.worker.employeeId};s.setupStep='process';emit(s,'worker_authenticated',at,{message:'등록 정보 대조와 화면 인증 완료 (강의용 인증 예시)',method:'training_code'});break;
 case 'process':
  ensure(s.authentication&&!s.started,'화면 인증 후 공정을 선택해 주세요.');ensure(payload.processId===s.bundle.processId,'선택한 공정의 자료가 준비되지 않았습니다.');s.process={...copy(PROCESS),selectedAt:at,ruleVersion:s.bundle.version};s.setupStep='ready';emit(s,'process_selected',at,{message:`${PROCESS.label} · 기준 ${s.bundle.version} 불러옴`,processId:PROCESS.id});break;
 case 'start':
  ensure(s.worker&&s.authentication&&s.process,'작업자 등록·화면 인증·공정 선택을 완료해 주세요.');ensure(!s.started,'이미 시작된 작업입니다.');s.started=true;s.startedAt=at;emit(s,'worker_started',at,{stageId:stage().id,message:'영상 입력을 연결하고 첫 작업을 시작했습니다.'});break;
 case 'progress':{
  ensure(s.started,'작업 시작 후 영상을 재생해 주세요.');const p=payload.progress;ensure(Number.isFinite(p)&&p>=0&&p<=1,'영상 진행률은 0에서 1 사이여야 합니다.');ensure(['video','still_fallback'].includes(payload.source),'지원하지 않는 영상 입력 출처입니다.');ensure(payload.stageId===stage().id,'현재 작업 단계의 영상만 반영할 수 있습니다.');ensure(p>=stage().progress,'이전 장면 재생은 이미 기록한 검사 결과를 되돌리지 않습니다.');stage().progress=p;const plan=PLAN[s.stageIndex];
  for(const rule of plan.checks){const row=s.checks.find(c=>c.id===rule.id);if(row.rawVerdict!==null||p+1e-9<rule.threshold)continue;const sourceTime=Number((plan.sourceStart+(plan.sourceEnd-plan.sourceStart)*rule.threshold).toFixed(3));ensure(rule.imageTime<=sourceTime+.001,'미래 시각의 사진을 현재 확인 근거로 사용할 수 없습니다.');Object.assign(row,{rawVerdict:rule.rawVerdict,verdict:rule.rawVerdict,observedAt:at,sourceTime,imagePath:rule.imagePath,imageTime:rule.imageTime,reason:rule.reason,inputMode:payload.source});emit(s,'agent_check',at,{stageId:plan.id,checkId:rule.id,criterionId:rule.criterionId,message:rule.label,verdict:rule.rawVerdict,sourceTime,imagePath:rule.imagePath,origin:'authored_demo',inputMode:payload.source});
   if(rule.question){const q={id:`question-${rule.id}`,checkId:rule.id,criterionId:rule.criterionId,taskId:plan.id,target:rule.target,text:rule.question,state:'created',createdAt:at,sourceTime,deliveries:[],answers:[]};s.questions.push(q);emit(s,'agent_question',at,{stageId:plan.id,checkId:rule.id,questionId:q.id,message:q.text});}
  }
  break;
 }
 case 'deliver':{
  const q=s.questions.find(q=>q.id===payload.questionId);ensure(q,'확인할 질문이 없습니다.');ensure(['screen','voice'].includes(payload.channel),'질문 전달 방식을 확인해 주세요.');ensure(q.taskId===stage().id,'현재 단계의 질문만 전달할 수 있습니다.');q.deliveries.push({at,channel:payload.channel});emit(s,'question_delivered',at,{questionId:q.id,stageId:q.taskId,message:payload.channel==='voice'?'음성으로 확인 질문 전달':'화면에서 확인 질문 확인',channel:payload.channel});break;
 }
 case 'answer':{
  const q=s.questions.find(q=>q.id===payload.questionId);ensure(q&&q.deliveries.length,'질문을 확인한 뒤 답변해 주세요.');ensure(q.taskId===stage().id,'현재 단계의 질문에 답변해 주세요.');ensure(['met','violated','unknown'].includes(payload.verdict),'답변 상태가 올바르지 않습니다.');const answer={verdict:payload.verdict,text:text(payload.text||({met:'방향이 맞는 것을 직접 확인했습니다.',violated:'방향이 맞지 않습니다.',unknown:'지금은 확인하기 어렵습니다.'}[payload.verdict]),500,'답변'),at,employeeId:s.worker.employeeId};q.answers.push(answer);s.checks.find(c=>c.id===q.checkId).workerAnswer=copy(answer);emit(s,'worker_answer',at,{questionId:q.id,checkId:q.checkId,stageId:q.taskId,message:answer.text,verdict:answer.verdict,origin:'worker_confirmed'});break;
 }
 case 'next':
  ensure(s.started&&stage().passed,'현재 단계의 검사 통과 신호를 받은 뒤 진행할 수 있습니다.');ensure(s.stageIndex<PLAN.length-1,'마지막 단계까지 완료했습니다.');emit(s,'worker_next',at,{stageId:stage().id,message:'작업자가 다음 단계 진행을 선택했습니다.'});s.stageIndex++;emit(s,'agent_stage_ready',at,{stageId:stage().id,message:`${stage().label}의 작업 정보와 검사 기준을 불러왔습니다.`});break;
 case 'policy':
  ensure(['worker_evidence','visual_only'].includes(payload.policy),'지원하지 않는 증거 인정 기준입니다.');s.policy=payload.policy;emit(s,'policy_changed',at,{message:payload.policy==='visual_only'?'영상 증거만 인정하도록 기준 변경':'작업자 직접 확인을 인정하도록 기준 변경',policy:payload.policy});break;
 default:throw new Error('알 수 없는 작업 기록 명령입니다.');
 }
 reevaluate(s,at);
 const current=stage();if(s.started&&current.status==='held'&&!s.events.some(e=>e.type==='agent_hold'&&e.stageId===current.id&&e.policy===s.policy&&e.progress===current.progress)){emit(s,'agent_hold',at,{stageId:current.id,message:'미확인 또는 불일치 항목이 있어 다음 단계 진행을 보류합니다.',policy:s.policy,progress:current.progress});}
 s.commands.push(copy(command));return s;
}
function dispatch(state,type,payload,at){ensure(state?.schema==='seminar.worker-flow.v1','작업 기록 형식이 다릅니다.');return reduce(copy(state),{type,payload:copy(payload),at:iso(at)});}
export const registerWorker=(s,p,at)=>dispatch(s,'register',p,at);
export const authenticateWorker=(s,p,at)=>dispatch(s,'authenticate',p,at);
export const selectProcess=(s,processId,at)=>dispatch(s,'process',{processId},at);
export const startWork=(s,at)=>dispatch(s,'start',{},at);
export function observeProgress(s,progress,options={}){if(progress===s.stages[s.stageIndex].progress)return s;return dispatch(s,'progress',{stageId:options.stageId||s.stages[s.stageIndex].id,progress,source:options.source||'video'},options.at);}
export const deliverQuestion=(s,questionId,channel='screen',at)=>dispatch(s,'deliver',{questionId,channel},at);
export const answerQuestion=(s,questionId,answer,at)=>dispatch(s,'answer',{questionId,...answer},at);
export const nextStage=(s,at)=>dispatch(s,'next',{},at);
export function setEvidencePolicy(s,policy,at){if(s.policy===policy)return s;return dispatch(s,'policy',{policy},at);}
export function summarizeWorker(s){
 const rows=s.checks.map(copy),stages=s.stages.map(copy),current=stages[s.stageIndex];return {rows,stages,current,total:rows.length,met:rows.filter(c=>c.verdict==='met').length,unknown:rows.filter(c=>c.verdict==='unknown').length,violated:rows.filter(c=>c.verdict==='violated').length,notDue:rows.filter(c=>c.verdict==='not_due').length,passedStages:stages.filter(st=>st.passed).length,canNext:!!current?.passed&&s.stageIndex<PLAN.length-1,completed:s.completed,pass:s.completed,openQuestions:s.questions.filter(q=>q.state!=='resolved').map(copy)};
}
export function validateWorkerState(saved,bundle){
 ensure(saved?.schema==='seminar.worker-flow.v1'&&saved.planVersion===PLAN_VERSION,'지원하지 않는 작업자 실습 기록입니다.');ensure(Array.isArray(saved.commands)&&saved.commands.length<=20000,'작업 기록 명령이 올바르지 않습니다.');checkBundle(saved.bundle);if(bundle)ensure(same(saved.bundle,bundle),'작업 시작 시 회사 기준과 현재 구축 기준이 다릅니다.');let replay=initial(saved.bundle,{id:saved.id,at:iso(saved.createdAt)});for(const cmd of saved.commands){ensure(cmd&&typeof cmd.type==='string'&&cmd.payload&&typeof cmd.payload==='object','작업 기록 명령이 손상되었습니다.');replay=reduce(replay,{type:cmd.type,payload:copy(cmd.payload),at:iso(cmd.at)});}ensure(same(replay,saved),'작업 기록과 검사 결과가 일치하지 않습니다.');return copy(replay);
}
