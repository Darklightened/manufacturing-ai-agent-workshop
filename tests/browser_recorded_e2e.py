"""Actual saved-model electronics UI rehearsal. No inference calls permitted.

Run after the model capture server is stopped, with scripts/serve.py on --url.
Optional Playwright dependency and browser executable are supplied by the tester.
This checks replay/controller/UI behavior, not independent recognition accuracy.
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
parser.add_argument('--output', type=Path, default=ROOT/'validation/recorded_electronics_v1')
args = parser.parse_args()
OUT = args.output
OUT.mkdir(parents=True, exist_ok=True)
PACK = json.loads((ROOT/'recordings/electronics_v1/pack.json').read_text())
base_origin = urlparse(args.url).netloc
page_errors, blocked_requests, requests = [], [], []


def download(page, selector, name):
    with page.expect_download(timeout=60000) as pending:
        page.locator(selector).click()
    dest = OUT/name
    pending.value.save_as(str(dest))
    return dest


def snapshot(page, name):
    return json.loads(download(page, '#backup', name).read_text())


def guard(route):
    req = route.request
    requests.append({'method':req.method, 'url':req.url})
    if urlparse(req.url).netloc != base_origin or req.method != 'GET':
        blocked_requests.append({'method':req.method, 'url':req.url})
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


def start_electronics(page):
    page.locator('#instructor-tools').evaluate('(el)=>el.open=true')
    page.locator('[data-select="electronics"]').click()
    page.locator('#compile').wait_for(timeout=120000)
    assert '응답 파일 무결성 검증 완료' in page.locator('main').inner_text()
    page.locator('#compile').click()
    page.locator('#next-setup').wait_for(timeout=120000)
    assert 'company_id:' in page.locator('#pdf-text').inner_text()
    page.locator('#next-setup').click()
    assert 'selected' in page.locator('[data-mode="recorded"]').get_attribute('class')
    page.locator('#start-session').click()


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=args.browser, headless=True,
        args=['--no-sandbox','--disable-gpu'])
    ctx, page = open_app(browser)
    start_electronics(page)
    for i, entry in enumerate(PACK['entries']):
        page.locator('#advance').click()
        assert '저장된 실제 모델 응답' in page.locator('#mode-banner').inner_text()
        if i == 0:
            page.locator('#model-inspector').evaluate('(el)=>el.open=true')
            assert entry['receipt']['id'] in page.locator('#model-inspector').inner_text()
            assert page.locator('#model-inspector .input-image-grid img').count() == len(entry['inputImages'])
            assert entry['responseContent'] in json.loads(page.locator('#raw-model-response').inner_text())['choices'][0]['message']['content']
    assert page.locator('#advance').is_disabled()
    before = snapshot(page, 'before-worker-session.json')
    assert before['session']['mode'] == 'recorded'
    assert before['session']['position'] == len(PACK['entries']) - 1
    unknown = [cid for cid, row in before['session']['assessments'].items() if row['modelVerdict']=='unknown']
    assert unknown, 'This real pack has no final unknown for the specified worker-confirmation exercise.'
    criterion = unknown[0]
    original_proposals = {cid:row['rawProposal'] for cid,row in before['session']['assessments'].items()}
    question = next(q for q in before['session']['questions'] if q['criterionId']==criterion and q['state'] not in ['resolved','superseded'])
    page.locator('#to-review').click()
    page.locator('#go-report').click()
    report_before = download(page, '#report-html', 'report-before.html').read_text()
    page.locator('[data-page="run"]').click()
    qselector = '[data-q="'+question['id']+'"]'
    page.locator(qselector+' .deliver').click()
    form = page.locator(qselector+' form')
    form.locator('[name="target"]').fill('wrong-workpiece')
    form.locator('[name="confirmation"]').select_option('met')
    form.locator('[name="text"]').fill('브라우저 검수용 작업자 답변: 해당 조건을 직접 확인했습니다.')
    form.locator('button[type="submit"]').click()
    assert '다릅니다' in page.locator('#toast').inner_text()
    rejected = snapshot(page, 'wrong-target-rejected.json')['session']
    assert not rejected['questions'][before['session']['questions'].index(question)]['answers']
    form.locator('[name="target"]').fill(question['target'])
    form.locator('button[type="submit"]').click()
    strict_answer = snapshot(page, 'strict-worker-session.json')['session']
    assert strict_answer['assessments'][criterion]['verdict']=='unknown'
    assert strict_answer['assessments'][criterion]['workerConfirmation']['confirmation']=='met'
    page.locator('#to-review').click()
    policy = page.locator('.policy-form[data-id="'+criterion+'"]')
    policy.locator('[name="policy"]').select_option('worker_attestation')
    policy.locator('button').click()
    allowed = snapshot(page, 'worker-allowed-session.json')['session']
    assert allowed['assessments'][criterion]['verdict']=='met'
    assert allowed['assessments'][criterion]['origin']=='worker_confirmed'
    assert {cid:row['rawProposal'] for cid,row in allowed['assessments'].items()}==original_proposals
    assert '작업자 확인 허용' in page.locator('tr[data-criterion="'+criterion+'"]').inner_text()
    page.screenshot(path=str(OUT/'review-worker-allowed.png'), full_page=True)
    page.locator('#go-report').click()
    report_after = download(page, '#report-html', 'report-worker-allowed.html').read_text()
    inspection = download(page, '#inspection-html', 'inspection-worker-allowed.html').read_text()
    assert report_before != report_after
    assert 'data:image/' in report_after and ('data:font/' in report_after or 'font/woff2;base64' in report_after)
    assert 'worker_attestation' in report_after and '작업자' in report_after
    assert 'rawProposal' in inspection and 'worker_confirmed' in inspection
    audit = json.loads(download(page,'#export-audit','decision-audit.json').read_text())
    audit_row = next(r for r in audit['rows'] if r['criterionId']==criterion)
    assert audit_row['modelVerdict']=='unknown' and audit_row['currentVerdict']=='met'
    assert audit['inferenceDuringReplay'] is False
    db_path = download(page, '#export-db', 'worker-allowed.sqlite')
    db = sqlite3.connect(db_path)
    assert db.execute('select allow_worker from criteria where id=?',(criterion,)).fetchone()[0] == 1
    payload = json.loads(db.execute('select payload from assessments where criterion_id=?',(criterion,)).fetchone()[0])
    assert payload['verdict']=='met' and payload['origin']=='worker_confirmed'
    db.close()
    page.screenshot(path=str(OUT/'report-worker-allowed.png'), full_page=True)
    page.reload(wait_until='networkidle')
    page.locator('#report-preview').wait_for(timeout=120000)
    restored = snapshot(page, 'restored-session.json')['session']
    assert restored == allowed
    # Import exact journal in a fresh browser storage context.
    imported_ctx, imported = open_app(browser)
    imported.locator('#import-session').set_input_files(str(OUT/'worker-allowed-session.json'))
    imported.locator('#go-report').wait_for(timeout=120000)
    assert snapshot(imported,'imported-session.json')['session'] == allowed
    imported_ctx.close()
    # Restore strict policy: original uncertainty returns, worker statement remains.
    page.locator('[data-page="review"]').click()
    policy=page.locator('.policy-form[data-id="'+criterion+'"]')
    policy.locator('[name="policy"]').select_option('visual_only');policy.locator('button').click()
    reverted=snapshot(page,'policy-reverted-session.json')['session']
    assert reverted['assessments'][criterion]['verdict']=='unknown'
    assert reverted['assessments'][criterion]['workerConfirmation']['confirmation']=='met'
    assert reverted['assessments'][criterion]['rawProposal']==original_proposals[criterion]
    page.locator('#go-report').click()
    report_reverted=download(page,'#report-html','report-policy-reverted.html').read_text()
    assert report_reverted != report_after
    # New answer explicitly reports a nonconforming observation; no model response is modified.
    page.locator('[data-page="run"]').click()
    newq=next(q for q in reverted['questions'] if q['criterionId']==criterion and q['state'] not in ['resolved','superseded'])
    qselector='[data-q="'+newq['id']+'"]';page.locator(qselector+' .deliver').click()
    form=page.locator(qselector+' form')
    form.locator('[name="confirmation"]').select_option('violated')
    form.locator('[name="text"]').fill('브라우저 검수용 다른 답변: 조건과 다른 상태를 직접 확인했습니다.')
    form.locator('button[type="submit"]').click()
    page.locator('#to-review').click();policy=page.locator('.policy-form[data-id="'+criterion+'"]')
    policy.locator('[name="policy"]').select_option('worker_attestation');policy.locator('button').click()
    negative=snapshot(page,'worker-negative-session.json')['session']
    assert negative['assessments'][criterion]['verdict']=='violated'
    assert negative['assessments'][criterion]['rawProposal']==original_proposals[criterion]
    page.locator('#go-report').click();download(page,'#report-html','report-worker-negative.html')
    ctx.close()
    # Forged session must be rejected, rather than silently replacing recorded observations.
    forged=json.loads((OUT/'worker-allowed-session.json').read_text())
    forged['session']['assessments'][criterion]['rawProposal']['reason']='forged model statement'
    forged_path=OUT/'tampered-session-rejected.json';forged_path.write_text(json.dumps(forged,ensure_ascii=False))
    bad_ctx,bad=open_app(browser)
    bad.locator('#import-session').set_input_files(str(forged_path))
    bad.wait_for_function("document.querySelector('#toast').style.display==='block'",timeout=120000)
    assert bad.locator('#go-report').count()==0
    bad_ctx.close()
    # A missing raw HTTP response prevents recorded mode. Explicit fixture mode stays distinct.
    bad_ctx,bad=open_app(browser)
    missing=PACK['entries'][0]['receipt']['responsePath']
    bad_ctx.route('**/'+missing,lambda route:route.fulfill(status=404,body='missing response'))
    bad.locator('#instructor-tools').evaluate('(el)=>el.open=true')
    bad.locator('[data-select="electronics"]').click();bad.locator('#compile').wait_for(timeout=120000)
    assert '실제 응답 재생 불가' in bad.locator('main').inner_text()
    bad.locator('#compile').click();bad.locator('#next-setup').wait_for(timeout=60000);bad.locator('#next-setup').click()
    assert bad.locator('[data-mode="recorded"]').is_disabled()
    assert 'selected' in bad.locator('[data-mode="fixture"]').get_attribute('class')
    bad_ctx.close()
    mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True)
    mobile.route('**/*',guard);mp=mobile.new_page();mp.goto(args.url,wait_until='networkidle')
    mp.locator('#import-session').set_input_files(str(OUT/'worker-allowed-session.json'))
    mp.locator('#go-report').wait_for(timeout=120000)
    assert mp.evaluate('document.documentElement.scrollWidth<=innerWidth')
    mp.screenshot(path=str(OUT/'mobile-recorded-review.png'),full_page=True)
    mobile.close();browser.close()

assert not page_errors,page_errors
assert not blocked_requests,blocked_requests
receipt={
 'schema':'seminar.recorded-browser-e2e.v1','status':'passed', 'url':args.url,
 'packId':PACK['id'],'model':PACK['model'],'checkpoints':len(PACK['entries']),
 'workerPolicyCriterion':criterion,'ruleAndReplyStates':['unknown','worker_confirmed:met','unknown:policy_reverted','worker_confirmed:violated'],
 'sourcePdfExtraction':True,'sqlitePolicyAndVerdict':True,'actualRequestResponseInspector':True,
 'rawProposalsUnchanged':True,'wrongTargetRejected':True,'refreshAndImportExact':True,
 'forgedSessionRejected':True,'missingResponseRejectsRecordedMode':True,
 'reportsWithEmbeddedImagesAndFont':True,'mobileOverflow':False,
 'browserRequests':len(requests),'nonGetRequests':0,'externalRequests':0,'inferenceCalls':0,
 'pageErrors':page_errors,'scope':'Actual saved model responses and deterministic controller/browser behavior; worker test answers are authored and not independent physical quality truth.'
}
(OUT/'browser_e2e.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(receipt,ensure_ascii=False))
