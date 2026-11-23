/** Local generated-document records. Storage is injected; never touches the active session. */
export const LIBRARY_KEY='documentLibrary';
export const LIMITS=Object.freeze({fileBytes:25*1024*1024,totalBytes:100*1024*1024,entries:100});
export const KINDS=Object.freeze({html:'text/html',docx:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',csv:'text/csv',json:'application/json',sqlite:'application/vnd.sqlite3'});
const demand=(ok,message)=>{if(!ok)throw new Error(message);};
export function safeFilename(name){
 demand(typeof name==='string'&&name.length>0&&name.length<=180&&name===name.trim(),'파일 이름이 비었거나 너무 깁니다.');
 let decoded;try{decoded=decodeURIComponent(name);}catch{throw new Error('파일 이름의 인코딩이 잘못되었습니다.');}
 demand(!/[\\/<>:"|?*\u0000-\u001f\u007f]/.test(decoded)&&!decoded.startsWith('.')&&!decoded.includes('..'),'안전한 파일 이름이 필요합니다.');
 demand(Object.hasOwn(KINDS,name.split('.').at(-1).toLowerCase()),'보관할 수 없는 문서 형식입니다.');return name;
}
export function safeLocalUrl(value){
 demand(typeof value==='string'&&value.length<500,'예제 주소가 잘못되었습니다.');
 let decoded;try{decoded=decodeURIComponent(value);}catch{throw new Error('예제 주소 인코딩이 잘못되었습니다.');}
 demand(/^(assets|docs)\/[A-Za-z0-9_./-]+\.(?:html|docx|pdf|csv|json|sqlite)$/.test(decoded)&&!decoded.split('/').includes('..')&&!decoded.includes('//'),'같은 실습 사이트의 예제 주소만 사용할 수 있습니다.');return value;
}
export function scopeFor(scenarioId){
 demand(typeof scenarioId==='string'&&/^[A-Za-z0-9_-]{1,100}$/.test(scenarioId),'실습 식별자가 잘못되었습니다.');
 return /^(electronics|electronic)/.test(scenarioId)?'lab1':/^(measurement|instruments)/.test(scenarioId)?'lab2':/^(mechanical|maintenance)/.test(scenarioId)?'lab3':'other';
}
export function summaryText(value){
 if(value===undefined||value===null)return '';
 if(typeof value==='string')return value.trim().slice(0,500);
 try{return JSON.stringify(value).slice(0,500);}catch{return '요약 정보 없음';}
}
export function emptyLibrary(){return {schemaVersion:1,entries:[]};}
export function validateLibrary(state){
 if(state===undefined||state===null)return emptyLibrary();
 demand(state&&state.schemaVersion===1&&Array.isArray(state.entries),'문서함 기록 형식을 읽을 수 없습니다. 기존 저장 내용은 유지됩니다.');
 demand(state.entries.length<=LIMITS.entries,'문서함 개수 제한을 초과했습니다.');
 const ids=new Set();let total=0;
 for(const entry of state.entries){
  demand(entry&&typeof entry.id==='string'&&/^[A-Za-z0-9_-]{1,100}$/.test(entry.id)&&!ids.has(entry.id),'문서 식별자가 잘못되었거나 중복되었습니다.');ids.add(entry.id);
  safeFilename(entry.filename);demand(scopeFor(entry.scenarioId)===entry.scope,'문서의 실습 구분이 일치하지 않습니다.');
  demand(entry.kind===entry.filename.split('.').at(-1).toLowerCase(),'문서 형식이 파일 이름과 다릅니다.');
  demand(typeof entry.title==='string'&&entry.title.length<=160&&typeof entry.summary==='string'&&entry.summary.length<=500,'문서 제목이나 요약이 잘못되었습니다.');
  demand(typeof entry.createdAt==='string'&&Number.isFinite(Date.parse(entry.createdAt)),'문서 저장 시각이 잘못되었습니다.');
  demand(entry.blob instanceof Blob&&Number.isSafeInteger(entry.size)&&entry.size===entry.blob.size&&entry.size<=LIMITS.fileBytes,'문서 파일이 없거나 크기가 다릅니다.');
  total+=entry.size;
 }
 demand(total<=LIMITS.totalBytes,'문서함 용량 제한을 초과했습니다.');return state;
}
let serial=0;
const nextId=()=>globalThis.crypto?.randomUUID?.()??`document-${Date.now()}-${++serial}`;
export function prepareDocument(doc,{id=nextId(),now=new Date()}={}){
 demand(doc&&typeof doc==='object','보관할 문서가 없습니다.');
 const filename=safeFilename(doc.filename),kind=filename.split('.').at(-1).toLowerCase(),scope=scopeFor(doc.scenarioId);
 demand(typeof doc.content==='string'||doc.content instanceof Blob||doc.content instanceof ArrayBuffer||ArrayBuffer.isView(doc.content),'문서 내용 형식을 지원하지 않습니다.');
 // Keep the exact Blob/bytes that were downloaded, including its original MIME type.
 const blob=doc.content instanceof Blob?doc.content:new Blob([doc.content],{type:typeof doc.mime==='string'?doc.mime:KINDS[kind]});
 demand(blob.size<=LIMITS.fileBytes,'파일 하나는 25 MB까지 문서함에 보관할 수 있습니다. 다운로드 파일은 그대로 저장됩니다.');
 const entry={id,filename,kind,scenarioId:doc.scenarioId,scope,title:typeof doc.title==='string'?doc.title.trim().slice(0,160):filename,summary:summaryText(doc.summary),createdAt:now.toISOString(),size:blob.size,blob};
 validateLibrary({schemaVersion:1,entries:[entry]});return entry;
}
export function appendDocument(state,entry){
 state=validateLibrary(state);demand(!state.entries.some(e=>e.id===entry.id),'같은 문서 식별자를 덮어쓸 수 없습니다.');
 demand(state.entries.length<LIMITS.entries,'문서함은 100개까지 보관합니다. 필요 없는 문서를 삭제한 뒤 다시 저장하세요.');
 demand(state.entries.reduce((n,e)=>n+e.size,0)+entry.size<=LIMITS.totalBytes,'문서함이 100 MB 한도에 도달했습니다. 필요 없는 문서를 삭제한 뒤 다시 저장하세요.');
 return validateLibrary({schemaVersion:1,entries:[entry,...state.entries]});
}
export function removeDocument(state,id){state=validateLibrary(state);demand(state.entries.some(e=>e.id===id),'삭제할 문서를 찾지 못했습니다.');return {schemaVersion:1,entries:state.entries.filter(e=>e.id!==id)};}
export const EXAMPLES=Object.freeze([
 {id:'lab1-inspection-html',scope:'lab1',title:'전자 조립 · 검수조서',kind:'html',url:'assets/worker-flow/examples/inspection.html',summary:'작업 단계·확인 답변·증거 사진이 포함된 완성 예제'},
 {id:'lab1-inspection-docx',scope:'lab1',title:'전자 조립 · Word 검수조서',kind:'docx',url:'assets/worker-flow/examples/inspection.docx',summary:'표 중심의 편집 가능한 검수 서식'},
 {id:'lab1-inspection-pdf',scope:'lab1',title:'전자 조립 · PDF 검수조서',kind:'pdf',url:'assets/worker-flow/examples/inspection.pdf',summary:'완성 문서의 인쇄용 예제'},
 {id:'lab2-standard',scope:'lab2',title:'계측 · 표준형 검수조서',kind:'html',url:'docs/measurement_input_v2/examples/inspection-standard.html',summary:'A/B 직접 입력과 C 확인 답변 · 세 치수 충족'},
 {id:'lab2-precision',scope:'lab2',title:'계측 · 정밀형 검수조서',kind:'html',url:'docs/measurement_input_v2/examples/inspection-precision.html',summary:'같은 40.02 mm가 더 좁은 길이 기준을 벗어난 비교 예제'},
 {id:'lab2-report',scope:'lab2',title:'계측 · 검사 보고서',kind:'html',url:'docs/measurement_input_v2/examples/report-standard.html',summary:'검사자·로트·도면·입력값과 검사 기록'},
 {id:'lab3-inspection',scope:'lab3',title:'기계 조립 · 검수조서',kind:'html',url:'assets/mechanical-flow/examples/inspection-mechanical.html',summary:'조립 단계·가려진 연결 핀 확인·사진 기록'},
 {id:'lab3-report',scope:'lab3',title:'기계 조립 · 작업 보고서',kind:'html',url:'assets/mechanical-flow/examples/report-mechanical.html',summary:'기계 조립의 전체 수행 기록'}
]);
for(const e of EXAMPLES)safeLocalUrl(e.url);
