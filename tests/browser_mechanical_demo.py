"""Finite browser check of the MechanicalExperience host + real video playback."""
from pathlib import Path
import asyncio,json,os
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/labs23_v2/mechanical_browser'
URL=os.environ.get('SEMINAR_URL','http://127.0.0.1:8937/')
async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/home/jovyan/.cache/ms-playwright/chromium-1187/chrome-linux/chrome',headless=True,args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':1365,'height':1050})
        errors=[];page.on('pageerror',lambda error: errors.append(str(error)))
        await page.goto(URL,wait_until='networkidle')
        await page.evaluate('''async () => {
          const Core=await import('/packages/core/core.mjs');
          const {MechanicalExperience}=await import('/packages/mechanical-flow/ui.mjs');
          const scenario=await(await fetch('/scenarios/mechanical_demo/scenario.json')).json();
          const text=await(await fetch('/scenarios/mechanical_demo/SOP.extracted.txt')).text();
          const csv=await(await fetch('/scenarios/mechanical_demo/criteria.csv')).text();
          const style=document.createElement('link');style.rel='stylesheet';style.href='/packages/mechanical-flow/style.css';document.head.append(style);
          window.mechBundle=Core.compileCompany(text,csv,scenario);window.mechState=Core.createSession(scenario,mechBundle);window.mechCore=Core;window.mechScenario=scenario;
          const main=document.querySelector('main');main.style.maxWidth='1300px';
          window.mechToast=[];window.mechNav=[];
          window.mechUI=new MechanicalExperience({main,scenario:()=>scenario,bundle:()=>mechBundle,session:()=>mechState,commit:async next=>{window.mechState=next;window.mechBundle=next.bundle},navigate:step=>mechNav.push(step),toast:message=>mechToast.push(message)});
          mechUI.render();
        }''')
        await page.wait_for_function("document.querySelector('#mechanical-video').readyState >= 2")
        await page.screenshot(path=str(OUT/'01_initial.png'),full_page=True)
        await page.evaluate("document.querySelector('#mechanical-video').currentTime=60")
        await page.wait_for_timeout(300)
        assert await page.evaluate('mechState.position') == -1
        assert await page.evaluate("document.querySelector('#mechanical-video').currentTime") < 1
        await page.select_option('#mechanical-speed','4')
        await page.click('#mechanical-play')
        await page.wait_for_function('mechState.position===0',timeout=30000)
        assert await page.locator('#mechanical-next').is_enabled()
        await page.click('#mechanical-next')
        await page.wait_for_function('mechState.position===1',timeout=15000)
        assert not await page.locator('#mechanical-next').is_enabled()
        assert await page.evaluate('mechState.questions.length') == 1
        await page.screenshot(path=str(OUT/'02_pin_question.png'),full_page=True)
        await page.click('[data-deliver]')
        await page.click('[data-confirmation="unknown"]')
        assert not await page.locator('#mechanical-next').is_enabled()
        await page.click('[data-confirmation="violated"]')
        assert not await page.locator('#mechanical-next').is_enabled()
        await page.click('[data-reopen]')
        await page.click('[data-deliver]')
        await page.click('[data-confirmation="met"]')
        assert await page.locator('#mechanical-next').is_enabled()
        assert await page.evaluate("mechState.assessments['MD-PIN'].rawExampleVerdict")=='unknown'
        await page.screenshot(path=str(OUT/'03_pin_confirmed.png'),full_page=True)
        await page.click('#mechanical-next')
        await page.wait_for_function('mechState.position===2',timeout=35000)
        await page.click('#mechanical-next')
        await page.wait_for_function('mechState.position===3',timeout=10000)
        assert await page.evaluate('mechCore.summarize(mechState,mechScenario).pass')
        assert await page.evaluate('mechCore.validateSession(mechState,mechScenario)')
        count=await page.evaluate('mechState.commands.length')
        await page.evaluate('mechUI.leave();mechUI.reset();mechState=JSON.parse(JSON.stringify(mechState));mechUI.render()')
        await page.wait_for_function("document.querySelector('#mechanical-video').readyState>=2")
        assert await page.evaluate('mechState.commands.length')==count
        assert await page.evaluate('mechUI.index')==3
        await page.screenshot(path=str(OUT/'04_completed_restore.png'),full_page=True)
        await page.click('#mechanical-next')
        assert await page.evaluate('mechNav.at(-1)')=='review'
        assert errors==[],errors
        result=await page.evaluate('({summary:mechCore.summarize(mechState,mechScenario),commands:mechState.commands.length,questions:mechState.questions,errors:mechToast})')
        result['checks']=['forward_seek_blocked','real_video_four_boundaries','explicit_question_delivery','unknown_hold','negative_hold','reconfirmation','raw_unknown_preserved','six_checks_pass','restore_no_replay','review_navigation']
        result['pageErrors']=errors
        (OUT/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        await page.evaluate('mechUI.leave()')
        await browser.close()
        print(json.dumps({'passed':len(result['checks']),'saved':str(OUT/'receipt.json')},ensure_ascii=False))
asyncio.run(main())
