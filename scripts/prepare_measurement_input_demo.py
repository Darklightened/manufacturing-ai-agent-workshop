#!/usr/bin/env python3
"""Versioned authored LAB2 input lesson. Never edits the original lesson or catalog."""
from pathlib import Path
import csv, hashlib, json, shutil
import prepare_measurement_demo as base

ROOT=base.ROOT
PAIRS=(('measurement_demo','measurement_input_demo'),('measurement_precision_demo','measurement_input_precision_demo'))

def main():
    protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for old,_ in PAIRS for p in (ROOT/'scenarios'/old).rglob('*') if p.is_file()}
    fb=base.font_bytes()
    for old,new in PAIRS:
        source=ROOT/'scenarios'/old;dest=ROOT/'scenarios'/new;dest.mkdir(exist_ok=True)
        s=json.loads((source/'scenario.json').read_text())
        s['id']=new;s['version']='measurement-input-teaching-v2';s['measurementEntry']='worker_input'
        s['description']='제품을 고르고 검사자·로트를 입력합니다. A/B 표시값을 직접 기록하고, 가려진 C 두께를 확인한 뒤 검수조서를 저장하세요.'
        s['demoNotice']='장비 화면은 강의용 예시입니다. 직접 입력한 측정값과 확인 답변을 현재 검사 기준에 비교합니다.'
        for c in s['criteria']:c['allowWorker']=True
        for cp in s['checkpoints']:
            cp['image']=cp['image'].replace('/'+old+'/', '/'+new+'/')
        s['inspection']['drawing']=s['inspection']['drawing'].replace('/'+old+'/', '/'+new+'/')
        for d in s['documents']:d['path']=d['path'].replace('/'+old+'/', '/'+new+'/')
        for v in s['variants']:
            v['id']=dict(PAIRS)[v['id']];v['config']='scenarios/'+v['id']+'/scenario.json'
        s['exercises']=['제품과 도면 A/B/C의 검사 위치를 확인하고 검사자·검사 로트를 입력하세요.','A 외경과 B 전체 길이의 장비 표시값을 직접 입력하세요. 표시값과 입력값은 별도로 남습니다.','C의 가려진 숫자는 작업자 확인 요청을 통해 답변하세요. 확인값을 추정한 판독값으로 바꾸지 않습니다.','정밀형은 별도 시편이며 같은 표시값 40.02 mm가 길이 기준을 벗어납니다. 다시 입력한 값과 기준 변경 전후를 검수조서에서 비교하세요.']
        for name in ('drawing.svg','product.svg','scene-a.svg','scene-b.svg','scene-c.svg'):shutil.copy2(source/name,dest/name)
        base.make_pdf(s,fb)
        # Add explicit learner-input instructions while retaining real PDF extraction.
        pdf=base.fitz.open(dest/'SOP.pdf');page=pdf.new_page(width=595,height=842);page.insert_font(fontname='NotoKR',fontbuffer=fb)
        lines=[('5. 수강생 입력과 기록 이력',17),('검사를 시작하기 전에 검사자와 검사 로트를 입력합니다.',11),('A 외경: 디지털 캘리퍼스의 26.30 mm 표시를 읽고 직접 입력합니다.',11),('B 전체 길이: 디지털 하이트 게이지의 40.02 mm 표시를 직접 입력합니다.',11),('C 두께: 5.?8 mm는 불확실한 표시입니다. 확인 질문에 답변합니다.',11),('A/B/C 모두 작업자 확인값을 허용합니다. 단위는 mm만 사용합니다.',11),('직접 입력한 값은 작업자 확인값이며 실제 OCR 결과로 표시하지 않습니다.',11),('입력값의 소수점을 임의로 옮기지 않습니다. 범위 밖 값도 그대로 기록합니다.',11),('재입력 시 이전 답변과 최초 표시를 보존합니다. 검수조서에 이력을 표시합니다.',11),('강의용 예시 · 실제 측정 인증이나 품질 승인 아님',10)]
        y=50
        for line,size in lines:
            page.insert_text((42,y),line,fontname='NotoKR',fontsize=size);y+=size*2.3
        pdf.subset_fonts();content=pdf.tobytes(garbage=4,deflate=True);pdf.close();(dest/'SOP.pdf').write_bytes(content)
        with base.fitz.open(dest/'SOP.pdf') as doc:extracted='\n'.join(p.get_text() for p in doc)
        (dest/'SOP.extracted.txt').write_text(extracted)
        normalized=' '.join(extracted.split())
        assert '26.30 mm' in normalized and '40.02 mm' in normalized and '검사 로트' in normalized
        with (dest/'criteria.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=['id','taskId','label','target','kind','unit','lower','upper','allowWorker']);writer.writeheader()
            for c in s['criteria']:writer.writerow({**c,'allowWorker':str(c['allowWorker']).lower()})
        (dest/'scenario.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
    assert protected=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in protected}
    print(json.dumps({'scenarios':[new for _,new in PAIRS],'preserved_original_files':len(protected),'model_calls':0},ensure_ascii=False))

if __name__=='__main__':main()
