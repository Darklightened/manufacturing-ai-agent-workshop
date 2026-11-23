/** Present the caller's inspection outcomes; never create or advance outcomes here. */
const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const normalized = status => ['met','unknown','violated'].includes(status) ? status : 'pending';
export function inspectionChecklist(items,{title='검사 항목',activeId=null}={}){
 const rows=(items||[]).map(item=>({...item,status:normalized(item.status)}));
 const active=rows.find(item=>item.id===activeId&&item.status!=='met')||rows.find(item=>item.status!=='met');
 const passed=rows.filter(item=>item.status==='met').length,complete=rows.length>0&&passed===rows.length;
 const current=complete?'모든 항목 통과':active?.status==='unknown'?'확인 답변 대기':active?.status==='violated'?'불일치 항목 확인':active?`현재 확인 · ${rows.indexOf(active)+1} / ${rows.length}`:'검사 항목 대기';
 return `<section class="inspection-checklist" aria-label="${escape(title)}" data-complete="${complete}"><div class="inspection-checklist-header"><span>${escape(title)}</span><span class="inspection-check-count">${passed} / ${rows.length}</span></div><p class="inspection-current">${escape(current)}</p><ol class="inspection-check-items">${rows.map((item,index)=>{
  const isActive=item===active,state=item.status,caption=state==='met'?'통과':state==='unknown'?'확인 필요':state==='violated'?'불일치':isActive?'확인 중':'다음 항목',icon=state==='met'?'✓':state==='unknown'?'?':state==='violated'?'!':isActive?'›':String(index+1);
  return `<li class="inspection-check-item" data-inspection-item="${escape(item.id)}" data-state="${state}" data-active="${isActive}" ${isActive?'aria-current="step"':''}><span class="inspection-check-icon" aria-label="${caption}">${icon}</span><div class="inspection-check-copy"><strong class="inspection-check-label">${escape(item.label)}</strong><span class="inspection-check-status">${caption}${item.detail?' · '+escape(item.detail):''}</span></div></li>`;
 }).join('')}</ol></section>`;
}
