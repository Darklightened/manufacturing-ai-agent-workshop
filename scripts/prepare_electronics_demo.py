#!/usr/bin/env python3
"""Build the standalone authored electronics lesson; never edit historical packs.

Uses existing, attributed public source images as illustrations. No inference,
media generation, GPU job or external publication is performed.
"""
from pathlib import Path
import csv
import hashlib
import io
import json

import pymupdf as fitz
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "scenarios/electronics_demo"
MEDIA = "data/source_pack/electronics/S1790005/"
TARGET = "circuit-board"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def criterion(code, task, label, worker=False):
    return dict(id=code, taskId=task, label=label, target=TARGET, kind="visual",
                unit="", lower="", upper="", allowWorker=worker)


def head(code, verdict, reason, **extra):
    return dict(criterionId=code, verdict=verdict, reason=reason, **extra)


def checkpoint(code, time, task, label, frame, note, heads):
    return dict(id=code, time=time, sourceTime=time, taskId=task, target=TARGET,
                label=label, note=note, image=MEDIA + frame, origin="authored_demo",
                assessments=heads)


def scenario():
    tasks = [dict(id=key, label=label) for key, label in [
        ("preparation", "부품과 작업 준비"), ("circuit", "회로 연결"),
        ("propeller", "프로펠러 장착"), ("battery", "배터리 삽입"),
        ("switch", "스위치 확인"), ("final", "최종 외관 기록"),
    ]]
    criteria = [
        criterion("E-PREP", "preparation", "보드·연결 부품·모터·프로펠러·배터리·지시서 준비"),
        criterion("E-CONNECTION", "circuit", "작업지시서에 따른 회로 연결 완료"),
        criterion("E-PROPELLER", "propeller", "프로펠러가 모터 축에 장착됨"),
        criterion("E-BATTERY", "battery", "배터리 두 개의 방향이 홀더 표시와 일치", True),
        criterion("E-SWITCH", "switch", "S1 확인 후 S2 확인 순서 준수"),
        criterion("E-FINAL", "final", "조립 완료 외관 사진과 확인 기록 확보"),
    ]
    return dict(
        id="electronics_demo", version="teaching-demo-v1", mode="demo",
        title="전자 조립 · 바람빛 회로 키트",
        description="부품 준비부터 조립, 작업자 확인, 검수조서까지. 질문 하나에 답하고 결과가 바뀌는 과정을 체험합니다.",
        companyId="edu-daon", companyName="다온에듀테크",
        processId="ELEC-DEMO-001", productName="바람빛 회로 키트", orderId="DEMO-001",
        sourceNote="EgoOops S1790005 공개 영상을 활용한 강의용 예시입니다. 회사·제품·작업지시서·판정 이벤트는 수업을 위해 작성했습니다. 원본 영상의 실제 모델 분석이나 품질 판정 결과가 아닙니다.",
        fixtureNotice="강의용 예시 · 공개 영상 + 미리 작성한 관찰 · GPU/API 없이 실행",
        demoNotice="예시 관찰을 재생하며, 확인 답변과 검사 정책은 실습 중 직접 바꿀 수 있습니다.",
        timelineKind="source_video_timestamps_with_authored_teaching_events",
        tasks=tasks, criteria=criteria,
        media=dict(path=MEDIA + "S1790005.mp4", codec="h264", browserPlayable=True),
        sources=[dict(label="EgoOops 공개 영상 · Yuto Haneji et al.",
                      url="https://y-haneji.github.io/EgoOops-project-page/", license="CC BY-SA 4.0")],
        variants=[dict(id="electronics", label="강사용: 저장된 실제 응답 비교",
                       config="scenarios/electronics/scenario.json", instructorOnly=True),
                  dict(id="electronics_error", label="강사용: 오류 사례 비교",
                       config="scenarios/electronics_error/scenario.json", instructorOnly=True)],
        exercises=[
            "정보 구축을 눌러 회사·공정·6개 검사 기준이 등록되는지 확인하세요.",
            "배터리 질문에 방향을 확인했다고 답하고, 보류가 충족으로 바뀌는지 확인하세요.",
            "배터리 기준을 '사진 증거만 인정'으로 바꾸어 같은 답변이 보류로 돌아가는지 비교하세요.",
            "검수조서와 보고서를 저장하고 예시 관찰과 작업자 확인이 따로 기록되는지 확인하세요.",
        ],
        checkpoints=[
            checkpoint("e1", 0.500, "preparation", "부품 준비 완료", "frame_00_0000.500s.jpg",
                       "보드, 연결 부품, 프로펠러, 배터리와 지시서가 놓인 시작 장면입니다.",
                       [head("E-PREP", "met", "작업에 필요한 부품과 지시서 준비를 완료했습니다.")]),
            checkpoint("e2", 76.731, "circuit", "회로 연결 완료", "frame_04_0076.731s.jpg",
                       "회로 연결을 마치고 프로펠러 장착 단계로 넘어갑니다.",
                       [head("E-CONNECTION", "met", "작업지시서에 따라 회로 연결을 완료했습니다.")]),
            checkpoint("e3", 89.659, "propeller", "프로펠러 장착 중", "frame_05_0089.659s.jpg",
                       "손으로 프로펠러를 잡고 장착하는 단계입니다. 완료 판정은 다음 관찰에서 기록합니다.", []),
            checkpoint("e4", 99.726, "battery", "배터리 방향 확인 요청", "frame_06_0099.726s.jpg",
                       "프로펠러 장착 후 배터리를 넣는 장면입니다. 손에 가린 방향은 작업자에게 확인합니다.",
                       [head("E-PROPELLER", "met", "모터 축에 프로펠러를 장착한 상태를 기록했습니다."),
                        head("E-BATTERY", "unknown", "손과 홀더 각도 때문에 배터리 두 개의 방향이 명확하지 않습니다.",
                             question="배터리 두 개의 방향이 홀더의 + / − 표시와 맞나요? 삽입을 마친 뒤 방향을 확인해 주세요.")]),
            checkpoint("e5", 113.870, "switch", "스위치 확인 완료", "frame_08_0113.870s.jpg",
                       "S1과 S2의 확인 순서를 기록하고 최종 외관을 준비합니다.",
                       [head("E-SWITCH", "met", "S1 확인 후 S2 확인 순서가 기록되었습니다.")]),
            checkpoint("e6", 120.021, "final", "최종 외관 기록", "frame_09_0120.021s.jpg",
                       "손을 치운 최종 외관을 기록합니다. 배터리 답변이 없으면 최종 보고서에 보류가 남습니다.",
                       [head("E-FINAL", "met", "조립 완료 외관 사진을 기록에 첨부했습니다.")]),
        ],
        documents=[dict(id="sop", title="작업지시서 · 조립 절차 PDF", path="scenarios/electronics_demo/SOP.pdf", type="pdf"),
                   dict(id="criteria", title="6개 검사 기준 CSV", path="scenarios/electronics_demo/criteria.csv", type="csv")],
    )


def pdf(s):
    font_path = ROOT / "assets/fonts/NotoSansKR.ttf"
    # The bundled variable font defaults to weight 100; freeze readable regular
    # weight before embedding rather than printing faint hairline text.
    source_font = TTFont(font_path)
    regular_font = instantiateVariableFont(source_font, {"wght": 400}, inplace=True)
    font_stream = io.BytesIO()
    regular_font.save(font_stream)
    font_bytes = font_stream.getvalue()
    font = fitz.Font(fontbuffer=font_bytes)
    doc = fitz.open()
    page = None
    y = 0

    def new_page():
        nonlocal page, y
        page = doc.new_page(width=595, height=842)
        page.insert_font(fontname="NotoKR", fontbuffer=font_bytes)
        page.draw_rect(fitz.Rect(0, 0, 595, 12), color=None, fill=(.08, .32, .35))
        y = 52

    def line(text="", size=10.5, color=(.12, .18, .23)):
        nonlocal y
        # Wrap with the actual Korean font width; PDFs remain readable and extractable.
        chunks, current = [], ""
        for char in text:
            if font.text_length(current + char, fontsize=size) > 507:
                chunks.append(current)
                current = ""
            current += char
        chunks.append(current)
        for chunk in chunks:
            if y > 780:
                new_page()
            # NotoKR maps a few ASCII glyph aliases to NBSP/nonbreaking hyphen
            # in PDF extraction. Machine IDs use the built-in Latin font so the
            # actual document parser receives the literal public identifiers.
            face = "helv" if chunk.isascii() else "NotoKR"
            page.insert_text((44, y), chunk, fontsize=size, fontname=face, color=color)
            y += size * 1.7

    def section(title):
        line()
        line(title, 14, (.08, .32, .35))

    new_page()
    line("다온에듀테크 | 교육용 작업지시서", 19)
    line("바람빛 회로 키트 조립", 16)
    line("문서번호: SOP-ELEC-DEMO-001 · 개정: 1 · 작업번호: DEMO-001")
    line("작업 수량: 1세트 · 검사 대상: 동일 보드 1개 · 담당자: 실습 참가자")
    line("강의용 가상 회사 문서 · 공개 영상에 맞춰 구성한 예시")
    line("company_id: " + s["companyId"], 9)
    line("process_id: " + s["processId"], 9)
    line("schema_version: workshop-company-v1", 9)
    section("1. 준비할 자료와 부품")
    line("베이스 보드, 연결 부품, 스위치 S1·S2, 모터, 램프 L1, 프로펠러, 배터리 홀더, 배터리 2개, 작업지시서.")
    line("이 키트의 조립은 부품을 손으로 결합합니다. 영상에 없는 공구나 측정값은 추가하지 않습니다.")
    section("2. 작업 순서")
    details = [
        "필요 부품과 지시서를 펼치고 작업할 보드 1개를 지정합니다.",
        "배터리 홀더–S1–모터를 연결하고, S2와 L1의 병렬 연결을 포함해 지시서 순서로 회로를 구성합니다.",
        "프로펠러를 모터 축에 장착합니다. 장착 중 상태와 장착 완료 기록은 구분합니다.",
        "배터리 두 개를 넣고 홀더의 + / − 표시와 방향이 맞는지 확인합니다.",
        "S1을 확인한 후 S2를 확인합니다. 이 수업의 순서 완료 사건은 미리 작성한 예시입니다.",
        "전체 보드의 최종 외관 사진을 남기고 모든 검사 항목과 작업자 답변을 함께 검토합니다.",
    ]
    for i, (task, detail) in enumerate(zip(s["tasks"], details), 1):
        line("task_id: " + task["id"], 9)
        line(f"{i}. {task['label']}", 11)
        line(detail, 10)
    new_page()
    line("검사 기준과 확인 처리", 19)
    line("작업번호 DEMO-001 · 바람빛 회로 키트 · 강의용 예시")
    section("3. 여섯 가지 검사 기준")
    for c in s["criteria"]:
        line(c["id"] + " | " + c["label"], 11)
        line("확인 방법: " + ("방향이 보이지 않으면 작업자에게 질문합니다. 긍정 확인을 별도 근거로 기록합니다." if c["allowWorker"] else "해당 단계의 예시 관찰과 사진을 기록합니다."), 10)
    section("4. 배터리 확인 질문")
    line("질문: 배터리 두 개의 방향이 홀더의 + / − 표시와 맞나요?")
    line("답변 예: 방향을 확인했습니다. → 작업자 확인 근거로 충족")
    line("답변 예: 반대로 들어가 있습니다. → 불일치 기록")
    line("답변 없음 / 확인할 수 없음 → 보류 유지")
    line("기본 정책은 작업자 확인을 인정합니다. 실습 중 사진 증거만 인정하도록 바꾸면 같은 답변이 있어도 보류가 됩니다.")
    section("5. 산출물과 완료 조건")
    line("검수조서: 여섯 기준의 판정, 근거 유형, 질문·답변, 사진, 변경한 확인 정책.")
    line("작업 보고서: 작업 순서, 주요 장면, 미확인 항목, 최종 판정 및 이력.")
    line("기본 예시는 배터리 확인 전 충족 5 / 보류 1, 긍정 확인 후 충족 6입니다. 작업 진행이 끝나도 미확인 항목을 자동으로 통과시키지 않습니다.")
    section("출처와 예시 범위")
    line("영상·사진: EgoOops S1790005, Yuto Haneji et al., CC BY-SA 4.0", 9)
    line("https://y-haneji.github.io/EgoOops-project-page/", 9)
    line("문서와 관찰 사건은 교육용 편집입니다. 실제 모델 출력이나 원본 작업의 품질 인증이 아닙니다. 원본 영상 시각을 유지하며, 순서·연결 완료 등 예시의 설정과 사진에서 보이는 내용을 구분합니다.", 9)
    for number, p in enumerate(doc, 1):
        p.insert_text((44, 816), f"DAON | Teaching demo | {number} / {len(doc)}", fontname="NotoKR", fontsize=8, color=(.4, .45, .5))
    doc.set_metadata(dict(title="바람빛 회로 키트 작업지시서·검사 기준", author="Manufacturing Agent Workshop", subject="Authored teaching scenario; not model output or industrial approval"))
    doc.subset_fonts()
    doc.save(DEST / "SOP.pdf", garbage=4, deflate=True)
    doc.close()
    with fitz.open(DEST / "SOP.pdf") as saved:
        extracted = "\n".join(p.get_text() for p in saved)
    (DEST / "SOP.extracted.txt").write_text(extracted, encoding="utf-8")
    assert "company_id: " + s["companyId"] in extracted
    assert "process_id: " + s["processId"] in extracted
    assert all("task_id: " + t["id"] in extracted for t in s["tasks"])


def main():
    # Historical JSON/PDF/CSV and recordings are immutable, including their bytes.
    protected = [p for folder in [ROOT / "scenarios/electronics", ROOT / "recordings/electronics_v1"]
                 for p in folder.rglob("*") if p.is_file()]
    before = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    DEST.mkdir(parents=True, exist_ok=True)
    s = scenario()
    pdf(s)
    with (DEST / "criteria.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "taskId", "label", "target", "kind", "unit", "lower", "upper", "allowWorker"])
        writer.writeheader()
        for item in s["criteria"]:
            writer.writerow({**item, "allowWorker": str(item["allowWorker"]).lower()})
    write_json(DEST / "scenario.json", s)
    index_path = ROOT / "scenarios/index.json"
    cards = json.loads(index_path.read_text(encoding="utf-8"))
    demo_card = dict(id=s["id"], title=s["title"], subtitle="준비 → 조립 → 확인 질문 → 검수조서",
                     description=s["description"], cover=MEDIA + "frame_09_0120.021s.jpg",
                     config="scenarios/electronics_demo/scenario.json")
    cards = [card for card in cards if card["id"] != "electronics_demo"]
    for card in cards:
        if card["id"] == "electronics":
            card["instructorOnly"] = True
    if not any(card["id"] == "electronics" for card in cards):
        cards.append(dict(id="electronics", title="강사용: 실제 응답 비교",
                          subtitle="기존 실제 모델 응답과 작성 이벤트", description="보존된 실제 응답을 비교하는 별도 실습입니다.",
                          cover=MEDIA + "frame_02_0020.361s.jpg", config="scenarios/electronics/scenario.json", instructorOnly=True))
    write_json(index_path, [demo_card] + cards)
    times = [c["sourceTime"] for c in s["checkpoints"]]
    assert times == sorted(times)
    assert len(set(times)) == len(times)
    assert all((ROOT / c["image"]).is_file() for c in s["checkpoints"])
    assert all(c["origin"] == "authored_demo" for c in s["checkpoints"])
    assert len([a for c in s["checkpoints"] for a in c["assessments"] if a["verdict"] == "unknown"]) == 1
    assert before == {str(p.relative_to(ROOT)): digest(p) for p in protected}
    print(json.dumps(dict(scenario=s["id"], tasks=len(s["tasks"]), criteria=len(s["criteria"]),
                         checkpoints=len(s["checkpoints"]), model_calls=0, protected_files_unchanged=len(before),
                         pdf_text_extracted=True, source_times_monotonic=True), ensure_ascii=False))


if __name__ == "__main__":
    main()
