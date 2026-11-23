"""Exercise company-folder onboarding through the actual local browser UI.

Authored educational outputs, real PDF preview, SQL draft/correction and downstream
controller. No model/GPU calls or public load testing. Each invocation writes into
an immutable attempt folder chosen by --output.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import zipfile
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:8937/')
parser.add_argument('--extra-gates-only', action='store_true')
parser.add_argument('--network-only', action='store_true')
parser.add_argument('--transfer-only', action='store_true')
parser.add_argument('--browser', default=None)
parser.add_argument('--output', type=Path, default=ROOT/'validation/company_build_v2'/('browser_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')))
args = parser.parse_args()
OUT = args.output
OUT.mkdir(parents=True, exist_ok=False)
base_origin = urlparse(args.url).netloc
requests, blocked_requests, page_errors, http_errors, checks, stages = [], [], [], [], [], []
receipt = {'status':'running','scope':'local browser company_build_v2; authored examples, not AI recognition or public capacity test','modelCalls':0,'gpuCalls':0,'checks':checks}
active_page = None


def save_receipt():
    receipt.update(localGetRequests=len(requests), blockedRequests=blocked_requests,
                   pageErrors=page_errors, httpErrors=http_errors, stages=stages)
    (OUT/'E2E_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')


def checked(label):
    checks.append(label)
    save_receipt()


def guard(route):
    req = route.request
    if urlparse(req.url).scheme in {'blob','data'}:
        route.continue_()
        return
    requests.append({'method':req.method,'url':req.url})
    if urlparse(req.url).netloc != base_origin or req.method != 'GET':
        blocked_requests.append({'method':req.method,'url':req.url})
        route.abort()
    else:
        route.continue_()


def open_app(browser):
    ctx=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
    ctx.route('**/*',guard)
    p=ctx.new_page()
    p.on('pageerror',lambda err:page_errors.append(str(err)))
    p.on('response',lambda response:http_errors.append({'url':response.url,'status':response.status}) if response.status>=400 else None)
    p.goto(args.url,wait_until='networkidle')
    p.locator('[data-select="electronics_demo"]').click()
    p.locator('#company-folder').wait_for(state='attached')
    return ctx,p


def shot(p,name):
    p.screenshot(path=str(OUT/name),full_page=True)


def download(p,selector,name):
    with p.expect_download(timeout=60000) as pending:
        p.locator(selector).click()
    dest=OUT/name
    pending.value.save_as(str(dest))
    return dest


def row_id(p,extension,contains=''):
    result=p.locator('#company-file-list [data-file-select]').evaluate_all('''(els,args)=>{
      const [extension,contains]=args;
      for(const el of els){const row=el.closest('[data-file-row]')||el.closest('.company-file-row')||el.parentElement.parentElement;
        const text=row.textContent; if(text.toLowerCase().includes(extension)&&text.includes(contains))return el.dataset.fileSelect;}
      return null;
    }''',[extension,contains])
    assert result, f'No uploaded file row: {extension}, {contains}'
    return result


def preview(p,identifier,kind):
    count=[]
    def on_download(d):count.append(d.suggested_filename)
    p.on('download',on_download)
    p.locator('[data-preview="'+identifier+'"]').click()
    panel=p.locator('#company-preview')
    if kind=='pdf':
        panel.locator('canvas').first.wait_for(timeout=30000)
        p.wait_for_function('()=>{const c=document.querySelector("#company-preview canvas");return c&&c.width>0&&c.height>0}')
    elif kind=='image':
        panel.locator('img').first.wait_for(timeout=15000)
        p.wait_for_function('()=>{const i=document.querySelector("#company-preview img");return i&&i.complete&&i.naturalWidth>0}')
    elif kind=='text':
        panel.locator('pre,table').first.wait_for(timeout=15000)
    p.wait_for_timeout(150)
    p.remove_listener('download',on_download)
    assert not count, 'Preview triggered a download'
    return panel.inner_text()


def db_inspect(path):
    with sqlite3.connect(path) as db:
        names=[x[0] for x in db.execute("select name from sqlite_master where type='table' order by name")]
        result={'tables':names,'criteria':db.execute('select id,task_id,label from criteria order by id').fetchall()}
        for name in names:
            if name not in {'company','tasks','criteria'}:
                result[name]=db.execute('select * from "'+name.replace('"','""')+'"').fetchall()
        return result


def state_dump(p):
    return p.evaluate('''async()=>await new Promise((resolve,reject)=>{const r=indexedDB.open('dynin-seminar-classroom-v1');r.onsuccess=()=>{const db=r.result;const t=db.transaction('state');const x=t.objectStore('state').get('current');x.onsuccess=()=>{resolve(x.result);db.close()};x.onerror=()=>reject(x.error)};r.onerror=()=>reject(r.error)})''')


def wait_review(p):
    started=time.monotonic()
    while time.monotonic()-started<90:
        if p.locator('#company-review').count():break
        if p.locator('#company-progress').count():
            now={'stage':p.locator('#company-stage-name').inner_text(),
                 'percent':p.locator('#company-progress').get_attribute('aria-valuenow'),
                 'log':p.locator('#company-logs').inner_text()}
            if not stages or stages[-1]!=now:stages.append(now)
        p.wait_for_timeout(180)
    p.locator('#company-review').wait_for(timeout=1000)
    assert len({x['stage'] for x in stages})>=4, stages
    assert len({x['log'] for x in stages})>=4, stages
    assert any(int(x['percent'] or -1)>0 for x in stages)
    assert any(int(x['percent'] or -1)<100 for x in stages)


try:
    if args.transfer_only:
        source_paths=['app.mjs','packages/company-build/ui.mjs','packages/company-build/state.mjs','tests/browser_company_build.py']
        receipt['sourceSha256']={rel:hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() for rel in source_paths}
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox','--disable-gpu'])
            ctx,p=open_app(browser);active_page=p
            p.locator('#company-bundled').evaluate('(el)=>el.closest("details").open=true')
            p.locator('#company-bundled').click();p.locator('#company-file-list').wait_for()
            p.locator('#compile').click();wait_review(p)
            p.locator('#review-task').select_option('battery')
            p.locator('#review-note').fill('작업지시서 배터리 삽입 단계와 대조')
            p.locator('#save-review').click();p.locator('#show-ontology').click()
            p.locator('#company-ontology').wait_for();p.locator('#next-setup').click()
            p.locator('#start-session').click();p.locator('#advance').click()
            exported=download(p,'#backup','new-with-company-history.json')
            original=json.loads(exported.read_text())
            history=original['companyBuild'];assert history['files']==[]
            assert history['state']['phase']=='ontology'
            assert len(history['state']['files'])==7
            assert any(e['type']=='task_mapping_reviewed' and e['note']=='작업지시서 배터리 삽입 단계와 대조' for e in history['state']['events'])
            checked('new JSON export includes approved review history and file metadata, excluding original File bytes')
            ctx.close()
            ctx,p=open_app(browser);active_page=p
            p.locator('#import-session').set_input_files(str(exported));p.locator('#go-report').wait_for()
            imported=json.loads(download(p,'#backup','new-imported-history.json').read_text())
            assert imported['session']==original['session']
            assert imported['companyBuild']['state']==original['companyBuild']['state']
            assert imported['companyBuild']['files']==[]
            p.locator('[data-page="documents"]').click();p.locator('#company-ontology').wait_for()
            p.locator('[data-ontology-task="battery"]').click()
            assert 'E-BATTERY' in p.locator('#ontology-detail').inner_text()
            p.locator('#company-back-review').click();p.locator('#company-review').wait_for()
            assert p.locator('#review-task').input_value()=='battery'
            assert p.locator('#review-task').is_disabled()
            assert p.locator('#company-back-files').is_disabled()
            p.locator('#company-query-table').select_option('build_audit')
            assert '작업지시서 배터리 삽입 단계와 대조' in p.locator('.company-sql-table').inner_text()
            shot(p,'01-transferred-review-audit.png')
            p.reload(wait_until='networkidle');p.locator('#company-ontology').wait_for()
            checked('fresh-context import and reload preserve ontology and immutable learner review audit')
            before=state_dump(p)
            tampered=json.loads(exported.read_text())
            next(c for c in tampered['companyBuild']['state']['draftBundle']['criteria'] if c['id']=='E-BATTERY')['taskId']='switch'
            bad=OUT/'tampered-company-history.json';bad.write_text(json.dumps(tampered,ensure_ascii=False))
            p.locator('#import-session').set_input_files(str(bad))
            p.wait_for_function('()=>!document.querySelector("#import-session").disabled')
            assert '다릅니다' in p.locator('#toast').inner_text()
            after=state_dump(p)
            assert after['session']==before['session']
            assert after['companyBuild']['state']==before['companyBuild']['state']
            assert p.locator('#company-ontology').is_visible()
            shot(p,'02-tampered-import-rejected.png')
            checked('tampered draft mapping is rejected before replacing the active session or reviewed company state')
            ctx.close()
            old=json.loads(exported.read_text());old.pop('companyBuild')
            legacy=OUT/'legacy-without-company-history.json';legacy.write_text(json.dumps(old,ensure_ascii=False))
            ctx,p=open_app(browser);active_page=p
            p.locator('#import-session').set_input_files(str(legacy));p.locator('#go-report').wait_for()
            p.locator('[data-page="documents"]').click()
            assert '자료 구축 이력이 포함되어 있지 않습니다' in p.locator('#main').inner_text()
            assert p.locator('#main table tbody tr').count()==6
            assert not p.locator('#company-folder').count()
            assert not p.locator('#compile').count()
            assert p.locator('#next-setup').is_enabled()
            shot(p,'03-legacy-company-summary.png')
            p.locator('#next-setup').click();p.locator('#start-session').click()
            continued=json.loads(download(p,'#backup','legacy-continued.json').read_text())
            assert continued['session']==original['session']
            assert 'companyBuild' not in continued
            checked('legacy export without build history shows six read-only criteria and continues the original session')
            ctx.close();browser.close();active_page=None
        assert not page_errors and not blocked_requests and not http_errors
        receipt['status']='passed'
        receipt['sourceUnchangedDuringTest']=all(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==sha for rel,sha in receipt['sourceSha256'].items())
        assert receipt['sourceUnchangedDuringTest']
        save_receipt()
        print(json.dumps({'status':'passed','checks':len(checks),'requests':len(requests),'output':str(OUT)},ensure_ascii=False))
        raise SystemExit(0)
    if args.network_only:

        source_paths=['app.mjs','packages/company-build/ui.mjs','packages/company-build/state.mjs','tests/browser_company_build.py']
        receipt['sourceSha256']={rel:hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() for rel in source_paths}
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox','--disable-gpu'])
            ctx,p=open_app(browser);active_page=p
            held=[]
            p.route('**/assets/company-materials/manifest.json',lambda route:held.append(route))
            p.locator('#company-bundled').evaluate('(el)=>el.closest("details").open=true')
            p.locator('#company-bundled').click()
            for _ in range(50):
                if held:break
                p.wait_for_timeout(100)
            assert len(held)==1
            assert p.locator('[data-page="home"]').is_disabled()
            assert p.locator('[data-page="setup"]').is_disabled()
            assert p.locator('#compile').is_disabled()
            assert p.locator('#choose-company-folder').is_disabled()
            shot(p,'01-delayed-bundled-guard.png')
            held.pop().continue_()
            p.locator('#company-file-list').wait_for(timeout=30000)
            p.wait_for_function('()=>!document.querySelector("[data-page=home]").disabled')
            assert p.locator('#company-file-list [data-file-select]').count()==7
            assert not p.locator('#compile').is_disabled()
            checked('delayed bundled request blocks navigation/other uploads until same-scenario adoption completes')
            ctx.close()
            ctx,p=open_app(browser);active_page=p
            p.locator('#company-files').set_input_files({'name':'retained-note.txt','mimeType':'text/plain','buffer':b'Keep the previous document set on network failure.'})
            p.locator('#company-file-list [data-file-select]').wait_for()
            p.wait_for_timeout(200)
            before=state_dump(p)
            hits=[]
            def unavailable(route):
                hits.append(route.request.url)
                route.fulfill(status=503,content_type='text/plain',body='controlled temporary failure')
            p.route('**/assets/company-materials/manifest.json',unavailable)
            p.locator('#company-bundled').evaluate('(el)=>el.closest("details").open=true')
            p.locator('#company-bundled').click()
            p.wait_for_function('()=>!document.querySelector("[data-page=home]").disabled')
            assert len(hits)==1, 'Unexpected automatic request retry'
            assert 'retained-note.txt' in p.locator('#company-file-list').inner_text()
            assert p.locator('#company-file-list [data-file-select]').count()==1
            assert '불러오지 못' in p.locator('#main').inner_text()
            failed=state_dump(p)
            assert failed['companyBuild']['state']==before['companyBuild']['state']
            shot(p,'02-bundled-failure-preserves-files.png')
            p.unroute('**/assets/company-materials/manifest.json',unavailable)
            p.locator('#company-bundled').evaluate('(el)=>el.closest("details").open=true')
            p.locator('#company-bundled').click()
            p.wait_for_function('()=>document.querySelectorAll("#company-file-list [data-file-select]").length===7')
            assert not p.locator('#compile').is_disabled()
            assert 'retained-note.txt' not in p.locator('#company-file-list').inner_text()
            checked('503 keeps prior files and releases guard; explicit retry adopts complete bundled company')
            ctx.close();browser.close();active_page=None
        assert not page_errors and not blocked_requests
        assert len(http_errors)==1 and http_errors[0]['status']==503 and 'manifest.json' in http_errors[0]['url']
        receipt.update(status='passed',expectedHttpFailures=http_errors,unexpectedHttpErrors=[])
        receipt['sourceUnchangedDuringTest']=all(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==sha for rel,sha in receipt['sourceSha256'].items())
        assert receipt['sourceUnchangedDuringTest']
        save_receipt()
        print(json.dumps({'status':'passed','checks':len(checks),'expectedHttpFailures':1,'output':str(OUT)},ensure_ascii=False))
        raise SystemExit(0)
    if args.extra_gates_only:

        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox','--disable-gpu'])
            ctx,p=open_app(browser);active_page=p
            p.locator('#company-bundled').evaluate('(el)=>el.closest("details").open=true')
            p.locator('#company-bundled').click()
            p.locator('#company-file-list').wait_for()
            p.locator('#compile').click();wait_review(p)
            p.locator('#review-task').select_option('battery');p.locator('#save-review').click()
            p.locator('#show-ontology').click();p.locator('#company-ontology').wait_for()
            before=state_dump(p)
            assert before['bundle'] and before['companyBuild']['state']['phase']=='ontology'
            p.locator('#company-back-review').click();p.locator('#company-back-files').click()
            p.locator('#company-file-list').wait_for()
            p.locator('#company-file-list [data-file-select]').first.uncheck()
            p.wait_for_timeout(300)
            changed=state_dump(p)
            assert changed['bundle'] is None
            assert changed['companyBuild']['state']['phase']=='selection'
            assert changed['companyBuild']['state']['archives']
            assert any(a['phase']=='ontology' for a in changed['companyBuild']['state']['archives'])
            p.locator('[data-page="setup"]').click()
            assert p.locator('#company-file-list').is_visible()
            assert not p.locator('#next-setup').count()
            shot(p,'01-invalidated-after-selection.png')
            checked('changing reviewed source archives completed outcome, clears active bundle and blocks setup')
            p.locator('#compile').click();p.locator('#company-progress').wait_for()
            p.wait_for_timeout(1000)
            p.reload(wait_until='networkidle')
            p.locator('#company-file-list').wait_for(timeout=30000)
            assert not p.locator('#compile').is_disabled()
            assert not p.locator('#company-ontology').count()
            p.wait_for_timeout(300)
            interrupted=state_dump(p)
            assert interrupted['bundle'] is None
            state=interrupted['companyBuild']['state']
            (OUT/'GATE_STATES.json').write_text(json.dumps({'before':before,'changed':changed,'interrupted':interrupted},ensure_ascii=False,indent=2)+'\n')
            assert state['phase']=='selection'
            assert any(e['type']=='build_interrupted' for e in state['events'])
            assert any(a['reason']=='interrupted_build' for a in state['archives'])
            checked('reload during processing preserves interrupted outcome and offers fresh build without false completion')
            (OUT/'GATE_STATES.json').write_text(json.dumps({'before':before,'changed':changed,'interrupted':interrupted},ensure_ascii=False,indent=2)+'\n')
            ctx.close();browser.close();active_page=None
        assert not page_errors and not blocked_requests and not http_errors
        receipt['status']='passed';save_receipt()
        print(json.dumps({'status':'passed','checks':len(checks),'requests':len(requests),'output':str(OUT)},ensure_ascii=False))
        raise SystemExit(0)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox','--disable-gpu'])
        ctx,p=open_app(browser);active_page=p
        assert '강의용' in p.locator('#main').inner_text()
        shot(p,'01-folder-start.png')
        zipped=download(p,'#company-zip','company-practice-materials.zip')
        assert hashlib.sha256(zipped.read_bytes()).hexdigest()==hashlib.sha256((ROOT/'assets/company-materials/company-practice-materials.zip').read_bytes()).hexdigest()
        with zipfile.ZipFile(zipped) as archive:
            assert archive.testzip() is None
            assert any(n.startswith('다온에듀테크/') for n in archive.namelist())
            assert any(n.startswith('다온정밀/') for n in archive.namelist())
        checked('company ZIP button downloads exact valid archive grouped by company name')
        manifest=json.loads((ROOT/'assets/company-materials/manifest.json').read_text())
        company=next(x for x in manifest['companies'] if 'electronics_demo' in x['scenarioIds'])
        source_path=ROOT/company['files'][0]['path']
        company_dir=next(q for q in [source_path.parent,*source_path.parents] if q.name==company['folder'])
        expected_files=len([x for x in company_dir.rglob('*') if x.is_file()])
        p.locator('#company-folder').set_input_files(str(company_dir))
        p.wait_for_function('(n)=>document.querySelectorAll("#company-file-list [data-file-select]").length===n',arg=expected_files)
        assert expected_files>=5
        checked('native directory input lists company files with actual names')
        pdf_id=row_id(p,'.pdf');csv_id=row_id(p,'.csv');svg_id=row_id(p,'.svg')
        preview(p,pdf_id,'pdf');shot(p,'02-pdf-preview.png')
        preview(p,csv_id,'text');shot(p,'03-csv-preview.png')
        preview(p,svg_id,'image');shot(p,'04-drawing-preview.png')
        checked('PDF canvas, CSV table/text and SVG image preview in page without downloads')
        ids=p.locator('#company-file-list [data-file-select]').evaluate_all('(els)=>els.map(x=>x.dataset.fileSelect)')
        for identifier in ids:
            p.locator('[data-file-select="'+identifier+'"]').uncheck()
        assert p.locator('#compile').is_disabled()
        p.locator('[data-file-select="'+csv_id+'"]').check()
        assert not p.locator('#compile').is_disabled()
        # Reload must preserve the chosen subset and file bytes needed for preview.
        p.wait_for_timeout(400)
        p.reload(wait_until='networkidle')
        p.locator('#company-file-list').wait_for()
        selected=p.locator('#company-file-list [data-file-select]:checked')
        assert selected.count()==1 and selected.get_attribute('data-file-select')==csv_id
        preview(p,pdf_id,'pdf')
        checked('zero selection blocks build; subset and uploaded PDF bytes survive reload')
        p.locator('#compile').click()
        wait_review(p)
        shot(p,'05-draft-sql-review.png')
        assert p.locator('#review-task').input_value()=='circuit'
        assert p.locator('#show-ontology').is_disabled()
        p.locator('[data-page="setup"]').click()
        assert p.locator('#company-review').is_visible(), 'Navigation bypassed unreviewed DB'
        draft=db_inspect(download(p,'#company-export-db','draft.sqlite'))
        assert next(r for r in draft['criteria'] if r[0]=='E-BATTERY')[1]=='circuit'
        checked('staged progress/logs and real SQLite draft; unresolved review blocks downstream')
        p.locator('#review-task').select_option('switch')
        p.locator('#save-review').click()
        assert p.locator('#show-ontology').is_disabled()
        p.locator('#review-task').select_option('battery')
        p.locator('#save-review').click()
        p.wait_for_function('()=>!document.querySelector("#show-ontology").disabled')
        corrected=db_inspect(download(p,'#company-export-db','corrected.sqlite'))
        assert next(r for r in corrected['criteria'] if r[0]=='E-BATTERY')[1]=='battery'
        assert corrected!=draft
        extras=[n for n in corrected['tables'] if 'audit' in n or 'review' in n]
        assert extras, corrected
        (OUT/'SQL_REVIEW.json').write_text(json.dumps({'draft':draft,'corrected':corrected},ensure_ascii=False,indent=2)+'\n')
        checked('incorrect review answer remains blocked; correct task updates SQL and preserves audit')
        p.wait_for_timeout(300)
        p.reload(wait_until='networkidle')
        p.locator('#show-ontology').wait_for()
        assert not p.locator('#show-ontology').is_disabled()
        assert p.locator('#review-task').input_value()=='battery'
        p.locator('#show-ontology').click()
        p.locator('#company-ontology').wait_for()
        p.locator('[data-ontology-task="battery"]').click()
        assert 'E-BATTERY' in p.locator('#company-ontology').inner_text()
        shot(p,'06-ontology.png')
        p.set_viewport_size({'width':390,'height':844})
        assert p.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        shot(p,'07-ontology-mobile.png')
        p.set_viewport_size({'width':1440,'height':1000})
        checked('review restoration and clickable ontology agree with corrected task and fit mobile')
        p.locator('#next-setup').click();p.locator('#start-session').click()
        for _ in range(4):p.locator('#advance').click()
        p.locator('#questions .deliver').last.click()
        p.locator('.quick-reply[data-confirmation="met"]').last.click()
        for _ in range(2):p.locator('#advance').click()
        p.locator('#to-review').click();p.locator('#go-report').click()
        report=download(p,'#inspection-html','downstream-inspection.html').read_text()
        assert '강의용' in report and 'data:image/' in report
        completed=json.loads(download(p,'#backup','downstream-session.json').read_text())['session']
        assert len(completed['assessments'])==6
        assert all(a['verdict']=='met' for a in completed['assessments'].values())
        p.reload(wait_until='networkidle');p.locator('#report-preview').wait_for()
        again=json.loads(download(p,'#backup','downstream-reload.json').read_text())['session']
        assert again==completed
        checked('reviewed company bundle continues through six electronic scenes, worker answer, report and exact session reload')
        ctx.close()
        # Independent context proves local files are previewed, not interpreted as markup.
        ctx,p=open_app(browser);active_page=p
        malicious='<img src=x onerror="globalThis.COMPANY_PREVIEW_PWNED=1"><script>globalThis.COMPANY_PREVIEW_PWNED=1</script>'
        p.locator('#company-files').set_input_files([
            {'name':'unsafe-note.txt','mimeType':'text/plain','buffer':malicious.encode()},
            {'name':'broken.pdf','mimeType':'application/pdf','buffer':b'%PDF-1.7\nnot-a-valid-pdf'},
        ])
        p.locator('#company-file-list [data-file-select]').first.wait_for()
        bad_text=row_id(p,'.txt')
        contents=preview(p,bad_text,'text')
        assert '<script>' in contents
        assert p.evaluate('globalThis.COMPANY_PREVIEW_PWNED||0')==0
        p.locator('[data-preview="'+row_id(p,'.pdf')+'"]').click()
        p.wait_for_timeout(1200)
        assert not p.locator('#company-preview canvas').count()
        assert any(s in p.locator('#company-preview').inner_text() for s in ['실패','못','오류','유효','지원'])
        assert p.evaluate('globalThis.COMPANY_PREVIEW_PWNED||0')==0
        checked('file-picker fallback previews literal hostile text safely; malformed PDF shows recoverable preview error')
        ctx.close();browser.close();active_page=None
    assert not page_errors,page_errors
    assert not blocked_requests,blocked_requests
    assert not http_errors,http_errors
    assert not [r for r in requests if '/recordings/' in r['url']], 'Unexpected model-recording fetch'
    receipt['status']='passed'
    receipt['limitations']=['Local browser implementation test only; authored fixed output irrespective selected file subset.','No external model/OCR/ASR, public deployment, physical metrology or classroom Wi-Fi test.','Original electronics H.264 decoder and audible TTS not exercised; scenes use still images.']
    save_receipt()
    print(json.dumps({'status':'passed','checks':len(checks),'requests':len(requests),'output':str(OUT)},ensure_ascii=False))
except Exception as exc:
    receipt.update(status='failed',error=str(exc),exceptionType=type(exc).__name__)
    if active_page:
        try:shot(active_page,'failure.png')
        except Exception:pass
    save_receipt()
    raise
