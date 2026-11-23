"""Exercise the actual worker UI, natural WebM playback and editable document exports.

CPU/browser test of authored classroom observations, not model recognition or
physical inspection. No seek/timeupdate injection and no direct controller calls.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import traceback
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import zipfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
a=argparse.ArgumentParser()
a.add_argument('--url',default='http://127.0.0.1:8939/')
a.add_argument('--browser',default=None)
a.add_argument('--output',type=Path,default=ROOT/'validation/worker_flow_v1'/('browser_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')))
args=a.parse_args();OUT=args.output;OUT.mkdir(parents=True,exist_ok=False)
origin=urlparse(args.url).netloc
requests=[];errors=[];http_errors=[];blocked=[];checks=[];video_samples=[];active_page=None
receipt={'status':'running','scope':'Actual local browser worker UI with naturally decoded VP9 playback; authored teaching outcomes, no model/GPU inference','checks':checks,'modelCalls':0,'gpuCalls':0,'seekInjection':False,'timeupdateInjection':False}

def save():
 receipt.update(requestCount=len(requests),pageErrors=errors,httpErrors=http_errors,blockedRequests=blocked,videoSamples=video_samples)
 (OUT/'E2E_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')

def passed(label):checks.append(label);save()

def guard(route):
 req=route.request
 if urlparse(req.url).scheme in {'blob','data'}:route.continue_();return
 requests.append({'method':req.method,'url':req.url})
 if req.method!='GET' or urlparse(req.url).netloc!=origin:
  blocked.append({'method':req.method,'url':req.url});route.abort()
 else:route.continue_()

def context(browser):
 ctx=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
 ctx.route('**/*',guard);p=ctx.new_page()
 p.on('pageerror',lambda e:errors.append(str(e)))
 p.on('response',lambda r:http_errors.append({'url':r.url,'status':r.status}) if r.status>=400 else None)
 p.goto(args.url,wait_until='networkidle')
 return ctx,p

def shot(p,name):p.screenshot(path=str(OUT/name),full_page=True)

def download(p,selector,name):
 with p.expect_download(timeout=60000) as pending:p.locator(selector).click()
 dest=OUT/name;pending.value.save_as(str(dest));return dest

def stored(p):
 return p.evaluate('''()=>new Promise((resolve,reject)=>{const r=indexedDB.open('dynin-seminar-classroom-v1',1);r.onerror=()=>reject(r.error);r.onsuccess=()=>{const db=r.result,t=db.transaction('state'),q=t.objectStore('state').get('current');q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error);t.oncomplete=()=>db.close();};})''')

def current_state(p):return stored(p)['workerFlow']['state']

def wait_state(p,predicate,timeout=10):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  state=current_state(p)
  if predicate(state):return state
  p.wait_for_timeout(100)
 raise AssertionError('Stored worker state did not reach expected state')

def enabled(p,selector):p.wait_for_function('(sel)=>{const e=document.querySelector(sel);return e&&!e.disabled;}',arg=selector)

def disabled(p,selector):p.wait_for_function('(sel)=>{const e=document.querySelector(sel);return e&&e.disabled;}',arg=selector)

def video_sample(p,stage):
 sample=p.locator('#worker-video').evaluate('(v)=>({currentTime:v.currentTime,duration:v.duration,paused:v.paused,readyState:v.readyState,videoWidth:v.videoWidth,videoHeight:v.videoHeight,decodedFrames:v.getVideoPlaybackQuality().totalVideoFrames,source:v.currentSrc,rate:v.playbackRate,error:v.error?.code||null})')
 sample['stage']=stage;sample['progress']=p.locator('.worker-timeline').get_attribute('aria-valuenow');video_samples.append(sample);save();return sample

def wait_stage_end(p,index):
 state=wait_state(p,lambda s:s['stageIndex']==index and s['stages'][index]['progress']==1,timeout=50)
 p.wait_for_function('()=>document.querySelector("#worker-video").paused')
 sample=video_sample(p,index)
 assert sample['videoWidth']==640 and sample['videoHeight']==360 and sample['decodedFrames']>1 and not sample['error']
 assert sample['currentTime']>=state['stages'][index]['sourceEnd']-.1
 return state

try:
 pw=sync_playwright().start()
 if True:
  browser=pw.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox','--disable-gpu'])
  ctx,p=context(browser);active_page=p
  p.locator('[data-select="electronics_demo"]').click();p.locator('#company-bundled').wait_for(state='attached')
  p.get_by_text('다운로드 없이 화면을 확인하려면',exact=True).click()
  p.locator('#company-bundled').click();enabled(p,'#compile');p.locator('#compile').click()
  p.locator('#review-task').wait_for(timeout=40000);p.locator('#review-task').select_option('battery')
  p.locator('#save-review').click();enabled(p,'#show-ontology');p.locator('#show-ontology').click()
  p.locator('#next-setup').wait_for();p.locator('#next-setup').click()
  p.locator('#worker-register').wait_for();assert not p.locator('#worker-auth').count()
  p.locator('[data-page="run"]').click();assert p.locator('#worker-register').is_visible()
  p.locator('#worker-name').fill('김실습 <b>교육</b>');p.locator('#worker-id').fill('CLASS-07')
  p.locator('#worker-photo').set_input_files(str(ROOT/'assets/worker-flow/avatar.svg'))
  p.wait_for_function('()=>document.querySelector("#worker-photo-preview").src.startsWith("data:image/jpeg")')
  shot(p,'01-worker-registration.png')
  p.locator('#worker-register-next').click();p.locator('#worker-auth').wait_for()
  assert not p.locator('#worker-register').count() and not p.locator('#worker-process').count()
  p.locator('#worker-auth-confirmed').check();p.locator('#worker-auth-code').fill('0000');p.locator('#worker-auth-next').click()
  p.wait_for_function('()=>document.querySelector("#toast").textContent.includes("다시 확인")')
  assert p.locator('#worker-auth').is_visible() and not p.locator('#worker-process').count()
  shot(p,'02-screen-authentication.png')
  p.locator('#worker-auth-code').fill('6421');p.locator('#worker-auth-next').click();p.locator('#worker-process').wait_for()
  disabled(p,'#start-session')
  options=p.locator('#worker-process option').evaluate_all('(es)=>es.map(e=>({value:e.value,text:e.textContent,disabled:e.disabled}))')
  (OUT/'PROCESS_OPTIONS.json').write_text(json.dumps({'options':options,'stored':stored(p)},ensure_ascii=False,indent=2)+'\n')
  assert any(o['value']=='ELEC-DEMO-001' and not o['disabled'] for o in options), options
  p.locator('#worker-process').select_option('ELEC-DEMO-001');enabled(p,'#start-session')
  assert '18항목' in p.locator('#worker-loaded-info').inner_text()
  shot(p,'03-process-selection.png')
  passed('Separate registration/photo, simulated screen authentication (wrong code rejected), process selection and premature run gate')
  p.locator('#start-session').click();p.locator('#worker-video').wait_for();disabled(p,'#worker-next')
  assert '<b>교육</b>' in p.locator('.page-heading p').inner_text()
  p.locator('#worker-speed').select_option('4');p.locator('#worker-play').click()
  p.wait_for_function('()=>document.querySelector("#worker-video").currentTime>2')
  initial=video_sample(p,0)
  assert 0<float(initial['progress'])<100 and not initial['paused'] and initial['decodedFrames']>1
  assert p.locator('#worker-checks .worker-check').count()==3
  shot(p,'04-continuous-video.png')
  passed('Actual VP9 video decodes continuously; real playback drives progress and staged checklist without injected events')
  states=[]
  for index in range(6):
   if index:
    p.locator('#worker-next').click()
    p.wait_for_function('(n)=>document.querySelector("#worker-stage-heading").textContent.startsWith(String(n)+"단계")',arg=index+1)
   state=wait_stage_end(p,index)
   if index==3:
    disabled(p,'#worker-next');assert state['questions'][0]['state']=='created'
    assert state['checks'][11]['rawVerdict']=='unknown'
    p.locator('.worker-deliver').click();p.locator('.worker-answer[data-verdict="violated"]').wait_for()
    p.locator('.worker-answer[data-verdict="violated"]').click()
    wait_state(p,lambda s:s['checks'][11]['verdict']=='violated');disabled(p,'#worker-next')
    p.locator('.worker-answer[data-verdict="unknown"]').click()
    wait_state(p,lambda s:s['checks'][11]['verdict']=='unknown');disabled(p,'#worker-next')
    shot(p,'05-agent-question-held.png')
    p.locator('.worker-answer[data-verdict="met"]').click();enabled(p,'#worker-next')
    state=wait_state(p,lambda s:s['stages'][3]['passed'])
    assert [a['verdict'] for a in state['questions'][0]['answers']]==['violated','unknown','met']
    assert state['checks'][11]['rawVerdict']=='unknown' and state['checks'][11]['origin']=='worker_confirmed'
    passed('Battery question delivery and negative/unknown holds; positive worker answer unlocks stage while preserving raw unknown and all three replies')
   else:enabled(p,'#worker-next')
   state=wait_state(p,lambda s:s['stages'][index]['passed'])
   assert sum(e['type']=='agent_pass' and e.get('stageId')==state['stages'][index]['id'] for e in state['events'])==1
   states.append(state)
   shot(p,f'06-stage-{index+1}-passed.png')
  complete=wait_state(p,lambda s:s['completed'])
  assert len(complete['checks'])==18 and all(c['verdict']=='met' for c in complete['checks'])
  assert all(s['passed'] for s in complete['stages'])
  assert len([e for e in complete['events'] if e['type']=='agent_pass'])==6
  (OUT/'COMPLETE_STATE.json').write_text(json.dumps(complete,ensure_ascii=False,indent=2)+'\n')
  passed('Six stages pause on boundaries; next stage requires agent pass; 18 checks, six unique pass signals and completion saved')
  p.locator('#worker-next').click();p.locator('#worker-open-report').wait_for();shot(p,'07-full-review.png')
  p.set_viewport_size({'width':390,'height':844})
  assert p.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  shot(p,'08-mobile-review.png');p.set_viewport_size({'width':1440,'height':1000})
  p.locator('#worker-open-report').click();p.locator('#worker-docx').wait_for()
  report=download(p,'#worker-html','completed-inspection.html')
  docx=download(p,'#worker-docx','completed-inspection.docx')
  backup=download(p,'#backup','complete-session.json')
  saved=json.loads(backup.read_text());assert saved['format']=='dynin-seminar-worker-export-v1'
  assert saved['workerFlow']['state']==complete
  text=report.read_text();assert '김실습' in text and 'CLASS-07' in text and 'data:image/' in text and '강의용 예시' in text
  assert all(c['id'] in text for c in complete['checks'])
  with zipfile.ZipFile(docx) as z:
   assert z.testzip() is None
   for required in ['[Content_Types].xml','_rels/.rels','word/document.xml','word/styles.xml','word/_rels/document.xml.rels']:assert required in z.namelist()
   body=z.read('word/document.xml').decode();ET.fromstring(body)
   assert '김실습' in body and all(c['id'] in body for c in complete['checks'])
   assert len([n for n in z.namelist() if n.startswith('word/media/')])==6
   docx_summary={'entries':len(z.namelist()),'images':6,'xmlParsed':True,'bytes':docx.stat().st_size}
  (OUT/'DOCX_CHECK.json').write_text(json.dumps(docx_summary,indent=2)+'\n')
  shot(p,'09-report-preview.png')
  passed('Dense HTML and valid editable DOCX exported from same state with 18 rows, worker identity, retained answers and six embedded evidence photos')
  p.reload(wait_until='networkidle');p.locator('#worker-report-preview').wait_for()
  assert current_state(p)==complete
  passed('Completed worker state, photo, evidence and pass ledger restore exactly after reload; mobile review fits390px')
  p.locator('#worker-return-review').click();p.locator('#worker-policy').select_option('visual_only');p.locator('#worker-apply-policy').click()
  held=wait_state(p,lambda s:not s['completed'] and s['policy']=='visual_only')
  assert held['stageIndex']==3 and held['checks'][11]['rawVerdict']=='unknown' and held['checks'][11]['verdict']=='unknown'
  assert held['questions'][0]['answers']==complete['questions'][0]['answers']
  assert any(e['type']=='agent_completion_revoked' for e in held['events'])
  assert len([e for e in held['events'] if e['type']=='agent_pass'])==6
  p.locator('#worker-back-run').click();p.locator('#worker-video').wait_for();disabled(p,'#worker-next')
  shot(p,'10-policy-revoked.png')
  p.locator('#worker-review').click();p.locator('#worker-open-report').click()
  held_html=download(p,'#worker-html','held-inspection.html').read_text()
  assert '보류' in held_html and '확인 필요' in held_html
  held_backup=download(p,'#backup','held-session.json')
  passed('Visual-only policy revokes battery/downstream passes and completion without erasing history; report and next gate remain held')
  ctx2,p2=context(browser);active_page=p2
  p2.locator('#import-session').set_input_files(str(backup));p2.locator('#worker-open-report').wait_for(timeout=30000)
  imported=wait_state(p2,lambda s:s['id']==complete['id'])
  assert imported==complete
  p2.locator('#worker-open-report').click();p2.locator('#worker-docx').wait_for()
  restored=download(p2,'#worker-html','imported-inspection.html').read_text()
  assert restored==text
  passed('Exported completion imports in a fresh browser context with identical state and identical HTML report')
  # Rejected corruption must retain the active valid state.
  tampered=json.loads(backup.read_text());tampered['workerFlow']['state']['checks'][11]['rawVerdict']='met'
  forged=OUT/'tampered-input.json';forged.write_text(json.dumps(tampered,ensure_ascii=False))
  p2.locator('#import-session').set_input_files(str(forged))
  p2.wait_for_function('()=>document.querySelector("#toast").textContent.includes("일치하지")')
  assert current_state(p2)==complete
  passed('Tampered raw observation is rejected on import without replacing the active validated session')
  # An exported worker record can be transferred without optional company-build history.
  no_company=json.loads(backup.read_text());no_company['companyBuild']=None
  portable=OUT/'without-company-history.json';portable.write_text(json.dumps(no_company,ensure_ascii=False))
  p2.locator('#import-session').set_input_files(str(portable));p2.locator('#worker-open-report').wait_for(timeout=30000)
  assert current_state(p2)==complete
  p2.reload(wait_until='networkidle');p2.locator('#worker-open-report').wait_for(timeout=30000)
  assert current_state(p2)==complete
  p2.locator('[data-page="documents"]').click()
  p2.wait_for_function('()=>document.querySelector("#main").textContent.includes("자료 구축 이력")')
  assert not p2.locator('#compile').count()
  p2.locator('[data-page="run"]').click();p2.locator('#worker-video').wait_for()
  assert current_state(p2)==complete
  passed('Worker transfer without optional company-build history survives reload and shows read-only source summary; literal name markup remains escaped')
  ctx2.close();ctx.close();browser.close();active_page=None
 assert not errors and not http_errors and not blocked
 receipt['status']='passed';receipt['limitations']=['Authored classroom conditions, not visual model accuracy.','No physical identity authentication or real microphone recognition.','Silent source video; audible TTS not tested.','One local browser host, not classroom network or public concurrency test.']
 save();print(json.dumps({'status':'passed','checks':len(checks),'requests':len(requests),'output':str(OUT)},ensure_ascii=False))
except Exception as e:
 receipt['status']='failed';receipt['error']=str(e);receipt['exceptionType']=type(e).__name__;receipt['traceback']=traceback.format_exc()
 try:
  if active_page and not active_page.is_closed():
   shot(active_page,'FAILURE.png')
   (OUT/'FAILURE_DOM.html').write_text(active_page.content())
   (OUT/'FAILURE_STATE.json').write_text(json.dumps(stored(active_page),ensure_ascii=False,indent=2)+'\n')
 except Exception as capture_error:receipt['captureError']=str(capture_error)
 save();raise

finally:
 try:pw.stop()
 except Exception:pass
