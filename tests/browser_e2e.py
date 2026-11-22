"""Real browser rehearsal. Run against scripts/serve.py; optional --browser executable.
Install the optional playwright test dependency separately. No model/GPU calls.
"""
import argparse, json, sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:8921/')
parser.add_argument('--browser',default=None)
parser.add_argument('--output',type=Path,default=ROOT/'validation')
args=parser.parse_args()
OUT=args.output;OUT.mkdir(parents=True,exist_ok=True)
errors=[];results=[]

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox','--disable-gpu'])
    for sid,base in [('electronics','electronics'),('electronics_error','electronics'),('instruments','instruments'),('mechanical','mechanical'),('maintenance','mechanical')]:
        ctx=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(args.url,wait_until='networkidle');page.evaluate('document.fonts.ready')
        assert page.locator('.cards [data-select]').count()==3
        if sid=='electronics':page.screenshot(path=str(OUT/'home.png'),full_page=True)
        if base in ['electronics','instruments']:page.locator('#instructor-tools').evaluate('(el)=>el.open=true')
        page.locator(f'[data-select="{base}"]').click()
        if sid!=base:page.locator(f'[data-variant="{sid}"]').click()
        page.locator('#compile').click();page.locator('#next-setup').wait_for(timeout=60000)
        assert 'company_id:' in page.locator('#pdf-text').inner_text()
        assert 'process_id:' in page.locator('#pdf-text').inner_text()
        if sid=='electronics':page.screenshot(path=str(OUT/'documents.png'),full_page=True)
        page.locator('#next-setup').click()
        # This regression suite exercises the unchanged authored teaching fixtures.
        # Electronics now defaults to a verified recording; choose fixture explicitly.
        page.locator('[data-mode="fixture"]').click()
        page.locator('#start-session').click()
        config=json.loads((ROOT/f'scenarios/{sid}/scenario.json').read_text())
        for i in range(len(config['checkpoints'])):
            page.locator('#advance').click()
            if sid=='instruments' and i==1:
                page.locator('.deliver').first.click()
                form=page.locator('.answer-form').first
                form.locator('input[name="target"]').fill('wrong-object')
                form.locator('input[name="value"]').fill('5.78')
                form.locator('input[name="unit"]').fill('mm')
                form.locator('button[type="submit"]').click()
                assert '다릅니다' in page.locator('#toast').inner_text()
                form.locator('input[name="target"]').fill('micrometer-case')
                form.locator('button[type="submit"]').click()
                assert '5.78' in page.locator('tbody').inner_text()
        assert page.locator('#advance').is_disabled()
        if sid=='instruments':
            page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(OUT/'run.png'),full_page=True)
        page.locator('#to-review').click()
        if sid=='instruments':
            f=page.locator('.range-form[data-id="I-DIGITAL"]')
            f.locator('input[name="upper"]').fill('26.2');f.locator('button').click()
            assert '불일치' in page.locator('tbody tr').first.inner_text()
        page.locator('#go-report').click()
        with page.expect_download() as d:page.locator('#export-json').click()
        saved=OUT/f'{sid}-session.json';d.value.save_as(str(saved));session=json.loads(saved.read_text())['session']
        assert session['mode']=='fixture'
        assert session['position']==len(config['checkpoints'])-1
        if sid=='maintenance':
            assert any(e['type']=='invalidated' for e in session['events'])
            assert session['assessments']['R-CURRENT']['attempt']==2
        if sid=='instruments':
            with page.expect_download() as d:page.locator('#report-html').click()
            d.value.save_as(str(OUT/'sample-report.html'))
            report=(OUT/'sample-report.html').read_text()
            assert 'data:image/' in report and 'base64,' in report and '5.78' in report
            assert 'Noto Sans KR' in report
            with page.expect_download() as d:page.locator('#inspection-html').click()
            d.value.save_as(str(OUT/'sample-inspection.html'))
            inspection=(OUT/'sample-inspection.html').read_text()
            assert 'data:image/' in inspection and '26.2' in inspection
            with page.expect_download() as d:page.locator('#export-db').click()
            d.value.save_as(str(OUT/'sample.sqlite'))
            db=sqlite3.connect(OUT/'sample.sqlite')
            assert db.execute('select count(*) from criteria').fetchone()[0]==3
            assert db.execute('select upper_bound from criteria where id="I-DIGITAL"').fetchone()[0]=='26.2'
            db.close()
            page.screenshot(path=str(OUT/'report-screen.png'),full_page=True)
        page.reload(wait_until='networkidle');assert page.locator('#report-preview').count()==1
        # An independent browser storage origin/session must import the explicit journal.
        fresh=browser.new_context();q=fresh.new_page();q.goto(args.url,wait_until='networkidle')
        q.locator('#import-session').set_input_files(str(saved));q.locator('#go-report').wait_for(timeout=10000)
        assert '결과와 남은 확인 사항' in q.locator('h1').inner_text()
        fresh.close()
        results.append({'scenario':sid,'checkpoints':len(config['checkpoints']),'pdf_extraction':True,'sqlite':True,'journal_export_import':True,'refresh_restore':True,'mode':'authored_fixture'})
        ctx.close()
    mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True)
    page=mobile.new_page();page.goto(args.url,wait_until='networkidle');page.evaluate('document.fonts.ready')
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    page.screenshot(path=str(OUT/'mobile.png'),full_page=True);mobile.close();browser.close()

assert not errors,errors
receipt={'schema':'seminar.browser-e2e.v1','status':'passed','scenarios':results,'page_errors':errors,'mobile_overflow':False,'inference_calls':0,'verification_scope':'Browser controller rehearsal with authored fixtures; not model/measurement accuracy.'}
(OUT/'browser_e2e.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(receipt,ensure_ascii=False))
