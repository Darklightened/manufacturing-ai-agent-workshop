#!/usr/bin/env python3
"""Build a self-contained Korean teaching deck from reviewed content and local assets.

Does not run inference or publish. Render/export with export_slides.py afterwards.
"""
from pathlib import Path
import base64, hashlib, html, json, mimetypes, shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'slides'
DATA = json.loads((OUT / 'content.json').read_text())
CAPTURES = ROOT / 'validation/seminar_final_v1/captures'
USED = {}

def esc(x): return html.escape(str(x))

def uri(path):
    path = Path(path)
    if not path.is_absolute(): path = ROOT / path
    body = path.read_bytes()
    USED[str(path.relative_to(ROOT))] = hashlib.sha256(body).hexdigest()
    return 'data:' + (mimetypes.guess_type(path.name)[0] or 'application/octet-stream') + ';base64,' + base64.b64encode(body).decode()

def picture(path, caption='', cls=''):
    return f'<figure class="{cls}"><img src="{uri(path)}" alt="{esc(caption)}" tabindex="0" data-zoom><figcaption>{esc(caption)}</figcaption></figure>'

def capture(name, caption):
    settled = {
        '06-electronics-documents-compiled-documents.png':'electronics-documents.png',
        '07-electronics-question-question.png':'electronics-question.png',
        '09-electronics-report-detail.png':'electronics-report.png',
        '01-measurement-product-drawing-product-selection.png':'measurement-product-selection.png',
        '02-measurement-uncertain-question.png':'measurement-question.png',
        '03-measurement-confirmed-measurement-results.png':'measurement-results.png',
        '04-measurement-report-detail.png':'measurement-report.png',
    }
    preferred = CAPTURES / 'settled_v3' / settled.get(name,name)
    source = preferred if preferred.is_file() else CAPTURES / name
    name = source.name
    dest = OUT / 'assets' / name
    if source.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    return picture(dest, caption, 'screen')

def tiles(items, cls=''):
    return '<div class="tiles '+cls+'">' + ''.join(f'<article><span class="tile-index">{i+1:02}</span><h3>{esc(a)}</h3><p>{esc(b)}</p></article>' for i,(a,b) in enumerate(items)) + '</div>'

def result_table(kind):
    if kind == 'electronics':
        header=['답변 / 인정 기준','충족','불일치','확인 필요']
        rows=[['방향 확인 + 작업자 확인 인정','6','0','0'],['반대 방향이라고 답변','5','1','0'],['미답변 / 영상 증거만 인정','5','0','1']]
    else:
        header=['제품 / 적용 기준','B 허용 범위','기록값','판정']
        rows=[['표준형','39.90–40.10 mm','40.02 mm','충족'],['정밀형','39.99–40.01 mm','40.02 mm','불일치'],['표준형 상한을 40.01로 변경','39.90–40.01 mm','40.02 mm','불일치']]
    return '<div class="comparison"><div class="eyebrow">조건별 판정 비교</div><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in header)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table><p class="table-note">관찰 기록·답변 보존 및 기준별 재판정</p></div>'

def content_table(table, key):
    note = '범위 단위: mm · C 조건: 작업자 확인값 5.78 mm' if len(table['headers'])==3 and '정밀형 범위' in table['headers'] else '관찰 기록·답변 보존 및 기준별 재판정'
    return '<div class="comparison"><div class="eyebrow">조건 변경 및 판정 비교</div><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in table['headers'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in table['rows'])+'</tbody></table><p class="table-note">'+note+'</p></div>'

def opening_visual(spec):
    kind=spec['kind']
    note='<div class="ribbon opening-note">'+esc(spec['note'])+'</div>' if spec.get('note') else ''
    if kind=='platform':
        return '''<div class="platform-diagram"><div class="platform-input">회사 문서 · 현장 영상 · 음성 · 장비 정보</div><div class="platform-branches"><article class="platform-focus"><span class="diagram-label">오늘의 주제 · 작업 지원</span><h3>Dynin-Omni</h3><p>문서·영상·음성의 해석</p><div class="diagram-arrow">↓</div><h3>업무 Agent</h3><p>정보 조회 · 질문 · 기록</p></article><article><span class="diagram-label">확장 영역 · 로봇 연계</span><h3>Dynin-Robotics</h3><p>작업 이해 · 상태 예측</p><div class="diagram-arrow">↓</div><h3>로봇 작업 실행</h3><p>제어 · 현장 안전 검증</p></article></div><div class="ontology-base"><strong>Field Ontology · 공통 현장 지식</strong><span>공정 · 제품 · 공구 · 작업 순서 · 안전·품질 조건</span></div></div>'''+note
    if kind=='omni':
        return '''<div class="omni-diagram"><div class="modality-row"><span>SOP·텍스트</span><span>사진</span><span>작업 영상</span><span>음성</span></div><div class="diagram-arrow">↓</div><div class="omni-core"><span>통합 모델</span><h3>Dynin-Omni</h3><p>입력 내용의 이해 · 맥락을 반영한 생성</p><small>소개자료: 단일 백본 · Masked Diffusion</small></div><div class="diagram-arrow">↓</div><div class="modality-row outputs"><span>작업 해석</span><span>질문·안내</span><span>결과 설명</span></div></div>'''+note
    if kind=='ontology':
        return '''<div class="ontology-example"><div class="ontology-product"><span class="diagram-label">강의용 제품</span><h3>BSH-2630 · 플랜지 부시</h3><p>제품 → 적용 도면 → 검사 위치 → 허용 조건</p></div><div class="relation-row"><b>도면</b><span>DR-BSH-2630 · 적용 개정 관리</span></div><div class="relation-row"><b>항목</b><span>B 전체 길이 · 단위 mm</span></div><div class="relation-row"><b>기준</b><span>39.90–40.10 mm · 표준형</span></div><div class="relation-row"><b>기록</b><span>40.02 mm · 계측 장면과 연결</span></div><div class="ontology-verdict">같은 대상·기준의 대조 <b>→ 충족</b></div></div>'''+note
    if kind=='access_qr':
        return '<div class="qr-access"><img class="qr-image" src="'+uri(spec['path'])+'" alt="실습 접속 QR"><a class="qr-address" href="'+esc(spec['url'])+'" target="_blank" rel="noopener">'+esc(spec['url'])+'</a><strong class="qr-next">'+esc(spec['button'])+' 선택</strong><p>접속 제한 시 강사 안내 대체 주소 이용</p><small>주소 전환 전 진행 내보내기 · 새 주소에서 가져오기</small></div>'
    if kind=='reference_sheet':
        headers=''.join('<th>'+esc(h)+'</th>' for h in spec['headers'])
        rows=''.join('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in row)+'</tr>' for row in spec['rows'])
        return '<div class="reference-sheet">'+picture(spec['path'],spec['caption'],'reference-figure')+'<table><thead><tr>'+headers+'</tr></thead><tbody>'+rows+'</tbody></table></div>'
    if kind=='record_relation':
        rows=''.join('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in row)+'</tr>' for row in spec['rows'])
        return '<div class="record-relation"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in spec['headers'])+'</tr></thead><tbody>'+rows+'</tbody></table><div class="relation-reading">'+''.join('<article><span>'+str(i+1).zfill(2)+'</span><div><h3>'+esc(a)+'</h3><p>'+esc(b)+'</p></div></article>' for i,(a,b) in enumerate(spec['items']))+'</div><p class="record-caption">연결 작업만 수정 · 원래 기준과 수정 이력의 보존</p></div>'
    if kind=='cards':return tiles(spec['items'],'opening-cards')+note
    if kind=='flow':
        return '<div class="pipeline opening-flow">'+''.join(f'<article><span>{i+1:02}</span><h3>{esc(a)}</h3><p>{esc(b)}</p></article>' for i,(a,b) in enumerate(spec['items']))+'</div>'+note
    if kind=='clip':
        return '<figure class="screen pov-slide"><video controls playsinline preload="metadata" poster="'+uri(spec['poster'])+'"><source src="'+uri(spec['webm'])+'" type="video/webm"><source src="'+uri(spec['mp4'])+'" type="video/mp4"></video><figcaption>'+esc(spec['caption'])+'</figcaption></figure><a class="access-link" href="'+esc(spec['url'])+'" target="_blank" rel="noopener"><strong>실습 영상 열기</strong><span>PDF에서는 링크로 열기 · HTML·PPTX에는 영상 포함</span></a>'
    if kind=='linked_screen':
        return picture(spec['path'],spec['caption'],'screen opening-screen')+f'<a class="access-link" href="{esc(spec["url"])}" target="_blank" rel="noopener"><strong>{esc(spec["linkLabel"])}</strong><span>{esc(spec["url"])}</span></a>'
    if kind=='checklist':
        return '<div class="ready-list">'+''.join(f'<div><b>{i+1:02}</b><strong>{esc(a)}</strong><span>{esc(b)}</span></div>' for i,(a,b) in enumerate(spec['items']))+'</div>'+note
    if kind=='lab_pipeline':
        return '<div class="lab-pipeline">'+''.join(f'<article><span class="diagram-label">{i+1:02} · {esc(t)}</span><h3>{esc(a)}</h3><p>{esc(b)}</p></article>' for i,(a,b,t) in enumerate(spec['items']))+'</div>'+note
    if kind=='stage_io':
        return '<div class="stage-io">'+''.join(f'<article><span class="diagram-label">{esc(label)}</span><h3>{esc(title)}</h3><p>{esc(body)}</p></article>' for label,title,body in spec['items'])+'</div>'+note
    raise ValueError('Unsupported opening visual: '+kind)

def technical_visual(s):
    """Keep the stage overview above a short, explicitly illustrative output trace."""
    t=s['technical'];spec=s['visualSpec']
    flow=[]
    for i,item in enumerate(spec['items']):
        if spec['kind']=='lab_pipeline':
            title,body,role=item;label=f'{i+1:02} · {role}'
        else:
            label,title,body=item
        flow.append(f'<article><span>{esc(label)}</span><h3>{esc(title)}</h3><p>{esc(body)}</p></article>')
    tags=''.join(f'<li>{esc(x)}</li>' for x in t['method_tags'])
    return '<div class="tech-flow" style="--steps:'+str(len(flow))+'">'+''.join(flow)+'</div>'+f'''
    <div class="tech-panels">
      <article class="tech-background"><h2>기술 배경</h2><h3>{esc(t['principle_title'])}</h3><p>{esc(t['principle'])}</p><ul>{tags}</ul></article>
      <article class="tech-output"><h2>입력과 출력 예시</h2><div class="tech-input"><b>입력</b><p>{esc(t['input'])}</p></div><h3>{esc(t['output_label'])}</h3><pre>{esc(t['output'])}</pre><small>구조 설명용 예시 · 실제 API 응답 형식과 다를 수 있음</small></article>
      <article class="tech-change"><h2>상태·판정의 변화</h2><div class="state-before"><b>이전</b><p>{esc(t['before'])}</p></div><div class="state-arrow" aria-hidden="true">↓</div><div class="state-after"><b>이후</b><p>{esc(t['after'])}</p></div><p class="tech-interpretation">{esc(t['interpretation'])}</p></article>
    </div><div class="tech-note">{esc(spec.get('note',''))}</div>'''

def visual(key):
    electronics=json.loads((ROOT/'scenarios/electronics_demo/scenario.json').read_text())
    frames=electronics['checkpoints']
    if key in ('overview','hero'):
        return '<div class="hero-pair">'+picture(frames[1]['image'],'01 · 전자 조립 / 공개 영상 장면')+picture('scenarios/measurement_demo/scene-a.svg','02 · 치수 검사 / 강의용 계측 도해')+'</div><div class="ribbon">자료 입력 → 작업 확인 → 판정 → 결과 기록</div>'
    if key=='agenda':
        rows=[(r['time'],r['title'],str(r['minutes'])+'분') for r in DATA['agenda']]
        return '<div class="agenda">'+''.join(f'<div class="agenda-row"><time>{a}</time><strong>{b}</strong><span>{c}</span></div>' for a,b,c in rows)+f'<p>총 {DATA["workshopMinutes"]}분 = 설명 {DATA["explanationMinutes"]}분 + 실습·토의 {DATA["activityMinutes"]}분 + 휴식 30분</p></div>'
    if key in ('pipeline','architecture'):
        return '<div class="pipeline">'+''.join(f'<article><span>{i+1:02}</span><h3>{a}</h3><p>{b}</p></article>' for i,(a,b) in enumerate([('회사 자료','작업지시서 PDF · 검사 기준 CSV'),('정보 구축','텍스트 추출 → 기준 검증 → SQLite'),('작업·제품 선택','작업 순서 · 도면 · 검사 위치'),('장면·측정 기록','준비된 예시를 순서대로 확인'),('질문과 답변','보이지 않거나 흐린 값 확인'),('기준 비교','충족 / 불일치 / 확인 필요'),('이력 저장','원래 값 · 확인값 · 적용 기준'),('결과 내보내기','검수조서 · 보고서 · 데이터')]))+'</div>'
    if key in ('boundaries','roles'):
        return '<div class="role-columns"><article><span class="label">사전 준비 자료</span><h3>영상·계측 관찰 예시</h3><p>전자 조립: 공개 영상·사전 작성 관찰</p><p>계측 검사: 가상 제품·도면·판독 예시</p><p>실시간 AI·OCR 호출 미사용</p></article><article><span class="label green">실습 중 실행 기능</span><h3>검증·판정·기록 처리</h3><p>PDF 추출 · CSV 검증 · DB 구성</p><p>답변·단위·허용 범위에 따른 판정</p><p>보고서 생성 · 저장 · 복원</p></article></div>'
    if key=='start':
        return '<div class="start-card"><span class="label">공용 서버 사용 시: 강사 제공 주소 접속</span><h3>로컬 실행 방법</h3><div class="command">python scripts/serve.py</div><p>Python 3 · macOS/Linux: python3 · Windows: py -3</p><div class="address">http://127.0.0.1:8921/</div><div class="small-steps"><span>ZIP 압축 해제</span><b>→</b><span>폴더에서 실행</span><b>→</b><span>브라우저 접속</span></div><p>저장 보고서: HTML 파일 직접 열기</p></div>'
    if key=='electronics_documents':
        return capture('06-electronics-documents-compiled-documents.png','실제 화면 · PDF에서 추출한 정보와 등록된 검사 기준')
    if key in ('electronics_run','electronics_scenes'):
        return '<div class="frame-grid">'+''.join(picture(cp['image'],f'{i+1:02} · {cp["label"]}') for i,cp in enumerate(frames))+'</div>'
    if key=='electronics_question':
        return capture('07-electronics-question-question.png','실습 화면 · 질문 확인 후 작업자 답변 입력')
    if key=='electronics_progress':
        return '<div class="role-columns"><article><span class="label">프로펠러 장면</span><h3>장착 진행 중</h3><p>장착 동작 및 작업 진행 기록</p><p>완료 증거 미확보</p></article><article><span class="label green">다음 배터리 장면</span><h3>장착 완료 기록</h3><p>프로펠러 장착 완료 기록</p><p>배터리 방향 질문 별도 유지</p></article></div><div class="ribbon">장면 진행 상태와 검사 완료 상태의 구분</div>'
    if key=='electronics_policy': return result_table('electronics')
    if key=='electronics_report':
        return capture('09-electronics-report-detail.png','실제 화면 · 관찰과 작업자 확인을 구분한 결과')
    if key=='measurement_product':
        return capture('01-measurement-product-drawing-product-selection.png','실제 화면 · 표준형 / 정밀형과 제품별 도면 선택')
    if key=='measurement_drawing':
        return picture('scenarios/measurement_demo/drawing.svg','자체 제작 검사 도면 · A 외경 / B 길이 / C 두께', 'drawing')
    if key in ('measurement_record','measurement_scenes'):
        return '<div class="instrument-grid">'+''.join(picture(f'scenarios/measurement_demo/scene-{x}.svg',label) for x,label in [('a','A · 외경 / 디지털 캘리퍼스'),('b','B · 길이 / 디지털 하이트 게이지'),('c','C · 두께 / 플랜지 가장자리 확대')])+'</div>'
    if key=='measurement_question':
        return capture('02-measurement-uncertain-question.png','실제 화면 · 불확실한 표시를 값과 단위로 재확인')
    if key=='measurement_provenance':
        return '<div class="role-columns"><article><span class="label">최초 후보 · 보존</span><h3>5.?8 mm</h3><p>숫자 한 자리 가림 상태</p><p>최초 판독 문자열 보존</p></article><article><span class="label green">작업자 확인값</span><h3>5.78 mm</h3><p>확인값·단위 직접 입력</p><p>확인 출처 및 이전 답변 보존</p></article></div><div class="ribbon">578 mm 입력 시 범위 불일치 · 소수점 자동 보정 없음</div>'
    if key=='measurement_compare': return result_table('measurement')
    if key=='measurement_results':
        return capture('03-measurement-confirmed-measurement-results.png','실제 화면 · 5.78 mm 확인 후 세 치수 기록')
    if key=='measurement_report':
        pieces=[]
        for suffix,label in [('header','실제 저장한 치수 검수조서 · 제품·도면·시편'),('table','치수별 결과 · 원래 후보와 작업자 확인값')]:
            name=f'measurement-inspection-{suffix}.png'
            source=CAPTURES/'inspection_final'/name
            dest=OUT/'assets'/name
            if source.is_file():shutil.copy2(source,dest)
            pieces.append(picture(dest,label,suffix))
        return '<div class="report-pair">'+''.join(pieces)+'</div>'
    if key=='recovery':
        return tiles([('진행 내보내기','답변·변경 기준·이력을 JSON으로 저장'),('새로고침','같은 브라우저·주소에서 진행 복원'),('가져오기','저장 JSON을 이용한 기록 복원'),('제품 변경','제품별 신규 검사 기록 생성')])
    if key in ('exports','report_formats'):
        return tiles([('검수조서 HTML','제품·도면·치수별 검사 결과'),('보고서 HTML','장면·질문·확인값과 상세 이력'),('CSV / SQLite','검사 결과와 구조화된 기록'),('진행 JSON','실습 상태 저장과 다음 시간 복원')])
    if key=='closing':
        return '<div class="closing"><div>검사 대상 · 적용 기준</div><div>관찰 기록 · 작업자 확인</div><div class="accent">미확인 항목 · 후속 조치</div><p>제출 자료: 보고서 · 검수조서 · 진행 JSON</p></div>'
    if key in ('exercise','discussion'):
        return tiles([('판정 예상','조건 변경 전 예상 결과 정리'),('조건 변경','답변 또는 기준 중 단일 조건 변경'),('근거 대조','원기록·현재 판정·적용 기준 대조'),('결과 비교','변경 전후 검수조서의 차이 정리')])
    return tiles([('기준','작업지시서와 검사 범위'),('관찰','현재 장면과 기록값'),('확인','불확실한 정보를 질문'),('기록','근거를 남긴 검수조서')])

CSS = r'''
.pov-slide video{width:100%;height:400px;max-height:400px;flex-shrink:0;aspect-ratio:16/9;object-fit:contain;background:#122039;border-radius:12px}.pov-slide{height:auto!important;flex-shrink:0}.pov-slide figcaption{font-size:17px;line-height:1.5}

.technical{padding:48px 60px 52px!important}.technical .brand{right:60px;top:42px;font-size:16px}.technical .kicker{font-size:17px;margin-bottom:11px}.technical h1{font-size:42px;line-height:1.3;max-width:1450px}.technical .lead{font-size:22px;line-height:1.4;margin-top:11px}.tech-flow{display:grid;grid-template-columns:repeat(var(--steps),1fr);gap:10px;margin-top:21px}.tech-flow article{background:#edf2fb;border:1px solid #dce4f2;border-radius:10px;padding:12px 15px;min-height:116px}.tech-flow span{font-size:14px;color:#6379a1}.tech-flow h3{font-size:21px;margin:6px 0;line-height:1.4;word-break:keep-all}.tech-flow p{font-size:16px;margin:0;line-height:1.45;color:#526780;word-break:keep-all}.tech-panels{display:grid;grid-template-columns:1fr 1.28fr 1.05fr;gap:16px;margin-top:18px;min-height:0;flex:1}.tech-panels>article{min-height:0;padding:20px;background:#fff;border:1px solid #dce4f2;border-radius:14px;min-width:0}.tech-panels h2{font-size:17px;line-height:1.4;color:#536da0;margin:0 0 12px}.tech-panels h3{font-size:25px;line-height:1.4;margin:0 0 12px;word-break:keep-all}.tech-background p{font-size:22px;line-height:1.55;margin:0;word-break:keep-all}.tech-background ul{padding-left:22px;margin:20px 0 0}.tech-background li{font-size:19px;line-height:1.6;color:#536780;margin:5px 0;word-break:keep-all}.tech-input{border-bottom:1px solid #e1e7ef;margin-bottom:12px;padding-bottom:11px}.tech-input b,.state-before b,.state-after b{font-size:15px;line-height:1.4;color:#5c7396}.tech-input p{font-size:20px;line-height:1.5;margin:6px 0 0;word-break:keep-all}.tech-output h3{font-size:18px}.tech-output pre{font-family:Noto,ui-monospace,monospace;font-size:20px;line-height:1.45;background:#edf2fa;border:1px solid #dee6f2;padding:14px;border-radius:9px;margin:0 0 12px;white-space:pre-wrap;overflow-wrap:anywhere}.tech-output small{display:block;font-size:14px;line-height:1.5;color:#697d99;word-break:keep-all}.state-before,.state-after{padding:14px 17px;border-radius:10px;background:#f3f5f9;border:1px solid #e0e6ef}.state-after{background:#eaf0ff;border-color:#cbd8f6}.state-before p,.state-after p{font-size:22px;line-height:1.4;margin:7px 0 0;word-break:keep-all}.state-arrow{color:#627ccb;text-align:center;font-size:25px;line-height:1.2;margin:7px 0}.tech-interpretation{font-size:19px;line-height:1.45;margin:17px 0 0;color:#4a607c;word-break:keep-all}.tech-note{margin-top:14px;padding:11px 16px;border-left:4px solid #667ddd;background:#eaf0ff;color:#3c5281;font-size:18px;line-height:1.5;word-break:keep-all}.technical .slide-foot{left:60px;right:60px;bottom:20px;font-size:13px}
.lab-pipeline{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.lab-pipeline article{background:white;border:1px solid #dbe4f1;border-radius:16px;padding:20px;min-height:165px}.lab-pipeline h3{font-size:25px;margin:10px 0}.lab-pipeline p{font-size:20px;line-height:1.5;color:#576b85;margin:0;word-break:keep-all}.stage-io{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.stage-io article{padding:25px 20px;background:white;border:1px solid #dbe4f1;border-radius:18px;min-height:260px}.stage-io h3{font-size:26px;line-height:1.4;margin:24px 0 18px}.stage-io p{font-size:21px;line-height:1.6;word-break:keep-all;color:#576b85;margin:0}
.walkthrough{padding:28px 52px 50px!important}.walkthrough .brand{top:26px;right:52px;font-size:16px}.walkthrough .kicker{font-size:15px;margin-bottom:8px}.walkthrough h1{font-size:33px;line-height:1.3;letter-spacing:-.7px;max-width:1410px}.walkthrough .lead{font-size:20px;line-height:1.4;margin-top:7px;max-width:1460px;color:#374e70}.phase-strip{display:flex;gap:8px;margin-top:13px;font-size:15px;line-height:1.4}.phase-strip span{flex:1;text-align:center;padding:7px 9px;border:1px solid #dce3ee;border-radius:6px;color:#6b7e94;background:#eef2f8}.phase-strip .current{background:#243e6c;border-color:#243e6c;color:white;font-weight:750}.walkthrough .slide-body{display:grid;grid-template-columns:minmax(0,1fr) 288px;gap:20px;margin-top:14px;padding-bottom:0;align-items:center;flex:1;min-height:0}.walkthrough .visual{gap:8px;min-height:0;align-self:center}.walkthrough .visual figure{gap:8px}.walkthrough .visual img{max-height:606px;width:100%;object-fit:contain;border:1px solid #d9e1ed;border-radius:10px;box-shadow:0 7px 25px #213d6812}.walkthrough figcaption{font-size:14px;line-height:1.5}.step-panel{display:flex;flex-direction:column;gap:14px;align-self:center}.step-panel article{background:white;border:1px solid #dce4ef;border-radius:12px;padding:18px}.step-panel h3{font-size:16px;line-height:1.4;color:#5d7392;margin:0 0 10px}.step-panel p{font-size:21px;line-height:1.5;margin:0;word-break:keep-all;color:#223b5e}.step-panel .execution-mode{border-left:4px solid #637dd2;background:#eef2ff;font-size:16px;line-height:1.5;color:#425c8d;padding:13px}.step-panel .capture-tip{font-size:14px;line-height:1.5;color:#687b93;margin:0 4px}.walkthrough .slide-foot{left:52px;right:52px;bottom:20px;font-size:13px}
.platform-diagram,.omni-diagram,.ontology-example{font-size:22px;line-height:1.5}.platform-input{padding:14px 18px;background:#e7ecf8;border-radius:12px;text-align:center;font-weight:650;color:#3d5273}.platform-branches{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:14px 0}.platform-branches article{padding:22px 25px;background:white;border:1px solid #d8e1ed;border-radius:15px}.platform-branches .platform-focus{background:#edf2ff;border-color:#8d9ee2}.diagram-label{font-size:16px;font-weight:650;color:#576991}.platform-branches h3{font-size:27px;margin:10px 0 4px}.platform-branches p{font-size:21px;color:#5a6f89;margin:0}.diagram-arrow{text-align:center;font-size:28px;line-height:1.3;color:#687de1;margin:8px 0}.ontology-base{background:#203453;color:white;border-radius:14px;padding:18px 24px;text-align:center}.ontology-base strong,.ontology-base span{display:block}.ontology-base strong{font-size:24px}.ontology-base span{font-size:19px;color:#c8d6ee;margin-top:5px}.modality-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.modality-row span{background:white;border:1px solid #d9e2ef;border-radius:12px;padding:18px 8px;text-align:center;font-size:21px}.modality-row.outputs{grid-template-columns:repeat(3,1fr)}.omni-core{background:#203453;color:white;border-radius:20px;padding:32px 25px;text-align:center}.omni-core>span{font-size:17px;color:#b7c9ee}.omni-core h3{font-size:44px;margin:8px 0 16px}.omni-core p{font-size:24px;margin:0 0 16px}.omni-core small{font-size:17px;color:#bacbec}.ontology-example{background:white;border:1px solid #dbe4f1;border-radius:18px;padding:24px 28px}.ontology-product{border-bottom:2px solid #e0e7f3;padding-bottom:17px;margin-bottom:5px}.ontology-product h3{font-size:28px;margin:5px 0 10px}.ontology-product p{font-size:20px;color:#5e728c;margin:0}.relation-row{display:grid;grid-template-columns:70px 1fr;gap:18px;padding:15px 0;border-bottom:1px solid #e3e9f1;font-size:22px}.relation-row b{color:#4c60b5}.ontology-verdict{font-size:22px;color:#60718a;padding-top:18px}.ontology-verdict b{color:#1c745f;margin-left:25px}
.opening-cards article{min-height:190px;padding:24px}.opening-cards h3{font-size:27px}.opening-cards p{font-size:22px}.opening-note{font-size:21px;line-height:1.5;padding:18px 20px}.opening-flow article{min-height:175px;padding:20px 15px}.opening-flow h3{font-size:24px;margin:14px 0 10px}.opening-flow p{font-size:19px}.opening-screen{height:auto;flex:1;min-height:0}.opening-screen img{max-height:360px}.access-link{display:block;border:1px solid #bccaf7;border-radius:14px;background:#e9efff;padding:18px 22px;text-decoration:none;color:#3049ad}.access-link strong{display:block;font-size:25px;margin-bottom:8px}.access-link span{display:block;font-size:19px;line-height:1.5;overflow-wrap:anywhere}.ready-list{background:white;border:1px solid #dbe4f1;border-radius:18px;padding:12px 25px}.ready-list>div{display:grid;grid-template-columns:48px 80px 1fr;gap:18px;align-items:center;padding:25px 0;border-bottom:1px solid #e1e7f2;font-size:23px;line-height:1.5}.ready-list>div:last-child{border-bottom:0}.ready-list b{color:#5c71ca}.ready-list span{color:#52677f}

@font-face{font-family:Noto;src:url(__FONT__) format('woff2');font-weight:100 900;font-display:block}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden}body{font-family:Noto,sans-serif;background:#10182c;color:#16233c}button{font:inherit;cursor:pointer}button:focus-visible,img:focus-visible{outline:4px solid #36bfc2;outline-offset:4px}#viewport{position:absolute;inset:44px 0 52px;display:flex;align-items:center;justify-content:center;overflow:hidden}#stage{position:relative;flex-shrink:0;width:1600px;height:900px;transform:scale(var(--scale,1));transform-origin:center}section.slide{position:absolute;inset:0;background:#f7f9fd;display:none;padding:56px 72px 46px;overflow:hidden}.slide.active{display:flex;flex-direction:column}.brand{position:absolute;right:72px;top:45px;font-size:18px;letter-spacing:3px;font-weight:800;color:#2947a9}.kicker{font-size:18px;font-weight:700;letter-spacing:2px;color:#4158df;margin-bottom:17px}h1{font-size:49px;line-height:1.3;letter-spacing:-1.5px;margin:0;max-width:1390px;word-break:keep-all}.lead{font-size:23px;line-height:1.55;color:#536780;max-width:1370px;margin:15px 0 0;word-break:keep-all}.slide-body{display:grid;grid-template-columns:440px 1fr;gap:40px;margin-top:32px;flex:1;min-height:0;padding-bottom:28px}.text-column{display:flex;flex-direction:column;justify-content:center}.points{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:21px}.points li{font-size:28px;line-height:1.5;word-break:keep-all;padding-left:23px;position:relative}.points li:before{content:'';position:absolute;width:7px;height:7px;left:0;top:17px;background:#4b5ce4;border-radius:50%}.aside-label{font-size:15px;color:#6b7e96;margin-top:28px;padding-top:20px;border-top:1px solid #d8e1ee}.visual{min-width:0;min-height:0;display:flex;flex-direction:column;justify-content:center;gap:22px}figure{margin:0;min-width:0;min-height:0;display:flex;flex-direction:column;align-items:center;gap:10px}figure img{display:block;max-width:100%;max-height:500px;object-fit:contain;border-radius:14px;cursor:zoom-in}figcaption{font-size:15px;line-height:1.4;color:#667a94;text-align:center;word-break:keep-all}.screen{height:100%;justify-content:center}.screen img{max-height:490px;border:1px solid #dae2f0;box-shadow:0 12px 32px #1a305012}.drawing img{max-height:530px}.hero-pair{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:center}.hero-pair img{height:340px;object-fit:cover}.ribbon{border-radius:14px;background:#e9edff;color:#3346ad;padding:24px;font-size:24px;text-align:center;font-weight:700}.tiles{display:grid;grid-template-columns:1fr 1fr;gap:22px}.tiles article{background:white;border:1px solid #dbe4f1;border-radius:20px;padding:27px;min-height:195px}.tile-index{font-size:17px;color:#687deb;font-weight:800}.tiles h3{margin:12px 0 10px;font-size:28px}.tiles p{font-size:21px;line-height:1.55;color:#546b86;margin:0;word-break:keep-all}.role-columns{display:grid;grid-template-columns:1fr 1fr;gap:20px}.role-columns article{border-radius:20px;background:white;padding:32px 25px;border:1px solid #dbe4f1}.label{font-size:17px;color:#5362c6;background:#eef0ff;padding:8px 13px;border-radius:8px;display:inline-block}.label.green{background:#dff4ed;color:#18745c}.role-columns h3{font-size:27px;line-height:1.4;margin:22px 0}.role-columns p{font-size:22px;line-height:1.55;color:#52677f;margin:20px 0}.pipeline{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}.pipeline article{border-radius:18px;border:1px solid #dce3f3;background:white;padding:25px 18px;min-height:210px}.pipeline span{font-weight:800;color:#5064e1;font-size:19px}.pipeline h3{font-size:25px;margin:18px 0 12px;word-break:keep-all}.pipeline p{font-size:19px;line-height:1.55;color:#5f7189;margin:0;word-break:keep-all}.comparison{border-radius:20px;padding:32px;background:white;border:1px solid #dbe4f1}.eyebrow{color:#576bd0;font-size:18px;font-weight:700;margin-bottom:26px}table{border-collapse:collapse;width:100%;font-size:21px}th{color:#63748b;font-size:18px;text-align:left;padding:15px 10px;background:#f4f6fc}td{padding:25px 10px;border-bottom:1px solid #e1e7f1;word-break:keep-all;line-height:1.55}td:first-child{font-weight:650}.table-note{font-size:18px;line-height:1.5;color:#63748b;margin:23px 0 0}.agenda{background:white;border:1px solid #dce3f1;border-radius:20px;padding:20px 28px}.agenda-row{display:grid;grid-template-columns:175px 1fr 150px;gap:18px;align-items:center;padding:10px 0;border-bottom:1px solid #e4e9f2;font-size:17px}.agenda-row time{font-weight:650;color:#5266cb}.agenda-row strong{font-weight:650}.agenda-row span{color:#6a7a91;text-align:right}.agenda>p{font-size:18px;color:#5362b1;text-align:center;margin:20px 0 5px}.start-card{border:1px solid #dce4f2;background:white;border-radius:22px;padding:35px}.start-card h3{font-size:30px;margin:28px 0 20px}.command,.address{padding:24px;border-radius:12px;font-family:Noto,sans-serif;font-size:28px;background:#152440;color:white;letter-spacing:.2px}.address{background:#edf1ff;color:#374ab4;font-size:25px;margin-top:23px}.start-card p{font-size:18px;color:#71829a}.small-steps{display:flex;align-items:center;justify-content:space-between;font-size:20px;margin-top:25px}.small-steps b{color:#7b8be2}.frame-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.frame-grid img{width:100%;height:195px;object-fit:cover}.frame-grid figcaption{font-size:18px}.instrument-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.instrument-grid figure:last-child{grid-column:1/-1}.instrument-grid img{max-height:228px}.closing{background:#172743;color:white;border-radius:24px;padding:60px 48px;font-size:44px;font-weight:750;line-height:1.6;letter-spacing:-1px}.closing .accent{color:#aebfff}.closing p{font-size:21px;line-height:1.6;color:#becbe0;font-weight:400;margin-top:25px}.slide-foot{position:absolute;bottom:26px;left:72px;right:72px;display:flex;justify-content:space-between;font-size:14px;color:#71829a}.slide-foot a{color:inherit;text-decoration:none}.slide-foot b{font-weight:600;color:#5269ba}.wide .slide-body{grid-template-columns:300px 1fr;gap:35px}.wide .points li{font-size:23px}.cover h1{font-size:67px;max-width:1200px}.cover .slide-body{grid-template-columns:380px 1fr}.cover .lead{font-size:25px}.notes-source{display:none}#topbar,#controls{position:fixed;left:0;right:0;display:flex;align-items:center;gap:9px;background:#10182c;color:#d7e2fb;padding:6px 18px;z-index:5}#topbar{height:44px;top:0;font-size:13px}#topbar .grow{flex:1}#controls{bottom:0;height:52px;justify-content:center}#controls button,#topbar button{border:1px solid #3b4964;background:#1c2b45;color:#e8edfb;border-radius:6px;padding:6px 12px;font-size:13px}#counter{min-width:90px;text-align:center;font-size:14px}#progress{position:fixed;bottom:0;height:3px;background:#94a4ff;left:0;z-index:9}#notes{display:none;position:fixed;bottom:58px;right:20px;width:min(630px,90vw);max-height:65vh;overflow:auto;background:#fff9e8;color:#24314a;padding:25px;z-index:20;border-radius:14px;box-shadow:0 16px 60px #0005;font-size:18px;line-height:1.7;white-space:pre-wrap}#notes.open{display:block}#toc{display:none;position:fixed;inset:50px 20px 60px;background:#edf2fb;padding:28px;z-index:30;border-radius:16px;overflow:auto;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}#toc.open{display:grid}#toc button{border:1px solid #d0d9e8;border-radius:8px;background:white;color:#1c304e;text-align:left;padding:18px;font-size:16px;line-height:1.5}#zoom{display:none;position:fixed;inset:0;background:#0a142bed;z-index:60;align-items:center;justify-content:center;padding:40px}#zoom.open{display:flex}#zoom img{max-width:96vw;max-height:90vh;object-fit:contain}#zoom button{position:absolute;right:20px;top:12px;background:white;border:0;padding:8px 15px;border-radius:5px}#topbar a{color:#d7e2fb;text-decoration:none}#topbar a:hover{text-decoration:underline}
 .report-pair{display:flex;flex-direction:column;gap:16px}.report-pair .header img{max-height:150px}.report-pair .table img{max-height:290px}
.visual figure.opening-screen{height:auto;flex:1;min-height:0}.visual figure.opening-screen img{max-height:380px}.visual figure.opening-screen figcaption{flex-shrink:0}
@media print{@page{size:1600px 900px;margin:0}html,body{width:auto;height:auto;overflow:visible;background:white}#topbar,#controls,#progress,#notes,#toc,#zoom{display:none!important}#viewport{position:static;display:block}#stage{width:1600px;height:auto;transform:none}.slide,section.slide{position:relative;display:flex!important;flex-direction:column;width:1600px;height:900px;break-after:page;page-break-after:always}.slide:last-child{break-after:auto;page-break-after:auto}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
'''


CSS += r'''
.qr-access{height:570px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:15px;background:#fff;border:1px solid #dce2ed;border-radius:16px;padding:22px}.qr-access .qr-image{width:335px;height:335px;object-fit:contain;image-rendering:pixelated}.qr-address{font-size:22px;line-height:1.4;overflow-wrap:anywhere;text-align:center;color:#243c95;max-width:790px}.qr-next{font-size:23px}.qr-access p{font-size:19px;margin:0}.qr-access small{font-size:16px;color:#69778a}.reference-sheet{display:flex;flex-direction:column;gap:14px}.reference-sheet figure{margin:0;display:flex;flex-direction:column;align-items:center;gap:8px}.reference-sheet img{width:100%;max-height:310px;object-fit:contain}.reference-sheet figcaption{font-size:16px;color:#62718a}.reference-sheet table,.record-relation table{width:100%;border-collapse:collapse;font-size:20px;line-height:1.4}.reference-sheet th,.reference-sheet td,.record-relation th,.record-relation td{padding:12px 13px;border:1px solid #cbd5e2;text-align:left}.reference-sheet th,.record-relation th{background:#edf2fa;font-weight:700}.relation-reading{display:flex;flex-direction:column;gap:14px;margin-top:25px}.relation-reading article{display:flex;gap:20px;align-items:center;border:1px solid #dce2ed;padding:17px 20px;border-radius:10px;background:#f8faff}.relation-reading article>span{font-size:21px;color:#4b5ce4}.relation-reading h3{font-size:23px;margin:0 0 5px}.relation-reading p{font-size:20px;margin:0}.record-caption{font-size:19px;color:#63718a;margin:18px 0 0}
'''

JS=r'''
const slides=[...document.querySelectorAll('.slide')];let current=0;const $=id=>document.getElementById(id);
function resize(){document.documentElement.style.setProperty('--scale',Math.min(innerWidth/1600,(innerHeight-96)/900));}addEventListener('resize',resize);resize();
function go(n){document.querySelectorAll('video').forEach(v=>v.pause());current=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,i)=>{s.classList.toggle('active',i===current);s.setAttribute('aria-hidden',i===current?'false':'true');});$('counter').textContent=`${current+1} / ${slides.length}`;$('progress').style.width=`${(current+1)/slides.length*100}%`;$('notes').textContent=slides[current].querySelector('.notes-source').textContent;$('prev').disabled=current===0;$('next').disabled=current===slides.length-1;history.replaceState(null,'',`#${current+1}`);}
window.goSlide=go;$('prev').onclick=()=>go(current-1);$('next').onclick=()=>go(current+1);$('notes-toggle').onclick=()=>$('notes').classList.toggle('open');$('toc-toggle').onclick=()=>$('toc').classList.toggle('open');$('print').onclick=()=>print();$('fullscreen').onclick=async()=>{try{document.fullscreenElement?await document.exitFullscreen():await document.documentElement.requestFullscreen();}catch(e){$('notes').textContent='브라우저 전체화면 단축키를 사용하세요.';$('notes').classList.add('open');}};
$('toc').querySelectorAll('button').forEach(b=>b.onclick=()=>{go(Number(b.dataset.index));$('toc').classList.remove('open');});
function closeZoom(){$('zoom').classList.remove('open');}document.querySelectorAll('[data-zoom]').forEach(img=>{function zoom(){$('zoom-image').src=img.src;$('zoom-image').alt=img.alt;$('zoom').classList.add('open');}img.onclick=zoom;img.onkeydown=e=>{if(e.key==='Enter')zoom();};});$('zoom-close').onclick=closeZoom;$('zoom').onclick=e=>{if(e.target===$('zoom'))closeZoom();};
addEventListener('keydown',e=>{if(/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;if(e.key==='Escape'){closeZoom();$('toc').classList.remove('open');$('notes').classList.remove('open');return;}if($('zoom').classList.contains('open'))return;if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();go(current+1);}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();go(current-1);}if(e.key==='Home')go(0);if(e.key==='End')go(slides.length-1);if(e.key.toLowerCase()==='n')$('notes-toggle').click();if(e.key.toLowerCase()==='o')$('toc-toggle').click();if(e.key.toLowerCase()==='f')$('fullscreen').click();});go((Number(location.hash.slice(1))||1)-1);
'''

def main():
    OUT.mkdir(exist_ok=True)
    sections=[];toc=[]
    for i,s in enumerate(DATA['slides']):
        if s.get('technical'):
            sections.append(f'<section class="slide technical" id="slide-{i+1}" data-slide-id="{esc(s["id"])}"><div class="brand">DYNIN · WORKSHOP</div><div class="kicker">파이프라인 · 기술 배경</div><h1>{esc(s["title"])}</h1><p class="lead">{esc(s["lead"])}</p>'+technical_visual(s)+f'<footer class="slide-foot"><span>강의용 예시 / 기술 원리·출력 구조·상태 변화 설명 / 실시간 모델 호출 없음</span><b>{i+1:02} / {len(DATA["slides"]):02}</b></footer><div class="notes-source">{esc(s["notes"])}</div></section>')
            toc.append(f'<button data-index="{i}">{i+1:02} · {esc(s["title"])}</button>')
            continue
        if s.get('walkthrough'):
            w=s['walkthrough']
            phases='<div class="phase-strip">'+''.join(f'<span class="{"current" if p==w["phase"] else ""}">{esc(p)}</span>' for p in w['phases'])+'</div>'
            panel='<aside class="step-panel">'+''.join(f'<article><h3>{esc(a)}</h3><p>{esc(b)}</p></article>' for a,b in [('들어오는 정보',w['input']),('시스템 처리',w['process']),('확인할 결과',w['output'])])+f'<div class="execution-mode">{esc(w["mode"])}</div><p class="capture-tip">{esc(w.get("tip","빨간 네모: 누르거나 입력할 위치"))}</p></aside>'
            notes=s.get('notes','')
            attribution = {'lab1':'전자 조립: EgoOops · CC BY-SA 4.0','lab3':'기계 조립: IndustReal · Apache-2.0'}.get(s.get('section'),'실제 브라우저 화면') + ' / 강의용 예시 · '+w.get('tip','빨간 네모: 조작 위치').split(' · ')[0]
            sections.append(f'<section class="slide walkthrough" id="slide-{i+1}" data-slide-id="{esc(s["id"])}"><div class="brand">DYNIN · WORKSHOP</div><div class="kicker">{esc(s["kicker"])}</div><h1>{esc(s["title"])}</h1><p class="lead">{esc(s["lead"])}</p>{phases}<div class="slide-body"><div class="visual">'+picture(w['image'],'실제 실습 화면 · 강의용 예시 · 그림 클릭으로 확대')+'</div>'+panel+f'</div><footer class="slide-foot"><span>{esc(attribution)}</span><b>{i+1:02} / {len(DATA["slides"]):02}</b></footer><div class="notes-source">{esc(notes)}</div></section>')
            toc.append(f'<button data-index="{i}">{i+1:02} · {esc(s["title"])}</button>')
            continue
        key=s.get('visualKey','overview')
        rendered_visual = opening_visual(s['visualSpec']) if s.get('visualSpec') else (content_table(s['table'],key) if key in ['electronics_policy','measurement_compare'] and s.get('table') else visual(key))
        classes='slide '+('cover' if i==0 else '')+(' wide' if key in ['pipeline','agenda','electronics_run','measurement_record','measurement_compare','electronics_policy','opening_flow'] else '')
        notes=s.get('notes','')
        if isinstance(notes,list):notes='\n\n'.join(notes)
        attribution = '전자 장면 발췌: <a href="https://y-haneji.github.io/EgoOops-project-page/">EgoOops · Yuto Haneji 외</a> · CC BY-SA 4.0 / 계측: 자체 제작 도해'
        if s.get('visualSpec',{}).get('kind')=='clip':
            attribution='작업자 시점 계측 장면 / 강의용 예시 / 재생 후 측정값 기록'
        if 1 <= i <= 8 and s.get('references'):
            attribution = '참고: 제공된 DyninAI·Dynin-Omni 소개 및 활용 안내 / 도해: 강의용 재구성'
        sections.append(f'<section class="{classes}" id="slide-{i+1}" data-slide-id="{esc(s["id"])}"><div class="brand">DYNIN · WORKSHOP</div><div class="kicker">{esc(s.get("kicker","제조 AI AGENT 실습"))}</div><h1>{esc(s["title"])}</h1><p class="lead">{esc(s.get("lead",""))}</p><div class="slide-body"><div class="text-column"><ul class="points">'+''.join(f'<li>{esc(b)}</li>' for b in s.get('bullets',[]))+f'</ul><div class="aside-label">강의용 예시</div></div><div class="visual">{rendered_visual}</div></div><footer class="slide-foot"><span>{attribution}</span><b>{i+1:02} / {len(DATA["slides"]):02}</b></footer><div class="notes-source">{esc(notes)}</div></section>')
        toc.append(f'<button data-index="{i}">{i+1:02} · {esc(s["title"])}</button>')
    font=uri('assets/fonts/NotoSansKR.woff2')
    page='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>'+esc(DATA['title'])+'</title><style>'+CSS.replace('__FONT__',font)+'</style></head><body><div id="topbar"><strong>DYNIN 제조 AI Agent 실습 안내</strong><span class="grow"></span><span>← → 이동 · N 강사 메모 · O 목차 · 그림 클릭 확대</span><button id="fullscreen">전체화면 F</button><button id="print">인쇄 / PDF</button></div><main id="viewport"><div id="stage">'+''.join(sections)+'</div></main><nav id="controls" aria-label="슬라이드 이동"><button id="toc-toggle">목차 O</button><button id="prev">← 이전</button><span id="counter" aria-live="polite"></span><button id="next">다음 →</button><button id="notes-toggle">강사 메모 N</button></nav><div id="progress"></div><aside id="notes" aria-label="강사 메모"></aside><div id="toc">'+''.join(toc)+'</div><div id="zoom" role="dialog" aria-label="이미지 확대"><button id="zoom-close">닫기 Esc</button><img id="zoom-image" alt=""></div><script>'+JS+'</script><script type="text/plain" id="font-license">'+esc((ROOT/'assets/fonts/OFL.txt').read_text())+'</script></body></html>'
    target=OUT/'실습_안내.html';target.write_text(page)
    manifest={'schema':'seminar.slides.v1','title':DATA['title'],'slide_count':len(DATA['slides']),'mode':'authored_classroom_explanation','inference_calls':0,'self_contained':True,'font_license':'../assets/fonts/OFL.txt','sources':USED,'content_sha256':hashlib.sha256((OUT/'content.json').read_bytes()).hexdigest(),'html_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'published':False}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'slides':len(DATA['slides']),'html_bytes':target.stat().st_size,'path':str(target)},ensure_ascii=False))

if __name__=='__main__':main()
