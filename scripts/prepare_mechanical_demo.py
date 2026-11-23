#!/usr/bin/env python3
"""Build the separate public mechanical lesson. Historical packs stay untouched."""
from pathlib import Path
import csv, io, json
import pymupdf as fitz
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'scenarios/mechanical_demo'
TARGET='training-chassis-01'

def criterion(cid,task,label,worker=False):
    return dict(id=cid,taskId=task,label=label,target=TARGET,kind='visual',unit='',lower='',upper='',allowWorker=worker)
def assessment(cid,verdict,reason,**extra):
    return dict(criterionId=cid,verdict=verdict,reason=reason,**extra)
def cp(cid,start,end,photo,task,label,note,heads):
    return dict(id=cid,time=end,sourceTime=photo,sourceStart=start,sourceEnd=end,
      taskId=task,target=TARGET,label=label,note=note,sceneSummary=note,
      scopeNote='외관과 배치 확인 예시입니다. 체결 토크·고정 강도·주행 성능은 이 영상으로 판정하지 않습니다.',
      image=f'assets/mechanical-flow/frame_{photo:03d}.jpg',
      videoPath='assets/mechanical-flow/assembly.webm',origin='authored_demo',assessments=heads)

def scenario():
    tasks=[dict(id=k,label=v) for k,v in [('chassis','차체 연결'),('bracket','브래킷 배치'),('axle','바퀴 축 조립'),('final','최종 외관 기록')]]
    criteria=[criterion('MD-CHASSIS','chassis','두 긴 차체 부재와 연결 부재가 조립된 외관'),
      criterion('MD-BRACKET','bracket','전방 브래킷이 차체 앞쪽에 놓인 상태'),
      criterion('MD-PIN','bracket','가려진 브래킷 안쪽 연결 핀의 삽입 상태 확인',True),
      criterion('MD-AXLE-1','axle','한쪽 축의 양쪽 바퀴가 배치된 외관'),
      criterion('MD-AXLE-2','axle','다른 축의 양쪽 바퀴가 배치된 외관'),
      criterion('MD-FINAL','final','차체·브래킷·네 바퀴를 포함한 최종 외관 사진 기록')]
    return dict(id='mechanical_demo',version='mechanical-teaching-v1',mode='demo',demoKind='mechanical',
      title='기계 조립 · 차체와 바퀴 키트',description='차체와 바퀴의 조립 영상을 따라가며 단계별 확인과 질문, 결과 기록을 체험합니다.',
      companyId='edu-daon-mechanical',companyName='다온기계교육',processId='MECH-DEMO-001',productName='차체와 바퀴 조립 키트',orderId='MECH-001',
      sourceNote='IndustReal 01_assy_0_1 공개 영상에 맞춘 강의용 예시입니다. 회사·작업지시서·관찰·질문은 교육용 작성이며 실제 모델 출력이나 생산 품질 승인이 아닙니다.',
      fixtureNotice='강의용 예시 · 공개 영상과 작성한 관찰 · GPU/API 없이 실행',
      demoNotice='영상에서 보이는 배치만 확인하고, 가려진 연결 핀은 작업자 확인을 별도로 기록합니다.',
      setupDescription='차체 연결 → 브래킷 배치 → 바퀴 축 조립 → 최종 외관 기록. 브래킷 안쪽 핀이 가려진 장면에서 한 번 확인을 요청합니다.',
      setupExpected='네 단계와 여섯 검사 항목을 불러옵니다. 브래킷 핀 확인을 포함해 모든 기준이 충족되면 결과를 검토합니다.',
      questionQuickReplies=[dict(confirmation='met',text='핀을 제자리에 끼운 것을 확인했습니다'),dict(confirmation='violated',text='핀이 제대로 끼워지지 않았습니다'),dict(confirmation='unknown',text='아직 확인할 수 없습니다')],
      timelineKind='source_video_timestamps_with_authored_teaching_events',tasks=tasks,criteria=criteria,
      media=dict(path='assets/mechanical-flow/assembly.webm',codec='vp9',browserPlayable=True,duration=184.5),
      sources=[dict(label='IndustReal 공개 조립 영상 · 01_assy_0_1',url='https://github.com/TimSchoonbeek/IndustReal',license='Apache-2.0')],
      variants=[dict(id='mechanical',label='강사용: 이전 기계 조립 기록',config='scenarios/mechanical/scenario.json',instructorOnly=True)],
      exercises=['영상을 재생하고 단계 끝에서 검사 결과와 Agent 통과 신호를 확인하세요.','브래킷 안쪽 연결 핀 질문에 실제 확인한 내용을 선택하세요.','미확인·불일치 답변이면 다음 단계가 보류되는지 확인하세요.','완료 후 질문·답변·네 장의 사진을 포함한 검수조서를 저장하세요.'],
      checkpoints=[
        cp('md1',0,70,69,'chassis','차체 연결 외관 확인','두 긴 차체 부재를 연결합니다. 단계 마지막에는 손을 뗀 차체 연결 상태를 확인합니다.',[
          assessment('MD-CHASSIS','met','69초 장면에서 두 긴 차체 부재와 연결 부재가 조립된 외관을 기록했습니다. 고정 강도는 별도 검사 대상입니다.')]),
        cp('md2',70,90,89,'bracket','브래킷 배치와 연결 핀 확인','앞쪽 브래킷을 놓고 연결합니다. 브래킷의 배치는 보이지만 안쪽 연결 핀은 손에 가려져 직접 확인이 필요합니다.',[
          assessment('MD-BRACKET','met','89초 장면에서 브래킷이 차체 앞쪽에 놓인 상태를 기록했습니다.'),
          assessment('MD-PIN','unknown','안쪽 연결 핀이 손에 가려 삽입 상태를 확인할 수 없습니다.',question='손에 가린 브래킷 안쪽 연결 핀이 제자리에 끼워졌나요? 직접 확인한 결과를 알려 주세요.')]),
        cp('md3',90,178,177,'axle','두 축의 바퀴 배치 확인','두 축에 바퀴를 차례로 배치합니다. 마지막 장면에서 양쪽 축의 네 바퀴가 보이는지만 확인합니다.',[
          assessment('MD-AXLE-1','met','177초 장면에서 한쪽 축 양쪽에 바퀴가 배치된 외관을 기록했습니다.'),
          assessment('MD-AXLE-2','met','177초 장면에서 다른 축 양쪽에도 바퀴가 배치되어 네 바퀴가 보입니다. 너트 체결 토크는 확인하지 않았습니다.')]),
        cp('md4',178,184.4,183,'final','최종 외관 사진 기록','손을 뗀 완성 외관을 기록합니다. 앞 단계의 작업자 확인과 검사 이력을 함께 검토합니다.',[
          assessment('MD-FINAL','met','183초의 차체·브래킷·네 바퀴가 보이는 최종 외관 사진을 기록했습니다. 기능 시험이나 안전 인증은 포함하지 않습니다.')])],
      documents=[dict(id='sop',title='기계 조립 작업지시서 PDF',path='scenarios/mechanical_demo/SOP.pdf',type='pdf'),dict(id='criteria',title='6개 외관·확인 기준 CSV',path='scenarios/mechanical_demo/criteria.csv',type='csv')])

def pdf(s):
    font_file=TTFont(ROOT/'assets/fonts/NotoSansKR.ttf');font_file=instantiateVariableFont(font_file,{'wght':400},inplace=True)
    stream=io.BytesIO();font_file.save(stream);font_bytes=stream.getvalue();font=fitz.Font(fontbuffer=font_bytes)
    doc=fitz.open();page=None;y=0
    def new_page():
        nonlocal page,y
        page=doc.new_page(width=595,height=842);page.insert_font(fontname='NotoKR',fontbuffer=font_bytes)
        page.draw_rect(fitz.Rect(0,0,595,12),color=None,fill=(.08,.32,.35));y=52
    def line(text='',size=10.5):
        nonlocal y
        chunks=[];part=''
        for char in text:
            if font.text_length(part+char,fontsize=size)>507:chunks.append(part);part=''
            part+=char
        chunks.append(part)
        for chunk in chunks:
            if y>780:new_page()
            page.insert_text((44,y),chunk,fontsize=size,fontname='helv' if chunk.isascii() else 'NotoKR',color=(.12,.18,.23));y+=size*1.7
    new_page();line('다온기계교육 | 교육용 작업지시서',19);line('차체와 바퀴 조립 키트',16)
    line('문서번호: SOP-MECH-DEMO-001 · 개정 1 · 작업번호: MECH-001')
    line('강의용 가상 회사 문서 · 공개 영상에 맞춘 외관 확인 예시')
    line('company_id: '+s['companyId'],9);line('process_id: '+s['processId'],9)
    line();line('1. 대상과 검사 범위',14)
    line('한 개의 차체, 앞쪽 브래킷, 두 축의 네 바퀴를 동일 작업 대상으로 기록합니다. 원본 영상의 시각을 유지하여 네 단계로 재생합니다.')
    line('외관·배치와 작업자 확인만 다룹니다. 체결 토크, 고정 강도, 구동 성능 및 생산 안전 승인은 판정하지 않습니다.')
    line();line('2. 작업 순서',14)
    for i,(task,c) in enumerate(zip(s['tasks'],s['checkpoints']),1):
        line('task_id: '+task['id'],9);line(f"{i}. {task['label']} | 원본 {c['sourceStart']}~{c['sourceEnd']}초",11);line(c['note'],10)
    new_page();line('검사 기준과 작업자 확인',19)
    for c in s['criteria']:
        line();line(c['id']+' | '+c['label'],11)
        line('확인 방법: '+('가려진 핀은 작업자 답변을 구분하여 기록합니다.' if c['allowWorker'] else '단계 끝의 공개 영상 장면과 예시 관찰을 기록합니다.'),10)
    line();line('3. 브래킷 연결 핀 질문',14)
    line(s['checkpoints'][1]['assessments'][1]['question'])
    line('제자리에 끼운 것을 확인 → 작업자 확인으로 충족. 제대로 끼워지지 않음 → 불일치. 확인 불가 또는 답변 없음 → 보류.')
    line('이전 답변은 삭제하지 않습니다. 재확인할 때 새 질문과 답변을 기록합니다. 영상 근거만 인정하는 정책으로 바꾸면 가려진 핀은 다시 보류됩니다.')
    line();line('4. 산출물과 출처',14)
    line('검수조서와 작업 보고서에 여섯 항목의 결과, 최초 관찰, 작업자 답변, 단계별 사진을 남깁니다.')
    line('IndustReal 01_assy_0_1 | Apache-2.0',9);line('https://github.com/TimSchoonbeek/IndustReal',9)
    line('문서·판정·질문은 강의용 작성 예시입니다. 실제 모델 분석 결과나 물리적 품질 인증이 아닙니다.',9)
    for i,p in enumerate(doc,1):p.insert_text((44,816),f'DAON | Teaching demo | {i} / {len(doc)}',fontname='helv',fontsize=8)
    doc.set_metadata(dict(title='차체와 바퀴 조립 키트 작업지시서',author='Manufacturing Agent Workshop',subject='Authored teaching example'))
    doc.subset_fonts();doc.save(DEST/'SOP.pdf',garbage=4,deflate=True);doc.close()
    with fitz.open(DEST/'SOP.pdf') as saved:text='\n'.join(p.get_text() for p in saved)
    (DEST/'SOP.extracted.txt').write_text(text,encoding='utf-8')
    assert all('task_id: '+t['id'] in text for t in s['tasks'])

def main():
    DEST.mkdir(parents=True,exist_ok=True);s=scenario()
    (DEST/'scenario.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (DEST/'criteria.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['id','taskId','label','target','kind','unit','lower','upper','allowWorker']);w.writeheader()
        for row in s['criteria']:w.writerow({**row,'allowWorker':str(row['allowWorker']).lower()})
    pdf(s);print('Prepared mechanical_demo: 4 stages / 6 criteria / 1 worker question.')
if __name__=='__main__':main()
