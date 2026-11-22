# Measurement classroom demo: named-path conformance

2026-11-22 KST · `measurement_demo_v1` · CPU/browser authored example. User requested product selection → drawing/inspection criteria → measurement recording → uncertain-value question → inspection document, in the same easy-to-present classroom style as electronics. No model/OCR/GPU calls or external publication are required or authorized by this implementation.

## Inputs and condition

Two fictional flanged-bushing products use separate IDs, specimen IDs and drawing bindings. Three authored measurement scenes represent A outer diameter, B overall length and C flange thickness. Values are26.30mm,40.02mm and an unresolved `5.?8 mm`. The explicit learner reply5.78mm illustrates numeric confirmation. Standard and precision products differ in tolerance; the precision length40.02 is outside39.99–40.01. Diagrams and instrument views are authored SVG illustrations of the fictional workpiece, not unrelated real photographs asserted to depict one part. Existing public-photo measurement examples remain separate instructor material.

Actual serialized model request: **not applicable**. The actual transport to test is PDF.js extraction → typed CSV/identity compiler → shared state/controller → browser rendering, SQLite and reports. `mode=demo`, `demoKind=measurement`, `origin=authored_demo` are mandatory. No recognition accuracy or physical calibration claim follows from a successful classroom run.

## Capability inheritance

| Lessons | Status and specific transport evidence required |
|---|---|
| L01–L04 | Intentional authored scenario: distinct product, drawing, revision, specimen and A/B/C feature IDs in PDF/CSV/scenario and compiled bundle. Generated drawing is instructional, not a production release |
| L05–L06 | Retained ordered record progress vs inspection completion; timestamps are lesson positions, not real video observations |
| L07–L09 | Retained durable commands, previous answers and target checks; product change must reset measurement state or create a separate session; unknown is not auto-pass |
| L10 | Retained exact decimal +unit +range comparison, feature and instrument binding, literal raw reading distinct from accepted worker value; no decimal shifting to satisfy limits |
| L11–L12 | Retained typed raw/final separation; authored verdict cannot override numeric comparison. Unknown raw remains unknown until a valid answer; model token budgets not applicable |
| L13–L14 | Functional E2E only: explicit recorded actions, zero inference; not a benchmark or production inspection |
| L15 | Korean controls/SOP/questions/reports and stable machine IDs |
| L16–L18 | Separate new demo; earlier electronics, oldmeasurement and actualrecording files preserved; GPU pause unchanged |
| L19–L20 | Complete criterion review, report contains product/drawing and perfeature value/unit/limits/outcome plus raw and answer history |
| L21–L23 | Not applicable: no training, calibration or model selection |
| L24–L25 | Delivered question, target-bound numeric reply, uncertainty retained, recheck preserves prior value/history and requires fresh answer, exact import/replay |

## Finite checks

Core regressions plus actual browser workflows for both products. Normal confirmation produces3met; standardnoanswer produces2met+1unknown; a578mm reply stays578mm/outofrange; wrongunit/target reject; narrowing a range changes only verdict and criterionversion. Test rawuncertain preservation, correction, restore/import, standalone image/drawing reports, SQLite identity/values, mobile layout and localstatic requests only. Verify exact selected drawing and no crossproduct carryover. Prior60coretests and electronics browser remain regression obligations. Tests and implementation must be recorded separately from planned checks.

Old v0.3 delivery ZIPs and preservation hashes are retained under `validation/measurement_demo_v1/baseline_v03`. Completed results and old failed attempts are not rewritten. Final executed evidence will be linked in `E2E_RECEIPT.json` after verification. The public site remains unpublished.

## Executed closeout — 2026-11-22 KST

The implemented `measurement_demo_v1` path passes 76 core tests (60 retained + 16 new) and 18 browser check groups for both product variants. Final browser receipt: 183 local static GETs, zero external/non-GET/model requests, zero page/HTTP errors. Actual PDF extraction, SQLite identity/features/current verdict, typed answers, unknown/correction/pending semantics, original versus modified limits, exact journal restore/import and standalone embedded reports all pass. Desktop/mobile geometry and final Korean drawing/question/inspection screenshots were visually reviewed. CSV was corrected during implementation to expose original/current limits and pending confirmation separately; final browser assertions cover both. Earlier preview/test outputs remain separately retained.

The existing authored electronics browser flow and all five legacy fixture packs/25 checkpoints pass fresh regressions. Actual-model recordings were not rerun; their bytes and source hashes remain unchanged. This is functional verification of authored classroom content and deterministic controller behavior, not independent OCR accuracy or manufacturing approval. TTS listening quality remains untested, and the existing electronics H.264 limitation is retained. See [executed receipt](E2E_RECEIPT.json); detailed local artifacts live under `validation/measurement_demo_v1`. No GPU/inference/publication action was performed.


## Final classroom rehearsal and slides — 2026-11-22 KST

The unchanged app/core paths passed a fresh 76-test core run and both current classroom browser workflows: 18 measurement and 14 electronics check groups, 319 local GETs, zero external/model requests and zero page/HTTP errors. Eighty-six app/scenario/recording/test files remain byte-identical. Learner guides now use the actual button names and require question acknowledgement before answering.

The 24-slide offline HTML/PDF/presentation-image PPTX explains the existing teaching modes using actual UI captures. Checks passed for navigation, notes, contents, zoom, small-screen fit, all slide bounds, embedded images, 24 PDF pages and 24 PPTX slides with notes. No GPU, inference or publication occurred. Detailed receipts are retained under `validation/seminar_final_v1`; see [current teaching readiness](../FINAL_CHECK.ko.md) and [slide guide](../../slides/README.ko.md). Native PowerPoint playback, classroom H.264 playback and TTS listening are not newly verified.
