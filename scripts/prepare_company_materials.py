#!/usr/bin/env python3
"""Assemble fictional company inputs for folder-upload practice, without inference.

Only writes assets/company-materials. Existing source scenarios are copied exactly.
No private company data, recorded predictions, videos or completed reports enter ZIP.
"""
from pathlib import Path
import csv
import hashlib
import io
import json
import shutil
import zipfile

import pymupdf as fitz
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/company-materials'
FILES = OUT / 'files'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, fields, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow(fields)
        writer.writerows(rows)


def make_drawing(folder):
    """Draw a teaching component map; it is expressly not an electrical schematic."""
    tt = instantiateVariableFont(TTFont(ROOT / 'assets/fonts/NotoSansKR.ttf'), {'wght': 400}, inplace=True)
    stream = io.BytesIO()
    tt.save(stream)
    font_bytes = stream.getvalue()
    doc = fitz.open()
    page = doc.new_page(width=960, height=680)
    page.insert_font(fontname='NotoKR', fontbuffer=font_bytes)
    ink, muted, teal = (.10,.17,.22), (.38,.45,.49), (.07,.37,.37)

    def text(x, y, value, size=13, color=ink):
        page.insert_text((x,y), value, fontname='helv' if value.isascii() else 'NotoKR', fontsize=size, color=color)

    def box(x,y,w,h,label,sub='',fill=(.94,.97,.97)):
        page.draw_rect(fitz.Rect(x,y,x+w,y+h), color=(.66,.77,.78), fill=fill, width=1)
        text(x+16,y+28,label,15)
        if sub: text(x+16,y+50,sub,10,muted)

    page.draw_rect(fitz.Rect(0,0,960,10), color=None, fill=teal)
    text(36,52,'다온에듀테크 | 바람빛 회로 키트 조립 구성도',23)
    text(36,80,'문서 DR-ELEC-DEMO-001 · 개정 1 · 제품 바람빛 회로 키트 · 강의용 예시',12,muted)
    text(36,104,'부품 식별과 작업 순서 안내용 도해 / 축척 없음 / 제조용 전기 회로도 아님',11,muted)
    page.draw_rect(fitz.Rect(36,126,924,438),color=(.70,.78,.80),fill=(.98,.99,.99))
    text(56,153,'검사 대상: 동일 보드 1개 (circuit-board)',14,teal)
    box(64,180,240,88,'배터리 홀더 + 배터리 2개','홀더의 + / − 표시와 방향 일치')
    box(342,180,210,88,'스위치 S1','스위치 확인 순서 ①')
    box(590,180,298,88,'모터 + 프로펠러','프로펠러를 모터 축에 장착')
    box(64,296,240,88,'연결 부품','회로 연결에 필요한 부품 세트')
    box(342,296,210,88,'스위치 S2','스위치 확인 순서 ②')
    box(590,296,298,88,'램프 L1','S2와 L1 병렬 연결: SOP 참조')
    text(56,418,'각 상자의 위치는 안내용 배치이며 실제 보드의 좌표·배선 길이를 나타내지 않음',11,muted)
    text(36,476,'작업 순서',16,teal)
    labels=['부품 준비','회로 연결','프로펠러 장착','배터리 삽입','스위치 확인','최종 외관']
    ids=['preparation','circuit','propeller','battery','switch','final']
    for i,(label,key) in enumerate(zip(labels,ids)):
        x=36+i*150
        box(x,494,136,66,f'{i+1}. {label}',key)
        if i<5:
            page.draw_line((x+138,527),(x+148,527),color=teal,width=1.5)
    text(36,596,'배터리 확인 기준 E-BATTERY → 배터리 삽입 (battery)',14,teal)
    text(36,620,'방향이 보이지 않으면 작업자 질문 → 답변 기록 / 스위치는 S1 확인 후 S2 확인',12)
    text(36,652,'실습용 가상 문서 · 기존 SOP와 검사 기준을 설명하기 위한 제작 도해',10,muted)
    doc.subset_fonts()
    doc.save(folder/'04_조립구성도.pdf',garbage=4,deflate=True,no_new_id=True)
    # Glyph paths keep Korean labels portable in previews without an installed font.
    (folder/'05_조립구성도.svg').write_text(page.get_svg_image(text_as_path=True),encoding='utf-8')
    doc.close()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    FILES.mkdir(exist_ok=True)
    companies=[]
    all_files=[]

    def register(folder,scenario,items):
        records=[]
        for filename,title,role in items:
            p=folder/filename
            row=dict(id=f"{scenario['id']}:{filename}",name=filename,title=title,
                     type=p.suffix[1:].lower(),path=p.relative_to(ROOT).as_posix(),
                     relativePath=p.relative_to(FILES).as_posix(),company=scenario['companyName'],
                     companyId=scenario['companyId'],scenarioId=scenario['id'],role=role,
                     bytes=p.stat().st_size,sha256=digest(p),origin='authored_demo')
            records.append(row);all_files.append(row)
        return records

    source=ROOT/'scenarios/electronics_demo'
    s=json.loads((source/'scenario.json').read_text())
    folder=FILES/s['companyName'];folder.mkdir(exist_ok=True)
    shutil.copyfile(source/'SOP.pdf',folder/'01_작업지시서.pdf')
    shutil.copyfile(source/'criteria.csv',folder/'02_검사기준.csv')
    (folder/'00_회사와공정.txt').write_text('''다온에듀테크 | 회사 자료 구축 실습

가상 회사 / 강의용 예시
회사 ID: edu-daon
공정 ID: ELEC-DEMO-001
제품: 바람빛 회로 키트
작업번호: DEMO-001
작업 수량: 1세트 / 검사 대상: 동일 보드 1개

작업 순서
1. 부품과 작업 준비 (preparation)
2. 회로 연결 (circuit)
3. 프로펠러 장착 (propeller)
4. 배터리 삽입 (battery)
5. 스위치 확인 (switch)
6. 최종 외관 기록 (final)

자료 확인
01: 조립 절차와 확인 질문을 담은 SOP PDF
02: 여섯 검사 기준 CSV
03: 준비 부품 목록과 수량을 담은 BOM CSV
04·05: 동일 조립 구성도의 PDF·SVG
06: 작업 ID, 순서, 검사 기준의 연결표

검토할 핵심 연결
E-BATTERY는 '회로 연결'이 아닌 '배터리 삽입 (battery)' 단계에 해당합니다.
배터리는 두 개이며, 홀더 + / − 표시와 방향을 맞춥니다.
스위치 확인은 S1 확인 후 S2 확인 순서입니다.

입력 문서는 올바른 원본입니다. 앱의 검토용 초안에는 수강생이 찾고 수정할
오류 한 곳이 포함될 수 있습니다. 원본과 수정 이력은 구분해 보관합니다.

조립 구성도는 부품과 작업 순서 안내용이며 제조용 전기 회로도가 아닙니다.
실제 생산용 기준, 전기적 안전 승인 또는 실측 결과가 아닙니다.
''',encoding='utf-8')
    write_csv(folder/'03_부품명세서.csv',
              ['part_id','part_name','quantity','unit','used_in_task','note'],[
        ['BASE','베이스 보드',1,'개','preparation','검사 대상 동일 보드 1개'],
        ['LINK','연결 부품',1,'세트','circuit','교육용 작업지시서에 필요한 연결 부품 묶음'],
        ['S1','스위치 S1',1,'개','circuit;switch','S1 확인 후 S2 확인'],
        ['S2','스위치 S2',1,'개','circuit;switch','S1 다음에 확인'],
        ['MOTOR','모터',1,'개','circuit;propeller','프로펠러 장착 대상'],
        ['L1','램프 L1',1,'개','circuit','S2와 L1 병렬 연결은 SOP 참조'],
        ['PROPELLER','프로펠러',1,'개','propeller','모터 축에 장착'],
        ['HOLDER','배터리 홀더',1,'개','circuit;battery','홀더 + / − 표시 확인'],
        ['BATTERY','배터리',2,'개','battery','두 개 모두 방향 확인'],
        ['SOP','작업지시서',1,'부','preparation','SOP-ELEC-DEMO-001'],
    ])
    write_csv(folder/'06_공정순서.csv',['sequence','task_id','task_name','criterion_id','review_note'],[
        [i,t['id'],t['label'],';'.join(c['id'] for c in s['criteria'] if c['taskId']==t['id']),
         '배터리 두 개의 방향 확인' if t['id']=='battery' else 'S1 확인 후 S2 확인' if t['id']=='switch' else 'SOP와 검사 기준 참조']
        for i,t in enumerate(s['tasks'],1)
    ])
    make_drawing(folder)
    files=register(folder,s,[('00_회사와공정.txt','회사와 공정 개요','company'),
        ('01_작업지시서.pdf','바람빛 회로 키트 작업지시서','sop'),
        ('02_검사기준.csv','여섯 검사 기준','criteria'),
        ('03_부품명세서.csv','부품 명세서 · BOM','bom'),
        ('04_조립구성도.pdf','조립 구성도 PDF','drawing'),
        ('05_조립구성도.svg','조립 구성도 SVG','drawing'),
        ('06_공정순서.csv','공정 순서와 기준 연결','process')])
    companies.append(dict(id=s['companyId'],name=s['companyName'],folder=s['companyName'],scenarioIds=[s['id']],files=files))

    measurement_files=[];scenario_ids=[]
    for key,label in [('measurement_demo','표준형_BSH-2630'),('measurement_precision_demo','정밀형_BSH-2630-P')]:
        source=ROOT/'scenarios'/key;s=json.loads((source/'scenario.json').read_text());scenario_ids.append(key)
        folder=FILES/s['companyName']/label;folder.mkdir(parents=True,exist_ok=True)
        copies=[('SOP.pdf','01_검사작업지시서.pdf','검사 작업지시서','sop'),
                ('criteria.csv','02_검사기준.csv','A·B·C 검사 기준','criteria'),
                ('drawing.pdf','03_제품도면.pdf','제품 도면 PDF','drawing'),
                ('drawing.svg','04_제품도면.svg','제품 도면 SVG','drawing'),
                ('product.svg','05_제품외관.svg','제품 외관 도해','product'),
                ('scene-a.svg','06_A외경_계측예시.svg','A 외경 계측 예시','measurement_scene'),
                ('scene-b.svg','07_B길이_계측예시.svg','B 길이 계측 예시','measurement_scene'),
                ('scene-c.svg','08_C두께_계측예시.svg','C 두께 계측 예시','measurement_scene')]
        for src,dest,_,_ in copies:shutil.copyfile(source/src,folder/dest)
        i=s['inspection']
        (folder/'00_제품과검사.txt').write_text(f'''다온정밀 | {s['productName']}

가상 회사 / 강의용 예시
회사 ID: {s['companyId']}
제품 ID: {i['productId']}
도면: {i['drawingId']} / 개정 {i['drawingRevision']}
시편: {i['specimenId']}

01: 검사 작업지시서
02: 허용 범위와 단위를 포함한 검사 기준 CSV
03·04: 동일 도면의 PDF·SVG
05: 제품 외관 도해
06~08: A 외경, B 길이, C 두께의 계측 장면 예시

측정 대상·도면·제품을 일치시킨 후 값을 기록합니다.
원래 판독과 작업자 확인값을 구분합니다. 불명확한 값은 질문으로 확인합니다.
표준형과 정밀형은 별도 제품이며 동일한 측정값에 다른 허용 범위가 적용됩니다.
도해와 숫자는 수업용 설정이며 실제 OCR 결과나 물리적 검사 인증이 아닙니다.
''',encoding='utf-8')
        measurement_files.extend(register(folder,s,[('00_제품과검사.txt','제품과 검사 개요','company')]+[(d,t,r) for _,d,t,r in copies]))
    companies.append(dict(id='edu-daon-precision',name='다온정밀',folder='다온정밀',scenarioIds=scenario_ids,files=measurement_files))

    (FILES/'자료_사용안내.txt').write_text('''제조 AI Agent 실습 | 회사별 입력 자료

이 ZIP에는 현재 수강생 실습의 두 가상 회사 자료가 들어 있습니다.
다온에듀테크: 전자 조립 실습
다온정밀: 플랜지 부시 계측 실습 (표준형 / 정밀형)

1. ZIP 압축을 풉니다.
2. 전자 조립의 폴더 업로드에서 '다온에듀테크' 폴더를 고릅니다.
3. 파일 목록에서 사용할 자료를 선택하고 화면에서 미리 봅니다.
4. 정보 구축 후 원문과 초안의 연결을 검토하고 수정합니다.

자료는 가상의 회사·제품·공정과 강의용 도해입니다.
교육용 자료의 작성 결과를 실제 AI 추론으로 표시하지 않습니다.
원본 PDF/CSV와 올바른 작업-기준 연결을 유지하고 검토 초안과 구분합니다.
영상을 비롯한 대형 미디어, 프로그램, 강의 슬라이드, 완성 보고서는 이 입력
자료 ZIP에 포함하지 않습니다. 기존 웹 실습에서 해당 자료를 이용합니다.
강사용 과거 실험 자료와 비공개 회사 자료는 포함하지 않습니다.

글꼴 고지는 'NotoSansKR_글꼴라이선스.txt'를 참고하세요.
''',encoding='utf-8')
    shutil.copyfile(ROOT/'assets/fonts/OFL.txt',FILES/'NotoSansKR_글꼴라이선스.txt')
    # Fixed ZIP metadata makes identical source inputs reproducible.
    zip_path=OUT/'company-practice-materials.zip'
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        packaged = [ROOT / row['path'] for row in all_files] + [FILES/'자료_사용안내.txt', FILES/'NotoSansKR_글꼴라이선스.txt']
        for p in sorted(packaged):
            info=zipfile.ZipInfo(p.relative_to(FILES).as_posix(),date_time=(2026,11,23,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
            z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(zip_path) as z:
        assert z.testzip() is None
        assert all(not x.startswith('/') and '..' not in Path(x).parts for x in z.namelist())
        members=len(z.namelist())
    manifest=dict(schema='seminar.company-materials.v1',origin='authored_demo',
        label='강의용 예시',zipPath=zip_path.relative_to(ROOT).as_posix(),
        zipBytes=zip_path.stat().st_size,zipSha256=digest(zip_path),zipMembers=members,
        scope='현재 수강생 실습 3개 / 가상 회사 2개 / 입력 문서와 도해',
        companies=companies,files=all_files,
        reviewReference=dict(criterionId='E-BATTERY',correctTaskId='battery',correctTaskLabel='배터리 삽입',source='다온에듀테크/02_검사기준.csv',batteryQuantity=2),
        publication=False,modelCalls=0,gpuCalls=0)
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert (FILES/'다온에듀테크/02_검사기준.csv').read_bytes()==(ROOT/'scenarios/electronics_demo/criteria.csv').read_bytes()
    for row in all_files:assert (ROOT/row['path']).is_file()
    print(json.dumps({'companies':len(companies),'inputFiles':len(all_files),'zipMembers':members,'zipBytes':manifest['zipBytes'],'zipSha256':manifest['zipSha256']},ensure_ascii=False))


if __name__=='__main__':main()
