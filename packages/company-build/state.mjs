/** Pure state for the company-folder teaching exercise; no model or file I/O. */
import {compileCompany} from '../core/core.mjs';

export const SCHEMA = 'seminar.company-build.v2';
export const REVIEW_CRITERION = 'E-BATTERY';
export const ORIGINAL_TASK = 'battery';
export const DRAFT_TASK = 'circuit';
const clone = value => JSON.parse(JSON.stringify(value));
const same = (a,b) => JSON.stringify(a) === JSON.stringify(b);
const expect = (value,message) => {if(!value) throw new Error(message);};
const phases = ['upload','selection','processing','review','ontology'];
const fail = message => `회사 자료 실습: ${message}`;
const record = (state,type,detail={}) => state.events.push({sequence:state.events.length+1,type,...clone(detail)});

function normalizeFiles(files) {
  const all=Array.from(files||[]),seen=new Set();
  expect(all.length<=300,fail('파일은 한 번에 300개까지 선택해 주세요.'));
  return all.map((file,index)=>{
    const path=String(file.webkitRelativePath||file.path||file.name||'').replaceAll('\\','/');
    expect(path&&path.length<=1024&&!path.startsWith('/')&&!/^[A-Za-z]:/.test(path)&&!/[\u0000-\u001f]/.test(path),fail('파일 경로를 확인해 주세요.'));
    expect(path.split('/').every(part=>part&&part!=='.'&&part!=='..'),fail('상위 폴더 경로는 사용할 수 없습니다.'));
    expect(!seen.has(path),fail('같은 경로의 파일이 중복되었습니다.'));seen.add(path);
    const size=Number(file.size??0),lastModified=Number(file.lastModified??0);
    expect(Number.isSafeInteger(size)&&size>=0&&Number.isSafeInteger(lastModified)&&lastModified>=0,fail('파일 크기와 수정 정보를 확인해 주세요.'));
    return {id:`file-${String(index+1).padStart(4,'0')}`,path,name:path.split('/').at(-1),size,type:String(file.type||''),lastModified,selected:file.selected!==false};
  });
}

export function makeBuildState(files=[]) {
  const normalized=normalizeFiles(files);
  return {schema:SCHEMA,origin:'authored_demo',phase:normalized.length?'selection':'upload',revision:0,
    files:normalized,canonicalBundle:null,draftBundle:null,issue:null,events:[],archives:[]};
}

function archiveAndClear(state,reason) {
  if(state.canonicalBundle||state.phase==='processing') state.archives.push({revision:state.revision,phase:state.phase,
    reason,selectedFiles:state.files.filter(f=>f.selected).map(f=>f.path),canonicalBundle:clone(state.canonicalBundle),
    draftBundle:clone(state.draftBundle),issue:clone(state.issue),events:clone(state.events)});
  state.canonicalBundle=null;state.draftBundle=null;state.issue=null;
  state.phase=state.files.length?'selection':'upload';state.revision++;
}

export function replaceFiles(input,files) {
  const normalized=normalizeFiles(files),state=clone(input);
  archiveAndClear(state,'folder_replaced');state.files=normalized;state.phase=normalized.length?'selection':'upload';
  record(state,'folder_selected',{files:normalized.map(({id,path,size})=>({id,path,size}))});return state;
}

export function setFileSelected(input,id,selected) {
  expect(typeof selected==='boolean',fail('선택 상태는 참 또는 거짓이어야 합니다.'));
  const state=clone(input),file=state.files.find(f=>f.id===id);
  expect(file,fail('선택한 파일을 찾을 수 없습니다.'));
  if(file.selected===selected)return state;
  archiveAndClear(state,'selection_changed');file.selected=selected;
  record(state,'file_selection_changed',{id,path:file.path,selected});return state;
}

export function setAllSelected(input,selected) {
  expect(typeof selected==='boolean',fail('선택 상태는 참 또는 거짓이어야 합니다.'));
  const state=clone(input);if(state.files.every(f=>f.selected===selected))return state;
  archiveAndClear(state,'selection_changed');state.files.forEach(f=>{f.selected=selected;});
  record(state,'all_files_selection_changed',{selected});return state;
}

export function startBuild(input) {
  const state=clone(input);
  expect(state.files.some(f=>f.selected),fail('자료를 한 개 이상 선택해 주세요.'));
  expect(state.phase!=='processing',fail('이미 정보 구축이 진행 중입니다.'));
  archiveAndClear(state,'new_build');state.phase='processing';
  record(state,'build_started',{selectedFiles:state.files.filter(f=>f.selected).map(f=>f.path),
    resultPolicy:'fixed_electronics_teaching_template',origin:'authored_demo'});return state;
}

function assertCanonical(bundle) {
  expect(bundle&&bundle.companyId==='edu-daon'&&bundle.processId==='ELEC-DEMO-001',fail('전자 조립 교육용 공정만 지원합니다.'));
  expect(bundle.source==='parsed_pdf_csv'&&typeof bundle.sourceText==='string'&&typeof bundle.sourceCsv==='string',fail('PDF·CSV에서 실제로 구성한 정보가 필요합니다.'));
  expect(Array.isArray(bundle.tasks)&&Array.isArray(bundle.criteria),fail('작업과 검사 기준이 필요합니다.'));
  expect(new Set(bundle.tasks.map(t=>t.id)).size===bundle.tasks.length&&new Set(bundle.criteria.map(c=>c.id)).size===bundle.criteria.length,fail('중복된 작업 또는 기준입니다.'));
  expect(bundle.tasks.some(t=>t.id===ORIGINAL_TASK)&&bundle.tasks.some(t=>t.id===DRAFT_TASK),fail('검토에 필요한 작업 목록이 없습니다.'));
  expect(bundle.criteria.find(c=>c.id===REVIEW_CRITERION)?.taskId===ORIGINAL_TASK,fail('배터리 기준의 원본 작업 연결이 다릅니다.'));
}

export function prepareReview(input,canonicalBundle) {
  expect(input.phase==='processing',fail('먼저 정보 구축을 시작해 주세요.'));assertCanonical(canonicalBundle);
  const state=clone(input);state.canonicalBundle=clone(canonicalBundle);state.draftBundle=clone(canonicalBundle);
  state.draftBundle.criteria.find(c=>c.id===REVIEW_CRITERION).taskId=DRAFT_TASK;
  state.issue={criterionId:REVIEW_CRITERION,field:'taskId',originalTaskId:ORIGINAL_TASK,draftTaskId:DRAFT_TASK,
    resolved:false,origin:'authored_demo',source:'교육용 SOP · 배터리 삽입 / 검사 기준 CSV E-BATTERY',
    instruction:'배터리 방향 검사 항목이 올바른 작업에 연결되어 있는지 원문과 비교해 주세요.'};
  state.phase='review';record(state,'draft_prepared',{criterionId:REVIEW_CRITERION,originalTaskId:ORIGINAL_TASK,draftTaskId:DRAFT_TASK,
    origin:'authored_demo',note:'검토 연습을 위해 의도적으로 잘못 연결한 초안'});return state;
}

function assertDraft(state) {
  assertCanonical(state.canonicalBundle);
  expect(state.draftBundle&&state.issue,fail('검토할 DB 초안이 없습니다.'));
  expect(same({...state.issue,resolved:false},{criterionId:REVIEW_CRITERION,field:'taskId',originalTaskId:ORIGINAL_TASK,draftTaskId:DRAFT_TASK,
    resolved:false,origin:'authored_demo',source:'교육용 SOP · 배터리 삽입 / 검사 기준 CSV E-BATTERY',
    instruction:'배터리 방향 검사 항목이 올바른 작업에 연결되어 있는지 원문과 비교해 주세요.'}),fail('검토 항목이 원래 실습과 다릅니다.'));
  const candidate=clone(state.draftBundle),row=candidate.criteria?.find(c=>c.id===REVIEW_CRITERION);
  expect(row&&state.canonicalBundle.tasks.some(t=>t.id===row.taskId),fail('등록되지 않은 작업 연결입니다.'));
  row.taskId=ORIGINAL_TASK;
  expect(same(candidate,state.canonicalBundle),fail('이번 검토 범위를 벗어난 DB 변경입니다.'));
  return state.draftBundle.criteria.find(c=>c.id===REVIEW_CRITERION);
}

export function correctTask(input,taskId,note='') {
  expect(input.phase==='review',fail('DB 검토 단계에서 수정해 주세요.'));
  expect(typeof note==='string'&&note.length<=1000,fail('검토 메모는 1,000자 이내로 입력해 주세요.'));
  const state=clone(input);const row=assertDraft(state);
  expect(state.canonicalBundle.tasks.some(t=>t.id===taskId),fail('등록된 작업을 선택해 주세요.'));
  const before=row.taskId;row.taskId=taskId;state.issue.resolved=taskId===ORIGINAL_TASK;
  record(state,'task_mapping_reviewed',{criterionId:REVIEW_CRITERION,before,after:taskId,accepted:state.issue.resolved,note:note.trim(),origin:'learner_review'});
  return state;
}

export function canCompleteReview(state) {
  if(!state||!['review','ontology'].includes(state.phase))return false;
  try {
    const row=assertDraft(state),last=[...state.events].reverse().find(e=>e.type==='task_mapping_reviewed');
    return row.taskId===ORIGINAL_TASK&&state.issue.resolved===true&&!!last&&last.after===ORIGINAL_TASK&&last.accepted===true;
  } catch {return false;}
}

export function completeReview(input) {
  expect(input.phase==='review',fail('DB 검토 단계가 아닙니다.'));
  expect(canCompleteReview(input),fail('배터리 검사 항목의 작업 연결을 수정한 뒤 완료해 주세요.'));
  const state=clone(input);state.phase='ontology';record(state,'review_completed',{criterionId:REVIEW_CRITERION,taskId:ORIGINAL_TASK});return state;
}

export function reviewedBundle(state) {
  expect(state.phase==='ontology'&&canCompleteReview(state),fail('DB 검토를 먼저 완료해 주세요.'));
  // Exact canonical values retain core session source/fingerprint validation.
  return clone(state.canonicalBundle);
}

export function restoreBuildState(saved,scenario) {
  expect(saved&&saved.schema===SCHEMA&&saved.origin==='authored_demo'&&phases.includes(saved.phase),fail('지원하지 않는 자료 구축 기록입니다.'));
  expect(Number.isSafeInteger(saved.revision)&&saved.revision>=0&&Array.isArray(saved.events)&&Array.isArray(saved.archives),fail('자료 구축 이력이 올바르지 않습니다.'));
  const state=clone(saved),files=normalizeFiles(saved.files);
  expect(same(files,state.files),fail('저장된 파일 목록이 올바르지 않습니다.'));
  state.events.forEach((event,index)=>expect(event.sequence===index+1&&typeof event.type==='string',fail('구축 이력 순서가 올바르지 않습니다.')));
  if(state.canonicalBundle){
    expect(scenario?.id==='electronics_demo',fail('현재 전자 조립 시나리오가 필요합니다.'));
    const compiled=compileCompany(state.canonicalBundle.sourceText,state.canonicalBundle.sourceCsv,scenario);
    expect(same(compiled,state.canonicalBundle),fail('원본 PDF·CSV와 저장된 DB가 다릅니다.'));
    const row=assertDraft(state);
    expect(state.issue.resolved===(row.taskId===ORIGINAL_TASK),fail('검토 상태와 작업 연결이 다릅니다.'));
    expect(['review','ontology'].includes(state.phase),fail('완성된 DB의 단계가 올바르지 않습니다.'));
    if(state.phase==='ontology')expect(canCompleteReview(state),fail('완료된 검토 근거가 없습니다.'));
  } else {
    expect(!state.draftBundle&&!state.issue&&!['review','ontology'].includes(state.phase),fail('검토할 원본 정보가 없습니다.'));
  }
  if(state.phase==='processing'){
    archiveAndClear(state,'interrupted_build');record(state,'build_interrupted',{note:'새로고침 전 구축은 완료되지 않았습니다. 다시 실행해 주세요.'});
  }
  return state;
}
