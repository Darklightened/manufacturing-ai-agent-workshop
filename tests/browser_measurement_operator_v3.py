"""Browser validation of authored LAB2 direct input. No external requests or model calls."""
import argparse,csv,io,json,sqlite3,traceback
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8937/');p.add_argument('--browser');p.add_argument('--output',type=Path,default=ROOT/'validation/labs23_v2/measurement_browser/attempt01');args=p.parse_args()
OUT=args.output;OUT.mkdir(parents=True,exist_ok=True)
origin=urlparse(args.url).netloc;blocked=[];errors=[];bad=[];checks=[]
def route(r):
    if urlparse(r.request.url).netloc!=origin or r.request.method!='GET':blocked.append(r.request.url);r.abort()
    else:r.continue_()
def opened(browser):
    ctx=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True);ctx.route('**/*',route);page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('response',lambda r:bad.append([r.url,r.status]) if r.status>=400 else None);page.goto(args.url,wait_until='networkidle');return ctx,page
def download(page,selector,name):
    with page.expect_download(timeout=60000) as item:page.locator(selector).click()
    dest=OUT/name;item.value.save_as(str(dest));return dest
def snapshot(page,name):
    page.wait_for_timeout(120)
    saved=page.evaluate("""async()=>{const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('dynin-seminar-classroom-v1',1);r.onsuccess=()=>resolve(r.result);r.onerror=reject});return await new Promise(resolve=>{const r=db.transaction('state').objectStore('state').get('current');r.onsuccess=()=>resolve(r.result)})}""")
    data={'format':'dynin-seminar-export-v1','scenarioId':saved['scenarioId'],'session':saved['session']}
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False))
    return saved['session']
def begin(page,precision=False):
    page.locator('[data-select="measurement_input_demo"]').click()
    if precision:page.locator('[data-product-scenario="measurement_input_precision_demo"]').click()
    page.locator('#compile').click();page.locator('#next-setup').wait_for(timeout=60000);assert 'product_id:' in page.locator('#pdf-text').text_content();page.locator('#next-setup').click()
    page.locator('#inspection-inspector').fill('교육 참가자');page.locator('#inspection-lot').fill('CLASS-LOT-01');page.locator('#start-session').click();page.locator('#measurement-entry').wait_for()
def typed(page,value,unit='mm'):
    f=page.locator('#measurement-entry');f.locator('[name="value"]').fill(value);f.locator('[name="unit"]').fill(unit);f.locator('[type="submit"]').click()
def ab(page):
    typed(page,'26.30');page.locator('#measurement-show-monitor').click();assert not page.locator('body').evaluate('(e)=>e.classList.contains("operator-active")');assert '26.30' in page.locator('[data-feature-result="M-OD"]').text_content();page.screenshot(path=str(OUT/'monitor-a.png'),full_page=True);page.locator('#measurement-next-scene').click();assert page.locator('#measurement-entry').get_attribute('data-criterion')=='M-LENGTH';typed(page,'40.02');page.locator('#measurement-show-monitor').click();page.locator('#measurement-next-scene').click();page.locator('#advance').click()
def reply(page,value):
    page.locator('#questions .deliver').last.click();f=page.locator('.answer-form').last;f.locator('[name="value"]').fill(value);f.locator('[name="unit"]').fill('mm');f.locator('[name="text"]').fill('가려진 표시를 직접 확인했습니다.');f.locator('[type="submit"]').click()
def reports(page,prefix):
    page.locator('#to-review').click();page.locator('#go-report').click();report=download(page,'#report-html',prefix+'-report.html');inspect=download(page,'#inspection-html',prefix+'-inspection.html');csvpath=download(page,'#export-csv',prefix+'-inspection.csv');return report,inspect,csvpath

with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox','--disable-gpu']);ctx,page=opened(browser)
    try:
        begin(page);before=snapshot(page,'00-start.json');assert before['position']==-1;assert before['inspectionDetails']=={'inspector':'교육 참가자','lot':'CLASS-LOT-01'}
        assert page.locator('#measurement-value').input_value()==''
        assert page.locator('body').evaluate('(e)=>e.classList.contains("operator-active")')
        page.wait_for_function('document.querySelector("#measurement-camera").currentTime>0.3')
        typed(page,'26.?0');assert '10진수' in page.locator('#toast').inner_text();assert snapshot(page,'01-invalid-decimal.json')==before
        typed(page,'26.30','cm');assert '단위' in page.locator('#toast').inner_text();assert snapshot(page,'02-invalid-unit.json')==before
        checks.append('invalid decimal/unit leave whole session unchanged; no partial advance or question')
        page.screenshot(path=str(OUT/'01-direct-input-desktop.png'),full_page=True)
        ab(page);pending=snapshot(page,'03-pending-c.json');assert pending['position']==2
        for cid,value in [('M-OD','26.30'),('M-LENGTH','40.02')]:assert pending['assessments'][cid]['measurement']['value']==value and pending['assessments'][cid]['origin']=='worker_confirmed'
        assert pending['assessments']['M-FLANGE']['measurement']['raw']=='5.?8 mm';assert len(pending['questions'])==3
        reply(page,'578');negative=snapshot(page,'04-out-of-range.json');assert negative['assessments']['M-FLANGE']['measurement']['value']=='578';assert negative['assessments']['M-FLANGE']['verdict']=='violated'
        reports(page,'out-of-range');page.locator('[data-page="review"]').click();page.locator('.reopen-answer[data-id="M-FLANGE"]').click();reply(page,'5.78');complete=snapshot(page,'05-complete-session.json')
        assert all(a['verdict']=='met' for a in complete['assessments'].values());assert [a['value'] for q in complete['questions'] if q['criterionId']=='M-FLANGE' for a in q['answers']]==['578','5.78']
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1');page.screenshot(path=str(OUT/'02-direct-input-mobile.png'),full_page=True);page.set_viewport_size({'width':1440,'height':1050})
        report,inspection,csvpath=reports(page,'completed');html=inspection.read_text();visible=html.split('<details>')[0]
        for item in ['교육 참가자','CLASS-LOT-01','578','5.78','26.30','40.02','5.?8 mm']:assert item in visible,item
        assert '<svg' in html and '검수' in html and '승인' in html
        assert 'data:image/svg+xml;base64' in html and 'data:font/' in html
        rows=list(csv.DictReader(io.StringIO(csvpath.read_text(encoding='utf-8-sig'))));assert len(rows)==3;assert all(r['검사자']=='교육 참가자' and r['LOT']=='CLASS-LOT-01' for r in rows)
        assert all(r['출처']=='worker_confirmed' and r['검사 완료']=='완료' for r in rows);assert rows[2]['최초후보']=='5.?8 mm'
        dbpath=download(page,'#export-db','completed.sqlite')
        with sqlite3.connect(dbpath) as db:
            assert db.execute('select count(*) from features').fetchone()[0]==3
            assert json.loads(db.execute('select payload from assessments where criterion_id=?',('M-FLANGE',)).fetchone()[0])['measurement']['raw']=='5.?8 mm'
        checks.append('A/B direct input and C question; no decimal correction; previous replies in visible HTML/CSV/SQLite')
        page.screenshot(path=str(OUT/'03-report-page.png'),full_page=True)
        page.reload(wait_until='networkidle');page.locator('#report-preview').wait_for(timeout=60000);assert snapshot(page,'06-reloaded.json')==complete
        other,ip=opened(browser);ip.locator('#import-session').set_input_files(str(OUT/'05-complete-session.json'));ip.locator('#go-report').wait_for(timeout=60000);assert snapshot(ip,'07-imported.json')==complete;other.close()
        checks.append('new snapshot reload and fresh browser import match exactly')
        # Separate product keeps its own drawing/specimen; the same length fails its narrower rule.
        pc,pp=opened(browser);begin(pp,True);ab(pp);reply(pp,'5.78');precision=snapshot(pp,'08-precision-session.json')
        assert precision['bundle']['inspection']['specimenId']=='EDU-BSH-P-001';assert precision['assessments']['M-LENGTH']['verdict']=='violated';assert len(precision['questions'])==3
        reports(pp,'precision');pc.close();checks.append('precision product isolation and 40.02 mm length violation')
        # Clean positive example for the public handout; failure/correction outputs stay separate.
        sc,sp=opened(browser);begin(sp);ab(sp);reply(sp,'5.78');snapshot(sp,'standard-sample-session.json');reports(sp,'standard-sample');sc.close()
        # Restore a saved v1 session through the real import UI, without creating optional metadata.
        legacy=json.loads((ROOT/'tests/fixtures/measurement_legacy_sessions.json').read_text())[0];path=OUT/'legacy-input.json';path.write_text(json.dumps({'format':'dynin-seminar-export-v1','scenarioId':legacy['scenarioId'],'session':legacy}))
        lc,lp=opened(browser);lp.locator('#import-session').set_input_files(str(path));lp.locator('#go-report').wait_for(timeout=60000);assert snapshot(lp,'09-legacy-restored.json')==legacy;lc.close();checks.append('original v1 saved session imports without reinterpretation')
        # The standalone report works without a server and keeps its authored images embedded.
        oc=browser.new_context(viewport={'width':1280,'height':1000});off=[]
        def offline_route(r):
            if r.request.url.startswith('file:'):r.continue_()
            else:off.append(r.request.url);r.abort()
        oc.route('**/*',offline_route);op=oc.new_page();op.goto(inspection.resolve().as_uri(),wait_until='networkidle');op.evaluate('document.fonts.ready')
        assert op.evaluate('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)');assert op.locator('img').count()>=3;assert op.locator('svg').count()==1;op.screenshot(path=str(OUT/'04-inspection-standalone.png'),full_page=True);assert not off,off;oc.close()
        checks.append('standalone inspection report loads embedded image/font without network')
        assert not errors,errors;assert not blocked,blocked;assert not bad,bad
        receipt={'status':'passed','mode':'authored_demo','checks':checks,'pageErrors':errors,'externalRequests':blocked,'httpErrors':bad,'modelCalls':0,'scenarioIds':['measurement_input_demo','measurement_input_precision_demo'],'limitations':['Authored scenes/values; not real OCR, sensor measurements or independently judged model output.','Actual audio listening quality untested.']}
        (OUT/'E2E_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False))
    except Exception as e:
        page.screenshot(path=str(OUT/'FAILURE_SCREEN.png'),full_page=True);(OUT/'FAILURE.json').write_text(json.dumps({'error':str(e),'traceback':traceback.format_exc(),'completedChecks':checks,'pageErrors':errors,'httpErrors':bad},ensure_ascii=False,indent=2));raise
    finally:browser.close()
