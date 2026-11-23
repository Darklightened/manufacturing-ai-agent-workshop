"""Finite integration test of the local document archive; imports existing valid sessions.

No new video observations, model calls, library-state injection or remote writes.
"""
import argparse,hashlib,json,time,traceback
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
a=argparse.ArgumentParser();a.add_argument('--url',default='http://127.0.0.1:8937/');a.add_argument('--output',type=Path,default=ROOT/'validation/labs23_v2/library_browser'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'));a.add_argument('--browser',default='/home/jovyan/.cache/ms-playwright/chromium-1187/chrome-linux/chrome');args=a.parse_args()
OUT=args.output;OUT.mkdir(parents=True,exist_ok=False)
origin=urlparse(args.url).netloc
measurement=ROOT/'docs/measurement_input_v2/examples/session-standard.json'
legacy_fixture=ROOT/'tests/fixtures/worker-v1-complete.json'
legacy_state=json.loads(legacy_fixture.read_text())
legacy=OUT/'legacy-v1-import.json'
legacy.write_text(json.dumps({'format':'dynin-seminar-worker-export-v1','scenarioId':'electronics_demo','workerFlow':{'state':legacy_state,'photo':legacy_state.get('worker',{}).get('photo')},'companyBuild':None},ensure_ascii=False,indent=2)+'\n')
checks=[];errors=[];http_errors=[];blocked=[];requests=[]
receipt={'status':'running','checks':checks,'mode':'authored_demo','modelCalls':0,'gpuCalls':0,'sources':{'measurement':str(measurement),'legacyWorker':str(legacy_fixture)}}
active=None

def save():
 receipt.update(pageErrors=errors,httpErrors=http_errors,blockedRequests=blocked,requestCount=len(requests))
 (OUT/'LIBRARY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
def passed(t):checks.append(t);save();print(t,flush=True)
def guard(route):
 r=route.request
 if urlparse(r.url).scheme in {'data','blob'}:route.continue_();return
 requests.append({'url':r.url,'method':r.method})
 if r.method!='GET' or urlparse(r.url).netloc!=origin:blocked.append(r.url);route.abort()
 else:route.continue_()
def download(p,selector,name):
 with p.expect_download(timeout=90000) as d:p.locator(selector).click()
 dest=OUT/name;d.value.save_as(str(dest));return dest

def stored(p,key='current'):
 return p.evaluate('''key=>new Promise((resolve,reject)=>{const r=indexedDB.open('dynin-seminar-classroom-v1',1);r.onerror=()=>reject(r.error);r.onsuccess=()=>{const db=r.result,t=db.transaction('state'),q=t.objectStore('state').get(key);q.onsuccess=()=>{const value=q.result;if(key==='documentLibrary'&&value)resolve({...value,entries:value.entries.map(({blob,...e})=>({...e,blobSize:blob.size,blobType:blob.type}))});else resolve(value);};q.onerror=()=>reject(q.error);t.oncomplete=()=>db.close();};})''',key)

def entries(p,count=None):
 end=time.monotonic()+30
 while time.monotonic()<end:
  data=stored(p,'documentLibrary');items=(data or {}).get('entries',[])
  if count is None or len(items)==count:return items
  p.wait_for_timeout(100)
 raise AssertionError(f'Library count expected {count}, got {len(items)}')

def owncards(p):return p.locator('.dl-card[data-sample="false"]')
def open_library(p):
 p.locator('[data-page="library"]').click();p.locator('.document-library').wait_for()
def find_entry(items,filename):return next(x for x in items if x['filename']==filename)
def card(p,entry):return p.locator('.dl-card[data-document-id="'+entry['id']+'"]')
def close_preview(p):p.locator('.dl-dialog-heading button').click();p.locator('.dl-dialog').wait_for(state='detached')
def unchanged(p,expected,key='session'):assert stored(p)[key]==expected

try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox','--disable-gpu'])
  c=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True);c.route('**/*',guard)
  p=c.new_page();active=p;p.on('pageerror',lambda e:errors.append(str(e)));p.on('response',lambda r:http_errors.append({'url':r.url,'status':r.status}) if r.status>=400 else None)
  p.goto(args.url,wait_until='networkidle');open_library(p)
  assert p.locator('[data-page]').last.get_attribute('data-page')=='library'
  assert owncards(p).count()==0 and p.locator('.dl-card[data-sample="true"]').count()==8
  builtin_urls=p.locator('.dl-card[data-sample="true"] .dl-download').evaluate_all('(els)=>els.map(x=>x.href)')
  statuses=p.evaluate('''async urls=>await Promise.all(urls.map(async url=>{const r=await fetch(url);const blob=await r.blob();return {url,status:r.status,bytes:blob.size,type:blob.type};}))''',builtin_urls)
  assert len(statuses)==8 and all(x['status']==200 and x['bytes']>0 for x in statuses),statuses
  receipt['builtins']=statuses
  p.reload(wait_until='networkidle');p.locator('.document-library').wait_for();assert owncards(p).count()==0
  passed('Library is the final navigation page and opens/reloads without an active session; all eight built-in sample URLs return content')
  p.locator('#import-session').set_input_files(str(measurement));p.locator('#go-report').wait_for(timeout=60000)
  source=json.loads(measurement.read_text())['session'];unchanged(p,source)
  p.locator('#go-report').click();p.locator('#open-document-library').wait_for()
  exports={}
  exports['measurement_input_demo-report.html']=download(p,'#report-html','lab2-report.html')
  exports['measurement_input_demo-inspection.csv']=download(p,'#export-csv','lab2-inspection.csv')
  exports['measurement_input_demo-session.json']=download(p,'#export-json','lab2-session.json')
  exports['measurement_input_demo.sqlite']=download(p,'#export-db','lab2.sqlite')
  initial=entries(p,4);unchanged(p,source)
  p.locator('#open-document-library').click();p.locator('.document-library').wait_for();assert owncards(p).count()==4
  assert all(x['scope']=='lab2' for x in initial)
  for filename,path in exports.items():
   e=find_entry(initial,filename)
   copied=download(p,'.dl-card[data-document-id="'+e['id']+'"] .dl-download','archive-'+path.name)
   assert copied.read_bytes()==path.read_bytes(),filename
  assert len(entries(p))==4
  passed('LAB2 HTML/CSV/JSON/SQLite exports create four separate archive entries; every archived download is byte-identical and does not create another entry')
  html_entry=find_entry(initial,'measurement_input_demo-report.html');card(p,html_entry).locator('.dl-preview').click();p.locator('.dl-frame').wait_for()
  frame=p.locator('.dl-frame');assert frame.get_attribute('sandbox')==''
  srcdoc=frame.get_attribute('srcdoc');assert "script-src 'none'" in srcdoc and "connect-src 'none'" in srcdoc and 'data:font/' in srcdoc
  preview=p.frame_locator('.dl-frame');preview.locator('h1').wait_for()
  assert preview.locator('img').count()==4
  assert preview.locator('img').evaluate_all('(imgs)=>imgs.every(i=>i.complete&&i.naturalWidth>0)')
  assert 'BSH-2630' in preview.locator('body').inner_text()
  assert '26.30' in preview.locator('body').inner_text()
  p.screenshot(path=str(OUT/'01-lab2-sandboxed-preview.png'),full_page=True)
  close_preview(p)
  passed('Archived HTML preview shows report text, four decoded images and an embedded font inside an empty sandbox with scripts/network disabled')
  # Text previews are rendered as text, not interpreted markup.
  for kind,filename in [('csv','measurement_input_demo-inspection.csv'),('json','measurement_input_demo-session.json')]:
   card(p,find_entry(initial,filename)).locator('.dl-preview').click();p.locator('.dl-text').wait_for();assert 'BSH-2630' in p.locator('.dl-text').inner_text();close_preview(p)
  p.get_by_label('문서 검색',exact=True).fill('.sqlite');assert owncards(p).count()==1
  p.get_by_label('문서 검색',exact=True).fill('no-such-document');assert owncards(p).count()==0
  p.get_by_label('문서 검색',exact=True).fill('');p.get_by_label('실습 구분',exact=True).select_option('lab1');assert owncards(p).count()==0 and p.locator('.dl-card[data-sample="true"]').count()==3
  p.get_by_label('실습 구분',exact=True).select_option('lab2');assert owncards(p).count()==4 and p.locator('.dl-card[data-sample="true"]').count()==3
  p.get_by_label('실습 구분',exact=True).select_option('all')
  before_reload=entries(p);p.reload(wait_until='networkidle');p.locator('.document-library').wait_for();assert entries(p)==before_reload;unchanged(p,source)
  p.screenshot(path=str(OUT/'02-library-desktop.png'),full_page=True)
  p.set_viewport_size({'width':390,'height':844});assert p.evaluate('document.documentElement.scrollWidth<=innerWidth+1');p.screenshot(path=str(OUT/'03-library-mobile.png'),full_page=True);p.set_viewport_size({'width':1440,'height':1050})
  passed('CSV/JSON text preview, title/filename search, per-lab filtering, reload persistence and 390 px layout work without changing the active inspection')
  # Repeat an export with the same filename; the existing entry must not be replaced.
  p.locator('[data-page="report"]').click();duplicate=download(p,'#export-csv','lab2-duplicate.csv');assert duplicate.read_bytes()==exports['measurement_input_demo-inspection.csv'].read_bytes()
  dup_items=entries(p,5);dups=[e for e in dup_items if e['filename']=='measurement_input_demo-inspection.csv'];assert len(dups)==2 and dups[0]['id']!=dups[1]['id']
  assert {x['id'] for x in initial}.issubset({x['id'] for x in dup_items})
  passed('Saving the same CSV filename again appends a new entry and preserves the previous document')
  p.locator('#import-session').set_input_files(str(legacy));p.locator('#worker-open-report').wait_for(timeout=60000)
  worker=stored(p)['workerFlow'];expected_worker=json.loads(legacy.read_text())['workerFlow'];assert worker==expected_worker
  p.locator('#worker-open-report').click();p.locator('#open-document-library').wait_for()
  word_html=download(p,'#worker-html','lab1-legacy-inspection.html');word_docx=download(p,'#worker-docx','lab1-legacy-inspection.docx')
  all_items=entries(p,7);unchanged(p,worker,'workerFlow')
  p.locator('#open-document-library').click();p.locator('.document-library').wait_for();assert owncards(p).count()==7
  assert {x['id'] for x in dup_items}.issubset({x['id'] for x in all_items})
  newlab1=[x for x in all_items if x['scope']=='lab1'];assert len(newlab1)==2 and {x['kind'] for x in newlab1}=={'html','docx'}
  for e in newlab1:
   local=word_html if e['kind']=='html' else word_docx
   copied=download(p,'.dl-card[data-document-id="'+e['id']+'"] .dl-download','archived-'+local.name);assert copied.read_bytes()==local.read_bytes()
  passed('Legacy LAB1 v1 imports unchanged and adds exact HTML/Word copies while retaining all five LAB2 archive entries')
  # Deletion is a library-only operation, including cancel, and never mutates a session.
  selected=dups[0];ids_before={x['id'] for x in all_items}
  p.once('dialog',lambda d:d.dismiss());card(p,selected).locator('.dl-delete').click();assert len(entries(p))==7;unchanged(p,worker,'workerFlow')
  p.once('dialog',lambda d:d.accept());card(p,selected).locator('.dl-delete').click();remaining=entries(p,6)
  assert {x['id'] for x in remaining}==ids_before-{selected['id']};unchanged(p,worker,'workerFlow')
  assert len([e for e in remaining if e['filename']==selected['filename']])==1
  p.reload(wait_until='networkidle');p.locator('.document-library').wait_for();assert entries(p)==remaining;unchanged(p,worker,'workerFlow')
  p.screenshot(path=str(OUT/'04-cross-lab-library.png'),full_page=True)
  passed('Delete cancellation retains all entries; confirmation removes only the selected duplicate and preserves current worker state and other lab documents across reload')
  assert not errors and not http_errors and not blocked,(errors,http_errors,blocked)
  passed('No JavaScript errors, failed HTTP requests, external requests, POST/model calls or new video observations')
  receipt.update(status='passed',finishedAt=datetime.now(timezone.utc).isoformat(),finalEntries=remaining,limitations=['Browser-local document storage only; deleting browser data removes local copies.','Imported sessions already passed separate video/measurement tests; no new observations are claimed here.']);save();browser.close()
except Exception:
 receipt.update(status='failed',error=traceback.format_exc())
 try:
  if active:active.screenshot(path=str(OUT/'FAILED.png'),full_page=True)
 except Exception:pass
 save();raise
print(OUT)
