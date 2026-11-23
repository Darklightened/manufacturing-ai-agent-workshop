import {appendDocument,emptyLibrary,EXAMPLES,LIMITS,prepareDocument,removeDocument,safeLocalUrl,validateLibrary} from './store.mjs';
const scopes={all:'전체 실습',lab1:'실습 1 · 전자 조립',lab2:'실습 2 · 계측',lab3:'실습 3 · 기계 조립',other:'기타 기록'};
const formats={html:'HTML',docx:'Word',csv:'CSV',json:'JSON',sqlite:'SQLite',pdf:'PDF'};
const sizeText=n=>n<1024?`${n} B`:n<1024*1024?`${(n/1024).toFixed(1)} KB`:`${(n/1024/1024).toFixed(1)} MB`;
function node(tag,className,text){const e=document.createElement(tag);if(className)e.className=className;if(text!==undefined)e.textContent=text;return e;}
function button(text,action,kind='secondary'){const b=node('button',kind,text);b.type='button';b.addEventListener('click',action);return b;}
const PREVIEW_CSP="default-src 'none'; script-src 'none'; connect-src 'none'; img-src data: blob:; style-src 'unsafe-inline'; font-src data:; media-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'";
/** Inject read()/write(state) bound exclusively to IndexedDB key documentLibrary. */
export class DocumentLibrary {
 constructor({main,read,write,toast=()=>{}}){this.main=main;this.read=read;this.write=write;this.toast=toast;this.active=false;this.generation=0;this.queue=Promise.resolve();this.urls=new Set();this.search='';this.scope='all';}
 _mutation(action){const next=this.queue.then(action);this.queue=next.catch(()=>{});return next;}
 async capture(doc){
  try{return await this._mutation(async()=>{const entry=prepareDocument(doc),state=validateLibrary(await this.read());await this.write(appendDocument(state,entry));return {ok:true,id:entry.id};});}
  catch(error){const message=`문서함에 보관하지 못했습니다. ${error.message||'브라우저 저장 공간을 확인해 주세요.'}`;this.toast(message);return {ok:false,error:message};}
 }
 leave(){this.active=false;this.generation++;for(const url of this.urls)URL.revokeObjectURL(url);this.urls.clear();this.dialog?.close();this.dialog?.remove();this.dialog=null;}
 async render(){
  this.leave();this.active=true;const generation=this.generation;let state=emptyLibrary(),failure='';
  try{state=validateLibrary(await this.read());}catch(error){failure=error.message||'브라우저 문서함을 읽을 수 없습니다.';}
  if(!this.active||generation!==this.generation)return;
  const root=node('div','document-library'),heading=node('header','dl-heading');heading.append(node('span','dl-eyebrow','DOCUMENTS · 내 문서함'),node('h1','', '실습 기록을 한곳에서 확인하세요'),node('p','','보고서·검수조서·검사 데이터가 파일로 저장될 때, 이 브라우저에도 사본을 보관합니다.'));
  root.append(heading);const privacy=node('div','dl-notice');privacy.append(node('strong','','이 브라우저에 저장된 문서'),node('p','','서버로 업로드하지 않습니다. 다른 기기에서는 별도로 내려받은 파일을 사용하세요. 브라우저 데이터를 지우면 문서함 기록도 없어집니다.'));root.append(privacy);
  if(failure){const warning=node('div','dl-error');warning.append(node('strong','','문서함 저장 공간을 사용할 수 없습니다'),node('p','',failure),node('p','','아래 완성 예제는 계속 열 수 있습니다. 기존 기록을 초기화하거나 덮어쓰지 않았습니다.'));root.append(warning);}
  const tools=node('div','dl-tools'),search=node('input','');search.type='search';search.placeholder='문서 제목 또는 파일 이름 검색';search.setAttribute('aria-label','문서 검색');search.value=this.search;
  const select=node('select','');select.setAttribute('aria-label','실습 구분');for(const [value,label] of Object.entries(scopes)){const option=node('option','',label);option.value=value;select.append(option);}select.value=this.scope;tools.append(search,select);root.append(tools);
  const own=node('section','dl-section');const ownhead=node('div','dl-section-heading');ownhead.append(node('h2','','내가 만든 문서'),node('span','dl-muted',`${state.entries.length}개 · ${sizeText(state.entries.reduce((n,e)=>n+e.size,0))} / 100 MB`));const cards=node('div','dl-grid');own.append(ownhead,cards,node('p','dl-muted','보고서 화면에서 HTML·Word·검사 CSV·실행 JSON·SQLite를 저장하면 자동으로 추가됩니다. 같은 이름으로 다시 저장해도 이전 파일을 남깁니다.'));root.append(own);
  const samples=node('section','dl-section'),samplecards=node('div','dl-grid');samples.append(node('h2','','완성 예제'),node('p','dl-muted','수업에서 제공하는 기본 예제입니다. 내가 만든 문서와 별도로 표시하며 문서함 용량에 포함하지 않습니다.'),samplecards);root.append(samples);
  const matches=e=>(this.scope==='all'||this.scope===e.scope)&&(!this.search||`${e.title} ${e.filename||''} ${e.summary}`.toLowerCase().includes(this.search.toLowerCase()));
  const draw=()=>{cards.replaceChildren();samplecards.replaceChildren();const list=state.entries.filter(matches);if(!list.length)cards.append(node('div','dl-empty',state.entries.length?'검색 조건에 맞는 문서가 없습니다.':'아직 저장한 문서가 없습니다. 실습을 마치고 보고서 파일을 저장해 보세요.'));for(const e of list)cards.append(this._card(e,false,generation));for(const e of EXAMPLES.filter(matches))samplecards.append(this._card(e,true,generation));};
  search.addEventListener('input',()=>{this.search=search.value;draw();});select.addEventListener('change',()=>{this.scope=select.value;draw();});draw();this.main.replaceChildren(root);
 }
 _card(entry,sample,generation){
  const card=node('article','dl-card');card.dataset.documentId=entry.id;card.dataset.sample=String(sample);
  const badges=node('div','dl-badges');badges.append(node('span','dl-kind',formats[entry.kind]),node('span','dl-muted',sample?'수업 제공 예제':scopes[entry.scope]));card.append(badges,node('h3','',entry.title||entry.filename));if(entry.summary)card.append(node('p','',entry.summary));
  if(!sample)card.append(node('p','dl-filename',entry.filename),node('p','dl-muted',`${new Date(entry.createdAt).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})} · ${sizeText(entry.size)}`));
  const actions=node('div','dl-actions');
  if(['html','csv','json'].includes(entry.kind))actions.append(button('미리보기',()=>this._preview(entry,sample,generation),'secondary dl-preview'));
  else if(sample&&entry.kind==='pdf'){const open=node('a','button secondary','PDF 열기');open.href=safeLocalUrl(entry.url);open.target='_blank';open.rel='noopener';actions.append(open);}
  if(sample){const a=node('a','button primary dl-download','다운로드');a.href=safeLocalUrl(entry.url);a.download=entry.url.split('/').at(-1);actions.append(a);}
  else {
   actions.append(button('다운로드',()=>this._download(entry),'primary dl-download'),button('삭제',()=>this._delete(entry),'quiet dl-delete'));
   if(['docx','sqlite'].includes(entry.kind))card.append(node('p','dl-muted',entry.kind==='docx'?'Word 파일은 다운로드 후 문서 프로그램에서 확인합니다.':'SQLite 파일은 다운로드 후 DB 도구에서 확인합니다.'));
  }
  card.append(actions);return card;
 }
 async _preview(entry,sample,generation){
  try{
   let content;if(sample){const response=await fetch(safeLocalUrl(entry.url));if(!response.ok)throw new Error('예제 파일을 불러오지 못했습니다.');content=await response.text();}else content=await entry.blob.text();
   if(!this.active||generation!==this.generation)return;
   this.dialog?.close();this.dialog?.remove();const dialog=node('dialog','dl-dialog');this.dialog=dialog;
   const header=node('div','dl-dialog-heading');header.append(node('strong','',entry.title||entry.filename),button('닫기',()=>dialog.close(),'quiet'));dialog.append(header,node('p','dl-muted',sample?'수업 제공 예제 미리보기':'보관한 파일의 미리보기 · 원본 파일은 다운로드로 확인'));
   if(entry.kind==='html'){const iframe=node('iframe','dl-frame');iframe.title='보고서 미리보기';iframe.setAttribute('sandbox','');iframe.referrerPolicy='no-referrer';iframe.srcdoc=`<!doctype html><meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}">`+content+'<style>button,.toolbar{display:none!important}</style>';dialog.append(iframe);}
   else {const pre=node('pre','dl-text',content.slice(0,200000));dialog.append(pre);if(content.length>200000)dialog.append(node('p','dl-muted','긴 문서의 앞부분만 표시했습니다. 전체 내용은 다운로드해 확인하세요.'));}
   dialog.addEventListener('close',()=>{dialog.remove();if(this.dialog===dialog)this.dialog=null;});this.main.append(dialog);dialog.showModal();
  }catch(error){this.toast(error.message||'미리보기를 열지 못했습니다.');}
 }
 _download(entry){const url=URL.createObjectURL(entry.blob);this.urls.add(url);const link=node('a');link.href=url;link.download=entry.filename;document.body.append(link);link.click();link.remove();setTimeout(()=>{URL.revokeObjectURL(url);this.urls.delete(url);},1000);}
 async _delete(entry){
  if(!window.confirm(`문서함에서 “${entry.filename}” 사본을 삭제할까요?\n컴퓨터에 내려받은 파일과 현재 실습 기록은 삭제되지 않습니다.`))return;
  try{await this._mutation(async()=>{const state=validateLibrary(await this.read());await this.write(removeDocument(state,entry.id));});this.toast('문서함의 사본을 삭제했습니다.');if(this.active)await this.render();}
  catch(error){this.toast(`문서를 삭제하지 못했습니다. ${error.message||''}`);}
 }
}
