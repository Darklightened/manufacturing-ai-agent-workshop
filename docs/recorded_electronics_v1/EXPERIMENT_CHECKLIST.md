# 전자 조립 실제 응답 수집 — 경로별 인계 검수

2026-11-22 KST · `electronics-sparse-causal-allcriteria-v1`

사용자 요청은 전자 조립 실습을 실제 모델 응답에 연결하고, 저장 응답을 GPU 없이 재생하면서 기준·작업자 답변이 판정과 보고서를 바꾸도록 검수하는 것이다. 이번 수집은 이 요청에 한정한 6회 모델 실행이다. 기존 HTech 연구 캠페인·기한·중단·정답·기준을 수정하지 않는다.

## 조건과 비교 범위

- 이전 경로: `../CONFORMANCE.ko.md`의 작성 이벤트 제어기. 모델 호출 0회였으며 실제 응답으로 소급 표시하지 않는다.
- 모델: Qwen3.8-27B-FP8, 모델 리비전 `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`. 실제 serving alias는 수집 `plan.json`과 요청에 보존한다.
- 입력: EgoOops `S1790005` 공개 원본에서 기존에 추출한 1280×720 키프레임. 시각은 20.361/76.731/89.659/99.726/113.870/120.021초, 각 요청에 현재까지의 3/5/6/7/9/10개 이미지가 실제 JPEG data URL로 포함된다.
- 교육용 SOP PDF를 실제 파싱하고 CSV와 시나리오 기준의 일치를 확인한다. 원문 전체와 실제 요청의 연속 발췌를 따로 보존한다. 모터·배터리·S1·S2 등 원본 8단계는 전달한다. 별도 원본 BOM·참조 도면은 이 사례에 없으며 존재한다고 주장하지 않는다.
- 각 요청은 전체 5개 기준을 관찰한다. 총 6개 요청 × 5개 관찰 = 30개 후보. 작업 순서는 문맥이며 현재 작업의 정답이 아니다. 기존 fixture 정답·해설·현재 작업 라벨은 요청에서 제외한다.
- 응답은 `present/absent/unclear`, `due/not_due/unclear`, 대상 확인, 근거 ID, 현재 관찰 작업·단계와 한국어 설명이다. 모델은 최종 합격을 결정하지 않는다.
- thinking off, temperature 0, seed 22, 응답 한도 2560 토큰. 이는 기존 384 토큰 관찰기와 동일한 성능 비교가 아니라, 5개 관찰 헤드를 한번에 저장하는 별도 교육용 조건이다.
- 수집 중 작업자 답변은 입력하지 않는다. 이후 수업의 답변과 정책 변경은 저장된 지각 후보를 바꾸지 않고 결정적 제어기에만 적용된다. 변경된 질문에 모델이 다시 답한 것처럼 표시하지 않는다.

## 교훈의 실제 전달

| 교훈 | 상태와 범위 | 현재 경로 증거 |
|---|---|---|
| L01–L03 출처·시간 | 유지. 원본/교육용 기준/실제 모델 출력 분리. 독립 품질 정답 없음 | `plan.json:sourcePins`, 각 `inputImages.time`, source PDF 전체/발췌 |
| L04 작업 규정 | 유지. 실제 PDF 파싱, CSV 일치, 8단계·5기준·대상 전달 | `scripts/capture_electronics.py:load_inputs/build_request`, `preflight.request.json` |
| L05 작업과 완료 | 유지. expectedTaskOrder와 observedTaskId·phase 분리 | 실제 JSON 요청/응답, fixture current-task 해설 제외 |
| L06 영상 입력 | 의도적 축소. 연속 영상 아닌 희소 키프레임 | 각 요청 JPEG data URL, 이미지 수·해시·시각. 프레임 사이 동작 추정 금지 |
| L07 인과 기억 | 유지. 이전의 모든 제공 키프레임과 수용된 과거 모델 관찰 전달 | `priorModelObservations`, historical role의 실제 이미지 |
| L08 대상 | 유지. 같은 공개 recording의 circuit-board만 지정 | target/targetConfirmed, 이미지 role, 별개 대상·문서 추측 금지 |
| L09 적용 시점 | 유지. due/not_due/unclear 별도 필드 | 전체 기준 반복 관찰, 준비·진행중 미완성을 결함으로 강제하지 않음 |
| L10 계측 | 비해당. 실측 장비·수치·OCR 없음 | 규정 모두 visual. 가상의 계측값을 만들지 않음 |
| L11 관찰·결론 | 유지. 모델 원시 관찰과 최종 제어기 판정 분리 | raw response와 parsed output 보존; 최종 verdict 키 schema 금지 |
| L12 예산·실패 | 유지. 2560 토큰·stop만 수용·정확한 raw bytes 보존 | 요청/응답 해시, receipt finishReason, failure. 실패 응답 재시도 없음 |
| L13 실행 시간 | 유지. 요청별 HTTP 서비스 시간과 전체 capture wall 분리 | receipt serviceSeconds, capture.summary.json. 서버 기동은 부모 실행 기록 |
| L14 평가 | 의도적 축소. 엔지니어링 재생과 장면 근거 검수이며 독립 정확도 주장 없음 | independentQualityLabels=0, qualityValidated=false 기본 |
| L15 한국어 | 유지. 설명/질문 한국어 요구 및 문자 검사 | 실제 요청 system과 응답 validator. 유창성 검수는 별도 |
| L16–L17 버전 | 유지. 새 recordings/electronics_v1, 기존 출력 불변 | plan/source hashes, 파일 exclusive-create, 요청 재실행 차단 |
| L18 GPU | 부모가 현재 소유권·fresh grant·기존 guard로 한시 실행 관리 | 이 스크립트는 서버 기동·GPU 변경·자동 모니터를 수행하지 않음 |
| L19–L20 검수 | 유지. 모든 30헤드·가림·미확인을 보고서에 보존 | pack entries/output/failure. 최종 UI 검수는 부모 통합 기록 |
| L21–L23 학습 | 비해당. 학습·confidence 보정·모델 승격 없음 | 이 사례는 저장 응답 실습 연결이며 모델 학습 아님 |
| L24 질문·보고서 | 제어기 통합 검수 대상 | 모델 질문은 후보. 실제 전달/대상/답변/정책은 코어·브라우저에서 별도 검증 |
| L25 결정적 제어기 | 제어기 통합 검수 대상 | 모델이 판정·정책·보고서 승인하지 않음 |

## 유한 실행과 보존

`prepare`는 CPU만 사용하며 실제 첫 요청과 각 프레임 해시를 검증한다. `run`은 이미 소유권이 확인된 localhost endpoint에만 요청한다. 각 요청을 보내기 전에 exact JSON bytes를 저장하고, HTTP 원문 bytes와 상태·시간·usage·finish_reason을 별도 파일에 보존한다. 실패/알 수 없음은 삭제하거나 성공으로 대체하지 않는다. 자동 재시도는 없고 두 요청 연속 실패 시 남은 요청은 untouched로 중단한다. 새 directory 없이는 수집을 다시 실행할 수 없다.

완료 여부는 `capture.summary.json`과 `pack.json`으로 확인한다. 계획 및 CPU 사전검증만으로 GPU 실행·품질 검수 완료를 주장하지 않는다. 브라우저는 pack/요청/응답/이미지 해시와 코어 계약이 일치할 때만 실제 응답 재생을 활성화해야 한다.

## 실행 전 확인 기록

- `preflight.json`: 실제 6개 wire builder의 현재/인과 이미지 수·시각·해시·fixture answer 제외 검사.
- `preflight.request.json`: 첫 번째 실제 모델 요청의 직렬화 preview. 실행 시 같은 방식으로 저장하며 이전 모델 관찰은 실행 결과만 추가한다.
- `scripts/capture_electronics_test.py`: raw JPEG hash 일치, 미래 증거 제외, SOP 순서/기준 전달, 과거 관찰 전달, 부정/보류 헤드, 중복/누락 ID, 미전달 근거, 근거 없는 주장, 다른 대상, 최종 verdict 주입, 한국어 출력 계약 검사.

이 문서는 실행 전 조건이며 결과 횟수는 터미널 receipt를 따른다.

## 실제 실행 후 확인 — 2026-11-22 KST

- 실제 요청 builder CPU 테스트 10개 통과. 6개 실제 GPU 요청과 30개 관찰 헤드가 정상 수용됐다. 전송/파싱 실패 0개, 미시도 0개이며 원시 파일은 덮어쓰지 않았다.
- [실제 wire 대조](REQUEST_REVIEW.json)에서 전체 요청/응답 SHA256, 실제 image data URL 바이트, 현재/과거 시각, 실제 이전 응답 연결, 모델 alias·종료 사유와 모든 기준 전달을 재확인했다.
- HTTP 서비스 합계 49.79초, 수집 클라이언트 wall 50.01초. GPU 서버 기동·종료와 브라우저 경로의 시간은 별도 기록이다.
- [장면 대조 검수](SOURCE_REVIEW.ko.md): 10개 원본 프레임과 30개 관찰을 검토했다. e4/e5의 작업 분류 지연, 현재 배터리 장면에 대한 이전 단계 설명, E-FINAL의 외관 속성/시점 혼합을 확인했다. 이 기록은 assistant 검토이며 독립 제조 품질 정답이 아니다.
- 관찰 후보는 present 2개/absent 12개/unclear 16개, 적용 시점은 due 13개/not_due 17개다. absent/not_due를 불량으로 집계하지 않는다. 기술적 6/6 성공을 의미적 정확도로 바꾸지 않는다.
- 학습·기존 baseline 승격·새 장기 캠페인은 없었다. 다음 조건 변경은 별도 버전으로 하고 현재 실제 응답팩을 보존해야 한다.
