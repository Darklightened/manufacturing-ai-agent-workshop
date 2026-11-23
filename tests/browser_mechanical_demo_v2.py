"""Integrated LAB3 browser validation with natural video playback and real document compilation.

Only the blocked-seek test changes currentTime. Successful observations always
come from decoded playback; no controller calls, timeupdate injection or inference.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time
import traceback
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
a = argparse.ArgumentParser()
a.add_argument('--url', default='http://127.0.0.1:8937/')
a.add_argument('--browser', default='/home/jovyan/.cache/ms-playwright/chromium-1187/chrome-linux/chrome')
a.add_argument('--output', type=Path, default=ROOT/'validation/labs23_v2/mechanical_browser'/datetime.now(timezone.utc).strftime('integrated_%Y%m%dT%H%M%S'))
args = a.parse_args()
OUT = args.output
OUT.mkdir(parents=True, exist_ok=False)
origin = urlparse(args.url).netloc
checks, errors, http_errors, blocked, requests, samples = [], [], [], [], [], []
receipt = {'status':'running', 'mode':'authored_demo', 'modelCalls':0, 'gpuCalls':0, 'checks':checks, 'videoSamples':samples, 'timeupdateInjection':False, 'seekTest':'one blocked forward seek; successful completion requires natural playback', 'startedAt':datetime.now(timezone.utc).isoformat()}
active = None

def save():
    receipt.update(pageErrors=errors, httpErrors=http_errors, blockedRequests=blocked, requestCount=len(requests))
    (OUT/'E2E_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')

def passed(text):
    checks.append(text)
    save()
    print(text, flush=True)

def route_guard(route):
    r = route.request
    if urlparse(r.url).scheme in {'blob','data'}:
        route.continue_(); return
    requests.append({'url':r.url, 'method':r.method})
    if r.method != 'GET' or urlparse(r.url).netloc != origin:
        blocked.append({'url':r.url, 'method':r.method}); route.abort()
    else:
        route.continue_()

def open_app(browser):
    ctx = browser.new_context(viewport={'width':1440,'height':1000}, accept_downloads=True)
    ctx.route('**/*', route_guard)
    p = ctx.new_page()
    p.on('pageerror', lambda e: errors.append(str(e)))
    p.on('response', lambda r: http_errors.append({'url':r.url,'status':r.status}) if r.status>=400 else None)
    p.goto(args.url, wait_until='networkidle')
    return ctx, p

def shot(p, name):
    p.screenshot(path=str(OUT/name), full_page=True)

def download(p, selector, name):
    with p.expect_download(timeout=60000) as d:
        p.locator(selector).click()
    path = OUT/name
    d.value.save_as(str(path))
    return path

def snapshot(p, name):
    return json.loads(download(p, '#backup', name).read_text())['session']

def state(p):
    return p.evaluate('''()=>new Promise((resolve,reject)=>{const r=indexedDB.open('dynin-seminar-classroom-v1',1);r.onerror=()=>reject(r.error);r.onsuccess=()=>{const db=r.result,t=db.transaction('state'),q=t.objectStore('state').get('current');q.onsuccess=()=>resolve(q.result?.session);q.onerror=()=>reject(q.error);t.oncomplete=()=>db.close();};})''')

def wait_state(p, predicate, timeout=65):
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        s=state(p)
        if s and predicate(s): return s
        p.wait_for_timeout(120)
    raise AssertionError('Saved session did not reach expected state: '+json.dumps(state(p), ensure_ascii=False)[:1200])

def enabled(p, selector):
    p.wait_for_function('(s)=>!!document.querySelector(s)&&!document.querySelector(s).disabled', arg=selector)

def sample(p, stage):
    x=p.locator('#mechanical-video').evaluate('(v)=>({currentTime:v.currentTime,duration:v.duration,readyState:v.readyState,paused:v.paused,decodedFrames:v.getVideoPlaybackQuality().totalVideoFrames,width:v.videoWidth,height:v.videoHeight,rate:v.playbackRate,error:v.error?.code||null})')
    x['stage']=stage
    samples.append(x);save()
    return x

def complete_stage(p, index, endpoint):
    s=wait_state(p, lambda s:s['position']==index)
    p.wait_for_function('document.querySelector("#mechanical-video").paused')
    v=sample(p,index)
    assert v['decodedFrames']>1 and v['width']==640 and v['height']==360 and v['error'] is None, v
    assert v['currentTime']>=endpoint-.1, v
    assert sum(e['type']=='checkpoint' for e in s['events'])==index+1
    return s

def answer(p, confirmation):
    p.locator('[data-confirmation="'+confirmation+'"]').last.click()
    wait_state(p, lambda s:s['assessments']['MD-PIN'].get('workerConfirmation',{}).get('confirmation')==confirmation)

try:
    pw=sync_playwright().start()
    browser=pw.chromium.launch(executable_path=args.browser, headless=True, args=['--no-sandbox','--disable-gpu'])
    ctx,p=open_app(browser);active=p
    p.locator('[data-select="mechanical_demo"]').click()
    p.locator('#compile').click();p.locator('#next-setup').wait_for(timeout=60000)
    assert 'MECH-DEMO-001' in p.locator('#pdf-text').text_content()
    dbpath=download(p,'#export-db','compiled.sqlite')
    with sqlite3.connect(dbpath) as db:
        assert db.execute('select count(*) from tasks').fetchone()[0]==4
        assert db.execute('select count(*) from criteria').fetchone()[0]==6
    shot(p,'01-company-compiled-desktop.png')
    passed('Actual bundled PDF extraction and CSV validation create SQLite with 4 tasks and 6 criteria')
    p.locator('#next-setup').click();shot(p,'02-task-setup-desktop.png')
    p.locator('#start-session').click();p.locator('#mechanical-video').wait_for()
    p.wait_for_function('document.querySelector("#mechanical-video").readyState>=2&&!document.querySelector("#mechanical-video").seeking')
    assert p.locator('#mechanical-next').is_disabled()
    assert p.locator('[data-stage="1"]').is_disabled()
    p.locator('#mechanical-video').evaluate('(v)=>v.currentTime=69.9')
    p.wait_for_timeout(700)
    assert p.locator('#mechanical-video').evaluate('(v)=>v.currentTime')<1
    assert state(p)['position']==-1
    assert p.locator('#mechanical-next').is_disabled()
    passed('Unplayed forward seek is corrected; no checkpoint or stage pass is fabricated')
    p.locator('#mechanical-speed').select_option('4')
    p.locator('#mechanical-play').click()
    complete_stage(p,0,70);enabled(p,'#mechanical-next')
    shot(p,'03-chassis-pass-desktop.png')
    p.locator('#mechanical-next').click()
    complete_stage(p,1,90)
    assert p.locator('#mechanical-next').is_disabled()
    assert p.locator('[data-stage="2"]').is_disabled()
    assert p.locator('[data-deliver]').count()==1
    assert p.locator('[data-answer]').count()==0
    before=snapshot(p,'bracket-before-answer.json')
    assert before['assessments']['MD-PIN']['rawExampleVerdict']=='unknown'
    shot(p,'04-bracket-question-desktop.png')
    p.set_viewport_size({'width':390,'height':844})
    assert p.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    shot(p,'05-bracket-question-mobile.png')
    p.set_viewport_size({'width':1440,'height':1000})
    passed('Stage 2 naturally stops for one undelivered hidden-pin question; desktop and mobile stay usable')
    p.locator('[data-deliver]').click();answer(p,'met')
    enabled(p,'#mechanical-next')
    pin=state(p)['assessments']['MD-PIN']
    assert pin['rawExampleVerdict']=='unknown' and pin['origin']=='worker_confirmed' and pin['verdict']=='met'
    p.locator('#mechanical-next').click();complete_stage(p,2,178)
    enabled(p,'#mechanical-next');p.locator('#mechanical-next').click();complete_stage(p,3,184.4)
    enabled(p,'#mechanical-next');shot(p,'06-final-stage-desktop.png')
    complete=snapshot(p,'complete-session.json')
    assert len(complete['assessments'])==6 and all(a['verdict']=='met' for a in complete['assessments'].values())
    assert len(complete['questions'])==1 and len(complete['questions'][0]['answers'])==1
    passed('All 4 stages completed through decoded 4x playback; 6 checks with one separately sourced positive worker answer')
    p.locator('#mechanical-next').click();p.locator('#go-report').wait_for()
    shot(p,'07-review-desktop.png')
    p.locator('#go-report').click();p.locator('#report-preview').wait_for()
    report=download(p,'#report-html','mechanical-report-complete.html')
    inspection=download(p,'#inspection-html','mechanical-inspection-complete.html')
    csv=download(p,'#export-csv','mechanical-inspection-complete.csv')
    dbpath=download(p,'#export-db','complete.sqlite')
    for path in [report,inspection]:
        html=path.read_text()
        assert '강의용 예시' in html and 'data:image/' in html and 'data:font/' in html
        assert '최초 예시 판정' in html and '작업자 확인' in html
        assert '확인 필요' in html and '연결 핀' in html
    with sqlite3.connect(dbpath) as db:
        saved=json.loads(db.execute('select payload from assessments where criterion_id="MD-PIN"').fetchone()[0])
        assert saved['rawExampleVerdict']=='unknown' and saved['verdict']=='met' and saved['origin']=='worker_confirmed'
    assert 'authored_demo' in csv.read_text() and 'worker_confirmed' in csv.read_text()
    shot(p,'08-report-desktop.png')
    passed('Standalone report, inspection, CSV and SQLite preserve real scene photos and original unknown versus worker-confirmed result')
    p.reload(wait_until='networkidle');p.locator('#report-preview').wait_for()
    assert snapshot(p,'reloaded-session.json')==complete
    imported_ctx,imp=open_app(browser)
    imp.locator('#import-session').set_input_files(str(OUT/'complete-session.json'))
    imp.locator('#go-report').wait_for(timeout=60000)
    assert snapshot(imp,'imported-session.json')==complete
    imp.locator('#go-report').click()
    assert download(imp,'#report-html','imported-report.html').read_bytes()==report.read_bytes()
    imported_ctx.close()
    passed('Reload and fresh-browser JSON import reproduce the exact session and identical standalone report')
    # Preserve the clean one-answer example, then exercise alternate answers from
    # the legitimately saved in-progress stage in another browser context.
    branch_ctx,b=open_app(browser);active=b
    b.locator('#import-session').set_input_files(str(OUT/'bracket-before-answer.json'))
    b.locator('#back-run').wait_for(timeout=60000);b.locator('#back-run').click()
    b.locator('[data-deliver]').click();answer(b,'unknown')
    assert b.locator('#mechanical-next').is_disabled()
    assert state(b)['assessments']['MD-PIN']['verdict']=='unknown'
    snapshot(b,'branch-unknown.json')
    answer(b,'violated')
    assert b.locator('#mechanical-next').is_disabled()
    assert state(b)['assessments']['MD-PIN']['verdict']=='violated'
    snapshot(b,'branch-negative.json');shot(b,'09-negative-answer.png')
    b.locator('[data-reopen="MD-PIN"]').click()
    assert b.locator('#mechanical-next').is_disabled()
    b.locator('[data-deliver]').last.click();answer(b,'met');enabled(b,'#mechanical-next')
    revised=snapshot(b,'branch-confirmed-after-revision.json')
    answers=[a['confirmation'] for q in revised['questions'] for a in q['answers']]
    assert answers==['unknown','violated','met'],answers
    assert revised['assessments']['MD-PIN']['rawExampleVerdict']=='unknown'
    passed('Unknown and negative answers keep the next task locked; explicit recheck plus positive answer unlocks it while preserving all three answers')
    branch_ctx.close();active=p
    # Offline report rendering checks the exported artifact rather than iframe HTML.
    offline=browser.new_context(viewport={'width':1440,'height':1050})
    offline.set_offline(True)
    for source,stem in [(report,'10-report-offline'),(inspection,'11-inspection-offline')]:
        doc=offline.new_page();doc.goto(source.as_uri(),wait_until='load');doc.evaluate('document.fonts.ready')
        assert doc.locator('img').count()>=4
        assert doc.locator('img').evaluate_all('(imgs)=>imgs.every(i=>i.complete&&i.naturalWidth>0)')
        shot(doc,stem+'.png')
        doc.pdf(path=str(OUT/(stem+'.pdf')),format='A4',print_background=True,prefer_css_page_size=True)
        doc.set_viewport_size({'width':390,'height':844})
        shot(doc,stem+'-mobile.png')
        doc.close()
    offline.close()
    passed('Exported report and inspection open fully offline with decoded embedded evidence photos and embedded Korean font; printable PDFs saved')
    assert not errors and not http_errors and not blocked,(errors,http_errors,blocked)
    passed('No page errors, failing HTTP requests, external requests or non-GET/model calls')
    receipt.update(status='passed',finishedAt=datetime.now(timezone.utc).isoformat(),limitations=['Authored classroom outcomes, not real model predictions or physical quality approval.','Mobile screenshots validate display only; no mobile-device codec hardware tested.'])
    save();browser.close();pw.stop()
except Exception:
    receipt.update(status='failed',error=traceback.format_exc(),finishedAt=datetime.now(timezone.utc).isoformat())
    try:
        if active:shot(active,'FAILED.png')
    except Exception:pass
    save()
    raise
print(str(OUT),flush=True)
