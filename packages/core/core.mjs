/** Educational controller: authored teaching examples, fixtures, or verified recorded observations. */
const clone = value => JSON.parse(JSON.stringify(value));
const fail = message => { throw new Error(message); };
const expect = (condition, message) => { if (!condition) fail(message); };
const statuses = new Set(['met', 'unknown', 'violated']);
const stable = value => JSON.stringify(value, (_, v) => v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])) : v);
const same = (a,b) => stable(a)===stable(b);
const digest = value => typeof value==='string' && /^[a-f0-9]{64}$/.test(value);
const hash = value => {
  let h = 2166136261;
  for (const c of JSON.stringify(value)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); }
  return (h >>> 0).toString(16).padStart(8, '0');
};
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeImage = value => {
  if(typeof value !== 'string') return '';
  try {
    const decoded=decodeURIComponent(value);
    return !/^(?:[a-z]+:|\/)/i.test(decoded) && !decoded.includes('\\') && !decoded.split('/').includes('..') ? value : '';
  } catch { return ''; }
};

export function parseCsv(text) {
  expect(typeof text === 'string', 'CSV 문자열이 필요합니다.');
  const rows = []; let row = [], field = '', quoted = false, afterQuote = false;
  const input = text.replace(/^\uFEFF/, '');
  for (let i = 0; i < input.length; i++) {
    const c = input[i];
    if (quoted) {
      if (c === '"' && input[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') { quoted = false; afterQuote = true; }
      else field += c;
    } else if (c === '"') {
      expect(field === '' && !afterQuote, 'CSV 따옴표 위치가 잘못되었습니다.'); quoted = true;
    } else if (c === ',' || c === '\n' || c === '\r') {
      row.push(field.trim()); field = ''; afterQuote = false;
      if (c !== ',') { if (row.some(Boolean)) rows.push(row); row = []; if (c === '\r' && input[i + 1] === '\n') i++; }
    } else {
      expect(!afterQuote || /\s/.test(c), 'CSV 닫는 따옴표 뒤에 값이 있습니다.');
      if (!afterQuote) field += c;
    }
  }
  expect(!quoted, 'CSV 따옴표가 닫히지 않았습니다.');
  row.push(field.trim()); if (row.some(Boolean)) rows.push(row);
  expect(rows.length > 1, 'CSV 헤더와 검사 기준 행이 필요합니다.');
  const headers = rows.shift();
  expect(headers.every(Boolean) && new Set(headers).size === headers.length, 'CSV 헤더가 비었거나 중복되었습니다.');
  return rows.map((r, i) => {
    expect(r.length === headers.length, `CSV ${i + 2}행의 열 개수가 다릅니다.`);
    return Object.fromEntries(headers.map((h, j) => [h, r[j]]));
  });
}

function decimal(value) {
  const raw = String(value).trim();
  expect(/^[+-]?\d+(?:\.\d+)?$/.test(raw) && raw.length <= 40, '유효한 10진수 값이 필요합니다.');
  const negative = raw.startsWith('-');
  const [a, b = ''] = raw.replace(/^[+-]/, '').split('.');
  return {n: BigInt((negative ? '-' : '') + a + b), scale: b.length, raw};
}
function cmp(a, b) {
  a = decimal(a); b = decimal(b);
  const scale = Math.max(a.scale, b.scale);
  const x = a.n * 10n ** BigInt(scale - a.scale), y = b.n * 10n ** BigInt(scale - b.scale);
  return x < y ? -1 : x > y ? 1 : 0;
}
function rangeVerdict(value, rule) {
  return cmp(value, rule.lower) >= 0 && cmp(value, rule.upper) <= 0 ? 'met' : 'violated';
}

function checkRules(criteria, scenario) {
  expect(Array.isArray(criteria) && criteria.length > 0, '검사 기준이 없습니다.');
  const tasks = new Set(scenario.tasks.map(t => t.id));
  const ids = new Set();
  for (const c of criteria) {
    expect(c && typeof c.id === 'string' && /^[A-Za-z0-9_-]+$/.test(c.id) && !ids.has(c.id), '검사 기준 ID가 잘못되었거나 중복되었습니다.'); ids.add(c.id);
    expect(tasks.has(c.taskId), `존재하지 않는 작업: ${c.taskId}`);
    expect(typeof c.label === 'string' && c.label && typeof c.target === 'string' && c.target, '기준 이름과 대상이 필요합니다.');
    expect(['visual', 'range'].includes(c.kind), '지원하지 않는 검사 종류입니다.');
    expect(typeof c.allowWorker === 'boolean', 'allowWorker는 true/false여야 합니다.');
    if (c.kind === 'range') {
      expect(typeof c.unit === 'string' && c.unit.trim(), '계측 기준에는 단위가 필요합니다.');
      expect(cmp(c.lower, c.upper) <= 0, '하한이 상한보다 큽니다.');
    }
  }
}

function inspectionContract(scenario) {
  if(scenario.demoKind!=='measurement') return null;
  expect(scenario.mode==='demo','계측 예시는 강의용 모드에서 실행해야 합니다.');
  const spec=scenario.inspection;
  expect(spec && ['productId','productName','drawingId','drawingRevision','specimenId','drawing'].every(k=>typeof spec[k]==='string'&&spec[k].trim()),'제품·도면·개정·시료 정보가 필요합니다.');
  expect(safeImage(spec.drawing),'도면 경로가 올바르지 않습니다.');
  expect(Array.isArray(spec.features)&&spec.features.length===scenario.criteria.length,'도면 검사 위치와 기준 개수가 다릅니다.');
  const ids=new Set(),codes=new Set();
  for(const feature of spec.features) {
    const rule=scenario.criteria.find(c=>c.id===feature.criterionId);
    expect(rule&&rule.kind==='range'&&rule.target===spec.specimenId,'검사 위치의 기준·시료가 다릅니다.');
    expect(!ids.has(feature.criterionId)&&typeof feature.code==='string'&&feature.code&&!codes.has(feature.code),'도면 검사 위치가 중복되거나 잘못되었습니다.');
    ids.add(feature.criterionId);codes.add(feature.code);
    expect(typeof feature.label==='string'&&feature.label&&typeof feature.instrument==='string'&&feature.instrument,'측정 위치와 장비 이름이 필요합니다.');
    expect(feature.unit===rule.unit&&cmp(feature.lower,rule.lower)===0&&cmp(feature.upper,rule.upper)===0,'도면의 단위·허용 범위가 기준과 다릅니다.');
    decimal(feature.nominal);
  }
  return clone(spec);
}
function measurementBinding(inspection,rule) {
  const feature=inspection.features.find(f=>f.criterionId===rule.id);
  return {productId:inspection.productId,drawingId:inspection.drawingId,drawingRevision:inspection.drawingRevision,
    specimenId:inspection.specimenId,criterionId:rule.id,featureCode:feature.code,instrument:feature.instrument,unit:rule.unit};
}

export function compileCompany(pdfText, csvText, scenario) {
  expect(typeof pdfText === 'string' && pdfText.trim(), '추출된 PDF 텍스트가 없습니다.');
  const token = key => [...pdfText.matchAll(new RegExp(`${key}\\s*:\\s*([A-Za-z0-9_-]+)`, 'g'))].map(m => m[1]);
  const companies = token('company_id'), processes = token('process_id');
  expect(companies.length > 0 && companies.every(x => x === scenario.companyId), 'PDF 회사 ID가 선택한 예제와 다릅니다.');
  expect(processes.length > 0 && processes.every(x => x === scenario.processId), 'PDF 공정 ID가 선택한 예제와 다릅니다.');
  const taskIds = [...new Set(token('task_id'))];
  expect(JSON.stringify(taskIds) === JSON.stringify(scenario.tasks.map(t=>t.id)), 'PDF의 작업 목록·순서가 선택한 예제와 다릅니다.');
  const inspection=inspectionContract(scenario);
  if(inspection) for(const [key,field] of Object.entries({product_id:'productId',drawing_id:'drawingId',drawing_revision:'drawingRevision',specimen_id:'specimenId'})) {
    const values=token(key);expect(values.length>0&&values.every(x=>x===inspection[field]),'PDF의 제품·도면·개정·시료가 선택한 제품과 다릅니다: '+key);
  }
  const rows = parseCsv(csvText);
  const required = ['id','taskId','label','target','kind','unit','lower','upper','allowWorker'];
  for (const key of required) expect(Object.hasOwn(rows[0], key), `CSV 필수 열이 없습니다: ${key}`);
  expect(Object.keys(rows[0]).length===required.length && Object.keys(rows[0]).every(key=>required.includes(key)), '지원하지 않는 CSV 열이 있습니다. 이 실습에서는 수치 하한·상한만 변경할 수 있습니다.');
  const criteria = rows.map(r => {
    expect(['true','false'].includes(r.allowWorker), 'allowWorker 값은 true 또는 false여야 합니다.');
    return {...r, allowWorker: r.allowWorker === 'true'};
  });
  checkRules(criteria, scenario);
  const known = new Map(scenario.criteria.map(c => [c.id, c]));
  expect(criteria.length === known.size && criteria.every(c => known.has(c.id)), '선택한 실습의 필수 검사 항목과 CSV 항목이 다릅니다.');
  for (const c of criteria) {
    const ref = known.get(c.id);
    expect(c.taskId === ref.taskId && c.target === ref.target && c.kind === ref.kind, '기준의 작업·대상·종류가 실습 계약과 다릅니다.');
    expect(c.label===ref.label, '검사 항목의 의미를 바꾸는 이름 변경은 지원하지 않습니다.');
    expect(c.allowWorker === ref.allowWorker, '작업자 확인 정책은 이 실습에서 변경할 수 없습니다.');
    expect(c.unit === (ref.unit??''), '검사 단위는 이 실습에서 변경할 수 없습니다.');
    if(c.kind!=='range') expect(c.lower==='' && c.upper==='', '시각적 검사에 수치 범위를 추가할 수 없습니다.');
  }
  return {companyId: scenario.companyId, processId: scenario.processId, tasks: clone(scenario.tasks), criteria,
    version: `source-${hash([pdfText, csvText])}`, source: 'parsed_pdf_csv', sourceText: pdfText,
    sourceCsv: csvText, documentFingerprint: hash([pdfText,csvText]), educational: true,...(inspection?{inspection}: {})};
}

function scenarioFingerprint(scenario) {
  const contract={id:scenario.id, companyId:scenario.companyId, processId:scenario.processId, tasks:scenario.tasks,
    criteria:scenario.criteria, checkpoints:scenario.checkpoints};
  if(scenario.mode==='recorded') contract.recording=scenario.recording;
  if(scenario.demoKind==='measurement') {contract.demoKind=scenario.demoKind;contract.inspection=scenario.inspection;}
  return hash(contract);
}

/** Transport verifies referenced file SHA256s before calling this pure binding validator. */
export function recordingContract(scenario) {
  return {companyId:scenario.companyId,processId:scenario.processId,tasks:clone(scenario.tasks),criteria:clone(scenario.criteria),
    checkpoints:scenario.checkpoints.map(cp=>({id:cp.id,time:cp.time,sourceTime:cp.sourceTime??cp.time,taskId:cp.taskId,target:cp.target,image:cp.image}))};
}
export function bindRecording(baseScenario,pack) {
  expect(baseScenario?.mode!=='recorded' && pack?.schema==='seminar.recording.v1','유효한 원본 시나리오와 실제 응답 묶음이 필요합니다.');
  expect(pack.scenarioId===baseScenario.id && typeof pack.id==='string' && pack.id && typeof pack.model==='string' && pack.model,'실제 응답의 시나리오·모델 식별자가 필요합니다.');
  expect(same(pack.baseContract,recordingContract(baseScenario)),'실제 응답을 수집한 작업·기준·원본 장면과 현재 시나리오가 다릅니다.');
  const cps=baseScenario.checkpoints, allIds=baseScenario.criteria.map(c=>c.id),taskIds=baseScenario.tasks.map(t=>t.id);
  expect(Array.isArray(pack.entries)&&pack.entries.length===cps.length,'모든 관찰 지점의 실제 응답 또는 실패 기록이 필요합니다.');
  expect(Array.isArray(pack.observationSchedule)&&pack.observationSchedule.length===cps.length,'실제 응답의 관찰 범위 기록이 필요합니다.');
  const s=clone(baseScenario);s.mode='recorded';
  s.recording={id:pack.id,model:pack.model,schema:pack.schema,observationSchedule:clone(pack.observationSchedule)};
  const receipts=new Set();
  s.checkpoints=cps.map((cp,i)=>{
    const entry=pack.entries[i], schedule=pack.observationSchedule[i],r=entry?.receipt;
    expect(entry?.checkpointId===cp.id && schedule?.checkpointId===cp.id,'실제 응답의 관찰 순서가 다릅니다.');
    expect(same(schedule.criterionIds,allIds),'이 재생 경로는 모든 기준을 매 관찰 지점에서 확인해야 합니다.');
    expect(r && typeof r.id==='string' && r.id && !receipts.has(r.id) && r.model===pack.model,'응답 영수증 ID 또는 모델이 잘못되었습니다.');receipts.add(r.id);
    expect(digest(r.requestSha256)&&digest(r.responseSha256)&&safeImage(r.requestPath)&&safeImage(r.responsePath),'요청·응답의 경로와 SHA256 기록이 필요합니다.');
    expect(Array.isArray(entry.inputImages)&&entry.inputImages.length>0,'실제로 전달한 이미지 목록이 필요합니다.');
    const imageIds=new Set();
    for(const image of entry.inputImages) {
      expect(typeof image.id==='string' && image.id && !imageIds.has(image.id),'입력 이미지 ID가 비었거나 중복되었습니다.');imageIds.add(image.id);
      expect(safeImage(image.path) && digest(image.sha256) && Number.isFinite(image.time) && image.time>=0 && image.time<=(cp.sourceTime??cp.time),'원본 경로·해시가 없거나 미래 이미지가 포함되었습니다.');
    }
    expect(entry.inputImages.some(img=>img.path===cp.image && img.time===(cp.sourceTime??cp.time)),'화면의 대표 장면이 실제 모델 입력에 없습니다.');
    let assessments,output=null;
    if(entry.failure) {
      expect(entry.output===null && typeof entry.failure.kind==='string' && typeof entry.failure.message==='string','실패한 응답과 정상 출력을 섞을 수 없습니다.');
      assessments=allIds.map(criterionId=>({criterionId,target:baseScenario.criteria.find(c=>c.id===criterionId).target,observation:'unclear',applicability:'unclear',targetConfirmed:false,evidenceIds:[],reason:`모델 응답 실패: ${entry.failure.kind}`}));
    } else {
      expect(typeof entry.responseContent==='string','원본 모델 응답 문자열이 필요합니다.');
      try {output=JSON.parse(entry.responseContent);} catch {fail('모델 응답 JSON을 해석할 수 없습니다. 실패 기록으로 보존해야 합니다.');}
      expect(same(output,entry.output),'저장된 원본 모델 응답과 표시용 관찰 값이 다릅니다.');
      expect(output.checkpointId===cp.id && (output.observedTaskId===null||taskIds.includes(output.observedTaskId)),'모델 관찰 지점 또는 관찰 작업 ID가 잘못되었습니다.');
      expect(['preparation','in_progress','completed','unclear'].includes(output.phase)&&typeof output.summaryKo==='string','모델의 관찰 단계와 설명이 필요합니다.');
      expect(Array.isArray(output.assessments)&&same(output.assessments.map(a=>a.criterionId).sort(),[...allIds].sort()),'모델 응답에 검사 항목이 빠졌거나 중복·추가되었습니다.');
      expect(Array.isArray(output.questions)&&output.questions.every(q=>allIds.includes(q.criterionId)&&typeof q.text==='string'&&q.text.trim()),'모델 질문의 검사 항목 또는 문장이 잘못되었습니다.');
      for(const a of output.assessments) {
        const rule=baseScenario.criteria.find(c=>c.id===a.criterionId);
        expect(a.target===rule.target && a.target===cp.target,'모델 관찰과 기준의 대상이 다릅니다.');
        expect(['present','absent','unclear'].includes(a.observation)&&['due','not_due','unclear'].includes(a.applicability)&&typeof a.targetConfirmed==='boolean','모델 관찰·적용 단계·대상 확인 형식이 잘못되었습니다.');
        expect(Array.isArray(a.evidenceIds)&&new Set(a.evidenceIds).size===a.evidenceIds.length&&a.evidenceIds.every(id=>imageIds.has(id)),'실제 입력에 없는 증거가 인용되었습니다.');
        expect(typeof a.reason==='string'&&a.reason.trim(),'모델 관찰의 설명이 필요합니다.');
        expect(rule.kind==='visual','현재 실제 응답 재생 경로는 시각적 전자 조립 검사만 지원합니다.');
      }
      assessments=clone(output.assessments);
    }
    return {...clone(cp),origin:'recorded_model',assessments,note:output?.summaryKo??entry.failure.message,
      observedTaskId:output?.observedTaskId??null,observedPhase:output?.phase??'unclear',
      recording:{receipt:clone(r),inputImages:clone(entry.inputImages),output:clone(output),responseContent:entry.responseContent??null,failure:clone(entry.failure??null)}};
  });
  s.sourceNote='공개 영상의 인과적 이미지 입력에 대한 실제 모델 응답을 저장해 재생합니다. 교육 기준·작업자 확인과 모델 관찰은 분리되며 실제 제품의 품질 승인을 의미하지 않습니다.';
  s.fixtureNotice='실제 모델 응답 재생: 수업 중 GPU·API 호출 없음. 기준 변경과 작업자 답변은 저장된 관찰을 바꾸지 않고 제어기에서 재판정합니다.';
  return s;
}
function event(s, type, payload) {
  s.revision++;
  s.events.push({id:`event-${s.revision}`, revision:s.revision, time:s.time, type, ...clone(payload)});
}
function initial(scenario, bundle, id) {
  checkRules(bundle.criteria, scenario);
  expect(bundle.companyId === scenario.companyId && bundle.processId === scenario.processId, '정보 묶음과 공정이 다릅니다.');
  if(scenario.demoKind==='measurement') expect(same(bundle.inspection,inspectionContract(scenario)),'정보 묶음의 제품·도면·시료 연결이 다릅니다.');
  return {schemaVersion:1, id, scenarioId:scenario.id, scenarioFingerprint:scenarioFingerprint(scenario), bundle:clone(bundle),
    initialBundle:clone(bundle), mode:scenario.mode==='recorded'?'recorded':scenario.mode==='demo'?'demo':'fixture', position:-1, time:0, revision:0, assessments:{}, questions:[], events:[],
    commands:[], attempts:{}, completed:false};
}
export function createSession(scenario, bundle) {
  expect(scenario?.id && Array.isArray(scenario.checkpoints) && scenario.checkpoints.length, '유효한 실습 시나리오가 필요합니다.');
  const inspection=inspectionContract(scenario);
  let last = -1; const ids = new Set();
  for (const cp of scenario.checkpoints) {
    if(inspection) expect(cp.target===inspection.specimenId,'관찰 시료가 선택한 제품과 다릅니다.');
    expect(Number.isFinite(cp.time) && cp.time >= 0 && cp.time >= last && typeof cp.id==='string' && /^[A-Za-z0-9_-]+$/.test(cp.id) && !ids.has(cp.id), '관찰 시각 또는 ID가 잘못되었습니다.');
    expect(cp.sourceTime===undefined || (Number.isFinite(cp.sourceTime) && cp.sourceTime>=0), '원본 시각이 잘못되었습니다.');
    expect(new Set((cp.assessments??[]).map(a=>a.criterionId)).size===(cp.assessments??[]).length,'한 관찰에 같은 검사 항목이 중복되었습니다.');
    expect(cp.origin === (scenario.mode==='recorded'?'recorded_model':scenario.mode==='demo'?'authored_demo':'authored_fixture'), '관찰 출처와 선택한 실행 모드가 다릅니다.');
    if(scenario.mode==='recorded') expect(cp.recording?.receipt && scenario.recording?.id,'검증된 실제 응답 연결이 필요합니다.');
    if(scenario.mode==='demo') expect(!cp.recording && !scenario.recording,'강의용 예시에 실제 모델 응답 식별 기록을 붙일 수 없습니다.');
    last = cp.time; ids.add(cp.id);
  }
  const id = globalThis.crypto?.randomUUID?.() ?? `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return initial(scenario, bundle, id);
}
function assertScenario(s, scenario) {
  expect(s.scenarioId === scenario.id && s.scenarioFingerprint === scenarioFingerprint(scenario), '시나리오 버전이 일치하지 않습니다.');
}
function findRule(s, id) { const rule = s.bundle.criteria.find(c => c.id === id); expect(rule, `알 수 없는 검사 항목: ${id}`); return rule; }
function recordAssessment(s, row) {
  const previous = s.assessments[row.criterionId];
  const current = clone(row), old = previous ? clone(previous) : null;
  if(old) delete old.history;
  s.assessments[row.criterionId] = {...current, history:previous ? [...(previous.history ?? []), old] : []};
}
function recordedVisualVerdict(raw) {
  if(raw.applicability==='not_due') return 'not_due';
  if(raw.applicability!=='due'||!raw.targetConfirmed||!raw.evidenceIds.length||raw.observation==='unclear') return 'unknown';
  return raw.observation==='present'?'met':'violated';
}
function applyVisualPolicy(row,rule) {
  const next={...clone(row),history:undefined};
  next.modelVerdict=recordedVisualVerdict(next.rawProposal);
  next.verdict=next.modelVerdict;next.origin='recorded_model';next.reason=next.rawProposal.reason;
  next.policy=rule.allowWorker?'worker_attestation':'visual_only';next.conflict=false;
  next.applicabilityConflict=Boolean(next.dueObserved && next.rawProposal.applicability==='not_due');
  if(next.applicabilityConflict) {
    next.verdict='unknown';
    next.reason='앞선 관찰에서 적용 단계였던 검사가 미도래로 바뀌었습니다. 동일 대상의 기존 검사 의무를 없애지 않고 적용 단계 충돌로 보류합니다.';
  }
  const answer=next.workerConfirmation;
  if(rule.allowWorker && answer && ['met','violated'].includes(answer.confirmation)) {
    if(next.modelVerdict==='not_due') {
      next.reason+=' 작업자 답변은 기록했지만 미도래 관찰의 적용 단계를 자동 변경하지 않습니다.';
    } else if(['met','violated'].includes(next.modelVerdict)&&next.modelVerdict!==answer.confirmation) {
      next.verdict='unknown';next.conflict=true;
      next.reason='영상의 모델 관찰과 작업자 확인이 충돌합니다. 원본 증거를 다시 검토해야 합니다.';
    } else {
      next.verdict=answer.confirmation;next.origin='worker_confirmed';
      next.reason='명시적으로 선택한 작업자 확인 허용 정책에 따라 답변을 반영했습니다. 영상으로 입증된 사실이나 자동 품질 승인이 아닙니다.';
    }
  }
  return next;
}
function applyDemoPolicy(row,rule) {
  const next={...clone(row),history:undefined};
  // Teaching observations are authored examples, never inferred model verdicts.
  next.rawExampleVerdict=next.rawProposal.verdict;
  next.verdict=next.rawExampleVerdict;next.origin='authored_demo';next.reason=next.rawProposal.reason??'';
  next.policy=rule.allowWorker?'worker_attestation':'visual_only';next.conflict=false;
  const answer=next.workerConfirmation;
  if(rule.allowWorker && answer && ['met','violated'].includes(answer.confirmation)) {
    if(answer.confirmation==='violated') {
      next.verdict='violated';next.origin='worker_confirmed';next.conflict=next.rawExampleVerdict==='met';
      next.reason='작업자가 불일치를 확인했습니다. 후속 예시 장면만으로 답변을 지우지 않으며, 재확인한 답변을 별도로 기록해야 합니다.';
    } else if(next.rawExampleVerdict==='violated') {
      next.verdict='unknown';next.conflict=true;
      next.reason='강의용 관찰 예시와 작업자 확인이 다릅니다. 해당 항목을 다시 확인해 주세요.';
    } else {
      next.verdict='met';next.origin='worker_confirmed';
      next.reason='이 기준은 작업자 확인을 허용하므로 입력한 확인 내용을 반영했습니다. 최초 예시 관찰과 답변은 별도로 보존합니다.';
    }
  }
  return next;
}
function openQuestion(s, rule, row) {
  const existing = s.questions.find(q => q.criterionId === rule.id && q.attempt === row.attempt && !['resolved','superseded'].includes(q.state));
  if (existing) return;
  s.questions.push({id:`q-${rule.id}-${row.attempt}-${s.position}${['recorded','demo'].includes(s.mode)?`-${s.questions.length}`:''}`, criterionId:rule.id, target:rule.target, taskId:rule.taskId,
    attempt:row.attempt, state:'created', time:s.time, allowWorker:rule.allowWorker, deliveredChannels:[], answers:[],
    ...(s.bundle.inspection?{binding:measurementBinding(s.bundle.inspection,rule)}:{}),
    text:row.proposedQuestion?`${rule.label} · 대상 ${rule.target}: ${row.proposedQuestion}`:rule.kind === 'range' ? `${rule.label}: ${rule.target}의 값과 단위(${rule.unit})를 확인해 주세요.` : `${rule.label}: 가려진 부분을 확인할 수 있는 후속 장면이 필요합니다. 확인 내용은 별도로 기록할 수 있습니다.`});
}
export function advance(session, scenario, index = session.position + 1) {
  assertScenario(session, scenario);
  expect(Number.isInteger(index) && index >= 0 && index < scenario.checkpoints.length, '관찰 범위를 벗어났습니다.');
  expect(index >= session.position, '이전 시각은 복습 화면에서 확인하거나 새 세션을 시작하세요.');
  if (index === session.position) return clone(session);
  const s = clone(session);
  for (let i = s.position + 1; i <= index; i++) {
    const cp = scenario.checkpoints[i]; s.position = i; s.time = cp.time;
    for (const cid of cp.invalidate ?? []) {
      const rule = findRule(s, cid);
      expect(rule.target===cp.target,'다른 대상의 검사 결과를 무효화할 수 없습니다.');
      expect(s.assessments[cid],'검사 이력이 없는 항목을 재작업 무효화할 수 없습니다.');
      s.attempts[cid] = (s.attempts[cid] ?? 1) + 1;
      for (const q of s.questions.filter(q => q.criterionId === cid && !['resolved','superseded'].includes(q.state))) q.state = 'superseded';
      recordAssessment(s, {criterionId:cid, taskId:rule.taskId,target:rule.target,verdict:'unknown',reason:'분리·재작업으로 새 검사가 필요합니다.',origin:cp.origin,time:s.time,sourceTime:cp.sourceTime??cp.time,attempt:s.attempts[cid],checkpointId:cp.id,image:cp.image,evidenceId:`${cp.id}-evidence`});
      openQuestion(s,rule,s.assessments[cid]);
      event(s, 'invalidated', {criterionId:cid,attempt:s.attempts[cid],checkpointId:cp.id});
    }
    for (const raw of cp.assessments ?? []) {
      const rule = findRule(s, raw.criterionId);
      expect(rule.target === cp.target, '관찰 대상과 기준 대상이 다릅니다.');
      if(s.mode==='recorded') {
        const previous=s.assessments[rule.id],attempt=s.attempts[rule.id]??1;
        const cited=raw.evidenceIds.map(id=>cp.recording.inputImages.find(img=>img.id===id)),primary=cited.at(-1);
        const candidate={criterionId:rule.id,taskId:rule.taskId,target:rule.target,time:s.time,sourceTime:primary?.time??cp.sourceTime??cp.time,
          observationSourceTime:cp.sourceTime??cp.time,checkpointImage:cp.image,evidenceFrames:clone(cited),evidenceKind:primary?'cited_model_input':'context_only',
          attempt,checkpointId:cp.id,image:primary?.path??cp.image,evidenceId:primary?.id??`${cp.id}-context`,measurement:null,rawProposal:clone(raw),
          receipt:clone(cp.recording.receipt),inputImages:clone(cp.recording.inputImages),inferenceFailure:clone(cp.recording.failure),
          observedTaskId:cp.observedTaskId,observedPhase:cp.observedPhase,
          proposedQuestion:cp.recording.output?.questions.find(q=>q.criterionId===rule.id)?.text??null,
          dueObserved:raw.applicability==='due'||(previous?.attempt===attempt&&Boolean(previous.dueObserved)),
          workerConfirmation:previous?.attempt===attempt?clone(previous.workerConfirmation??null):null};
        const row=applyVisualPolicy(candidate,rule);recordAssessment(s,row);
        if(row.verdict==='unknown') openQuestion(s,rule,row);
        else if(row.verdict!=='not_due') for(const q of s.questions.filter(q=>q.criterionId===rule.id&&q.attempt===attempt&&!['resolved','superseded'].includes(q.state))) {
          q.state='resolved';q.resolvedAt=s.time;q.resolution=row.origin==='worker_confirmed'?'worker_confirmed':'later_recorded_model';
        }
        continue;
      }
      if(s.mode==='demo' && scenario.demoKind==='measurement') {
        expect(rule.kind==='range' && rule.taskId===cp.taskId,'계측 위치의 작업·종류가 현재 관찰과 다릅니다.');
        expect(raw.target===undefined||raw.target===rule.target,'계측 관찰의 시료가 다릅니다.');
        expect(statuses.has(raw.verdict),'지원하지 않는 계측 예시 상태입니다.');
        const binding=measurementBinding(s.bundle.inspection,rule);
        if(raw.featureCode!==undefined) expect(raw.featureCode===binding.featureCode,'도면 측정 위치가 다릅니다.');
        let valid=false;
        if(raw.verdict!=='unknown' && raw.value!==undefined && raw.value!==null && raw.unit===rule.unit) {
          try {decimal(raw.value);valid=true;} catch {}
        }
        const measurement={raw:String(raw.raw??raw.value??''),rawUnit:String(raw.unit??''),unit:rule.unit,valid,
          ...(valid?{value:String(raw.value)}:{})};
        const previous=s.assessments[rule.id],attempt=s.attempts[rule.id]??1;
        const row={criterionId:rule.id,taskId:rule.taskId,target:rule.target,binding,time:s.time,sourceTime:cp.sourceTime??cp.time,
          attempt,checkpointId:cp.id,image:cp.image,evidenceId:`${cp.id}-example`,evidenceKind:'authored_measurement_scene',
          rawProposal:clone(raw),rawExampleVerdict:raw.verdict,proposedQuestion:raw.question??null,
          measurement,verdict:valid?rangeVerdict(measurement.value,rule):'unknown',origin:'authored_demo',
          reason:valid?(raw.reason??'예시 측정값과 허용 범위를 비교했습니다.'):(raw.reason??'숫자나 단위가 불확실합니다. 값을 확인해 주세요.')};
        if(previous?.attempt===attempt&&previous.workerConfirmation&&rule.allowWorker) {
          row.workerConfirmation=clone(previous.workerConfirmation);
          row.measurement={...measurement,value:previous.workerConfirmation.value,unit:rule.unit,valid:true,workerConfirmed:true};
          row.verdict=rangeVerdict(row.measurement.value,rule);row.origin='worker_confirmed';
          row.reason='기록된 작업자 확인값을 유지하여 현재 허용 범위와 비교했습니다.';
        }
        recordAssessment(s,row);
        if(row.verdict==='unknown') openQuestion(s,rule,row);
        else for(const q of s.questions.filter(q=>q.criterionId===rule.id&&q.attempt===attempt&&!['resolved','superseded'].includes(q.state))) {
          q.state='resolved';q.resolvedAt=s.time;q.resolution=row.origin==='worker_confirmed'?'worker_confirmed':'later_authored_measurement';
        }
        continue;
      }
      if(s.mode==='demo') {
        expect(rule.kind==='visual','이 강의용 예시 경로는 시각적 조립 검사만 지원합니다.');
        expect(rule.taskId===cp.taskId || s.events.some(e=>e.type==='checkpoint'&&e.taskId===rule.taskId),'아직 시작하지 않은 작업의 판정을 미리 적용할 수 없습니다.');
        expect(raw.target===undefined || raw.target===rule.target,'강의용 관찰과 기준 대상이 다릅니다.');
        expect(statuses.has(raw.verdict),'지원하지 않는 강의용 판정입니다.');
        const previous=s.assessments[rule.id],attempt=s.attempts[rule.id]??1;
        const candidate={criterionId:rule.id,taskId:rule.taskId,target:rule.target,time:s.time,sourceTime:cp.sourceTime??cp.time,
          attempt,checkpointId:cp.id,image:cp.image,evidenceId:`${cp.id}-example`,evidenceKind:'authored_demo_scene',measurement:null,
          rawProposal:clone(raw),rawExampleVerdict:raw.verdict,proposedQuestion:raw.question??null,
          workerConfirmation:previous?.attempt===attempt?clone(previous.workerConfirmation??null):null};
        const row=applyDemoPolicy(candidate,rule);recordAssessment(s,row);
        if(row.verdict==='unknown') openQuestion(s,rule,row);
        else for(const q of s.questions.filter(q=>q.criterionId===rule.id&&q.attempt===attempt&&!['resolved','superseded'].includes(q.state))) {
          q.state='resolved';q.resolvedAt=s.time;q.resolution=row.origin==='worker_confirmed'?'worker_confirmed':'later_authored_demo';
        }
        continue;
      }
      expect(rule.taskId === cp.taskId, '다른 작업의 판정을 현재 관찰에 적용할 수 없습니다.');
      expect(statuses.has(raw.verdict), '지원하지 않는 교육용 판정입니다.');
      let verdict = raw.verdict, measurement = null, reason = raw.reason ?? '';
      if (rule.kind === 'range') {
        const valid = raw.value !== undefined && raw.value !== null && String(raw.unit ?? '').trim() === rule.unit;
        if (valid) {
          try { decimal(raw.value); measurement = {raw:String(raw.raw ?? raw.value), value:String(raw.value),unit:rule.unit,valid:true}; }
          catch { measurement = null; }
        }
        if (measurement && raw.verdict !== 'unknown') verdict = rangeVerdict(measurement.value, rule);
        else { verdict = 'unknown'; measurement = {...(measurement ?? {}),raw:String(raw.raw ?? raw.value ?? ''),valid:false}; reason = reason || '값·단위 또는 판독이 불명확합니다.'; }
      }
      const row = {criterionId:rule.id,taskId:rule.taskId,target:rule.target,verdict,reason,origin:'authored_fixture',time:s.time,
        sourceTime:cp.sourceTime??cp.time,attempt:s.attempts[rule.id] ?? 1,checkpointId:cp.id,image:cp.image,evidenceId:`${cp.id}-evidence`,measurement,rawProposal:clone(raw)};
      recordAssessment(s,row);
      if (verdict === 'unknown') openQuestion(s, rule, row);
      else for (const q of s.questions.filter(q => q.criterionId === rule.id && q.attempt === row.attempt && !['resolved','superseded'].includes(q.state))) {
        q.state = 'resolved'; q.resolvedAt=s.time; q.resolution='later_authored_fixture';
      }
    }
    const observed={checkpointId:cp.id,taskId:cp.taskId,target:cp.target,origin:cp.origin,image:cp.image,sourceTime:cp.sourceTime??cp.time};
    if(s.mode==='recorded') Object.assign(observed,{observedTaskId:cp.observedTaskId,observedPhase:cp.observedPhase,receiptId:cp.recording.receipt.id,inferenceFailure:cp.recording.failure});
    event(s,'checkpoint',observed);
  }
  s.completed = index === scenario.checkpoints.length - 1;
  s.commands.push({type:'advance',index});
  return s;
}

export function markDelivered(session, qid, channel = 'screen') {
  expect(['screen','audio'].includes(channel), '지원하지 않는 전달 채널입니다.');
  const s=clone(session), q=s.questions.find(q=>q.id===qid);
  expect(q, '질문을 찾을 수 없습니다.');
  expect(!['resolved','superseded'].includes(q.state), '이미 종료되거나 새 시도로 바뀐 질문입니다.');
  if (q.deliveredChannels.includes(channel)) return s;
  q.deliveredChannels.push(channel); if(q.state==='created') q.state='delivered';
  event(s,'question_delivered',{questionId:qid,channel}); s.commands.push({type:'deliver',qid,channel}); return s;
}
export function answerQuestion(session,qid,answer) {
  const s=clone(session), q=s.questions.find(q=>q.id===qid);
  expect(q && !['resolved','superseded'].includes(q.state), '이 질문은 현재 답변할 수 없습니다.');
  expect(q.deliveredChannels.length>0, '질문을 먼저 화면이나 음성으로 전달해야 합니다.');
  expect(answer && answer.target === q.target, '답변의 대상이 질문과 다릅니다.');
  const rule=findRule(s,q.criterionId), previous=s.assessments[q.criterionId];
  if(q.binding) for(const key of ['productId','drawingId','drawingRevision','specimenId','featureCode']) {
    expect(answer[key]===undefined||answer[key]===q.binding[key],'답변의 제품·도면·측정 위치가 질문과 다릅니다.');
  }
  expect(previous && previous.attempt===q.attempt, '이전 작업 시도의 질문입니다.');
  const response={target:answer.target,text:String(answer.text??''),value:answer.value===undefined?null:String(answer.value),unit:answer.unit===undefined?null:String(answer.unit),origin:'worker_input',time:s.time};
  if(['recorded','demo'].includes(s.mode)&&rule.kind==='visual') {
    expect(answer.confirmation===undefined||['met','violated','unknown'].includes(answer.confirmation),'작업자 확인 상태를 명시적으로 선택하세요.');
    response.confirmation=answer.confirmation??'unknown';
  }
  if(q.answers.some(a=>JSON.stringify(a)===JSON.stringify(response))) return s;
  if(rule.kind==='range' && rule.allowWorker) {
    expect(response.value!==null && response.unit===rule.unit,'측정값과 정확한 단위를 입력하세요.'); decimal(response.value);
    recordAssessment(s,{...previous,history:undefined,verdict:rangeVerdict(response.value,rule),origin:'worker_confirmed',time:s.time,
      reason:'작업자가 입력한 값으로 교육용 범위를 비교했습니다. 자동 판독 결과가 아닙니다.',
      measurement:{raw:previous.measurement?.raw??'',...(s.bundle.inspection?{rawUnit:previous.measurement?.rawUnit??''}:{}),value:response.value,unit:response.unit,valid:true,workerConfirmed:true},
      ...(s.bundle.inspection?{workerConfirmation:{...clone(response),questionId:qid,binding:clone(q.binding)}}:{}),
      evidenceOrigin:s.bundle.inspection?'authored_measurement_scene':'original_fixture_image',questionId:qid});
    q.state='resolved';q.resolvedAt=s.time;q.resolution='worker_confirmed';
  } else if(['recorded','demo'].includes(s.mode)&&rule.kind==='visual') {
    expect(response.text.trim(),'확인 내용을 입력하세요.');
    const apply=s.mode==='demo'?applyDemoPolicy:applyVisualPolicy;
    const row=apply({...previous,workerConfirmation:{...clone(response),questionId:qid}},rule);
    recordAssessment(s,row);
    if(row.origin==='worker_confirmed'&&row.verdict!=='unknown') {
      q.state='resolved';q.resolvedAt=s.time;q.resolution='worker_confirmed';
    } else q.state='answered';
  } else {
    expect(response.text.trim(), '확인 내용을 입력하세요.');
    q.state='answered';
  }
  q.answers.push(response); event(s,'answer',{questionId:qid,answer:response,resolved:q.state==='resolved'});
  s.commands.push({type:'answer',qid,answer:clone(answer)}); return s;
}
/** Reconfirmation creates a new question; it never edits or deletes the previous worker reply. */
export function reopenQuestion(session,criterionId) {
  expect(session.mode==='demo','답변 재확인은 강의용 예시에서만 지원합니다.');
  const s=clone(session),rule=findRule(s,criterionId),row=s.assessments[criterionId];
  expect((rule.kind==='visual'||(s.bundle.inspection&&rule.kind==='range')) && row?.workerConfirmation,'다시 확인할 작업자 답변이 없습니다.');
  if(s.questions.some(q=>q.criterionId===criterionId&&q.attempt===row.attempt&&!['resolved','superseded'].includes(q.state))) return s;
  openQuestion(s,rule,row);
  event(s,'question_reopened',{criterionId,questionId:s.questions.at(-1).id,origin:'worker_reconfirmation'});
  s.commands.push({type:'reopen',criterionId});return s;
}
export function setRange(session,criterionId,lower,upper) {
  const s=clone(session),rule=findRule(s,criterionId);
  expect(rule.kind==='range','수치 기준만 변경할 수 있습니다.'); decimal(lower);decimal(upper);
  expect(cmp(lower,upper)<=0,'하한이 상한보다 큽니다.');
  const lo=String(lower).trim(),hi=String(upper).trim();
  if(rule.lower===lo && rule.upper===hi) return s;
  const before={lower:rule.lower,upper:rule.upper,version:s.bundle.version};
  rule.lower=lo;rule.upper=hi;s.bundle.version=`rules-${hash(s.bundle.criteria)}`;
  const row=s.assessments[criterionId];
  if(row?.measurement?.valid) recordAssessment(s,{...row,history:undefined,verdict:rangeVerdict(row.measurement.value,rule),
    time:s.time,reason:'기존의 유효한 판독/확인값에 변경한 교육용 범위를 적용했습니다.',ruleVersion:s.bundle.version});
  event(s,'range_changed',{criterionId,before,after:{lower:lo,upper:hi,version:s.bundle.version},origin:'learner_rule_change'});
  s.commands.push({type:'range',criterionId,lower:lo,upper:hi}); return s;
}

/** An explicit educational decision-policy edit; it cannot modify the criterion meaning or model output. */
export function setWorkerPolicy(session,criterionId,policy) {
  expect(['recorded','demo'].includes(session.mode),'작업자 확인 정책 변경은 강의용 예시 또는 실제 응답 재생 실습에서 지원합니다.');
  expect(['visual_only','worker_attestation'].includes(policy),'지원하지 않는 작업자 확인 정책입니다.');
  const s=clone(session),rule=findRule(s,criterionId);
  expect(rule.kind==='visual','시각적 검사 항목의 정책만 변경할 수 있습니다.');
  const allow=policy==='worker_attestation';
  if(rule.allowWorker===allow) return s;
  const before={policy:rule.allowWorker?'worker_attestation':'visual_only',version:s.bundle.version};
  rule.allowWorker=allow;s.bundle.version=`rules-${hash(s.bundle.criteria)}`;
  for(const q of s.questions.filter(q=>q.criterionId===criterionId)) q.allowWorker=allow;
  const current=s.assessments[criterionId];
  if(current?.rawProposal) {
    const apply=s.mode==='demo'?applyDemoPolicy:applyVisualPolicy;
    const row=apply(current,rule);row.ruleVersion=s.bundle.version;recordAssessment(s,row);
    if(row.verdict==='unknown') openQuestion(s,rule,row);
    else if(row.verdict!=='not_due') for(const q of s.questions.filter(q=>q.criterionId===criterionId&&q.attempt===row.attempt&&!['resolved','superseded'].includes(q.state))) {
      q.state='resolved';q.resolvedAt=s.time;q.resolution=row.origin==='worker_confirmed'?'worker_confirmed':s.mode==='demo'?'authored_demo_policy_recheck':'recorded_model_policy_recheck';
    }
  }
  event(s,'worker_policy_changed',{criterionId,before,after:{policy,version:s.bundle.version},origin:'learner_rule_change'});
  s.commands.push({type:'worker_policy',criterionId,policy});return s;
}

export function summarize(session,scenario) {
  assertScenario(session,scenario);
  const counts={met:0,violated:0,unknown:0,not_due:0,unassessed:0};
  const seenTasks=new Set(session.events.filter(e=>e.type==='checkpoint').map(e=>e.taskId));
  const rows=session.bundle.criteria.map(c=>{
    const a=session.assessments[c.id];
    const verdict=a?.verdict ?? (seenTasks.has(c.taskId)||session.completed?'unassessed':'not_due');
    counts[verdict]++;
    return {...c,...(a??{}),criterionId:c.id,verdict};
  });
  const openQuestions=session.questions.filter(q=>!['resolved','superseded'].includes(q.state)).length;
  const pass=session.completed && counts.met===rows.length && openQuestions===0;
  return {...counts,counts,total:rows.length,pass,completed:session.completed,openQuestions,rows,
    status:pass?'교육용 기준 충족':counts.violated?'불일치 항목 있음':'검토 필요',mode:session.mode};
}

export function validateSession(session,scenario) {
  expect(session && session.schemaVersion===1 && ['fixture','recorded','demo'].includes(session.mode),'지원하지 않는 실행 기록입니다.');
  expect(session.mode===(scenario.mode==='recorded'?'recorded':scenario.mode==='demo'?'demo':'fixture'),'저장된 실행과 현재 관찰 모드가 다릅니다.');
  expect(typeof session.id==='string' && session.id.length<200,'세션 ID가 잘못되었습니다.');
  assertScenario(session,scenario);
  expect(Array.isArray(session.commands) && session.commands.length<=5000,'실행 원장이 없거나 너무 큽니다.');
  expect(session.initialBundle?.source==='parsed_pdf_csv','원본 문서 구축 기록이 필요합니다.');
  const rebuiltBundle=compileCompany(session.initialBundle.sourceText,session.initialBundle.sourceCsv,scenario);
  expect(JSON.stringify(rebuiltBundle)===JSON.stringify(session.initialBundle),'원본 문서와 구축 결과가 일치하지 않습니다.');
  let rebuilt=initial(scenario,rebuiltBundle,session.id);
  for(const cmd of session.commands) {
    if(cmd.type==='advance') rebuilt=advance(rebuilt,scenario,cmd.index);
    else if(cmd.type==='deliver') rebuilt=markDelivered(rebuilt,cmd.qid,cmd.channel);
    else if(cmd.type==='answer') rebuilt=answerQuestion(rebuilt,cmd.qid,cmd.answer);
    else if(cmd.type==='range') rebuilt=setRange(rebuilt,cmd.criterionId,cmd.lower,cmd.upper);
    else if(cmd.type==='worker_policy') rebuilt=setWorkerPolicy(rebuilt,cmd.criterionId,cmd.policy);
    else if(cmd.type==='reopen') rebuilt=reopenQuestion(rebuilt,cmd.criterionId);
    else fail('지원하지 않는 기록 명령입니다.');
  }
  expect(JSON.stringify(rebuilt)===JSON.stringify(session),'실행 원장과 현재 상태가 다릅니다. 변조·버전 불일치 또는 손상된 기록입니다.');
  return true;
}

function makeDemoReport(session,scenario,options) {
  const summary=summarize(session,scenario),inspection=Boolean(options.inspection);
  const labels={met:'충족',violated:'불일치',unknown:'확인 필요',not_due:'예정',unassessed:'확인 전'};
  const origins={authored_demo:'예시 관찰',worker_confirmed:'작업자 확인'};
  const policy=rule=>rule.allowWorker?'작업자 직접 확인도 인정':'시각 증거만 인정';
  const tone=summary.pass?'success':summary.violated?'failure':'pending';
  const title=inspection?'조립 검수조서':'조립 작업 보고서';
  const headline=summary.pass?'모든 검사 항목을 확인했습니다':summary.violated?'기준과 다른 항목이 있습니다':'추가 확인이 남아 있습니다';
  const disposition=summary.pass?'관찰 예시와 작업자 확인을 모아 이번 실습을 완료했습니다.':summary.violated?'아래 불일치 항목을 확인하세요. 다음 장면으로 넘어가도 작업자 답변은 유지됩니다.':'영상 장면을 모두 보았더라도 확인되지 않은 항목은 그대로 남습니다.';
  const chip=value=>`<span class="result ${escape(value)}">${escape(labels[value]??value)}</span>`;
  const pending=criterionId=>session.questions.some(q=>q.criterionId===criterionId&&!['resolved','superseded'].includes(q.state));
  const table=summary.rows.map(r=>`<tr><td><strong>${escape(r.label)}</strong><small>${escape(scenario.tasks.find(t=>t.id===r.taskId)?.label??r.taskId)}</small></td><td>${chip(r.verdict)}${pending(r.criterionId)&&r.workerConfirmation?'<small>답변 재확인 대기</small>':''}</td><td>${escape(origins[r.origin]??'아직 관찰하지 않음')}<small>${escape(policy(r))}</small></td><td>${escape(r.reason??'해당 장면에서 확인할 예정입니다.')}<small>${r.rawExampleVerdict?`최초 예시 판정: ${escape(labels[r.rawExampleVerdict])}`:''}${r.workerConfirmation?` · 작업자 확인: ${escape(labels[r.workerConfirmation.confirmation]??'확인 필요')}`:''}</small></td></tr>`).join('');
  const confirmations=summary.rows.filter(r=>session.questions.some(q=>q.criterionId===r.criterionId)).map(r=>{
    const questions=session.questions.filter(q=>q.criterionId===r.criterionId),latest=questions.at(-1),answer=r.workerConfirmation;
    const currentAnswers=latest.answers??[],waiting=pending(r.criterionId);
    return `<article class="confirmation"><div class="section-line"><h3>${escape(r.label)}</h3>${chip(r.verdict)}</div><p class="question">${escape(r.proposedQuestion??latest.text)}</p><div class="answer"><span>${waiting&&!currentAnswers.length&&answer?'이전 작업자 답변 · 재확인 요청 중':'작업자 답변'}</span><blockquote>${answer?escape(answer.text):'아직 작업자 답변이 없습니다.'}</blockquote></div><p class="policy"><strong>현재 확인 기준</strong> ${escape(policy(r))}${!r.allowWorker&&answer?'<br>답변은 기록했으며, 시각 증거만 인정하는 현재 기준에 따라 확인 필요가 유지됩니다.':''}${waiting?'<br>진행 중인 확인 요청이 남아 있습니다.':''}</p></article>`;
  }).join('');
  const photographs=scenario.checkpoints.slice(0,session.position+1).filter(cp=>safeImage(cp.image)).map(cp=>`<figure><img src="${escape(cp.image)}" alt="${escape(cp.label??scenario.tasks.find(t=>t.id===cp.taskId)?.label??'실습 장면')}"><figcaption><strong>${escape(cp.label??scenario.tasks.find(t=>t.id===cp.taskId)?.label??cp.id)}</strong><span>원본 ${escape(cp.sourceTime??cp.time)}초 · 강의용 예시 장면</span></figcaption></figure>`).join('');
  const eventNames={checkpoint:'장면 확인',invalidated:'재작업 후 재검사',question_delivered:'질문 전달',question_reopened:'작업자 답변 재확인',answer:'작업자 답변',worker_policy_changed:'증거 인정 기준 변경'};
  const journal=session.events.map(e=>`<li><strong>${escape(eventNames[e.type]??e.type)}</strong><span>실습 ${escape(e.time)}초 · ${escape(e.checkpointId??e.criterionId??e.questionId??'')}</span>${e.type==='answer'?`<p>${escape(e.answer.text)}</p>`:''}${e.type==='worker_policy_changed'?`<p>${escape(e.before.policy)} → ${escape(e.after.policy)}</p>`:''}</li>`).join('');
  const historicalAnswers=session.questions.flatMap(q=>q.answers.map(a=>({questionId:q.id,question:q.text,criterionId:q.criterionId,...a})));
  const metadata={sessionId:session.id,scenarioId:session.scenarioId,scenarioFingerprint:session.scenarioFingerprint,
    initialRuleVersion:session.initialBundle.version,currentRuleVersion:session.bundle.version,revision:session.revision};
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escape(title)} · ${escape(scenario.productName??scenario.title)}</title><style>
  *{box-sizing:border-box}body{margin:0;background:#edf2f7;color:#20334c;font:15px/1.65 system-ui,sans-serif}main{max-width:1120px;margin:32px auto;background:white;padding:48px 52px;border-radius:16px;box-shadow:0 8px 35px #21344c0a}.toolbar{max-width:1120px;margin:24px auto 0;text-align:right}button{background:#214cb8;color:white;border:0;border-radius:9px;padding:11px 18px;font:inherit;cursor:pointer}h1{font-size:34px;letter-spacing:-1.1px;line-height:1.3;margin:14px 0 8px}h2{font-size:21px;letter-spacing:-.5px;margin:0 0 18px}h3{font-size:16px;margin:0}p{margin:8px 0}header{border-bottom:1px solid #e0e6ef;padding-bottom:24px}.top-line,.section-line{display:flex;align-items:center;justify-content:space-between;gap:16px}.brand{font-weight:800;letter-spacing:1.4px;color:#315eab;font-size:13px}.demo-tag{border:1px solid #d9e4f5;background:#f2f6fd;color:#5272a2;padding:4px 10px;border-radius:99px;font-size:12px}.subtitle{color:#65758c}.identity{display:grid;grid-template-columns:2fr 2fr 1fr;gap:18px;margin-top:24px}.identity small{display:block;color:#76839a;font-size:12px;margin-bottom:4px}.identity strong{font-size:16px}.outcome{padding:24px 26px;border-radius:12px;background:#f5f8fc;margin:28px 0 18px;border-left:4px solid #6384bd}.outcome.success{background:#eff8f3;border-color:#3b9166}.outcome.failure{background:#fff2ef;border-color:#cf6854}.outcome h2{margin:0 0 6px;font-size:23px}.outcome p{margin:0;color:#5d6c80}.counts{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:34px}.count{padding:16px 18px;border:1px solid #e0e7ef;border-radius:10px}.count small{display:block;color:#738198}.count strong{font-size:25px;letter-spacing:-.5px}.count em{font-size:15px;font-style:normal;color:#8490a3}.report-section{margin-top:32px}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;table-layout:fixed}th{background:#f4f7fb;color:#6b7b92;font-size:12px;padding:12px 14px;text-align:left;font-weight:600}td{padding:16px 14px;border-bottom:1px solid #e3e9f1;vertical-align:top;font-size:13px;overflow-wrap:anywhere}td strong{font-size:14px}td small{display:block;color:#738198;font-size:11px;line-height:1.6;margin-top:6px}th:first-child{width:27%}th:nth-child(2){width:12%}th:nth-child(3){width:20%}.result{display:inline-block;border-radius:6px;padding:4px 8px;white-space:nowrap;font-size:12px;font-weight:700;background:#eef2f7;color:#6b7c93}.result.met{background:#e6f4eb;color:#29724c}.result.violated{background:#fdebe6;color:#a64b35}.result.unknown{background:#fff1d5;color:#8d6b29}.confirmation{border:1px solid #dee6f1;border-radius:12px;padding:22px 24px;margin-top:12px}.question{margin:14px 0;color:#50627a}.answer{border-radius:9px;background:#f5f8fd;padding:15px 18px}.answer span{font-size:11px;color:#77869c;font-weight:700}blockquote{margin:6px 0 0;font-size:16px;line-height:1.65}.policy{color:#6a7a91;font-size:12px;margin-top:14px}.policy strong{color:#475a76;margin-right:8px}.photo-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}figure{margin:0;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;background:#f8fafc}img{display:block;width:100%;height:190px;object-fit:contain;background:#edf1f6}figcaption{padding:12px 14px}figcaption strong{display:block;font-size:13px}figcaption span{display:block;font-size:11px;color:#738198;margin-top:4px}.explain{color:#748198;font-size:12px;margin:-10px 0 18px}details{border-top:1px solid #e0e7ef;padding:17px 0;margin-top:14px;font-size:13px}summary{cursor:pointer;color:#526783;font-weight:600}details pre{background:#f5f7fb;border-radius:8px;padding:16px;white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.6 ui-monospace,monospace}details li{margin:12px 0}details li span{display:block;font-size:12px;color:#77879a}.notes{margin-top:30px;color:#718097;font-size:12px}.signature{padding-top:24px;margin-top:28px;border-top:1px solid #e0e7ef;display:flex;gap:44px;color:#6f7e93;font-size:13px}.source-list{padding-left:18px;overflow-wrap:anywhere}.source-list li{margin:6px 0}
  @media(max-width:700px){main{margin:0;padding:28px 20px;border-radius:0}.toolbar{margin:12px 20px}.identity{grid-template-columns:1fr 1fr}.counts{grid-template-columns:1fr 1fr}.photo-grid{grid-template-columns:1fr 1fr}table{min-width:660px}.confirmation{padding:18px}.top-line{align-items:flex-start}h1{font-size:28px}img{height:155px}}
  @media print{body{background:white}main{max-width:none;box-shadow:none;margin:0;padding:0;border-radius:0}.toolbar{display:none}header{padding-bottom:18px}.report-section{margin-top:24px}.photo-grid{grid-template-columns:repeat(3,1fr)}tr,figure,.confirmation,.outcome{break-inside:avoid}thead{display:table-header-group}img{height:155px}details:not([open]){display:none}.signature{margin-bottom:20px}}
  </style></head><body><div class="toolbar"><button onclick="window.print()">인쇄 / PDF 저장</button></div><main><header><div class="top-line"><span class="brand">DYNIN · WORK RECORD</span><span class="demo-tag">강의용 예시</span></div><h1>${escape(title)}</h1><p class="subtitle">${escape(scenario.productName??scenario.title)} · 작업 장면과 확인 내용을 한눈에</p><div class="identity"><div><small>회사</small><strong>${escape(scenario.companyName??session.bundle.companyId)}</strong></div><div><small>공정</small><strong>${escape(scenario.title)}</strong></div>${scenario.orderId?`<div><small>작업 지시</small><strong>${escape(scenario.orderId)}</strong></div>`:''}</div></header>
  <section class="outcome ${tone}"><h2>${escape(headline)}</h2><p>${escape(disposition)}</p></section><div class="counts"><div class="count"><small>충족한 검사</small><strong>${summary.met} <em>/ ${summary.total}</em></strong></div><div class="count"><small>불일치</small><strong>${summary.violated}</strong></div><div class="count"><small>확인 필요 · 확인 전</small><strong>${summary.unknown+summary.unassessed+summary.not_due}</strong></div><div class="count"><small>남은 확인 요청</small><strong>${summary.openQuestions}</strong></div></div>
  <section class="report-section"><h2>검사 결과</h2><div class="table-wrap"><table><thead><tr><th>검사 항목</th><th>결과</th><th>판정 출처</th><th>확인 내용</th></tr></thead><tbody>${table}</tbody></table></div></section>
  <section class="report-section"><h2>작업자와 확인한 내용</h2>${confirmations||'<p class="explain">아직 작업자 확인 요청이 없습니다.</p>'}</section>
  <section class="report-section"><h2>작업 사진</h2><p class="explain">실습에서 확인한 원본 영상 장면입니다. 판정의 출처는 예시 관찰과 작업자 확인으로 구분합니다.</p><div class="photo-grid">${photographs||'<p>아직 기록한 장면이 없습니다.</p>'}</div></section>
  <div class="notes"><strong>강의용 예시 안내</strong><p>영상 장면에 맞춰 작성한 관찰을 사용하며 실제 모델 추론 결과가 아닙니다. 답변과 확인 정책을 바꾸면 판정과 보고서가 바뀝니다. 이 결과는 실제 제품의 품질 승인이 아닙니다.</p></div>
  <details class="history-details"><summary>이전 답변과 기준 변경 이력 보기</summary><ol>${journal}</ol><h3>기록된 모든 작업자 답변</h3><pre>${escape(JSON.stringify(historicalAnswers,null,2))}</pre></details>
  <details class="source-details"><summary>영상 출처와 예시 구성 보기</summary><p>${escape(scenario.sourceNote??'')}</p><ul class="source-list">${(scenario.sources??[]).map(x=>`<li>${escape(x.label)} · ${escape(x.license)}<br>${escape(x.url)}</li>`).join('')}</ul></details>
  <details class="technical-details"><summary>강사용 · 원본 예시와 전체 실행 원장</summary><h3>기록 식별 정보</h3><pre>${escape(JSON.stringify(metadata,null,2))}</pre><h3>실행 원장 · 관찰·답변·이전 판정 포함</h3><pre>${escape(JSON.stringify(session,null,2))}</pre></details><div class="signature"><span>확인자 __________________</span><span>확인일 __________________</span></div></main></body></html>`;
}

function makeMeasurementDemoReport(session,scenario,options={}) {
  const summary=summarize(session,scenario),spec=session.bundle.inspection;
  const inspection=Boolean(options.inspection),title=inspection?'치수 검수조서':'계측 검사 보고서';
  const labels={met:'충족',violated:'불일치',unknown:'확인 필요',not_due:'예정',unassessed:'미기록'};
  const result=value=>`<span class="result ${escape(value)}">${escape(labels[value]??value)}</span>`;
  const feature=id=>spec.features.find(f=>f.criterionId===id);
  const changed=r=>cmp(r.lower,feature(r.criterionId).lower)!==0||cmp(r.upper,feature(r.criterionId).upper)!==0;
  const featureLabel=f=>f.label.startsWith(f.code+' · ')?f.label.slice((f.code+' · ').length):f.label;
  const pending=criterionId=>session.questions.some(q=>q.criterionId===criterionId&&!['resolved','superseded'].includes(q.state));
  const table=summary.rows.map(r=>{
    const f=feature(r.criterionId),m=r.measurement;
    return `<tr><td><span class="feature-code">${escape(f.code)}</span><strong>${escape(featureLabel(f))}</strong><small>${escape(f.instrument)}</small></td><td><strong>${escape(f.lower)}–${escape(f.upper)} ${escape(f.unit)}</strong><small>도면 기준 · ${escape(f.nominal)} ${escape(f.unit)} 기준 치수</small>${changed(r)?`<strong class="edited">${escape(r.lower)}–${escape(r.upper)} ${escape(r.unit)}</strong><small>실습 적용 기준 · 변경됨</small>`:''}</td><td><strong class="reading">${m?.valid?`${escape(m.value)} <small>${escape(m.unit)}</small>`:'—'}</strong><small>${m?`처음 읽은 표시: ${escape(m.raw)}`:'측정 전'}</small>${pending(r.criterionId)&&r.workerConfirmation?'<small>이전 확인값 · 재확인 대기</small>':''}</td><td>${result(r.verdict)}</td><td>${r.origin==='worker_confirmed'?'작업자 확인값':r.origin==='authored_demo'?'강의용 판독 예시':'아직 기록 없음'}<small>${escape(r.reason??'해당 위치를 측정하면 기록됩니다.')}</small></td></tr>`;
  }).join('');
  const questions=session.questions.map(q=>{
    const f=feature(q.criterionId),answer=q.answers.at(-1),isOpen=!['resolved','superseded'].includes(q.state);
    return `<article class="question-card"><div class="line"><h3>${escape(f.code)} · ${escape(featureLabel(f))}</h3><span class="subtle">${isOpen?'답변 대기':'답변 기록 완료'}</span></div><p>${escape(session.assessments[q.criterionId]?.proposedQuestion??q.text)}</p><blockquote>${answer?escape(answer.text||`${answer.value} ${answer.unit}`):'아직 확인한 값을 입력하지 않았습니다.'}</blockquote>${answer?`<p><strong>기록한 확인값: ${escape(answer.value)} ${escape(answer.unit)}</strong></p>`:''}<small>도면 ${escape(spec.drawingId)} · 개정 ${escape(spec.drawingRevision)} · 시료 ${escape(q.target)} · ${escape(f.instrument)}</small></article>`;
  }).join('');
  const scenes=scenario.checkpoints.slice(0,session.position+1).filter(c=>safeImage(c.image)).map((cp,i)=>`<figure><img src="${escape(cp.image)}" alt="${escape(cp.label)}"><figcaption><strong>${escape(cp.label)}</strong><span>측정 예시 ${i+1} · 직접 작성한 계측 장면</span></figcaption></figure>`).join('');
  const details={product:spec,initialRuleVersion:session.initialBundle.version,currentRuleVersion:session.bundle.version,sessionId:session.id,scenarioFingerprint:session.scenarioFingerprint};
  const headline=summary.pass?'세 곳의 치수 확인을 마쳤습니다':summary.violated?'허용 범위를 벗어난 치수가 있습니다':'확인이 필요한 치수가 남아 있습니다';
  const tone=summary.pass?'success':summary.violated?'failure':'pending';
  const modified=summary.rows.some(changed);
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escape(title)} · ${escape(spec.productName)}</title><style>
  *{box-sizing:border-box}body{margin:0;background:#edf2f7;color:#20334c;font:15px/1.65 system-ui,sans-serif}main{max-width:1120px;margin:32px auto;background:#fff;padding:44px 48px;border-radius:16px}h1{font-size:34px;line-height:1.3;letter-spacing:-1px;margin:14px 0 8px}h2{font-size:21px;margin:0 0 18px}h3{font-size:16px;margin:0}p{margin:8px 0}.toolbar{max-width:1120px;margin:24px auto 0;text-align:right}button{border:0;border-radius:8px;background:#215db5;color:white;padding:11px 18px;font:inherit;cursor:pointer}.line{display:flex;justify-content:space-between;align-items:center;gap:16px}.brand{font-size:13px;letter-spacing:1.4px;font-weight:800;color:#287f8a}.demo-tag{font-size:12px;border:1px solid #cae4e9;background:#f1f9fa;border-radius:99px;padding:4px 12px;color:#377b85}header{padding-bottom:24px;border-bottom:1px solid #e2e8f0}.subtitle,.subtle,small{color:#728198}small{display:block;font-size:12px;font-weight:400;margin-top:6px}.identity{display:grid;grid-template-columns:2fr 2fr 1fr;gap:20px;margin-top:24px}.identity strong{display:block}.status{padding:24px;margin:26px 0 18px;border-radius:12px;border-left:4px solid #c48b21;background:#fff9ed}.status h2{margin:0}.status.success{border-color:#309365;background:#eff9f3}.status.failure{border-color:#c94f54;background:#fff1f2}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.metrics div{border:1px solid #e0e7f0;border-radius:10px;padding:16px}.metrics strong{font-size:25px;display:block}.report-section{margin-top:34px}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:700px;table-layout:fixed}th,td{padding:14px 12px;text-align:left;vertical-align:top;border-bottom:1px solid #e1e7ef;overflow-wrap:anywhere}th{background:#f4f7fb;font-size:12px;color:#71829a}th:nth-child(1){width:21%}th:nth-child(2){width:23%}th:nth-child(3){width:19%}th:nth-child(4){width:12%}th:nth-child(5){width:25%}td{font-size:13px}.result{display:inline-block;font-size:12px;white-space:nowrap;padding:3px 8px;border-radius:6px;background:#eef1f6;color:#718198}.result.met{background:#e7f5ee;color:#27815a}.result.violated{background:#fdebed;color:#bd4750}.result.unknown{background:#fff0d7;color:#a67216}.feature-code{display:inline-block;margin-right:8px;background:#e4f3f5;color:#277986;border-radius:5px;padding:2px 7px;font-weight:700}.reading{font-size:21px;line-height:1.3}.reading small{display:inline}.edited{display:block;margin-top:10px;color:#ad6c10}.drawing{width:100%;display:block;border:1px solid #e0e7f0;border-radius:12px}.question-card{border:1px solid #dce5f0;padding:22px;border-radius:12px;margin-top:14px}.question-card blockquote{margin:16px 0 8px;border-left:3px solid #6ea5af;padding:14px 18px;background:#f3f8fa}.photo-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}figure{margin:0;border:1px solid #dde6f0;border-radius:10px;overflow:hidden;background:#f8fafc}figure img{display:block;width:100%;height:210px;object-fit:contain;background:#f4f7fb}figcaption{padding:14px;font-size:13px}figcaption span{display:block;color:#7a89a0;font-size:11px;margin-top:7px}.notes{margin-top:28px;color:#728198;font-size:12px}details{border-top:1px solid #dde5ef;padding:16px 0;margin-top:14px;font-size:13px}summary{cursor:pointer;font-weight:600;color:#58708f}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#f8fafc;padding:15px}.signature{display:flex;gap:50px;border-top:1px solid #dce5ef;margin-top:24px;padding-top:24px;font-size:13px;color:#74829a}@media(max-width:720px){main{margin:0;padding:24px 18px;border-radius:0}.identity{grid-template-columns:1fr 1fr}.metrics{grid-template-columns:1fr 1fr}.photo-grid{grid-template-columns:1fr}.toolbar{padding:12px;margin:0}h1{font-size:28px}}@media print{body{background:#fff}main{margin:0;max-width:none;padding:0;border-radius:0}.toolbar{display:none}.photo-grid{grid-template-columns:repeat(3,1fr)}tr,figure,.question-card,.status{break-inside:avoid}.table-wrap{overflow:visible}table{min-width:0}details:not([open]){display:none}}
  </style></head><body><div class="toolbar"><button onclick="window.print()">인쇄 / PDF 저장</button></div><main><header><div class="line"><span class="brand">DYNIN · DIMENSION INSPECTION</span><span class="demo-tag">강의용 예시</span></div><h1>${escape(title)}</h1><p class="subtitle">${escape(spec.productName)} · 도면 위치별 측정값과 확인 기록</p><div class="identity"><div><small>회사 / 제품</small><strong>${escape(scenario.companyName??session.bundle.companyId)}</strong><span>${escape(spec.productId)}</span></div><div><small>검사 도면</small><strong>${escape(spec.drawingId)}</strong><span>개정 ${escape(spec.drawingRevision)}</span></div><div><small>검사 시료</small><strong>${escape(spec.specimenId)}</strong></div></div></header><div class="status ${tone}"><h2>${headline}</h2><p>${summary.pass?'판독 예시와 작업자 확인값을 모아 검수조서를 완성했습니다.':'불확실한 값은 확인 후 기록하고, 범위를 벗어난 값은 그대로 남깁니다.'}</p></div><div class="metrics"><div><small>충족한 치수</small><strong>${summary.met} / ${summary.total}</strong></div><div><small>불일치</small><strong>${summary.violated}</strong></div><div><small>확인 필요 · 미기록</small><strong>${summary.unknown+summary.unassessed+summary.not_due}</strong></div><div><small>남은 확인 요청</small><strong>${summary.openQuestions}</strong></div></div>
  <section class="report-section"><h2>치수 검사 결과</h2>${modified?'<p class="subtle">수강생이 검사 범위를 변경했습니다. 도면 기준은 그대로 보존하고 실습 적용 기준을 별도로 표시합니다.</p>':''}<div class="table-wrap"><table><thead><tr><th>측정 위치</th><th>허용 범위</th><th>기록한 값</th><th>판정</th><th>근거</th></tr></thead><tbody>${table}</tbody></table></div></section>
  <section class="report-section"><h2>검사 도면</h2><p class="subtle">${escape(spec.drawingId)} · 개정 ${escape(spec.drawingRevision)} · A/B/C는 이번 실습의 검사 위치입니다.</p><img class="drawing" src="${escape(spec.drawing)}" alt="${escape(spec.productName)}의 A B C 검사 위치 도면"></section>
  <section class="report-section"><h2>작업자에게 확인한 값</h2>${questions||'<p class="subtle">아직 확인 질문이 없습니다.</p>'}</section><section class="report-section"><h2>측정 장면 기록</h2><div class="photo-grid">${scenes||'<p>아직 측정 장면을 기록하지 않았습니다.</p>'}</div></section><div class="notes"><strong>강의용 예시</strong><p>제품·도면·계측 장면과 판독 후보는 수업을 위해 작성했습니다. 실제 OCR 결과나 측정 인증이 아닙니다. 작업자 답변과 변경한 검사 범위는 실제로 기록·계산됩니다.</p></div><details><summary>이전 답변과 기준 변경 이력 보기</summary><pre>${escape(JSON.stringify({questions:session.questions,changes:session.events.filter(e=>['range_changed','answer','question_reopened'].includes(e.type))},null,2))}</pre></details><details class="technical-details"><summary>강사용 · 연결 정보와 전체 기록</summary><pre>${escape(JSON.stringify(details,null,2))}</pre><pre>${escape(JSON.stringify(session,null,2))}</pre></details><div class="signature"><span>확인자 __________________</span><span>확인일 __________________</span></div></main></body></html>`;
}

export function makeReport(session,scenario,options={}) {
  if(session.mode==='demo'&&scenario.demoKind==='measurement') return makeMeasurementDemoReport(session,scenario,options);
  if(session.mode==='demo') return makeDemoReport(session,scenario,options);
  const s=summarize(session,scenario);
  const labels={met:'충족',violated:'불일치',unknown:'확인 필요',not_due:'미도래',unassessed:'미검사'};
  const origins={authored_fixture:'작성된 교육용 관찰',authored_demo:'강의용 예시 관찰',recorded_model:'저장된 실제 모델 관찰',worker_confirmed:'작업자 확인값',worker_input:'작업자 입력',learner_rule_change:'수강생 기준 변경'};
  const states={created:'질문 생성 · 아직 전달 안 됨',delivered:'전달 완료 · 답변 대기',answered:'답변 기록 · 추가 증거 필요',resolved:'확인 절차 처리 완료',superseded:'이전 시도 질문 · 현재 적용 안 됨'};
  const eventNames={checkpoint:'교육용 장면 관찰',invalidated:'현재 구성 변경 · 재검사 필요',question_delivered:'질문 전달',question_reopened:'작업자 답변 재확인',answer:'작업자 답변',range_changed:'교육용 허용 범위 변경',worker_policy_changed:'작업자 확인 허용 정책 변경'};
  const recorded=session.mode==='recorded',demo=session.mode==='demo';
  const notice=recorded?`<strong>저장된 실제 모델 응답 재생</strong><p>모델 ${escape(scenario.recording.model)} · 응답 묶음 ${escape(scenario.recording.id)}. 수업 중 모델·GPU 호출 없이 저장된 원본 응답을 사용합니다. 기준 변경과 작업자 답변은 제어기의 판정만 바꾸며 모델 관찰을 덮어쓰지 않습니다. 모델의 시각 제안과 작업자 진술은 실제 제품의 품질 승인이 아닙니다.</p>`:demo?'<strong>강의용 예시</strong><p>영상 장면에 맞춰 구성한 예시 관찰로 작업 흐름을 실습합니다. 실제 모델 추론 결과가 아닙니다. 작업자 답변과 확인 정책에 따라 판정과 보고서가 바뀌며, 최초 관찰과 답변 이력은 그대로 남습니다.</p>':'<strong>교육용 입력으로 실행한 제어 실습</strong><p>실제 영상·사진 위에 작성된 관찰 이벤트를 적용했습니다. 모델 추론이나 실제 제품의 품질 승인이 아닙니다. 원본 영상·교육용 판정·작업자 입력을 구분합니다.</p>';
  const isCases=scenario.timelineKind==='lesson_case_order_not_continuous_video';
  const timeline=t=>isCases?`교육용 진행 지점 ${escape(t)}`:`진행 시각 ${escape(t)}초`;
  const reading=r=>r.measurement?.valid?`${escape(r.measurement.value)} ${escape(r.measurement.unit)}`:'유효한 값 없음';
  const imageBlock=r=>{
    const frames=r.evidenceFrames?.length?r.evidenceFrames:[{path:r.image,id:r.evidenceId,time:r.sourceTime??r.time}];
    return frames.filter(f=>safeImage(f.path)).map(f=>`<figure><img src="${escape(f.path)}" alt="${r.evidenceKind==='context_only'?'검사 시점의 참고 장면':demo?'강의용 예시에 사용한 영상 장면':'관찰에서 인용한 원본 장면'}"><figcaption>${r.evidenceKind==='context_only'?'참고 장면 · 모델 인용 증거 없음':demo?'예시 장면':'인용 장면'} ${escape(f.id)} · 원본 시각 ${escape(f.time)}초</figcaption></figure>`).join('');
  };
  const raw=r=>escape(r.measurement?.raw??r.rawProposal?.raw??'—');
  const observation=r=>r.kind==='range'?`<strong>${reading(r)}</strong><br>초기 판독 문자열: ${raw(r)}<br>${r.measurement?.workerConfirmed?'작업자가 확인한 값':'교육용 판독 후보'}`:recorded&&r.rawProposal?`모델 관찰: ${escape(r.rawProposal.observation)}<br>적용 단계: ${escape(r.rawProposal.applicability)}<br>원래 제안: ${escape(labels[r.modelVerdict])}${r.workerConfirmation?`<br>작업자 확인: ${escape(labels[r.workerConfirmation.confirmation]??'보류')}`:''}${r.conflict?'<br><strong>모델·작업자 충돌 — 재검토</strong>':''}`:demo&&r.rawProposal?`최초 예시 판정: ${escape(labels[r.rawExampleVerdict])}${r.workerConfirmation?`<br>작업자 확인: ${escape(labels[r.workerConfirmation.confirmation]??'확인 필요')}<br>답변: ${escape(r.workerConfirmation.text)}`:''}${r.conflict?'<br><strong>관찰과 작업자 답변이 달라 재확인이 필요합니다.</strong>':''}`:'—';
  const rows=s.rows.map(r=>`<tr><td>${escape(r.label)}<br><small>${escape(r.criterionId)} · 시도 ${escape(r.attempt??'미관찰')}</small></td><td>${escape(r.target)}</td><td>${r.kind==='range'?`${escape(r.lower)}–${escape(r.upper)} ${escape(r.unit)}`:`시각적 확인${recorded||demo?`<br>${r.allowWorker?'작업자 확인 허용':'영상 증거만 적용'}`:''}`}</td><td>${observation(r)}</td><td>${labels[r.verdict]}</td><td>${escape(origins[r.origin]??'미관찰')}<br>${escape(r.reason??'')}${r.time!==undefined?`<br><small>${timeline(r.time)} · 원본 ${escape(r.sourceTime??r.time)}초</small>`:''}${imageBlock(r)}</td></tr>`).join('');
  const questions=session.questions.map(q=>`<li><strong>${escape(q.text)}</strong><p>대상 ${escape(q.target)} · 시도 ${escape(q.attempt)} · ${escape(states[q.state]??q.state)}<br>전달 채널: ${escape(q.deliveredChannels.map(c=>c==='audio'?'음성':'화면').join(', ')||'미전달')} · 생성 ${timeline(q.time)}${q.resolvedAt!==undefined?` · 처리 ${timeline(q.resolvedAt)}`:''}</p>${q.answers.map(a=>`<p>작업자 입력 (${timeline(a.time)}): ${escape(a.value??a.text)} ${escape(a.unit??'')}${a.confirmation?` · 명시적 확인: ${escape(labels[a.confirmation])}`:''}</p>`).join('')}</li>`).join('');
  const history=s.rows.filter(r=>r.history?.length).map(r=>`<h3>${escape(r.label)}</h3><table><thead><tr><th>이전 시도</th><th>판정과 값</th><th>초기 문자열</th><th>당시 근거</th></tr></thead><tbody>${r.history.map(h=>`<tr><td>시도 ${escape(h.attempt)}<br>${timeline(h.time)}</td><td>${labels[h.verdict]}<br>${h.measurement?reading(h):''}<br>${escape(origins[h.origin]??h.origin)}</td><td>${raw(h)}</td><td>${escape(h.reason)}${imageBlock(h)}</td></tr>`).join('')}</tbody></table>`).join('');
  const events=session.events.map(e=>`<li>${timeline(e.time)}${e.sourceTime!==undefined?` · 원본 ${escape(e.sourceTime)}초`:''} · ${escape(eventNames[e.type]??e.type)} · ${escape(e.checkpointId??e.questionId??e.criterionId??'')}${e.type==='range_changed'?`<br>이전 범위 ${escape(e.before.lower)}–${escape(e.before.upper)} → 새 범위 ${escape(e.after.lower)}–${escape(e.after.upper)}`:e.type==='worker_policy_changed'?`<br>이전 정책 ${escape(e.before.policy)} → 새 정책 ${escape(e.after.policy)}`:''}</li>`).join('');
  const originalResponses=recorded?'<h2>실제 모델 원본 응답과 식별 기록</h2>'+scenario.checkpoints.slice(0,session.position+1).map(cp=>`<details><summary>${escape(cp.id)} · 원본 ${escape(cp.sourceTime??cp.time)}초 · 관찰 작업 ${escape(cp.observedTaskId??'불명확')}</summary><p>요청 SHA256: ${escape(cp.recording.receipt.requestSha256)}<br>응답 SHA256: ${escape(cp.recording.receipt.responseSha256)}<br>응답 ID: ${escape(cp.recording.receipt.id)} · 입력 이미지 ${cp.recording.inputImages.length}장</p><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${escape(cp.recording.responseContent??JSON.stringify(cp.recording.failure))}</pre></details>`).join(''):'';
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escape(scenario.title)} 교육용 보고서</title><style>body{font:16px/1.6 system-ui,sans-serif;color:#172a41;max-width:1100px;margin:40px auto;padding:0 24px}h1,h2,h3{line-height:1.3}table{border-collapse:collapse;width:100%}th,td{border:1px solid #cbd5e1;padding:10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#eef3fa}figure{margin:12px 0}img{max-width:260px;max-height:160px}aside{border:1px solid #c4d2e5;padding:16px;background:#f6f8fc}small,figcaption{font-size:13px;color:#52647a}@media print{body{margin:0;padding:0}tr,figure{break-inside:avoid}button{display:none}thead{display:table-header-group}}</style></head><body><button onclick="window.print()">인쇄 / PDF 저장</button><h1>${escape(scenario.title)}</h1><p>교육용 검수조서 및 작업 보고서</p><aside>${notice}${isCases?'<p>서로 다른 계측 사례를 수업 순서로 제시했습니다. 교육용 진행 지점은 연속 촬영 시각이 아니며 각 증거의 원본 시각을 따로 표시합니다.</p>':''}</aside><p>세션 ${escape(session.id)}<br>회사 ${escape(session.bundle.companyId)} · 공정 ${escape(session.bundle.processId)}<br>초기 기준 ${escape(session.initialBundle.version)} · 현재 기준 ${escape(session.bundle.version)}<br>기록 revision ${session.revision} · 시나리오 변경 확인값 ${escape(session.scenarioFingerprint)}</p><h2>${escape(s.status)}</h2><p>충족 ${s.met} / 불일치 ${s.violated} / 확인 필요 ${s.unknown} / 미검사 ${s.unassessed} / 미도래 ${s.not_due}</p><table><thead><tr><th>검사 항목</th><th>대상</th><th>현재 교육 기준</th><th>원시 판독과 확인값</th><th>판정</th><th>출처와 증거</th></tr></thead><tbody>${rows}</tbody></table><h2>질문과 확인</h2><ul>${questions||'<li>질문 없음</li>'}</ul><h2>이전 판정과 원시 기록</h2><p>현재 판정이 바뀌어도 이전 기록은 삭제하지 않습니다. 재작업 후 이전 사진은 당시의 이력이며 현재 상태의 합격 근거로 재사용하지 않습니다.</p>${history||'<p>이전 판정 없음</p>'}<h2>수행 기록</h2><ol>${events}</ol>${originalResponses}<h2>자료 출처</h2><p>${escape(scenario.sourceNote??'')}</p><ul>${(scenario.sources??[]).map(x=>`<li>${escape(x.label)} · ${escape(x.license)} · ${escape(x.url)}</li>`).join('')}</ul><p>확인자: ____________________ &nbsp; 확인일: ____________________</p><small>자동 서명·교정·승인을 생성하지 않았습니다. 작업자 입력과 교육용 관찰의 출처를 유지합니다.</small></body></html>`;
}
