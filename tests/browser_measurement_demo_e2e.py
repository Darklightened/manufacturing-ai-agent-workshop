"""Product-bound authored measurement lesson; no inference or external requests."""
import argparse,json,sqlite3,csv as csv_module,io
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8924/');p.add_argument('--browser');p.add_argument('--output',type=Path,default=ROOT/'validation/measurement_demo_v1/browser_01');args=p.parse_args()
OUT=args.output;OUT.mkdir(parents=True,exist_ok=True)
requests=[];blocked=[];errors=[];bad_status=[];origin=urlparse(args.url).netloc

def guard(route):
 r=route.request;requests.append({'url':r.url,'method':r.method})
 if urlparse(r.url).netloc!=origin or r.method!='GET':blocked.append(r.url);route.abort()
 else:route.continue_()

def open_app(browser):
 c=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True);c.route('**/*',guard);page=c.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('response',lambda r:bad_status.append({'url':r.url,'status':r.status}) if r.status>=400 else None);page.goto(args.url,wait_until='networkidle');return c,page

def download(page,selector,name):
 with page.expect_download(timeout=60000) as d:page.locator(selector).click()
 path=OUT/name;d.value.save_as(str(path));return path

def snapshot(page,name):return json.loads(download(page,'#backup',name).read_text())['session']

def compile_start(page):
 page.locator('#compile').click();page.locator('#next-setup').wait_for(timeout=60000)
 assert 'product_id:' in page.locator('#pdf-text').text_content()
 assert 'drawing_revision:' in page.locator('#pdf-text').text_content()
 page.locator('#next-setup').click();page.locator('#start-session').click()

def record_three(page):
 for _ in range(3):page.locator('#advance').click()
 assert page.locator('#advance').is_disabled()
 assert page.locator('.answer-form').count()==1

def reply(page,value='5.78',unit='mm'):
 page.locator('#questions .deliver').last.click();f=page.locator('.answer-form').last
 f.locator('[name="value"]').fill(value);f.locator('[name="unit"]').fill(unit);f.locator('[name="text"]').fill('계측기 표시를 직접 다시 확인했습니다.');f.locator('[type="submit"]').click()

def reopen(page):
 page.locator('[data-page="review"]').click();page.locator('.reopen-answer[data-id="M-FLANGE"]').click()

def change_range(page,cid,lower,upper):
 f=page.locator('.range-form[data-id="'+cid+'"]');f.locator('[name="lower"]').fill(lower);f.locator('[name="upper"]').fill(upper);f.locator('button[type="submit"]').click()

with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox','--disable-gpu'])
 ctx,page=open_app(browser)
 assert page.locator('.cards [data-select]').count()==3
 assert page.locator('[data-select="measurement_demo"]').is_visible()
 assert not page.locator('[data-select="instruments"]').is_visible()
 page.locator('[data-select="measurement_demo"]').click();page.locator('.product-options').wait_for()
 assert 'BSH-2630' in page.locator('.measurement-identity').inner_text()
 assert page.locator('.inspection-drawing').get_attribute('src').startswith('scenarios/measurement_demo/')
 page.locator('[data-product-scenario="measurement_precision_demo"]').click()
 page.wait_for_function("document.querySelector('.inspection-drawing').getAttribute('src').includes('measurement_precision_demo')")
 assert 'BSH-2630-P' in page.locator('.measurement-identity').inner_text()
 assert '39.99' in page.locator('.drawing-values').inner_text()
 page.locator('[data-product-scenario="measurement_demo"]').click()
 page.wait_for_function("document.querySelector('.inspection-drawing').getAttribute('src')==='scenarios/measurement_demo/drawing.svg'")
 page.screenshot(path=str(OUT/'01-product-drawing.png'),full_page=True)
 compile_start(page)
 page.locator('#advance').click()
 assert '26.30' in page.locator('[data-feature-result="M-OD"]').inner_text()
 assert '—' in page.locator('[data-feature-result="M-LENGTH"]').inner_text()
 assert page.locator('[data-drawing-feature="M-OD"]').get_attribute('class').find('active')>=0
 page.locator('#advance').click();page.locator('#advance').click()
 assert page.locator('.answer-form').count()==1
 assert page.locator('.answer-form [type="submit"]').is_disabled()
 assert page.locator('.fill-measurement').is_disabled()
 assert '확인 필요' in page.locator('[data-feature-result="M-FLANGE"]').inner_text()
 assert '5.?8' in page.locator('#reading-value').inner_text()
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 page.screenshot(path=str(OUT/'02-uncertain-value.png'),full_page=True)
 before=snapshot(page,'before-confirmation.json');assert before['assessments']['M-FLANGE']['verdict']=='unknown'
 page.locator('#questions .deliver').click();f=page.locator('.answer-form')
 assert f.locator('[name="value"]').input_value()==''
 f.locator('[name="value"]').fill('5.78');f.locator('[name="unit"]').fill('cm');f.locator('[type="submit"]').click()
 assert '단위' in page.locator('#toast').inner_text()
 assert snapshot(page,'wrong-unit-rejected.json')['assessments']['M-FLANGE']['verdict']=='unknown'
 f.locator('[name="unit"]').fill('mm');f.locator('[name="target"]').evaluate("el=>el.value='OTHER-SPECIMEN'");f.locator('[type="submit"]').click()
 assert '대상' in page.locator('#toast').inner_text()
 f.locator('[name="target"]').evaluate("el=>el.value='EDU-BSH-001'")
 page.locator('.fill-measurement').click()
 assert f.locator('[name="value"]').input_value()=='5.78'
 assert snapshot(page,'example-filled-not-submitted.json')['assessments']['M-FLANGE']['verdict']=='unknown'
 f.locator('[type="submit"]').click()
 complete=snapshot(page,'complete-session.json')
 assert all(a['verdict']=='met' for a in complete['assessments'].values())
 assert complete['assessments']['M-FLANGE']['measurement']['raw']=='5.?8 mm'
 assert complete['assessments']['M-FLANGE']['measurement']['value']=='5.78'
 assert complete['assessments']['M-FLANGE']['origin']=='worker_confirmed'
 assert '5.78' in page.locator('[data-feature-result="M-FLANGE"]').inner_text()
 assert '세 위치의 검사가 완료되었습니다' in page.locator('#main').inner_text()
 page.screenshot(path=str(OUT/'03-complete.png'),full_page=True)
 page.locator('#to-review').click();page.locator('#go-report').click()
 report=download(page,'#report-html','report-complete.html').read_text()
 inspection=download(page,'#inspection-html','inspection-complete.html').read_text()
 assert all(x in report for x in ['BSH-2630','DR-BSH-2630','EDU-BSH-001','5.78','5.?8','강의용 예시'])
 assert 'data:image/svg+xml;base64' in report and 'data:image/svg+xml;base64' in inspection
 assert 'data:font/' in report
 csv=download(page,'#export-csv','inspection.csv').read_text()
 assert 'drawing_revision' in csv and 'EDU-BSH-001' in csv and '5.?8' in csv
 assert all(x in csv for x in ['도면 하한','적용 상한','확인 상태','검사 완료'])
 dbpath=download(page,'#export-db','complete.sqlite')
 with sqlite3.connect(dbpath) as db:
  identity=db.execute('select product_id,drawing_id,drawing_revision,specimen_id from inspection').fetchone();assert identity==('BSH-2630','DR-BSH-2630','A','EDU-BSH-001'),identity
  assert db.execute('select count(*) from features').fetchone()[0]==3
  a=json.loads(db.execute('select payload from assessments where criterion_id=?',('M-FLANGE',)).fetchone()[0]);assert a['measurement']['value']=='5.78'
 page.screenshot(path=str(OUT/'04-report.png'),full_page=True)
 page.reload(wait_until='networkidle');page.locator('#report-preview').wait_for(timeout=60000)
 assert snapshot(page,'reloaded-session.json')==complete
 fresh,imported=open_app(browser);imported.locator('#import-session').set_input_files(str(OUT/'complete-session.json'));imported.locator('#go-report').wait_for(timeout=60000)
 assert snapshot(imported,'imported-session.json')==complete;fresh.close()
 page.locator('[data-page="review"]').click();change_range(page,'M-OD','26.10','26.25')
 changed=snapshot(page,'changed-range-session.json');assert changed['assessments']['M-OD']['verdict']=='violated' and changed['assessments']['M-OD']['measurement']['value']=='26.30'
 assert changed['bundle']['inspection']['features'][0]['upper']=='26.50'
 assert '도면' in page.locator('[data-criterion="M-OD"]').inner_text() and '26.50' in page.locator('[data-criterion="M-OD"]').inner_text()
 page.locator('#go-report').click();changedreport=download(page,'#report-html','report-range-changed.html').read_text();assert '26.25' in changedreport and '26.50' in changedreport
 changed_csv=list(csv_module.DictReader(io.StringIO(download(page,'#export-csv','changed-range.csv').read_text(encoding='utf-8-sig'))));assert changed_csv[0]['도면 상한']=='26.50' and changed_csv[0]['적용 상한']=='26.25' and changed_csv[0]['기준 변경']=='변경됨'
 page.locator('[data-page="review"]').click();change_range(page,'M-OD','26.10','26.50');page.locator('.reopen-answer[data-id="M-FLANGE"]').click()
 assert '확인 필요' in page.locator('[data-feature-result="M-FLANGE"]').inner_text()
 page.locator('[data-page="report"]').click();pending_csv=list(csv_module.DictReader(io.StringIO(download(page,'#export-csv','pending-confirmation.csv').read_text(encoding='utf-8-sig'))));assert pending_csv[2]['확인 상태']=='확인 대기' and pending_csv[2]['현재 상태']=='unknown' and pending_csv[2]['검사 완료']=='미완료';page.locator('[data-page="run"]').click()
 reply(page,'578')
 large=snapshot(page,'out-of-range-session.json');assert large['assessments']['M-FLANGE']['measurement']['value']=='578' and large['assessments']['M-FLANGE']['verdict']=='violated'
 page.locator('#to-review').click();page.locator('#go-report').click();negative=download(page,'#inspection-html','inspection-out-of-range.html').read_text();assert '578' in negative
 reopen(page);reply(page,'5.78')
 corrected=snapshot(page,'corrected-session.json');assert corrected['assessments']['M-FLANGE']['verdict']=='met'
 assert any(a.get('value')=='578' for q in corrected['questions'] for a in q['answers'])
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1');page.screenshot(path=str(OUT/'05-mobile.png'),full_page=True);page.set_viewport_size({'width':1440,'height':1050})
 # An explicit product switch resets the current inspection without mixing numeric records.
 page.locator('[data-page="review"]').click();page.locator('#change-product').click();page.once('dialog',lambda d:d.accept());page.locator('[data-product-scenario="measurement_precision_demo"]').click()
 page.wait_for_function("document.querySelector('.inspection-drawing').getAttribute('src').includes('measurement_precision_demo')")
 compile_start(page);empty=snapshot(page,'precision-empty-session.json');assert not empty['assessments'];assert empty['bundle']['inspection']['specimenId']=='EDU-BSH-P-001'
 record_three(page);reply(page,'5.78')
 precision=snapshot(page,'precision-session.json');assert precision['assessments']['M-LENGTH']['verdict']=='violated';assert precision['assessments']['M-LENGTH']['measurement']['value']=='40.02';assert precision['assessments']['M-OD']['verdict']=='met'
 assert len(precision['questions'])==1 and len(precision['questions'][0]['answers'])==1
 page.locator('#to-review').click();page.locator('#go-report').click();download(page,'#inspection-html','inspection-precision.html')
 # Exported report and inspection must work from file:// with images/fonts embedded.
 offline=browser.new_context(viewport={'width':1280,'height':1000});offline_requests=[]
 def offline_guard(route):
  if route.request.url.startswith('file:'):route.continue_()
  else:offline_requests.append(route.request.url);route.abort()
 offline.route('**/*',offline_guard)
 for name,png in [('report-complete.html','06-report-standalone.png'),('inspection-complete.html','07-inspection-standalone.png')]:
  op=offline.new_page();op.goto((OUT/name).resolve().as_uri(),wait_until='networkidle');op.evaluate('document.fonts.ready');assert op.locator('img').count()>=4
  assert op.evaluate('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
  assert op.evaluate('document.documentElement.scrollWidth<=innerWidth+1');op.screenshot(path=str(OUT/png),full_page=True);op.close()
 assert not offline_requests,offline_requests;offline.close()
 assert not errors,errors;assert not blocked,blocked;assert not bad_status,bad_status
 assert not [r for r in requests if '/recordings/' in r['url']]
 receipt={'status':'passed','mode':'authored_demo','scenarios':['measurement_demo','measurement_precision_demo'],'checks':['explicit product selection loads distinct drawing/limits','real PDF extraction and SQLite identity/feature mapping','A/B/C drawing values update only from recorded data','uncertain candidate stays unknown until delivery and numeric confirmation','wrong unit and target rejected','example fill is explicit and does not submit','confirmed value and original raw candidate retained','range change preserves original drawing limits and raw numeric','578 remains 578 and fails rather than decimal normalization','answer correction retains old answers','product switch clears previous measurements and changes specimen','precision length correctly violates narrower limit','HTML report and inspection contain embedded drawing/scenes/font','standalone exported HTML opens offline','CSV and SQLite reflect product/values plus original versus applied bounds and pending confirmation','exact reload and fresh-context import','mobile no horizontal overflow','no model/external/POST/recording requests'],'staticGets':len(requests),'externalOrNonGetRequests':len(blocked),'pageErrors':errors,'httpErrors':bad_status,'modelCalls':0,'limitations':['Product/drawing/instrument scenes and readings are authored classroom examples; not OCR results or physical inspection certification.','TTS actual listening quality is not verified.']}
 (OUT/'E2E_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False));ctx.close();browser.close()
