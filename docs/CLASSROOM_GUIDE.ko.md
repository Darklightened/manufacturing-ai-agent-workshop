# 강의 준비와 수강생 안내

2026년 11월 23일 · 15–20명 수업 운영 · 전자 조립 / 계측 검사

**실습 1은 회사별 입력 자료 ZIP(약 0.69MB)을 받아 폴더 업로드를 연습합니다.** 다운로드가 어려우면 준비된 회사 자료로 시작할 수 있습니다. 슬라이드 PDF와 아래 참고 ZIP은 선택 자료입니다. 새 자료 구축 순서는 웹앱을 따르며 슬라이드는 이전 화면입니다. 전체 실습팩은 강사가 미리 확보할 비상 자료입니다.

[실습 페이지](https://darklightened.github.io/manufacturing-ai-agent-workshop/) · [자료 다운로드](https://darklightened.github.io/manufacturing-ai-agent-workshop/downloads.html) · [슬라이드 보기](../slides/실습_안내.html) · [수강생 안내문 TXT](STUDENT_NOTICE.ko.txt)

[회사별 입력 자료 ZIP](../assets/company-materials/company-practice-materials.zip) · [새 자료 구축 안내](company_build_v2/README.ko.md)

## 1. 강사가 미리 가지고 있을 자료

| 자료 | 준비 방법 | 용도 |
|---|---|---|
| 전체 실습팩 · 약 0.36 GB | [workshop-offline.zip](https://github.com/Darklightened/manufacturing-ai-agent-workshop/releases/latest/download/workshop-offline.zip) 저장·압축 해제 | 슬라이드·예제·영상·프로그램을 함께 보관하는 비상본 |
| 발표본 · HTML 약 19.4 MB | 실습팩의 slides/실습_안내.html 또는 [HTML 저장](../slides/실습_안내.html) | 인터넷 없이 발표·이미지 확대·강사 메모 |
| PDF 약 7 MB / PPTX 약 33.2 MB | [PDF](../slides/실습_안내.pdf)와 필요 시 [PPTX](../slides/실습_안내.pptx) 별도 복사 | 발표 대체본과 인쇄본. PPTX는 이미지 슬라이드+노트 형식 |
| 강사 진행 메모·기술 해설 | [진행 메모](../slides/INSTRUCTOR_NOTES.ko.md) / [기술 배경](../slides/TECHNICAL_GUIDE.ko.md) | 시간표·버튼 순서·설명용 출력의 의미 확인 |
| 입력 자료·완성 예제 · 약 41 MB | [workshop-handouts.zip](https://github.com/Darklightened/manufacturing-ai-agent-workshop/releases/latest/download/workshop-handouts.zip) 저장·압축 해제 | SOP·기준 CSV·도면·표준형/정밀형 검수조서 비교 |
| 리허설 진행 JSON | 본인 PC에서 실습 완료 후 진행 내보내기 | 중단 시 가져오기 테스트. HTML 보고서와 구분 |

전체 실습팩 안에 대부분 포함되어 있으므로 같은 대용량 파일을 여러 번 받을 필요는 없습니다. 강사 PC와 USB 등 별도 위치에 한 번씩 보관하고, 다운로드 폴더보다 강의 전용 폴더로 정리하는 편이 좋습니다.

## 2. 수강생에게 받을 파일과 준비물

| 항목 | 안내 |
|---|---|
| 기기 | 노트북 또는 PC, 충전기, Chrome 또는 Edge, 인터넷 연결 |
| 업로드 실습 자료 | 회사별 입력 자료 ZIP · 약 0.69 MB · 압축 해제 |
| 선택 참고 자료 | 슬라이드 PDF 약 7 MB / 완성 예제 포함 workshop-handouts.zip 약 13 MB |
| 온라인 실습 | 실습 링크 접속 → 회사 폴더 업로드. 다운로드가 어려우면 준비된 회사 자료로 시작 |
| 별도 준비 불필요 | GitHub 로그인, Python·모델 설치, GPU·API 키, 스마트글래스·마이크·실물 계측기 |
| 개인 작업 폴더 | 예: 제조AI_실습/입력자료, 제조AI_실습/결과. 결과 파일은 실습별로 구분 |

폴더 업로드 활동을 위해 회사 입력 ZIP 약 0.69 MB만 미리 받도록 안내합니다. PDF와 큰 참고 ZIP은 선택 사항입니다. 수강생 전체에게 PPTX·전체 실습팩·소스 ZIP·영상 ZIP을 동시에 받게 할 필요는 없습니다. 음성은 강사만 재생하고 수강생은 질문 확인과 버튼·텍스트 답변으로 진행해도 됩니다.

## 3. 강의 전날 리허설

- 실제 강의 PC와 강의실 네트워크에서 실습 링크·자료실·PDF/ZIP 다운로드 확인.
- 전자 조립을 끝까지 실행하고 배터리 질문에 긍정 답변: 충족 6개, 보고서·검수조서 저장 확인.
- 계측 표준형에서 C=5.78 mm 답변: 충족 3개 확인. 정밀형은 같은 예시값으로 A/C 충족, B 불일치 확인.
- 진행 JSON을 내보낸 뒤 가져오기로 제품·값·판정·답변이 복원되는지 확인.
- 원본 영상 재생과 한국어 질문 듣기 확인. 영상 코덱이나 TTS가 맞지 않으면 준비된 장면 사진과 화면 질문으로 진행.
- 강사 브라우저에는 실습 탭 한 개와 슬라이드·자료실 탭을 열어두기. 리허설 결과는 따로 저장하고 수업 시작 위치 준비.
- 수강생 결과를 받을 제출처와 파일명 규칙 미리 정하기. 사이트에 강사용 자동 수집·진도 대시보드는 없음.

## 4. 인터넷 장애 시 강사용 대안

슬라이드 HTML·PDF·PPTX와 저장한 보고서는 직접 열 수 있습니다. **전체 실습 앱은 index.html을 더블클릭하지 말고 로컬 서버로 실행**합니다. PDF worker와 SQLite 파일을 정상적으로 불러오기 위한 구분입니다.

```text
1) workshop-offline.zip 압축 해제
2) 11_21_seminar 폴더에서 터미널 열기
3) macOS / Linux: python3 scripts/serve.py
   Windows:       py -3 scripts/serve.py
4) 브라우저: http://127.0.0.1:8921/
5) 실습이 끝날 때까지 터미널 유지
```

Python 3은 이 오프라인 실행을 사용할 강사 PC에만 사전 설치·시험합니다. 위 주소는 해당 PC 전용이며 수강생에게 그대로 보내도 강사 PC에 접속되지 않습니다. 강사 시연은 로컬 앱으로 계속하고, 수강생 전원 오프라인 실행은 미리 설치와 실행을 확인한 PC에서만 대안으로 사용합니다.

온라인 주소와 로컬 주소는 브라우저 저장 영역이 다릅니다. 서로 이동할 때는 진행 JSON 내보내기·가져오기로 옮깁니다. 브라우저 캐시는 완전한 오프라인 실습팩을 대신하지 않습니다.

## 5. 15–20명 동시 사용 판단

**현재 구성은 15–20명이 같은 링크를 열어 실습하기에 적합한 구조입니다.** GitHub Pages는 파일을 전달하고 PDF 처리·DB 구성·판정·보고서는 각자의 브라우저에서 실행합니다. 공용 모델 서버나 서버 DB의 처리 순서를 기다리지 않으며, 강의용 실습을 위해 연구용 GPU 서버를 켜둘 필요도 없습니다.

공식 한도는 게시 사이트 1 GB, 월 전송량 100 GB의 소프트 한도이며 요청 제한 시 429 응답이 발생할 수 있습니다. 공식 문서에는 수강생 수로 정한 동시 접속 보장 수치가 없습니다. 따라서 “20명 무조건 보장”이 아니라 현재 구조와 자료 규모에 근거한 운영 판단입니다. [GitHub Pages 공식 한도](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) · [정적 호스팅 설명](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)

영향이 큰 부분은 강의실 Wi-Fi와 각 PC의 브라우저 성능입니다. PDF·예제 ZIP을 사전에 받고 기본 실습은 장면 사진으로 진행합니다. 원본 영상 전체를 모두 동시에 재생하거나 대용량 실습팩을 일제히 받는 것은 피하고, 필요한 경우 몇 명씩 순서대로 다운로드합니다. 단순 새로고침을 반복하면 자료를 다시 가져올 수 있습니다.

로컬 검수에서는 한 서버에서 20개의 독립 브라우저 세션을 동시에 열어 전자 긍정 5명·전자 반대 5명·계측 표준형 5명·정밀형 5명 모두 통과했습니다. PDF 처리→질문·답변→검수조서 저장→새로고침 복원과 브라우저별 저장 일치를 확인했습니다. 페이지·HTTP 오류는 0건입니다. 이는 앱의 동시 실행·저장 분리 검수이며, 실제 20대 PC나 GitHub Pages·강의장 Wi-Fi 부하 검증은 아닙니다.

새 회사 입력 ZIP은 한 사람 약 0.69 MB, 20명 약 13.8 MB입니다. 선택 자료인 PDF와 큰 참고 ZIP까지 받으면 한 사람 약 48 MB가 추가됩니다(현재 참고 ZIP 약 41 MB + 슬라이드 PDF 약 7 MB). 기본 앱의 비영상 자료는 원본 파일 크기 합산 약 9.6 MB이며 캐시·이동·보고서 생성 횟수에 따라 실제 전송량은 달라집니다. ZIP 다운로드는 GitHub Releases에서 제공하므로 이 합계를 Pages 월 전송량으로 그대로 계산하지 않습니다.

## 6. 개인 저장과 결과 제출

- 서로 다른 PC·브라우저 프로필의 진행 기록은 분리. 한 사람의 답변이나 기준 변경이 다른 사람의 판정을 바꾸지 않음.
- 같은 브라우저 프로필·같은 실습 주소의 여러 앱 탭은 현재 저장 영역을 공유. 실습 앱 탭은 한 개만 사용하고 슬라이드·자료실은 별도 탭 사용 가능.
- 진행은 브라우저 IndexedDB에 저장. 사이트 데이터 삭제, 시크릿 창 종료, PC 변경 등에 대비해 진행 JSON을 직접 내보내기.
- 실습별 검수조서 HTML·작업 보고서 HTML·진행 JSON 저장. 예: 03_실습1_검수조서.html, 03_실습1_진행.json.
- 개인 결과는 서버에 자동 제출되지 않음. 강사가 정한 제출처에 직접 업로드하며 단독 HTML 보고서는 그대로 열람 가능.

## 7. 수강생 공지문

[안내문 TXT 다운로드](STUDENT_NOTICE.ko.txt). 아래 문구를 교육 안내 메일·게시판에 복사해서 사용할 수 있습니다.

```text
[제조 AI Agent 실습 사전 안내]

노트북(또는 PC)과 충전기를 준비해 주세요. Chrome 또는 Edge를 사용합니다.

실습 주소
https://darklightened.github.io/manufacturing-ai-agent-workshop/

자료 다운로드
https://darklightened.github.io/manufacturing-ai-agent-workshop/downloads.html

실습 1 준비
회사별 입력 자료 ZIP (약 0.69MB)을 다운로드하고 압축을 풀어 주세요.
https://darklightened.github.io/manufacturing-ai-agent-workshop/assets/company-materials/company-practice-materials.zip

실습 화면에서 '폴더 전체 업로드'를 누르고 '다온에듀테크' 폴더를 선택합니다.
다운로드·폴더 선택이 어려우면 화면의 '준비된 회사 자료로 시작'으로 같은 실습을 할 수 있습니다.
슬라이드 PDF(약 7MB)는 선택 자료이며, 회사 자료 구축 화면은 이전 버전입니다. 새 순서는 웹앱 안내를 따릅니다.

GitHub 로그인, Python 설치, API 키, 모델·GPU, 마이크는 필요하지 않습니다.
실습 앱은 한 탭만 열어 주세요. 수업 종료 전 검수조서·보고서와 진행 JSON을 저장하고 강사가 안내하는 곳에 제출합니다.
```

## 8. 이번 수업에서 실행하는 범위

관찰·최초 판독은 준비된 강의용 예시이며, 문서 추출·규칙 비교·답변·판정·보고서는 실제 브라우저 처리입니다. 슬라이드의 모델 출력 예시는 기술 구조 설명용입니다. 실제 계측 정확도나 생산 승인 실습으로 해석하지 않습니다.
