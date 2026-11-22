#!/usr/bin/env python3
"""Import immutable public workshop sources and author explicitly synthetic teaching packets.
No model execution, no video editing, and no private company inputs.
"""
from pathlib import Path
import argparse, csv, hashlib, json, shutil, textwrap
import pymupdf as fitz

ROOT=Path(__file__).resolve().parents[1]
SOURCE_DEFAULT=ROOT.parent/'agentic_harness/artifacts/workshops/video_first_assets_20261120'

def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def criterion(id,task,label,target,kind='visual',unit='',lower='',upper='',allow=False):
    return dict(id=id,taskId=task,label=label,target=target,kind=kind,unit=unit,lower=lower,upper=upper,allowWorker=allow)

def assessment(id,status,reason,**kwargs):
    return dict(criterionId=id,verdict=status,reason=reason,**kwargs)

def checkpoint(id,time,task,target,label,image,assessments,note='',**kwargs):
    return dict(id=id,time=time,taskId=task,target=target,label=label,note=note or '교육용으로 작성한 관찰·판정 입력입니다. 실제 모델 예측이나 독립 품질 인증이 아닙니다.',origin='authored_fixture',image=image,assessments=assessments,**kwargs)

BASE='data/source_pack/'
E=BASE+'electronics/S1790005/'
ER=BASE+'electronics/S1790010/'
A=BASE+'assembly/01_assy_0_1/frames/'
M=BASE+'assembly/01_main_0_1/frames/'
I=BASE+'measurement/'
SOURCE_E=dict(label='EgoOops 공개 원본 및 절차 주석',url='https://y-haneji.github.io/EgoOops-project-page/',license='CC BY-SA 4.0')
SOURCE_A=dict(label='IndustReal 공식 원본',url='https://github.com/TimSchoonbeek/IndustReal',license='Apache-2.0')

TASKS_E=[dict(id='circuit',label='회로 연결'),dict(id='propeller',label='프로펠러 장착'),dict(id='battery',label='배터리 삽입'),dict(id='switch',label='스위치 확인'),dict(id='final',label='최종 외관')]
CRITERIA_E=[criterion('E-CONNECTION','circuit','S2와 L1의 병렬 연결을 확인','circuit-board'),criterion('E-PROPELLER','propeller','모터의 프로펠러 장착 외관','circuit-board'),criterion('E-BATTERY','battery','배터리 2개와 삽입 방향 확인','circuit-board'),criterion('E-SWITCH','switch','S1·S2 조작 순서 확인','circuit-board'),criterion('E-FINAL','final','최종 프로펠러 장착 외관 기록','circuit-board')]

scenarios=[]
scenarios.append(dict(id='electronics',title='전자 조립 작업 지원',description='회로 연결부터 배터리·작동 확인까지. 보이는 것과 확인이 필요한 것을 구분합니다.',sourceNote='EgoOops S1790005의 실제 영상·원본8단계를 참고한 교육용 제어 실습입니다. 아래 판정은 작성된 fixture이며 모델 출력이 아닙니다.',companyId='edu-dynin',processId='ELEC-001',mode='fixture',tasks=TASKS_E,criteria=CRITERIA_E,media=dict(path=E+'S1790005.mp4',codec='h264',browserPlayable=True),sources=[SOURCE_E],exercises=['정보 구축 후 원본 절차와 DB 기준을 대조하세요.','가려진 배터리에 “확인했습니다”라고 답해도 시각 검사가 완료되지 않는 이유를 확인하세요.','정상 주석은 모든 품질의 독립 합격 인증과 다르다는 점을 보고서에서 확인하세요.'],variants=[dict(id='electronics_error',label='원본 오류 주석 사례',config='scenarios/electronics_error/scenario.json')],checkpoints=[
checkpoint('e1',20.361,'circuit','circuit-board','회로 연결 작업',E+'frame_02_0020.361s.jpg',[assessment('E-CONNECTION','unknown','연결 작업 중입니다. 완료된 병렬 관계를 확인할 근거가 충분하지 않습니다.')]),
checkpoint('e2',76.731,'circuit','circuit-board','연결부 확인 요청',E+'frame_04_0076.731s.jpg',[assessment('E-CONNECTION','unknown','손이 연결부를 가립니다. S2와 L1의 접점을 보여 주는 증거가 필요합니다.')]),
checkpoint('e3',89.659,'propeller','circuit-board','프로펠러 장착',E+'frame_05_0089.659s.jpg',[assessment('E-PROPELLER','unknown','장착 중인 한 장면으로 최종 안착 여부를 확정하지 않습니다.')]),
checkpoint('e4',99.726,'battery','circuit-board','배터리 방향 확인',E+'frame_06_0099.726s.jpg',[assessment('E-BATTERY','unknown','손과 홀더 각도로 두 배터리의 방향을 충분히 볼 수 없습니다.')]),
checkpoint('e5',113.870,'switch','circuit-board','스위치 조작',E+'frame_08_0113.870s.jpg',[assessment('E-SWITCH','unknown','이 스냅샷만으로 두 스위치의 시간 순서를 검증할 수 없습니다.')]),
checkpoint('e6',120.021,'final','circuit-board','최종 외관과 미확인 항목',E+'frame_09_0120.021s.jpg',[assessment('E-FINAL','met','교육용 외관 조건: 최종 프레임에서 프로펠러가 모터 위에 보입니다. 회전 성능은 검증하지 않습니다.')])]))
scenarios.append(dict(id='electronics_error',title='전자 조립 오류 주석 비교',description='병렬·직렬 연결의 원본 오류 주석과 수정 행동을 비교합니다.',sourceNote='EgoOops S1790010 원본 오류 주석을 참고한 교육용 fixture입니다. 오류 탐지를 실제 모델이 수행한 결과가 아닙니다. S1790005와 별도 개체/실행입니다.',companyId='edu-dynin',processId='ELEC-ERR-001',mode='fixture',tasks=TASKS_E,criteria=CRITERIA_E,media=dict(path=ER+'S1790010.mp4',codec='h264',browserPlayable=True),sources=[SOURCE_E],exercises=['원본 주석 기반 오류 이벤트와 실제 모델 관찰을 구분하세요.','수정 행동을 했다는 사실만으로 방향 검사까지 끝났다고 처리하는지 확인하세요.'],checkpoints=[
checkpoint('ee1',72.444,'circuit','circuit-board','연결 오류 주석 구간',ER+'frame_03_0072.444s.jpg',[assessment('E-CONNECTION','violated','교육 이벤트: 원본 주석은 S2와 L1을 병렬 대신 직렬로 연결했다고 설명합니다. 독립 시각 검수 결과는 아닙니다.')]),
checkpoint('ee2',164.071,'propeller','circuit-board','프로펠러 장착 작업',ER+'frame_05_0164.071s.jpg',[assessment('E-PROPELLER','unknown','장착 중인 프레임입니다. 완료된 안착 상태를 추가 확인해야 합니다.')]),
checkpoint('ee3',195.450,'battery','circuit-board','배터리 방향 오류 주석',ER+'frame_07_0195.450s.jpg',[assessment('E-BATTERY','violated','교육 이벤트: 원본 오류 주석은 배터리 방향 문제를 설명합니다. 새 모델 판정이 아닙니다.')]),
checkpoint('ee4',202.977,'battery','circuit-board','수정 행동 이후 재확인',ER+'frame_08_0202.977s.jpg',[assessment('E-BATTERY','unknown','원본에 수정 행동이 기록되지만 수정 후 방향 확인은 별도 증거가 필요합니다.')]),
checkpoint('ee5',222.168,'switch','circuit-board','최종 작동 단계',ER+'frame_11_0222.168s.jpg',[assessment('E-SWITCH','unknown','최종 조작 장면과 전체 순서 검증은 구분합니다.')])]))

scenarios.append(dict(id='instruments',title='계측 판독과 추가 확인',description='소수점·단위·작업자 확인을 분리해 기록하고 교육용 허용 범위를 비교합니다.',sourceNote='서로 다른 장비·사진의 독립 판독 사례입니다. 같은 제품의 여러 치수가 아닙니다. 허용 범위와 판독 제안은 교육용 fixture입니다.',companyId='edu-dynin',processId='MEASURE-001',mode='fixture',timelineKind='lesson_case_order_not_continuous_video',tasks=[dict(id='digital',label='디지털 캘리퍼스'),dict(id='micrometer',label='마이크로미터 확인'),dict(id='vernier',label='버니어 관찰')],criteria=[criterion('I-DIGITAL','digital','디지털 사례 교육 허용 범위','digital-case','range','mm',26.0,26.5,True),criterion('I-MICRO','micrometer','마이크로미터 값과 단위 확인','micrometer-case','range','mm',5.7,5.8,True),criterion('I-VERNIER','vernier','버니어 눈금의 안정적 판독 가능성','vernier-case')],media=dict(path='',codec='mixed',browserPlayable=False),sources=[dict(label='디지털 캘리퍼스 사진 · Elektrobjørn',url='https://commons.wikimedia.org/wiki/File:Measure_pipe_thread.jpg',license='CC0'),dict(label='마이크로미터 사진 · Glenn McKechnie',url='https://commons.wikimedia.org/wiki/File:578metric-micrometer.jpg',license='CC BY-SA 3.0 photo; benchmark record CC BY-SA 4.0'),dict(label='Dynamic Gauge Dataset',url='https://zenodo.org/records/20624895',license='CC BY 4.0')],exercises=['26.30mm의 교육용 상한을26.5에서26.2로 바꾸어 판정이 달라지는지 확인하세요.','마이크로미터 확인 답변은 예: 5.78 mm입니다. 실제 교정/측정 인증이 아니라 수강생 확인 기록입니다.','버니어와 디지털 사진은 같은 제품의 서로 다른 부위로 연결하지 않습니다.'],checkpoints=[
checkpoint('i1',0,'digital','digital-case','디지털 표시 읽기',I+'Measure pipe thread.jpg',[assessment('I-DIGITAL','met','사진에서 읽은 값을 바탕으로 만든 교육용 판독 제안입니다. 규칙 엔진이 범위를 별도로 비교합니다.',value='26.30',unit='mm',raw='26.30 mm')],sourceTime=0),
checkpoint('i2',10,'micrometer','micrometer-case','눈금 해석 확인 요청',I+'micrometer_0_benchmark_image.jpg',[assessment('I-MICRO','unknown','본척과 회전척 합산 값을 확인해 주세요. 예시 원본 판독 범위는5.7–5.8mm이며 교정된 제품 치수를 뜻하지 않습니다.',raw='소수점과 눈금 확인 필요',unit='mm')],sourceTime=0),
checkpoint('i3',20,'vernier','vernier-case','움직이는 눈금의 판독 한계',I+'analog_vernier_closing_v1_slow.poster.png',[assessment('I-VERNIER','unknown','움직임과 눈금 정렬 때문에 안정된 값의 확인이 필요합니다. 단일 프레임에 자동 합격을 주지 않습니다.')],video=I+'analog_vernier_closing_v1_slow.mp4',sourceTime=12.256)]))

scenarios.append(dict(id='mechanical',title='기계 조립과 최종 검수',description='차체·브래킷·바퀴 축의 작업군을 따라가며 가림과 최종 외관 증거를 기록합니다.',sourceNote='IndustReal 실제 원본 프레임과 행동 주석을 참고한 교육용 fixture입니다. 작업군은 교재용 묶음이며 토크·강도 검증을 포함하지 않습니다.',companyId='edu-dynin',processId='ASM-001',mode='fixture',tasks=[dict(id='chassis',label='차체 결합'),dict(id='bracket',label='전방 브래킷'),dict(id='axle',label='바퀴 축'),dict(id='final',label='최종 외관')],criteria=[criterion('M-CHASSIS','chassis','차체 연결 외관 확인','chassis-01'),criterion('M-BRACKET','bracket','전방 브래킷 배치 확인','chassis-01'),criterion('M-AXLE','axle','바퀴 축 조립 외관 확인','chassis-01'),criterion('M-FINAL','final','최종 차체와 네 바퀴 외관 기록','chassis-01')],media=dict(path=BASE+'assembly/01_assy_0_1/01_assy_0_1.mp4',codec='mpeg4-part2',browserPlayable=False),sources=[SOURCE_A],exercises=['가려진 체결부에 답변해도 시각적 검증은 남는지 확인하세요.','최종 외관과 체결 토크의 검증 범위를 구분하세요.','전체 영상은 별도 다운로드하고 현재 앱은 검증된 정지 프레임으로 진행합니다.'],variants=[dict(id='maintenance',label='부품 교체 후 재검수',config='scenarios/maintenance/scenario.json')],checkpoints=[
checkpoint('m1',33,'chassis','chassis-01','차체 결합 중',A+'t033.000.jpg',[assessment('M-CHASSIS','unknown','부품을 결합하는 중이며 완료된 연결부의 충분한 시야가 없습니다.')]),
checkpoint('m2',63,'chassis','chassis-01','가림 확인 요청',A+'t063.000.jpg',[assessment('M-CHASSIS','unknown','손이 체결 위치를 가립니다. 연결부가 보이는 증거가 필요합니다.')]),
checkpoint('m3',80,'bracket','chassis-01','전방 브래킷 배치',A+'t080.000.jpg',[assessment('M-BRACKET','unknown','브래킷 배치 작업은 보이지만 최종 고정 상태는 별도 확인합니다.')]),
checkpoint('m4',123,'axle','chassis-01','첫 바퀴 축 조립',A+'t123.000.jpg',[assessment('M-AXLE','unknown','축을 장착하는 과정이며 다른 축과 최종 상태까지 확인하지 않았습니다.')]),
checkpoint('m5',167,'axle','chassis-01','풀리 포함 축 조립',A+'t167.000.jpg',[assessment('M-AXLE','unknown','풀리와 축 조립 장면입니다. 가려진 체결과 구름 기능은 아직 확인하지 않았습니다.')]),
checkpoint('m6',181,'final','chassis-01','최종 외관 증거',A+'t181.000.jpg',[assessment('M-FINAL','met','교육용 외관 조건: 최종 프레임에 조립된 차체와 네 바퀴가 보입니다. 토크·강도·구름 성능은 범위 밖입니다.')])]))

scenarios.append(dict(id='maintenance',title='부품 교체 후 재검수',description='긴 차체 부품을 짧은 부품으로 교체하는 별도 정비 작업입니다.',sourceNote='IndustReal 유지보수 원본입니다. 조립 영상과 같은 개체라는 연결은 검증되지 않았습니다. 판정은 교육용 fixture입니다. 분리 시 현재 구성 검사를 다시 여는 교육 정책을 적용하며, 과거 사진과 판정 이력은 보존합니다.',companyId='edu-dynin',processId='MNT-001',mode='fixture',tasks=[dict(id='remove',label='기존 부품 분리'),dict(id='replace',label='짧은 부품 교체'),dict(id='reassemble',label='축 재조립'),dict(id='review',label='재검수')],criteria=[criterion('R-CURRENT','remove','현재 구성의 외관 확인 · 변경 시 재검사','repair-01'),criterion('R-REMOVE','remove','기존 부품 분리 확인','repair-01'),criterion('R-REPLACE','replace','짧은 부품으로 교체 확인','repair-01'),criterion('R-AXLE','reassemble','분리한 축의 재조립 검토','repair-01'),criterion('R-FINAL','review','새 시도의 최종 외관 확인','repair-01')],media=dict(path=BASE+'assembly/01_main_0_1/01_main_0_1.mp4',codec='mpeg4-part2',browserPlayable=False),sources=[SOURCE_A],exercises=['교체 전 사진으로 교체 후 검사를 승인하지 않는 이유를 설명하세요.','긴 부품으로 원상 복구하는 작업이 아니라 짧은 부품 교체임을 문서와 대조하세요.'],checkpoints=[
checkpoint('r0',0,'remove','repair-01','변경 전 구성의 외관 기록',M+'t000.000.jpg',[assessment('R-CURRENT','met','교육용 입력: 현재 구성의 외관을 기록했습니다. 전체 품질 합격이 아니며 부품 변경 후 새 검사를 요구합니다.')]),
checkpoint('r1',34,'remove','repair-01','분리 후 현재 구성 검사 다시 열기',M+'t034.000.jpg',[assessment('R-REMOVE','unknown','분리 작업 장면이며 완료 조건을 추가 확인합니다.')],note='교육용 재검사 정책: 기존 부품 분리 후 현재 구성의 검사를 새 시도로 엽니다. 이전 사진과 met 기록은 이력에 남고 현재 구성의 승인에 재사용하지 않습니다.',invalidate=['R-CURRENT']),
checkpoint('r2',65,'replace','repair-01','교체 체결부의 가림',M+'t065.000.jpg',[assessment('R-REPLACE','unknown','짧은 부품의 연결 위치를 손이 가립니다. 새 시도 증거를 확인해 주세요.')]),
checkpoint('r3',112,'reassemble','repair-01','바퀴와 풀리 재조립',M+'t112.000.jpg',[assessment('R-AXLE','unknown','재조립 작업 중입니다. 변경 이전 사진을 현재 검사 증거로 쓰지 않습니다.')]),
checkpoint('r4',131,'review','repair-01','재검수 기록',M+'t131.000.jpg',[assessment('R-FINAL','unknown','최종으로 보이는 외관을 기록하되 연결부와 기능의 미확인 항목은 남깁니다.')])]))

def pdf(s, folder):
    doc=fitz.open();font_buffer=fitz.Font('korea').buffer
    page=doc.new_page(width=595,height=842);page.insert_font(fontname='Workshop',fontbuffer=font_buffer)
    y=48
    def line(text, size=11, bold=False):
        nonlocal page,y
        if y>786:
            page=doc.new_page(width=595,height=842);page.insert_font(fontname='Workshop',fontbuffer=font_buffer);y=48
        page.insert_text((42,y),text,fontname='Workshop',fontsize=size,color=(.10,.15,.22));y+=size*1.65
    line('교육용 작업 절차 및 검사 기준',19);line(s['title'],15);line('문서 버전: education-v1 / 실제 회사 SOP 아님')
    line('company_id: '+s['companyId']);line('process_id: '+s['processId']);line('schema_version: workshop-company-v1');line('')
    for part in textwrap.wrap(s['sourceNote'],width=52):line(part,10)
    line('');line('작업 순서',14)
    for i,t in enumerate(s['tasks'],1):
        line("task_id: "+t["id"],9)
        line(f"{i}. {t['id']} | {t['label']}")
    if s['id'].startswith('electronics'):
        line('');line('원본 절차 8단계의 교육용 번역',14)
        for item in [
            '1. 배터리 홀더와 S1을 직렬로 연결한다.',
            '2. S1과 모터를 직렬로 연결한다.',
            '3. S2와 L1을 병렬로 연결한다.',
            '4. S2를 모터·배터리 홀더 회로와 직렬로 연결한다.',
            '5. 모터에 프로펠러를 장착한다.',
            '6. 배터리 홀더에 배터리 두 개를 삽입한다.',
            '7. S1을 켠다.',
            '8. S2를 켠다.'
        ]:line(item,10)
        line('출처: EgoOops, Yuto Haneji et al. / CC BY-SA 4.0',9)
        line('한국어 번역·작업군 구성·검사 정책은 교육용 편집입니다.',9)
    line('');line('교육용 검사 규정',14)
    for c in s['criteria']:
        line(c['id']+' | '+c['label'],10)
        detail=('교육 허용 범위 '+str(c['lower'])+' - '+str(c['upper'])+' '+c['unit']) if c['kind']=='range' else '교육용 외관·증거 검토. 보이지 않는 조건은 보류.'
        line(detail,10)
        line('대상: '+c['target']+' / 작업자 수치 확인 허용: '+('예' if c['allowWorker'] else '아니오'),9)
    line('');line('근거와 한계',14)
    for text in ['원본 절차/사진과 교육용 증거 정책은 구분합니다.','현재 판정 입력은 작성한 교육용 fixture입니다. 모델 추론 결과가 아닙니다.','시각적 확인이 필요한 항목은 말로 확인해도 자동 완료하지 않습니다.','정보가 부족한 항목은 보류하고 원본 증거와 질문을 보고서에 남깁니다.']:
        line(text,10)
    doc.set_metadata({'title':s['title']+' 교육용 SOP','author':'Manufacturing Agent Workshop','subject':'Synthetic training document; public media source-grounded; not company SOP'})
    path=folder/'SOP.pdf';doc.subset_fonts();doc.save(path,garbage=4,deflate=True);doc.close()
    extracted='\n'.join(page.get_text() for page in fitz.open(path))
    assert 'company_id: '+s['companyId'] in extracted
    assert 'process_id: '+s['processId'] in extracted
    (folder/'SOP.extracted.txt').write_text(extracted)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=SOURCE_DEFAULT);ap.add_argument('--documents-only',action='store_true');args=ap.parse_args()
    source=args.source.resolve();dest=ROOT/'data/source_pack'
    if not source.is_dir():raise SystemExit('Expected prepared public source pack does not exist: '+str(source))
    if args.documents_only:
        records=json.loads((ROOT/'data/import_manifest.json').read_text())['files']
    else:
        shutil.copytree(source,dest,dirs_exist_ok=True)
        records=[]
        for p in sorted(source.rglob('*')):
            if not p.is_file():continue
            q=dest/p.relative_to(source)
            h=digest(p);assert digest(q)==h
            records.append({'path':str(q.relative_to(ROOT)),'bytes':q.stat().st_size,'sha256':h,'source_relative':str(p.relative_to(source))})
        write_json(ROOT/'data/import_manifest.json',{'schema':'workshop-source-import-v1','source_pack':'video_first_assets_20261120','import_date':'2026-11-21','private_company_data_included':False,'model_calls':0,'copy_policy':'byte-identical copies; original provenance files preserved','files':records})
    for s in scenarios:
        folder=ROOT/'scenarios'/s['id'];folder.mkdir(parents=True,exist_ok=True)
        pdf(s,folder)
        with (folder/'criteria.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=['id','taskId','label','target','kind','unit','lower','upper','allowWorker']);w.writeheader()
            for c in s['criteria']:w.writerow({**c,'allowWorker':str(c['allowWorker']).lower()})
        s['documents']=[dict(id='sop',title='교육용 작업 절차 PDF',path=f"scenarios/{s['id']}/SOP.pdf",type='pdf'),dict(id='criteria',title='교육용 검사 기준 CSV',path=f"scenarios/{s['id']}/criteria.csv",type='csv')]
        s['fixtureNotice']='모든 체크포인트 판정은 사람이 작성한 교육용 입력입니다. 모델 실행은 0회입니다.'
        s['version']='education-v1'
        write_json(folder/'scenario.json',s)
    cards=[]
    subtitles={'electronics':'회로 연결 · 추가 확인 · 보고서','instruments':'숫자와 단위 · 확인 답변 · 규정 비교','mechanical':'작업군 · 가림 · 최종 외관'}
    for s in scenarios:
        if s['id'] not in subtitles:continue
        cards.append(dict(id=s['id'],title=s['title'],subtitle=subtitles[s['id']],description=s['description'],cover=s['checkpoints'][-1 if s['id']=='mechanical' else 0]['image'],config=f"scenarios/{s['id']}/scenario.json"))
    write_json(ROOT/'scenarios/index.json',cards)
    validation=[]
    for s in scenarios:
        cr={c['id']:c for c in s['criteria']}
        taskids={t['id'] for t in s['tasks']}
        assert all(c['taskId'] in taskids for c in cr.values())
        for cp in s['checkpoints']:
            assert (ROOT/cp['image']).exists(),cp['image']
            assert cp['origin']=='authored_fixture'
            for a in cp['assessments']:
                assert a['criterionId'] in cr
                assert cr[a['criterionId']]['target']==cp['target']
                assert cr[a['criterionId']]['taskId']==cp['taskId']
            if cp.get('video'):assert (ROOT/cp['video']).exists()
        for d in s['documents']:assert (ROOT/d['path']).exists()
        if s['media']['path']:assert (ROOT/s['media']['path']).exists()
        assert any(a['verdict']=='unknown' for cp in s['checkpoints'] for a in cp['assessments'])
        validation.append({'scenario':s['id'],'checkpoints':len(s['checkpoints']),'criteria':len(s['criteria']),'documents':len(s['documents']),'all_references_exist':True,'model_calls':0})
    write_json(ROOT/'data/preparation_validation.json',{'schema':'workshop-preparation-validation-v1','source_files':len(records),'source_bytes':sum(r['bytes'] for r in records),'scenario_count':len(scenarios),'main_cards':len(cards),'checks':validation,'pdf_text_extraction_checked':True,'browser_pdf_rendering_checked':False})
    (ROOT/'data/README.ko.md').write_text('''# 강의용 공개 자료\n\n`source_pack/`는 기존에 선별한 공개 영상7개·사진2개 및 출처·주석의 원본 바이트 복사입니다.\n`import_manifest.json`으로 각 파일의 크기와 SHA256을 검증할 수 있습니다. 원본 패키지 내부 메타데이터의 이전 로컬 경로는 출처 기록이며 앱 경로로 사용하지 않습니다.\n\n`../scenarios/`는 이 자료를 사용하는 교육용 SOP PDF·검사 CSV·실습 설정입니다. 실제 회사 자료가 아니며 현재 모든 판정은 `authored_fixture`입니다. 실제 모델 응답팩은 아직 없고 모델 호출은0회입니다.\n\n전자 조립 정상/오류, 기계 조립/정비는 서로 다른 원본 실행입니다. 계측 사진과 영상은 독립 사례이며 동일 제품의 다지점 치수가 아닙니다. 공개 배포 시 미디어별 원래 라이선스·저작자 고지를 유지해야 합니다.\n\n원본 미디어 목록은 `source_pack/assets_manifest.json`, 라이선스 세부는 각 하위 source/ 및 sources.json을 확인하세요.\n''')
    print(json.dumps({'source_files':len(records),'source_bytes':sum(r['bytes'] for r in records),'scenarios':validation},ensure_ascii=False))

if __name__=='__main__':main()
