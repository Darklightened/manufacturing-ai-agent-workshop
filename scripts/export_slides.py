#!/usr/bin/env python3
"""Validate offline HTML slides, render PDF and presentation-image PPTX with notes.

Authoring-only dependencies: playwright, python-pptx, Pillow, PyMuPDF.
Learners need none of these. No model/GPU/external requests.
"""
from pathlib import Path
import argparse, hashlib, json, zipfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--browser',required=True)
p.add_argument('--output',type=Path,required=True,help='New validation folder; do not replace previous receipts')
args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
content=json.loads((ROOT/'slides/content.json').read_text());n=len(content['slides'])
page_errors=[];external=[];layout=[];media_placements={}
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox','--disable-gpu'])
    ctx=browser.new_context(viewport={'width':1600,'height':996},device_scale_factor=1)
    def guard(route):
        if route.request.url.startswith('file:'):route.continue_()
        else:external.append(route.request.url);route.abort()
    ctx.route('**/*',guard)
    page=ctx.new_page();page.on('pageerror',lambda e:page_errors.append(str(e)))
    page.goto((ROOT/'slides/실습_안내.html').as_uri(),wait_until='networkidle')
    page.evaluate('document.fonts.ready')
    assert page.locator('.slide').count()==n
    assert page.evaluate('Array.from(document.images).filter(i=>i.hasAttribute("data-zoom")).every(i=>i.complete&&i.naturalWidth>0)')
    assert page.locator('#counter').inner_text()==f'1 / {n}'
    page.keyboard.press('ArrowRight');assert page.locator('#counter').inner_text()==f'2 / {n}'
    page.keyboard.press('n');assert page.locator('#notes').is_visible();page.keyboard.press('Escape');assert not page.locator('#notes').is_visible()
    page.keyboard.press('o');assert page.locator('#toc').is_visible();page.locator('#toc button').nth(4).click();assert page.locator('#counter').inner_text()==f'5 / {n}'
    page.evaluate('goSlide(0)');page.locator('.slide.active img').first.click();assert page.locator('#zoom').is_visible();page.keyboard.press('Escape');assert not page.locator('#zoom').is_visible()
    poster_js='''v=>{const f=v.closest('figure');f.style.position='relative';const i=document.createElement('img');i.className='export-video-poster';i.src=v.poster;i.alt='작업자 시점 계측 장면';Object.assign(i.style,{position:'absolute',left:v.offsetLeft+'px',top:v.offsetTop+'px',width:v.clientWidth+'px',height:v.clientHeight+'px',objectFit:'contain',background:'#122039',borderRadius:'12px',zIndex:'2'});f.append(i);return i.decode();}'''
    for i in range(n):
        page.evaluate('(n)=>{goSlide(n);scrollTo(0,0);document.querySelector(".slide.active").scrollTop=0;}',i)
        page.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        violations=page.evaluate('''()=>{
          const s=document.querySelector('.slide.active'),b=s.getBoundingClientRect();
          const violations=[...s.querySelectorAll('h1,.lead,.points li,.visual img,.visual figcaption,.visual .access-link,.visual table,.agenda,.pipeline,.tiles,.role-columns,.closing,.platform-diagram,.omni-diagram,.ontology-example,.visual h3,.visual p,.relation-row,.opening-note,.step-panel,.step-panel p,.phase-strip,.lab-pipeline,.stage-io,.tech-flow,.tech-flow h3,.tech-flow p,.tech-panels,.tech-panels h2,.tech-panels h3,.tech-panels p,.tech-panels pre,.tech-panels small,.tech-background li,.tech-note')].map(e=>({tag:e.tagName,cls:e.className,text:e.innerText?.slice(0,80),r:e.getBoundingClientRect()})).filter(x=>x.r.left<b.left+40||x.r.right>b.right-40||x.r.bottom>b.bottom-45||x.r.top<b.top+30).map(x=>({tag:x.tag,cls:x.cls,text:x.text,x:x.r.x,y:x.r.y,width:x.r.width,height:x.r.height}));
          for(const header of s.querySelectorAll('.kicker,.brand')){const r=header.getBoundingClientRect();if(r.top<b.top+18||r.bottom>b.bottom-18)violations.push({tag:'header',text:'Slide header outside safe margins'});}
          const cap=s.querySelector('.opening-screen figcaption,.pov-slide figcaption'),link=s.querySelector('.access-link');
          if(cap&&link&&cap.getBoundingClientRect().bottom>link.getBoundingClientRect().top)violations.push({tag:'figcaption',text:'Screen caption overlaps access link'});
          const panel=s.querySelector('.tech-panels'),technicalNote=s.querySelector('.tech-note');
          if(panel&&technicalNote){
            for(const article of panel.children){
              const ar=article.getBoundingClientRect();
              if(ar.bottom>technicalNote.getBoundingClientRect().top-8)violations.push({tag:'article',text:'Technical panel overlaps lower note'});
              for(const child of article.children){
                const cr=child.getBoundingClientRect();
                if(cr.bottom>ar.bottom-9)violations.push({tag:child.tagName,text:'Technical content exceeds its panel'});
              }
            }
          }
          return violations;
        }''')
        if violations:layout.append({'slide':i+1,'violations':violations})
        if content['slides'][i].get('visualSpec',{}).get('kind')=='clip':
            page.wait_for_function("document.querySelector('.slide.active video').readyState >= 2",timeout=20000)
            page.wait_for_timeout(200)
            media_placements[i]=page.evaluate('''()=>{const s=document.querySelector('#stage').getBoundingClientRect(),v=document.querySelector('.slide.active video').getBoundingClientRect();return {x:v.x-s.x,y:v.y-s.y,width:v.width,height:v.height};}''')
        if i in media_placements:
            page.locator('.slide.active video').evaluate(poster_js)
        box=page.locator('#stage').bounding_box()
        page.screenshot(path=str(out/f'slide-{i+1:02}.png'),clip=box)
        page.evaluate("document.querySelectorAll('.export-video-poster').forEach(e=>e.remove())")

    for media_index in media_placements:
        page.evaluate('(n)=>goSlide(n)',media_index)
        page.locator('.slide.active video').evaluate('(v)=>v.play()')
        page.wait_for_function("document.querySelector('.slide.active video').currentTime > 0.2",timeout=20000)
        page.locator('.slide.active video').evaluate('(v)=>{v.pause();v.currentTime=0;}')
    # Navigation/fit also work at a smaller classroom laptop size.
    page.set_viewport_size({'width':1280,'height':720});page.evaluate('goSlide(16)')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(out/'laptop-preview.png'))
    page.set_viewport_size({'width':1600,'height':996})
    for media_index in media_placements:
        page.evaluate('(n)=>goSlide(n)',media_index)
        page.locator('.slide.active video').evaluate(poster_js)
    page.emulate_media(media='print')
    page.evaluate('document.fonts.ready')
    page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
    print_layout = page.evaluate('''() => Array.from(document.querySelectorAll('.slide')).flatMap((s,i) => {
      const errors=[],r=s.getBoundingClientRect(),style=getComputedStyle(s);
      if(style.display!=='flex'||style.flexDirection!=='column')errors.push({slide:i+1,medium:'print',issue:'slide must remain a vertical flex column'});
      for(const sel of ['h1','.lead','.slide-body','.tech-flow','.tech-panels','.phase-strip','.slide-foot']){
        const el=s.querySelector(sel);if(!el)continue;const b=el.getBoundingClientRect();
        if(b.left<r.left-1||b.right>r.right+1||b.top<r.top-1||b.bottom>r.bottom+1)errors.push({slide:i+1,medium:'print',issue:'out of slide bounds',selector:sel});
      }
      const h=s.querySelector('h1')?.getBoundingClientRect(),l=s.querySelector('.lead')?.getBoundingClientRect();
      if(h&&l&&h.bottom>l.top+1)errors.push({slide:i+1,medium:'print',issue:'heading and lead overlap'});
      return errors;
    })''')
    layout.extend(print_layout)
    page.pdf(path=str(ROOT/'slides/실습_안내.pdf'),width='1600px',height='900px',print_background=True,prefer_css_page_size=True)
    browser.close()

receipt={'status':'passed' if not(page_errors or external or layout) else 'failed','slides':n,'page_errors':page_errors,'external_requests':external,'layout_violations':layout,'checks':['file:// without external requests','all embedded images decode','keyboard prev/next','speaker notes','contents navigation','image zoom','all slide bounds','1280x720 fit','all printed slide columns/bounds','PDF export','embedded video playback'],'model_calls':0,'printed_layout_slides':n}
(out/'browser_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
assert not page_errors,page_errors
assert not external,external
assert not layout,layout

import fitz
pdf=fitz.open(ROOT/'slides/실습_안내.pdf');assert len(pdf)==n,(len(pdf),n)
assert all('강의용 예시' in p.get_text() for p in pdf)
pdf_counts=[len(p.get_text()) for p in pdf];assert min(pdf_counts)>100
pdf.close()

from pptx import Presentation
from pptx.util import Inches
prs=Presentation();prs.slide_width=Inches(13.333333);prs.slide_height=Inches(7.5)
prs.core_properties.title=content['title'];prs.core_properties.subject='전자 조립·계측 검사·기계 조립·문서 보관 · 강의용 예시'
prs.core_properties.author='DYNIN';prs.core_properties.comments='Presentation-image slides with speaker notes. Editable source: slides/content.json and scripts/build_slides.py.'
for i,s in enumerate(content['slides']):
    slide=prs.slides.add_slide(prs.slide_layouts[6])
    pic=slide.shapes.add_picture(str(out/f'slide-{i+1:02}.png'),0,0,width=prs.slide_width,height=prs.slide_height)
    pic._element.nvPicPr.cNvPr.set('descr',s['title']+'\n'+s.get('lead','')+'\n'+'\n'.join(s.get('bullets',[])))
    if i in media_placements:
        r=media_placements[i];spec=s['visualSpec']
        movie_width=min(r['width'],r['height']*16/9)
        movie_left=r['x']+(r['width']-movie_width)/2
        movie_poster=ROOT/Path(spec['mp4']).parent/'overview-poster.png'
        slide.shapes.add_movie(str(ROOT/spec['mp4']),Inches(movie_left/120),Inches(r['y']/120),Inches(movie_width/120),Inches(r['height']/120),poster_frame_image=str(movie_poster if movie_poster.exists() else ROOT/spec['poster']),mime_type='video/mp4')

    notes=s.get('notes','');notes='\n'.join(notes) if isinstance(notes,list) else notes
    slide.notes_slide.notes_text_frame.text=s['title']+'\n\n'+notes+'\n\n전자 장면: EgoOops, Yuto Haneji 외, CC BY-SA 4.0; https://y-haneji.github.io/EgoOops-project-page/ . 기계 장면: IndustReal, Apache-2.0; https://github.com/TimSchoonbeek/IndustReal . 계측 그림은 자체 제작 강의용 도해.\n화면 보존형 발표본입니다. 문구 수정은 slides/content.json 원본을 사용하세요.'
pptx=ROOT/'slides/실습_안내.pptx';prs.save(pptx)
reopened=Presentation(pptx);assert len(reopened.slides)==n
assert all(s.notes_slide.notes_text_frame.text.strip() for s in reopened.slides)
with zipfile.ZipFile(pptx) as z:assert z.testzip() is None

from PIL import Image,ImageOps,ImageDraw
thumbs=[]
for i in range(n):
    im=Image.open(out/f'slide-{i+1:02}.png').convert('RGB');im.thumbnail((400,225))
    tile=Image.new('RGB',(420,255),'#dce4f0');tile.paste(im,(10,10));ImageDraw.Draw(tile).text((12,238),str(i+1),fill='#16233c');thumbs.append(tile)
sheet=Image.new('RGB',(420*4,255*((n+3)//4)),'#dce4f0')
for i,im in enumerate(thumbs):sheet.paste(im,((i%4)*420,(i//4)*255))
sheet.save(out/'contact-sheet.jpg',quality=90)
receipt.update({'pdf_pages':n,'pdf_text_chars':pdf_counts,'pptx_slides':n,'pptx_notes':n,'pptx_type':'presentation_image_with_speaker_notes_and_embedded_video','embedded_videos':len(media_placements),'outputs':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [ROOT/'slides/실습_안내.html',ROOT/'slides/실습_안내.pdf',pptx]}})
(out/'export_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'passed','slides':n,'PDF':n,'PPTX':n,'layout_violations':0,'external_requests':0}))
