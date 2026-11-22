#!/usr/bin/env python3
"""Create authored product inspection lessons. Never read or change private company data."""
from pathlib import Path
import csv, hashlib, io, json, math
from html import escape
import pymupdf as fitz
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.varLib.instancer import instantiateVariableFont

ROOT=Path(__file__).resolve().parents[1]
PIDS=('measurement_demo','measurement_precision_demo')
SVG_FONTS={}
SVG_GLYPHS={}

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def txt(x,y,s,size=20,fill='#253d57',weight=400,anchor='start'):
    # Outlined Korean survives browser <img>, offline reports and MuPDF's SVG
    # conversion without any system-font or network-font dependency.
    value=str(s)
    if any('\uac00'<=c<='\ud7af' for c in value):
        w=700 if weight>=600 else 400
        if w not in SVG_FONTS:
            f=TTFont(ROOT/'assets/fonts/NotoSansKR.ttf')
            f=instantiateVariableFont(f,{'wght':w},inplace=True)
            SVG_FONTS[w]=(f,f.getGlyphSet(),f.getBestCmap(),f['head'].unitsPerEm)
        f,gs,cmap,upem=SVG_FONTS[w];cursor=0;pieces=[]
        for char in value:
            name=cmap.get(ord(char),'.notdef');key=(w,name)
            if key not in SVG_GLYPHS:
                pen=SVGPathPen(gs);gs[name].draw(pen);SVG_GLYPHS[key]=pen.getCommands()
            path=SVG_GLYPHS[key]
            if path:pieces.append(f'<path d="{path}" transform="translate({cursor} 0)"/>')
            cursor+=f['hmtx'][name][0]
        width=cursor*size/upem
        if anchor=='middle':x-=width/2
        elif anchor=='end':x-=width
        return f'<g fill="{fill}" aria-label="{escape(value)}"><title>{escape(value)}</title><g transform="translate({x} {y}) scale({size/upem} {-size/upem})">'+''.join(pieces)+'</g></g>'
    return f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(value)}</text>'
def svg(body,title,width=1200,height=800):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img"><title>{escape(title)}</title><defs><linearGradient id="metal" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#c5d3df"/><stop offset=".45" stop-color="#eef4f7"/><stop offset="1" stop-color="#9bafc0"/></linearGradient><linearGradient id="side"><stop stop-color="#8ba1b4"/><stop offset=".5" stop-color="#d5e0e8"/><stop offset="1" stop-color="#8ba1b4"/></linearGradient><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#345cad"/></marker></defs><rect width="100%" height="100%" fill="#f6f9fc"/>{body}</svg>'''

def line(x1,y1,x2,y2,color='#365a7a',width=2,extra=''):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" {extra}/>'
def dim(x1,y1,x2,y2,label,tx,ty):
    dx,dy=x2-x1,y2-y1; length=math.hypot(dx,dy);ux,uy=dx/length,dy/length
    points=[]
    for x,y,sign in [(x1,y1,1),(x2,y2,-1)]:
        a=(x+sign*10*ux+4*uy,y+sign*10*uy-4*ux);b=(x+sign*10*ux-4*uy,y+sign*10*uy+4*ux)
        points.append(f'<polygon points="{x},{y} {a[0]},{a[1]} {b[0]},{b[1]}" fill="#345cad"/>')
    return line(x1,y1,x2,y2,'#345cad',2)+''.join(points)+txt(tx,ty,label,22,'#345cad',700)
def badge(x,y,label,color='#345cad'):
    return f'<circle cx="{x}" cy="{y}" r="21" fill="{color}"/>'+txt(x,y+7,label,21,'white',700,'middle')

def part(x=350,y=220,scale=1):
    # Same authored flanged bushing across all scenes; side section + consistent bore.
    return f'''<g transform="translate({x} {y}) scale({scale})"><ellipse cx="190" cy="300" rx="175" ry="26" fill="#18364d" opacity=".08"/><path d="M65 62L280 62L280 232L65 232Z" fill="#afc0ce" stroke="#698499" stroke-width="3"/><ellipse cx="280" cy="147" rx="42" ry="85" fill="#c8d5df" stroke="#698499" stroke-width="3"/><ellipse cx="280" cy="147" rx="17" ry="38" fill="#50687c"/><path d="M20 25L85 25L85 269L20 269Z" fill="#afc0ce" stroke="#698499" stroke-width="3"/><ellipse cx="20" cy="147" rx="58" ry="122" fill="#c8d5df" stroke="#698499" stroke-width="3"/><ellipse cx="20" cy="147" rx="22" ry="52" fill="#3b5265"/><ellipse cx="25" cy="147" rx="13" ry="39" fill="#8ba0b1"/><path d="M20 25L85 25M20 269L85 269" stroke="#698499" stroke-width="3"/></g>'''

def make_scenario(precision=False):
    sid=PIDS[int(precision)]; product='BSH-2630-P' if precision else 'BSH-2630'
    specimen='EDU-BSH-P-001' if precision else 'EDU-BSH-001'
    ranges=[('26.25','26.35'),('39.99','40.01'),('5.75','5.85')] if precision else [('26.10','26.50'),('39.90','40.10'),('5.70','5.90')]
    labels=['A · 플랜지 외경','B · 전체 길이','C · 플랜지 두께'];codes=['A','B','C'];keys=['M-OD','M-LENGTH','M-FLANGE'];tasks=['diameter','length','flange']
    inst=['디지털 캘리퍼스','디지털 하이트 게이지','디지털 마이크로미터'];nominals=['26.30','40.00','5.80']
    name='플랜지 부시 · 정밀형' if precision else '플랜지 부시 · 표준형'
    features=[dict(criterionId=k,code=code,label=label,nominal=nominal,instrument=instrument,lower=lo,upper=hi,unit='mm',anchor={'A':{'x':8.5,'y':47.5},'B':{'x':31,'y':67},'C':{'x':18,'y':20.5}}[code]) for k,code,label,nominal,instrument,(lo,hi) in zip(keys,codes,labels,nominals,inst,ranges)]
    criteria=[dict(id=k,taskId=t,label=label,target=specimen,kind='range',unit='mm',lower=lo,upper=hi,allowWorker=k=='M-FLANGE') for k,t,label,(lo,hi) in zip(keys,tasks,labels,ranges)]
    cp=[]
    notes=['캘리퍼스 표시 26.30 mm를 도면 A 외경에 기록합니다.','기준면에서 윗면까지의 높이 40.02 mm를 도면 B 전체 길이에 기록합니다.','두께 표시의 한 자리가 가려져 있습니다. 도면 C 위치와 실제 표시값을 작업자에게 확인합니다.']
    for i in range(3):
        h=dict(criterionId=keys[i],verdict='unknown' if i==2 else 'met',raw=['26.30 mm','40.02 mm','5.?8 mm'][i],unit='mm',reason=notes[i])
        if i<2:h['value']=['26.30','40.02'][i]
        else:h['question']='C 위치의 플랜지 두께를 다시 확인해 주세요. 마이크로미터에 표시된 값과 단위가 무엇인가요?'
        cp.append(dict(id=f'm{i+1}',time=(i+1)*10,sourceTime=(i+1)*10,taskId=tasks[i],target=specimen,featureCode=codes[i],label=["A 외경 측정값 기록","B 전체 길이 측정값 기록","C 두께 표시 확인 요청"][i],note=notes[i],origin='authored_demo',image=f'scenarios/{sid}/scene-{codes[i].lower()}.svg',assessments=[h]))
    return dict(id=sid,version='measurement-teaching-v1',mode='demo',demoKind='measurement',title='계측 판독 · '+name,description='제품과 도면을 선택하고 세 치수를 기록합니다. 가려진 숫자를 확인한 뒤 검수조서를 완성하세요.',companyId='edu-daon-precision',companyName='다온정밀',processId='INSPECT-BSH-P' if precision else 'INSPECT-BSH',productName=name,orderId='QC-P-001' if precision else 'QC-001',sourceNote='제품·도면·장비 화면·측정값은 이 강의를 위해 구성한 예시입니다. 서로 다른 실제 계측 사진을 같은 제품의 측정으로 합치지 않았으며, 실제 모델 판독이나 공인 검사 결과가 아닙니다.',fixtureNotice='강의용 예시 · 제품 도면과 측정 장면을 직접 구성',demoNotice='기록한 값과 작업자 답변을 검사 기준에 비교합니다.',timelineKind='authored_measurement_sequence',inspection=dict(productId=product,productName=name,drawingId='DR-'+product,drawingRevision='A',specimenId=specimen,drawing=f'scenarios/{sid}/drawing.svg',features=features),tasks=[dict(id=t,label=label) for t,label in zip(tasks,labels)],criteria=criteria,media=dict(path='',codec='authored_svg',browserPlayable=False),sources=[dict(label='Manufacturing Agent Workshop · 강의용 자체 제작 도면·장비 장면',license='교육용 작성 자료',url='docs/MEASUREMENT_DEMO.ko.md')],variants=[dict(id=PIDS[int(not precision)],title='표준형 제품' if precision else '정밀형 제품',label='표준형 제품' if precision else '정밀형 제품',config=f'scenarios/{PIDS[int(not precision)]}/scenario.json',productId='BSH-2630' if precision else 'BSH-2630-P')],exercises=['표준형 제품을 선택하고 도면 A/B/C의 검사 위치와 허용 범위를 확인하세요.','C 두께 질문에 5.78 mm를 입력하여 미확인 값이 작업자 확인값으로 기록되는지 확인하세요.','상한 또는 작업자 확인값을 바꾸고 검수조서의 판정이 바뀌는지 비교하세요.','정밀형은 별도 제품과 검사 시편입니다. 같은 예시 수치라도 길이 기준이 더 좁아 불일치가 생깁니다.'],checkpoints=cp,documents=[dict(id='sop',title='검사 작업지시서 PDF',path=f'scenarios/{sid}/SOP.pdf',type='pdf'),dict(id='criteria',title='A/B/C 검사 기준 CSV',path=f'scenarios/{sid}/criteria.csv',type='csv'),dict(id='drawing',title='제품 도면 PDF · 개정 A',path=f'scenarios/{sid}/drawing.pdf',type='pdf')],workerAnswerExamples=[dict(value='5.78',unit='mm',label='5.78 mm로 확인'),dict(value='6.08',unit='mm',label='6.08 mm로 확인')])

def drawing(s):
    p=s['inspection'];fs=p['features'];b='<rect x="32" y="28" width="1136" height="744" rx="16" fill="white" stroke="#dae4ef"/>'
    b+=txt(66,78,'다온정밀 / 제품 검사도면',23,'#345cad',700)+txt(66,112,p['productId']+'  /  '+p['drawingId']+'  /  REV '+p['drawingRevision'],19)+txt(1130,78,'강의용 예시',14,'#8090a1',600,'end')+txt(1130,110,'단위 mm · 비축척 예시',13,'#8090a1',400,'end')
    # Side section with flange at left; overall 40 and flange thickness 5.8.
    b+='<path d="M180 225H245V264H565V396H245V435H180Z" fill="#c8d5df" stroke="#49647c" stroke-width="3"/><path d="M180 305H565V355H180Z" fill="white" stroke="#49647c" stroke-width="2"/>'
    b+=line(145,330,600,330,'#95a6b7',1.5,'stroke-dasharray="9 7"')
    b+=line(180,448,180,500)+line(565,410,565,500)+dim(180,488,565,488,'B  40.00',320,524)
    b+=line(180,216,180,168)+line(245,255,245,168)+dim(180,182,245,182,'C  5.80',170,155)
    b+=line(170,225,115,225)+line(170,435,115,435)+dim(130,225,130,435,'A',82,333)
    b+=txt(70,365,'Ø26.30',17,'#345cad',700)
    # End view, bore intentionally not a required lesson inspection.
    b+='<circle cx="835" cy="330" r="108" fill="#c8d5df" stroke="#49647c" stroke-width="3"/><circle cx="835" cy="330" r="48" fill="white" stroke="#49647c" stroke-width="3"/>'
    b+=line(705,330,965,330,'#95a6b7',1.5,'stroke-dasharray="9 7"')+line(835,200,835,460,'#95a6b7',1.5,'stroke-dasharray="9 7"')
    b+=txt(835,490,'정면도',17,'#8090a1',500,'middle')+txt(370,566,'측면 단면도',17,'#8090a1',500,'middle')
    b+=txt(66,615,'검사 위치',14,'#8090a1',700)+txt(340,615,'기준치',14,'#8090a1',700)+txt(620,615,'허용 범위',14,'#8090a1',700)+txt(1000,615,'단위',14,'#8090a1',700)
    for i,f in enumerate(fs):
        y=651+i*34;b+=badge(81,y-7,f['code'])+txt(128,y,['플랜지 외경','전체 길이','플랜지 두께'][i],16)+txt(340,y,f['nominal'],18,'#253d57',600)+txt(620,y,f['lower']+' – '+f['upper'],18,'#345cad',600)+txt(1000,y,'mm',18)
    return svg(b,p['productName']+' 검사 도면 A/B/C')

def scene(s,i):
    p=s['inspection'];f=p['features'][i];code=f['code'];b='<rect x="30" y="24" width="1140" height="752" rx="24" fill="white" stroke="#dde7ef"/>'
    b+=txt(64,72,'다온정밀 / 치수 검사',22,'#345cad',700)+txt(1132,72,'강의용 예시',14,'#8090a1',600,'end')
    b+=txt(64,112,p['productId']+'  |  '+p['specimenId'],20)+badge(1080,124,code)
    b+='<rect x="65" y="157" width="1070" height="485" rx="18" fill="#eff4f8"/>'
    if i==0:
        b+=part(355,195,1.1)
        # Caliper beam and jaws surround flange height without obscuring part.
        b+='<rect x="215" y="195" width="34" height="390" rx="5" fill="#8198ab" stroke="#506a80" stroke-width="3"/><path d="M215 195H378V222H249V285H215Z" fill="#c8d5df" stroke="#506a80" stroke-width="3"/><path d="M215 449H249V491H378V514H215Z" fill="#c8d5df" stroke="#506a80" stroke-width="3"/><rect x="190" y="365" width="175" height="94" rx="12" fill="#263b4c"/><rect x="207" y="381" width="140" height="48" rx="5" fill="#dce7ce"/>'
        b+=txt(277,415,'26.30',35,'#27362c',600,'middle')+txt(312,448,'mm',15,'white')
        b+=txt(740,235,'디지털 캘리퍼스',21,'#345cad',700)+txt(740,285,'A / 플랜지 외경',25,'#253d57',700)+txt(740,345,'26.30',58,'#162e44',700)+txt(947,345,'mm',24)
        b+=txt(740,399,'표시값이 선명합니다',18,'#72879b')+txt(740,429,'도면 A 위치에 기록합니다',18,'#72879b')
    elif i==1:
        # Height gauge touching top of upright same flange bushing on datum plate.
        b+='<rect x="150" y="550" width="570" height="42" rx="6" fill="#768c9c"/><rect x="225" y="245" width="60" height="305" fill="#c8d5df" stroke="#506a80" stroke-width="3"/><rect x="286" y="311" width="270" height="18" fill="#9aafbe" stroke="#506a80" stroke-width="2"/><path d="M550 311H571V350H554V329H550Z" fill="#687e92"/>'
        for y in range(260,540,12):b+=line(232,y,244 if y%24 else 251,y,'#617487',1)
        b+='<path d="M435 350H575V520H605V550H405V520H435Z" fill="#c8d5df" stroke="#698499" stroke-width="3"/><ellipse cx="505" cy="350" rx="70" ry="18" fill="#dbe5ec" stroke="#698499" stroke-width="3"/><ellipse cx="505" cy="350" rx="28" ry="8" fill="#4c6172"/><rect x="180" y="280" width="145" height="100" rx="12" fill="#263b4c"/><rect x="192" y="300" width="121" height="48" rx="5" fill="#dce7ce"/>'
        b+=txt(252,334,'40.02',31,'#27362c',600,'middle')+txt(284,367,'mm',15,'white')
        b+=line(628,350,670,350)+line(628,550,670,550)+dim(652,350,652,550,'B',680,458)
        b+=txt(760,235,'디지털 하이트 게이지',20,'#345cad',700)+txt(760,285,'B / 전체 길이',23,'#253d57',700)+txt(760,345,'40.02',58,'#162e44',700)+txt(967,345,'mm',24)
        b+=txt(760,399,'기준면에서 윗면까지 측정',18,'#72879b')+txt(760,429,'도면 B 위치에 기록합니다',18,'#72879b')
    else:
        # Micrometer across flange thickness; one decimal digit masked to prompt a worker.
        b+='<path d="M230 287C90 270 85 560 260 568H405V505H270C185 505 185 350 270 350H405V287Z" fill="#3d6377" stroke="#24485d" stroke-width="3"/><rect x="373" y="290" width="40" height="70" rx="4" fill="#c8d5df" stroke="#506a80" stroke-width="2"/><rect x="440" y="300" width="130" height="45" rx="3" fill="#c8d5df" stroke="#506a80" stroke-width="2"/><rect x="545" y="268" width="170" height="118" rx="14" fill="#263b4c"/><rect x="560" y="284" width="140" height="60" rx="4" fill="#dce7ce"/><rect x="715" y="285" width="68" height="85" rx="7" fill="#c8d5df" stroke="#506a80" stroke-width="3"/>'
        for x in range(724,775,7):b+=line(x,291,x,365,'#7e95a7',2)
        # Flange side-view between anvils, remaining body extends below.
        b+='<path d="M412 255H440V388H480V515H412Z" fill="#c8d5df" stroke="#698499" stroke-width="3"/>'
        b+=txt(628,328,'5.78',35,'#27362c',600,'middle')+'<rect x="624" y="286" width="23" height="55" fill="#f3cf86" transform="rotate(-7 635 312)"/><path d="M625 291L641 335M631 288L647 332" stroke="#d5a855" stroke-width="1"/>'
        b+=txt(678,369,'mm',15,'white')+badge(424,235,'C','#bf822a')
        b+=txt(826,222,'디지털',20,'#345cad',700)+txt(826,249,'마이크로미터',20,'#345cad',700)+txt(826,300,'C / 플랜지 두께',21,'#253d57',700)
        b+=txt(826,365,'5.?8',48,'#a66a17',700)+txt(980,365,'mm',24)+txt(826,410,'한 자리가 가려져 있습니다',17,'#9d742c')+txt(826,441,'작업자에게 확인해 주세요',19,'#9d742c',700)
    b+=f'<rect x="65" y="665" width="1070" height="78" rx="14" fill="{ "#fff5e3" if i==2 else "#edf4ff"}"/>'
    b+=badge(103,704,code,'#bf822a' if i==2 else '#345cad')+txt(143,700,['플랜지 외경','전체 길이','플랜지 두께'][i],19,'#253d57',700)+txt(143,728,'도면 '+p['drawingId']+' / 개정 A',15,'#6f8398')+txt(1098,710,f['lower']+' – '+f['upper']+' mm',23,'#345cad',700,'end')
    return svg(b,f['label']+' 계측 장면 · '+p['specimenId'])

def font_bytes():
    f=TTFont(ROOT/'assets/fonts/NotoSansKR.ttf');f=instantiateVariableFont(f,{'wght':400},inplace=True);bio=io.BytesIO();f.save(bio);return bio.getvalue()

def make_pdf(s,fb):
    dest=ROOT/'scenarios'/s['id'];font=fitz.Font(fontbuffer=fb);doc=fitz.open();page=None;y=0
    def newpage():
        nonlocal page,y
        page=doc.new_page(width=595,height=842);page.insert_font(fontname='NotoKR',fontbuffer=fb);page.draw_rect(fitz.Rect(0,0,595,12),fill=(.12,.3,.5),color=None);y=47
    def text(t='',size=10.5):
        nonlocal y
        chunks=[];cur=''
        for ch in t:
            if font.text_length(cur+ch,fontsize=size)>505:chunks.append(cur);cur=''
            cur+=ch
        chunks.append(cur)
        for part in chunks:
            if y>776:newpage()
            page.insert_text((44,y),part,fontname='helv' if part.isascii() else 'NotoKR',fontsize=size,color=(.13,.21,.3));y+=size*1.65
    p=s['inspection'];newpage();text('다온정밀 | 제품 검사 작업지시서',19);text(s['productName'],16);text('강의용 예시 · 제품 1개 · A/B/C 세 위치 검사',10)
    for key,value in [('company_id',s['companyId']),('process_id',s['processId']),('product_id',p['productId']),('drawing_id',p['drawingId']),('drawing_revision',p['drawingRevision']),('specimen_id',p['specimenId'])]:text(key+': '+value,9)
    text();text('1. 제품과 도면 확인',13);text('선택한 제품번호와 도면번호·개정 A를 확인합니다. 표준형과 정밀형의 검사 범위는 다르며, 각각 별도 실습 시편입니다.');text('검사 위치는 A 외경, B 전체 길이, C 플랜지 두께입니다. 도면의 위치 표시에 따라 장비와 기준을 연결합니다.')
    text();text('2. 측정값 기록 순서',13)
    for task,f in zip(s['tasks'],p['features']):
        text('task_id: '+task['id'],9);text(f['label']+' / '+f['instrument'],11);text(f"기준: {f['lower']} ~ {f['upper']} mm · 기준치 {f['nominal']} mm",10)
    text();text('3. 판독이 불확실한 경우',13);text('값이 명확하지 않으면 추정값을 확정하지 않고 작업자에게 해당 검사 위치의 값과 단위를 묻습니다. 최초 표시와 확인 답변을 각각 남깁니다.');text('C의 예시 표시 5.?8 mm는 한 자리가 가려진 상태입니다. 수업에서는 질문을 확인하고 5.78 mm 또는 다른 확인값을 직접 입력합니다.')
    text();text('4. 결과와 산출물',13);text('각 측정값을 현재 허용 범위와 비교합니다. 범위 밖 값은 불일치, 값이 없는 항목은 확인 필요로 유지합니다. 도면·판독·답변·판정이 포함된 검수조서를 저장합니다.');text('기준 변경 실습에서는 원시값을 유지한 채 판정만 재계산합니다. 단위 오류나 제품·검사 위치 불일치는 기록하지 않습니다.')
    text();text('이 문서·도면·장비 화면·값은 강의를 위해 만든 예시입니다. 실제 모델 판독, 실측값 또는 공인 검사 승인으로 사용하지 않습니다.',9)
    for i,pg in enumerate(doc,1):pg.insert_text((44,816),f'DAON / 강의용 예시 / {i}',fontname='NotoKR',fontsize=8,color=(.4,.5,.6))
    doc.subset_fonts();doc.save(dest/'SOP.pdf',garbage=4,deflate=True);doc.close()
    with fitz.open(dest/'SOP.pdf') as doc:extracted='\n'.join(p.get_text() for p in doc)
    (dest/'SOP.extracted.txt').write_text(extracted)
    assert all(x in extracted for x in ['product_id: '+p['productId'],'drawing_id: '+p['drawingId'],'drawing_revision: A','specimen_id: '+p['specimenId']])
    # Vector drawing PDF preserves diagram geometry; Korean title/footer are real text.
    vector=fitz.open(stream=(dest/'drawing.svg').read_bytes(),filetype='svg');converted=fitz.open('pdf',vector.convert_to_pdf());drawing_doc=fitz.open();pg=drawing_doc.new_page(width=842,height=595);pg.insert_font(fontname='NotoKR',fontbuffer=fb);pg.insert_text((34,29),s['productName']+' 검사 도면 · 강의용 예시',fontname='NotoKR',fontsize=13,color=(.13,.21,.3));pg.show_pdf_page(fitz.Rect(16,38,826,578),converted,0);drawing_doc.subset_fonts();drawing_doc.save(dest/'drawing.pdf',garbage=4,deflate=True);drawing_doc.close();converted.close();vector.close()


def main():
    protected=[p for d in ['scenarios/electronics_demo','scenarios/electronics','scenarios/instruments','recordings/electronics_v1'] for p in (ROOT/d).rglob('*') if p.is_file()];before={str(p.relative_to(ROOT)):digest(p) for p in protected}
    fb=font_bytes()
    for precision in (False,True):
        s=make_scenario(precision);dest=ROOT/'scenarios'/s['id'];dest.mkdir(exist_ok=True)
        (dest/'drawing.svg').write_text(drawing(s));(dest/'product.svg').write_text(svg(txt(66,76,'다온정밀 / '+s['inspection']['productId'],27,'#345cad',700)+txt(66,120,'플랜지 부시 / 강의용 예시',18,'#8090a1')+part(415,205,1.35)+txt(600,720,'A  Ø26.30      B  40.00      C  5.80 mm',29,'#345cad',700,'middle'),s['productName']))
        for i,code in enumerate('abc'):(dest/f'scene-{code}.svg').write_text(scene(s,i))
        make_pdf(s,fb)
        with (dest/'criteria.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=['id','taskId','label','target','kind','unit','lower','upper','allowWorker']);writer.writeheader()
            for c in s['criteria']:writer.writerow({**c,'allowWorker':str(c['allowWorker']).lower()})
        write_json(dest/'scenario.json',s)
    index=ROOT/'scenarios/index.json';cards=json.loads(index.read_text());cards=[c for c in cards if c['id'] not in PIDS]
    for c in cards:
        if c['id']=='instruments':c['instructorOnly']=True
    measurement=dict(id='measurement_demo',title='계측 판독 · 도면과 검수조서',subtitle='제품 선택 → 측정값 기록 → 확인 질문 → 검수조서',description='표준형과 정밀형 제품의 도면을 불러오고 A/B/C 측정값을 기록합니다. 불확실한 숫자 하나를 직접 확인하세요.',cover='scenarios/measurement_demo/product.svg',config='scenarios/measurement_demo/scenario.json')
    at=next((i+1 for i,c in enumerate(cards) if c['id']=='electronics_demo'),0);cards.insert(at,measurement);write_json(index,cards)
    assert before=={str(p.relative_to(ROOT)):digest(p) for p in protected}
    print(json.dumps({'scenarios':list(PIDS),'features_per_product':3,'model_calls':0,'preserved_files':len(before),'pdf_tokens_verified':True},ensure_ascii=False))
if __name__=='__main__':main()
