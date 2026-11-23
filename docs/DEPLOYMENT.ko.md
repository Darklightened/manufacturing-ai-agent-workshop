# 실행과 배포

배포 구성은 **공개 GitHub 저장소 + GitHub Pages 정적 앱 + 버전 고정 Release 자료**입니다.

- [온라인 실습](https://darklightened.github.io/manufacturing-ai-agent-workshop/)
- [강의 자료 다운로드](https://darklightened.github.io/manufacturing-ai-agent-workshop/downloads.html)
- [공개 저장소](https://github.com/Darklightened/manufacturing-ai-agent-workshop)
- [v0.5.3 자료 묶음](https://github.com/Darklightened/manufacturing-ai-agent-workshop/releases/tag/v0.5.4)

수강생은 온라인 실습 링크만 열면 됩니다. GitHub 로그인이나 설치가 필요 없으며, 진행 기록은 각자 브라우저에 저장됩니다. PDF·CSV·영상·슬라이드는 같은 사이트에서 제공하고, 큰 ZIP은 GitHub Release에서 받습니다. 아래 명령은 오프라인 사용 또는 운영자용입니다.

## 로컬 수업

```sh
python scripts/serve.py --port 8921
```

기본 주소는 `http://127.0.0.1:8921/`이며 루프백에만 열립니다. 강사가 교실 LAN에 제공할 때만 `--host 0.0.0.0`를 명시합니다. 이 서버는 교육용 정적 파일 서버로 인증 기능이 없으므로 사적인 문서·음성을 그 폴더에 넣지 않습니다. 영상 탐색을 위한 단일 Range 요청을 지원합니다.

기본 수업은 버튼·텍스트 답변으로 진행합니다. 질문 듣기는 브라우저 TTS를 사용하며, 실제 음성 인식은 포함하지 않습니다. 강의 PC의 한국어 음성을 사전에 확인하세요.

## 정적 배포 후보 만들기

```sh
node --test tests/*.test.mjs
python scripts/verify_recording.py
node tests/core-recorded-audit.mjs
python scripts/build.py
python scripts/serve.py --directory dist
```

기본 화면은 강의용 전자 조립 예시입니다. 빌드는 필요한 앱·시나리오·강사용 과거 응답팩·라이브러리와 허용한 원본 파일만 `dist`로 복사합니다. 내부 실행 경로·자격증명 패턴·심볼릭 링크를 거부합니다. 전체 연구 프로젝트는 복사하지 않습니다. `dist/build-manifest.json`은 파일별 SHA256·용량, 사용 가능한 모드와 실제 응답팩의 해시를 기록합니다. 모델에 전달된 과거 프레임도 미디어 묶음에 포함합니다.

배포본은 루트 또는 `/repository-name/` 같은 하위 경로에서 열 수 있도록 앱의 모든 자료 경로를 상대 경로로 유지해야 합니다. PDF worker와 WASM도 같은 배포본에 포함합니다. 실제 subpath 및 브라우저 검수 결과를 배포 전에 확인합니다.

## 다운로드 전달본 만들기

```sh
python scripts/build.py
python scripts/package.py
```

- `workshop-source.zip`: 코드·문서·교육 시나리오·고정 라이브러리·실제 응답팩. 정확한 모델 요청에는 입력 이미지 데이터도 포함되며, 화면 재생용 원본 미디어는 별도입니다.
- `workshop-media.zip`: 빌드에서 사용한 공개 미디어와 원본 라이선스. Release용 `source_pack/` 구조입니다.
- `workshop-offline.zip`: 코드와 선택 미디어를 함께 넣은 실행팩입니다. 압축을 풀고 `python scripts/serve.py`로 실행합니다.
- `workshop-handouts.zip`: 전자 조립·두 제품 계측의 SOP, CSV, 도면과 완성된 검수조서 예제입니다.
- `packages-manifest.json`: 파일 수·용량·SHA256을 기록합니다. ZIP을 실제 검사한 뒤 생성합니다.

패키지 생성 명령은 로컬 파일만 만듭니다. Release 업로드와 Pages workflow 실행은 별도이며, 버전별 게시 상태는 저장소의 Release·Actions에서 확인합니다.

## GitHub 저장소 준비

1. `scripts/package.py`의 허용 목록으로 만든 소스 ZIP을 독립 저장소로 사용합니다. 부모 연구 프로젝트나 로컬 검수 폴더를 추가하지 않습니다.
2. 자체 코드에 임의의 라이선스를 새로 부여하지 않고 외부 자료의 개별 고지를 유지합니다. [자료 출처](../DATA_LICENSES.md)를 확인합니다.
3. `data/source_pack`과 ZIP·결과물은 `.gitignore`에 따라 코드 커밋에서 제외합니다.
4. 빌드가 만든 공개 후보에서 미디어만 `source_pack/`을 최상위로 가진 ZIP으로 묶습니다. 원래 내부 자료팩 전체를 무검수 업로드하지 않습니다.
5. 미디어 ZIP을 해당 버전 Release에 올리고 SHA256을 기록합니다.
6. GitHub Pages의 Source를 GitHub Actions로 설정합니다.
7. 수동 `Deploy workshop` workflow에 해당 미디어 URL과 SHA256을 넣어 실행합니다.

미디어 아카이브에는 `source_pack/...` 폴더가 있어야 합니다. 제공된 `scripts/import_media.py`는 체크섬과 압축 경로를 검증한 뒤 이를 `data/source_pack`에 가져옵니다. 파일 부족이나 잘못된 체크섬이면 빌드가 실패해야 하며, 실패를 빈 영상으로 바꾸지 않습니다.

저장소는 `Darklightened/manufacturing-ai-agent-workshop`, 기본 브랜치는 `main`입니다. 미디어 Release ZIP의 체크섬은 함께 제공하는 `packages-manifest.json`을 사용합니다. 영상 없이 소스만 clone한 경우에는 위 미디어 가져오기 단계가 필요합니다. `prepare_data.py` 등 원본 준비 스크립트는 강사용 원본 입력을 요구하므로 수강생 실행 절차가 아닙니다.

## 배포 workflow

workflow는 `workflow_dispatch`만 사용하므로 push만으로 사이트가 자동 공개되지 않습니다. 실행자가 공개 준비를 완료한 후 수동으로 실행하는 흐름입니다. 사용한 GitHub Actions 구성은 [공식 Pages workflow 안내](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)를 따릅니다.

실제 모델 추론 서버는 정적 Pages 안에서 실행하지 않습니다. 향후 강사 서버에 `/api` 게이트웨이를 두고, 모델 키는 서버에 보관하며 수업 앱과 동일한 요청·응답 계약을 사용합니다. 현재 제어 실습에는 이 서버가 필요 없습니다.

## 오프라인과 진행 기록

전체 폴더에는 PDF.js와 sql.js를 포함해 실행 중 외부 CDN을 사용하지 않습니다. 다른 호스트/포트로 이동하면 브라우저 저장 영역도 달라집니다. 진행 기록을 내보내고 새 주소에서 가져오는 절차가 필요합니다. 동일 버전·시나리오·자료에 대한 검증 후 복구하고, 새로고침과 호스트 전환을 같은 동작으로 취급하지 않습니다.

단독 HTML 보고서는 앱과 다른 산출물입니다. 필요한 사진이 임베드된 보고서는 더블클릭으로 열 수 있지만 전체 실습 앱은 HTTP 서버로 실행합니다.

## 준비 스크립트와 실행 의존성

`scripts/prepare_data.py`는 교재 제작자가 원본 자료팩을 가져와 PDF·CSV·교육 이벤트를 다시 작성할 때 쓰는 도구입니다. 기본 원본 위치는 연구 작업 폴더를 기준으로 한 상대 경로이며, 독립 환경에서는 `--source`로 원본 팩을 명시해야 합니다. 이 제작 경로는 PyMuPDF가 필요합니다. 이미 생성된 실습을 실행하는 학생에게는 PyMuPDF, npm, 모델 환경을 요구하지 않습니다.

미디어 Release 팩은 앱 실행에 필요한 선별 미디어이며, 원본 전체 메타데이터까지 복원하는 연구 아카이브가 아닙니다. 새 시나리오를 원본 주석부터 재생성하려면 권리 확인된 전체 원본 자료와 별도 제작 의존성을 준비합니다.
