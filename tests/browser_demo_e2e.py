"""Classroom authored example: real PDF/SQLite plus interactive decisions, no inference.

Exercises the shipped browser path, including answer reversal, policy reversal,
self-contained reports, restore/import, and locally served assets only.
"""
import argparse
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:8923/')
parser.add_argument('--browser')
parser.add_argument('--output', type=Path, default=ROOT/'validation/classroom_demo_v1')
args = parser.parse_args()
OUT = args.output
OUT.mkdir(parents=True, exist_ok=True)
base_origin = urlparse(args.url).netloc
page_errors, blocked_requests, requests = [], [], []
video_check = {}


def guard(route):
    req = route.request
    requests.append({'method': req.method, 'url': req.url})
    if urlparse(req.url).netloc != base_origin or req.method != 'GET':
        blocked_requests.append({'method': req.method, 'url': req.url})
        route.abort()
    else:
        route.continue_()


def open_app(browser):
    ctx = browser.new_context(viewport={'width':1440, 'height':1000}, accept_downloads=True)
    ctx.route('**/*', guard)
    page = ctx.new_page()
    page.on('pageerror', lambda error:page_errors.append(str(error)))
    page.goto(args.url, wait_until='networkidle')
    return ctx, page


def download(page, selector, name):
    with page.expect_download(timeout=60000) as pending:
        page.locator(selector).click()
    dest = OUT/name
    pending.value.save_as(str(dest))
    return dest


def snapshot(page, name):
    return json.loads(download(page, '#backup', name).read_text())['session']


def start_demo(page):
    assert page.locator('#mode-banner').inner_text() == '강의용 예시'
    assert page.locator('[data-select="electronics_demo"]').is_visible()
    assert not page.locator('[data-select="electronics"]').is_visible()
    page.locator('[data-select="electronics_demo"]').click()
    page.locator('#compile').wait_for()
    assert '강의용 예시' in page.locator('#main').inner_text()
    page.locator('#compile').click()
    page.locator('#next-setup').wait_for(timeout=120000)
    assert 'company_id:' in page.locator('#pdf-text').text_content()
    page.locator('#next-setup').click()
    assert 'DEMO-001' in page.locator('#main').inner_text()
    page.locator('#start-session').click()


def reach_question(page):
    for _ in range(4):
        page.locator('#advance').click()
    page.locator('.quick-reply[data-confirmation="met"]').wait_for()
    assert page.locator('.quick-reply[data-confirmation="met"]').is_disabled()
    assert page.locator('.quick-reply[data-confirmation="violated"]').is_disabled()


def answer(page, confirmation):
    page.locator('#questions .deliver').last.click()
    page.locator('.quick-reply[data-confirmation="'+confirmation+'"]').last.click()


def policy(page, value):
    form = page.locator('.policy-form[data-id="E-BATTERY"]')
    form.locator('[name="policy"]').select_option(value)
    form.locator('button[type="submit"]').click()


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=args.browser, headless=True,
        args=['--no-sandbox', '--disable-gpu'])
    ctx, page = open_app(browser)
    page.screenshot(path=str(OUT/'01-home.png'), full_page=True)
    start_demo(page)
    # Check the actual source MP4 decodes and seeks in this Chromium build.
    video = page.locator('video[aria-label="원본 조립 영상"]')
    video.locator('..').evaluate('(el)=>el.open=true')
    video.evaluate('(el)=>el.load()')
    try:
        page.wait_for_function("()=>{const v=document.querySelector('video');return v&&v.readyState>=2&&v.videoWidth>0}", timeout=20000)
        video.evaluate('(el)=>el.currentTime=20.361')
        page.wait_for_function("()=>{const v=document.querySelector('video');return !v.seeking&&Math.abs(v.currentTime-20.361)<0.5&&v.readyState>=2}", timeout=20000)
        video_check = video.evaluate('(v)=>({status:"decoded_and_seeked",duration:v.duration,width:v.videoWidth,height:v.videoHeight,seekSeconds:v.currentTime,readyState:v.readyState})')
    except Exception as exc:
        video_check = video.evaluate('(v)=>({status:"browser_codec_limitation",readyState:v.readyState,error:v.error?{code:v.error.code,message:v.error.message}:null})')
        video_check['testMessage'] = str(exc)[:500]
        assert '장면 사진' in page.locator('.video-fallback').inner_text()
        video_check['frameFallbackVerified'] = True
    video.locator('..').evaluate('(el)=>el.open=false')
    reach_question(page)
    page.screenshot(path=str(OUT/'02-question.png'), full_page=True)
    before = snapshot(page, 'before-answer.json')
    assert before['mode'] == 'demo'
    assert before['assessments']['E-BATTERY']['verdict'] == 'unknown'
    assert before['assessments']['E-BATTERY']['origin'] == 'authored_demo'
    assert all('modelVerdict' not in a for a in before['assessments'].values())
    answer(page, 'met')
    confirmed = snapshot(page, 'after-positive-answer.json')
    assert confirmed['assessments']['E-BATTERY']['verdict'] == 'met'
    assert confirmed['assessments']['E-BATTERY']['origin'] == 'worker_confirmed'
    assert confirmed['assessments']['E-BATTERY']['rawExampleVerdict'] == 'unknown'
    for _ in range(2):
        page.locator('#advance').click()
    assert page.locator('#advance').is_disabled()
    assert '검사가 모두 완료되었습니다' in page.locator('#main').inner_text()
    page.screenshot(path=str(OUT/'03-complete.png'), full_page=True)
    completed = snapshot(page, 'completed-session.json')
    assert len(completed['assessments']) == 6
    assert all(a['verdict'] == 'met' for a in completed['assessments'].values())
    page.locator('#to-review').click()
    page.locator('#go-report').click()
    report = download(page, '#report-html', 'report-complete.html').read_text()
    inspection = download(page, '#inspection-html', 'inspection-complete.html').read_text()
    assert '강의용 예시' in report and '강의용 예시' in inspection
    assert 'data:image/' in report and 'data:image/' in inspection
    assert 'font/woff2;base64' in report or 'data:font/' in report
    assert '작업자' in report and 'worker_confirmed' not in page.locator('h1').inner_text()
    assert '실제 모델 응답' not in report
    db_path = download(page, '#export-db', 'completed.sqlite')
    with sqlite3.connect(db_path) as db:
        assert db.execute('select count(*) from criteria').fetchone()[0] == 6
        data = json.loads(db.execute('select payload from assessments where criterion_id=?', ('E-BATTERY',)).fetchone()[0])
        assert data['verdict'] == 'met' and data['rawExampleVerdict'] == 'unknown'
    page.screenshot(path=str(OUT/'04-report.png'), full_page=True)
    offline_ctx = browser.new_context(offline=True, viewport={'width':1280, 'height':1000})
    offline_page = offline_ctx.new_page()
    offline_page.on('pageerror', lambda error:page_errors.append(str(error)))
    offline_page.goto((OUT/'report-complete.html').resolve().as_uri(), wait_until='load')
    offline_page.wait_for_function('()=>Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
    assert offline_page.locator('img').count() >= 6
    assert '강의용 예시' in offline_page.locator('body').inner_text()
    offline_page.screenshot(path=str(OUT/'06-standalone-report.png'), full_page=True)
    offline_page.goto((OUT/'inspection-complete.html').resolve().as_uri(), wait_until='load')
    offline_page.wait_for_function('()=>Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
    assert '검수조서' in offline_page.locator('h1').inner_text()
    offline_page.screenshot(path=str(OUT/'07-standalone-inspection.png'), full_page=True)
    offline_ctx.close()
    page.reload(wait_until='networkidle')
    page.locator('#report-preview').wait_for(timeout=120000)
    assert snapshot(page, 'reloaded-session.json') == completed
    imported_ctx, imported = open_app(browser)
    imported.locator('#import-session').set_input_files(str(OUT/'completed-session.json'))
    imported.locator('#go-report').wait_for(timeout=120000)
    assert snapshot(imported, 'imported-session.json') == completed
    imported_ctx.close()
    page.locator('[data-page="review"]').click()
    policy(page, 'visual_only')
    strict = snapshot(page, 'strict-policy-session.json')
    assert strict['assessments']['E-BATTERY']['verdict'] == 'unknown'
    assert strict['assessments']['E-BATTERY']['workerConfirmation']['confirmation'] == 'met'
    assert strict['assessments']['E-BATTERY']['rawExampleVerdict'] == 'unknown'
    page.locator('#go-report').click()
    strict_report = download(page, '#report-html', 'report-strict.html').read_text()
    assert strict_report != report
    page.locator('[data-page="review"]').click()
    policy(page, 'worker_attestation')
    allowed = snapshot(page, 'restored-policy-session.json')
    assert allowed['assessments']['E-BATTERY']['verdict'] == 'met'
    page.locator('.reopen-answer[data-id="E-BATTERY"]').click()
    assert page.locator('.quick-reply[data-confirmation="violated"]').last.is_disabled()
    answer(page, 'violated')
    negative = snapshot(page, 'negative-answer-session.json')
    assert negative['assessments']['E-BATTERY']['verdict'] == 'violated'
    assert negative['assessments']['E-BATTERY']['rawExampleVerdict'] == 'unknown'
    assert any(a.get('confirmation') == 'met' for q in negative['questions'] for a in q['answers'])
    assert any(a.get('confirmation') == 'violated' for q in negative['questions'] for a in q['answers'])
    page.locator('#to-review').click()
    page.locator('#go-report').click()
    negative_report = download(page, '#report-html', 'report-negative.html').read_text()
    assert negative_report != report and '반대로' in negative_report
    page.locator('[data-page="run"]').click()
    page.set_viewport_size({'width':390, 'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    page.screenshot(path=str(OUT/'05-mobile.png'), full_page=True)
    assert not page_errors, page_errors
    assert not blocked_requests, blocked_requests
    assert not [r for r in requests if '/recordings/' in r['url']], 'Default demo fetched actual model captures'
    receipt = {'status':'passed', 'scenario':'electronics_demo', 'mode':'demo',
        'inputOrigin':'authored_demo', 'videoCheck':video_check, 'checks':[
            'default classroom and advanced legacy separation', 'real PDF extraction and SQLite compilation',
            'six checkpoints and six final met criteria', 'delivery required before quick answer',
            'positive and negative explicit worker response', 'raw example observation retained',
            'strict-policy hold and policy restoration', 'answer correction retains prior answers',
            'embedded-image and font reports plus inspection export', 'standalone report and inspection render offline', 'SQLite row matches current result',
            'exact reload and fresh-context import', 'mobile no horizontal overflow',
            'no actual-recording fetch, model API, POST or external request'],
        'localGetRequests':len(requests), 'externalOrNonGetRequests':len(blocked_requests),
        'pageErrors':page_errors, 'modelCalls':0, 'limitations':[
            'Authored classroom observation, not a model-quality or real product certification test.',
            'Speech playback availability and classroom speaker quality are not verified.'] + ([
            'This Chromium cannot decode the original H.264 MP4; video metadata/seek did not pass. Frame-based interaction and the explicit playback fallback passed.'
        ] if video_check.get('status') == 'browser_codec_limitation' else [])}
    (OUT/'E2E_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    ctx.close()
    browser.close()
