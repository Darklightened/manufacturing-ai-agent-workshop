"""Render only the current classroom guide; never rebuild slides or old receipts."""

from pathlib import Path
import argparse
import base64
import html
import re


ROOT = Path(__file__).resolve().parents[1]
SECTION_IDS = {
    "1": "instructor",
    "2": "students",
    "3": "rehearsal",
    "4": "windows",
    "5": "concurrency",
    "6": "saving",
    "7": "notice",
    "8": "scope",
}

CSS = '''
@font-face{font-family:GuideKR;src:url(__GUIDE_FONT__) format("woff2");font-weight:100 900}
*{box-sizing:border-box}body{margin:0;font-family:GuideKR,system-ui,-apple-system,"Noto Sans KR","Malgun Gothic",sans-serif;background:#f4f6fb;color:#1b2c45;line-height:1.8}
header{background:#162841;color:white;padding:24px max(24px,calc((100vw - 1080px)/2));display:flex;justify-content:space-between;gap:20px}header a{color:#dce7ff;text-decoration:none}
main{max-width:1080px;margin:32px auto;padding:38px;background:white;border:1px solid #dce4ef;border-radius:16px}h1{font-size:32px;letter-spacing:-1px;line-height:1.35;margin-top:0}h2{font-size:23px;line-height:1.5;margin:42px 0 14px;padding-bottom:10px;border-bottom:2px solid #edf1f9}
p,li{font-size:16px;overflow-wrap:anywhere}li{margin-bottom:7px}a{color:#355dcc;text-underline-offset:3px;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:15px}th,td{padding:13px 15px;border-bottom:1px solid #dfe6f0;text-align:left;vertical-align:top}th{background:#edf2fb}td:first-child{min-width:170px;font-weight:650}
pre{font:15px/1.85 GuideKR,system-ui,sans-serif;white-space:pre-wrap;overflow-wrap:anywhere;background:#eef3fc;border:1px solid #dbe5f6;border-radius:10px;padding:22px}code{background:#edf2f9;padding:2px 4px;border-radius:4px;word-break:break-word}.table-wrap{overflow-x:auto}
.guide-actions{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:30px}.guide-actions a,.guide-actions button{font:inherit;border:1px solid #cad6ed;border-radius:8px;padding:9px 15px;background:#edf2ff;color:#2d4f9a;text-decoration:none;cursor:pointer}footer{max-width:1080px;margin:0 auto 32px;padding:0 22px;color:#64758d;font-size:14px}
@media(max-width:680px){main{margin:12px;padding:22px}h1{font-size:27px}header{padding:18px}table,tbody,tr,td{display:block}thead{display:none}tr{border:1px solid #dfe6f0;border-radius:10px;overflow:hidden;margin-bottom:12px}td{border:0;padding:10px 13px}td:first-child{min-width:0;background:#edf2fb;font-size:16px}td:not(:first-child)::before{content:attr(data-label) " · ";font-weight:700;color:#5d7290}p,li{font-size:15px}}
@media print{body{background:white}header,.guide-actions{display:none}main{border:0;margin:0;padding:0;max-width:none}h2{break-after:avoid}tr,pre{break-inside:avoid}a{color:inherit}}
'''


def inline(text):
    """Render the links, bold and code used by this maintained Markdown source."""
    value = html.escape(text)
    value = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', value)
    value = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', value)
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', value)


def render_markdown(source):
    """Support the guide's explicit block forms, retaining mobile table labels."""
    lines = source.splitlines()
    body = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("```"):
            code = []
            index += 1
            while index < len(lines) and lines[index] != "```":
                code.append(lines[index])
                index += 1
            if index == len(lines):
                raise ValueError("Unclosed code block in classroom guide")
            body.append("<pre>" + html.escape("\n".join(code)) + "</pre>")
            index += 1
            continue
        if line.startswith("#"):
            match = re.fullmatch(r"(#{1,2}) (.+)", line)
            if not match:
                raise ValueError(f"Unsupported guide heading: {line}")
            level = len(match[1])
            title = match[2]
            number = title.split(".", 1)[0]
            section = f' id="{SECTION_IDS[number]}"' if level == 2 else ""
            body.append(f"<h{level}{section}>{inline(title)}</h{level}>")
            index += 1
            continue
        if line.startswith("|"):
            headers = [part.strip() for part in line.strip("|").split("|")]
            if index + 1 >= len(lines) or not re.fullmatch(r"[| :\-]+", lines[index + 1]):
                raise ValueError("Guide table is missing its header separator")
            index += 2
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                cells = [part.strip() for part in lines[index].strip("|").split("|")]
                if len(cells) != len(headers):
                    raise ValueError("Guide table cell count differs from header")
                rows.append("<tr>" + "".join(
                    f'<td data-label="{html.escape(headers[i])}">{inline(cell)}</td>'
                    for i, cell in enumerate(cells)
                ) + "</tr>")
                index += 1
            body.append('<div class="table-wrap"><table><thead><tr>' + "".join(
                "<th>" + inline(cell) + "</th>" for cell in headers
            ) + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
            continue
        if line.startswith("- "):
            items = []
            while index < len(lines) and lines[index].startswith("- "):
                items.append("<li>" + inline(lines[index][2:]) + "</li>")
                index += 1
            body.append("<ul>" + "".join(items) + "</ul>")
            continue
        paragraph = []
        while index < len(lines) and lines[index].strip():
            paragraph.append(lines[index])
            index += 1
        body.append("<p>" + inline(" ".join(paragraph)) + "</p>")
    return "\n".join(body)


def build_page():
    source = (ROOT / "docs/CLASSROOM_GUIDE.ko.md").read_text(encoding="utf-8")
    notice = (ROOT / "docs/STUDENT_NOTICE.ko.txt").read_text(encoding="utf-8").rstrip()
    if source.count("```text\n" + notice + "\n```") != 1:
        raise ValueError("Guide's copyable notice differs from STUDENT_NOTICE.ko.txt")
    font = base64.b64encode((ROOT / "assets/fonts/NotoSansKR.woff2").read_bytes()).decode()
    css = CSS.replace("__GUIDE_FONT__", "data:font/woff2;base64," + font)
    license_text = html.escape((ROOT / "assets/fonts/OFL.txt").read_text(encoding="utf-8"))
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>강의 준비와 수강생 안내 · DYNIN</title><style>' + css + '</style></head><body>'
        '<header><strong>DYNIN · CLASSROOM GUIDE</strong><a href="../downloads.html">자료실로</a></header>'
        '<main><nav class="guide-actions"><a href="#instructor">강사 준비</a>'
        '<a href="#students">수강생 준비</a><a href="#windows">선택 Windows ZIP</a>'
        '<a href="#concurrency">30명 수업 운영</a><a href="#notice">복사용 공지</a>'
        '<button onclick="window.print()">인쇄 / PDF 저장</button></nav>\n'
        + render_markdown(source) + '\n</main>'
        '<footer>강의용 예시 · 웹 링크로 시작 · 사전 백업 다운로드 불필요</footer>'
        '<script type="text/plain" id="font-license">' + license_text + '</script></body></html>\n'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check the current HTML without writing")
    args = parser.parse_args()
    target = ROOT / "docs/classroom-guide.html"
    page = build_page()
    if args.check:
        if target.read_text(encoding="utf-8") != page:
            raise SystemExit("classroom-guide.html is stale; run scripts/build_classroom_guide.py")
        print("Classroom guide HTML and notice match current sources")
    else:
        target.write_text(page, encoding="utf-8")
        print("Wrote docs/classroom-guide.html only")


if __name__ == "__main__":
    main()
