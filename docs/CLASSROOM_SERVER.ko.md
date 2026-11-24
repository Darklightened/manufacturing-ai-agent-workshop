# 강의용 대체 주소: 공개 중계 서버와 비공개 터널

GitHub Pages가 차단된 환경에서는 **공개 서버의 실습 주소**를 수강생에게 제공합니다. 제조 연구 서버 주소와 SSH 정보는 수강생에게 전달하지 않습니다.

```text
수강생 브라우저
  → 공개 서버의 HTTPS 실습 주소
  → 공개 서버 127.0.0.1:18921
  → SSH 역방향 터널
  → 제조 서버 127.0.0.1:8921
  → 검토된 dist 파일 및 지정 ZIP
```

공개 중계 대상과 접속 계정은 운영자의 별도 설정으로 관리합니다. 도메인·TLS와 실제 중계 서비스는 별도 확인 대상입니다. 아래 설정은 운영 준비용이며 공개 접속이 검증되었다는 뜻이 아닙니다. SSH 인증 실패는 강사 PC의 개인키를 복사해 해결하지 않고, 필요한 경우 **이 중계 작업만 위한 별도 공개키 등록**으로 해결합니다. 공개키 지문을 확인하고 기존 계정 설정·다른 서비스는 유지합니다.

## 1. 제조 서버의 정적 제공 범위

```sh
python scripts/build.py
python scripts/package.py
python scripts/serve_classroom.py --host 127.0.0.1 --port 8921 --with-packages --hours 72
```

실행 위치와 관계없이 기본 제공 디렉터리는 이 프로젝트의 `dist`입니다. `--directory`로 지정한 경우에도 `seminar.build.v3` 매니페스트가 필요합니다. 서버는 시작 시 모든 허용 파일의 크기와 SHA256을 확인하며, 매니페스트에 없는 파일은 공개하지 않습니다. 시작 후 파일이 변경되면 해당 응답을 보류하므로 새 빌드 완료 후 서버를 다시 실행합니다.

- 허용 요청: GET·HEAD, 영상 탐색을 위한 단일 byte Range
- 차단 범위: 디렉터리 목록, 숨김 파일, 심볼릭 링크, 상위 경로, 업로드·실행·API 요청
- 기본 수명: 72시간, 지정 가능한 최대 수명: 168시간
- 기본 연결 제한: 128개, 소켓 무응답 제한: 15초
- 종료 범위: 이 서버 프로세스만 종료. 다른 서비스·GPU 프로세스와 무관
- 기록 범위: 시작·종료와 HTTP 상태 수. 수강생 IP·URL 쿼리·입력 본문을 접근 로그에 기록하지 않음

`--with-packages`를 지정하면 `packages-manifest.json`에 있는 **workshop-source/media/offline/handouts.zip 네 파일**을 한 번 검증한 뒤 `/classroom-downloads/`에서 제공합니다. 기본 패키지 위치는 프로젝트 루트이며 `--package-root`로 명시할 수 있습니다. 그 폴더의 다른 파일은 공개하지 않습니다. 다운로드 페이지의 해당 GitHub Release 링크만 응답 시 로컬 ZIP 주소로 바뀌며, 원본 HTML은 변경하지 않습니다. 변환된 응답의 길이·ETag·Range는 변환 후 바이트를 기준으로 계산합니다.

회사 입력 ZIP·PDF·영상·폰트·WASM·슬라이드는 이미 같은 배포본에 포함되어 있습니다. 회사 자료 선택과 답변은 브라우저 안에서 처리하며 이 서버에 업로드하지 않습니다.

정적 서버는 `X-Classroom-Origin: static-v1` 표식을 반환합니다. 중계가 엉뚱한 로컬 서비스를 연결했는지 구분하기 위한 표식이며 비밀 토큰·인증·서명이 아닙니다.

## 2. 역방향 터널 구성 확인

다음 `<...>` 부분은 실제 운영자가 준비한 경로로 바꿉니다. 아래 예시 자체로는 접속하지 않습니다.

```sh
python scripts/start_classroom_tunnel.py \
  --ssh-target seminar@relay.example.org \
  --identity-file '<전용 개인키 경로>' \
  --known-hosts-file '<검증한 host key 파일 경로>' \
  --local-port 8921 --remote-port 18921 --hours 72
```

기본 동작은 **구성 확인만**입니다. `--run`을 추가해야 실제 연결합니다. `known_hosts`가 없거나 대상 host key가 등록되지 않았으면 실제 연결을 중단합니다. `StrictHostKeyChecking=yes`이며 서버 키를 자동 승인하지 않습니다. 최초 공개키 지문은 신뢰 가능한 경로로 대조해야 합니다.

기본 SSH 설정은 `-F /dev/null`로 공유 설정을 읽지 않습니다. 기존 별칭이 필요한 경우에만 `--ssh-config`를 명시합니다. 지정 구성에 추가 포워딩이 상속되면 실행 전 중단합니다. 전용 키 경로를 지정하면 해당 키만 시도합니다. 암호 대화상자, 에이전트 전달, X11, TTY, 공유 SSH control socket은 사용하지 않습니다.

터널은 공개 서버의 **127.0.0.1:18921에만** 열립니다. `-R 0.0.0.0:...`나 `GatewayPorts` 변경을 요구하지 않습니다. SSH 연결이 끊어지면 최대 3회 재연결하며 전체 72시간 만료 시각은 연장하지 않습니다. 인증·host key·포트 점유 오류에서는 반복하지 않습니다. 이 실행이 만든 SSH 프로세스만 종료합니다. `ssh_started` 로그는 프로세스 생성 표시이며 외부 HTTP 접속 성공 증거가 아닙니다.

## 3. 공개 서버의 HTTPS 프록시 예시

아래는 **기존 서비스와 분리된 주소**를 준비한 운영자가 검토할 설정 예시입니다. 설치·인증서 발급·방화벽 변경을 자동 실행하지 않습니다. 도메인은 실제 DNS가 공개 서버를 가리킨 뒤 대체합니다.

Caddy 예시:

```caddyfile
workshop.example.org {
    @read method GET HEAD
    handle @read {
        reverse_proxy 127.0.0.1:18921
    }
    respond "Method not allowed" 405
}
```

기존 nginx를 사용하는 경우:

```nginx
server {
    listen 443 ssl;
    server_name workshop.example.org;
    ssl_certificate     /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;
    access_log off;
    location / {
        limit_except GET HEAD { deny all; }
        proxy_pass http://127.0.0.1:18921;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_read_timeout 30s;
        proxy_buffering off;
    }
}
```

실습 주소는 별도 도메인의 `/`에 제공하는 구성을 기준으로 합니다. 하위 경로에 올릴 때는 프록시 경로와 로컬 ZIP URL 변환을 함께 검수해야 합니다. 전용 SSH 계정까지 구성할 경우 운영자가 `AllowTcpForwarding remote`와 `PermitListen 127.0.0.1:18921`을 해당 계정에만 적용할 수 있습니다. 기존 공용 계정 전체의 SSH 정책을 임의로 바꾸지 않습니다.

## 4. 외부 접속 검수와 수강생 안내

공개 주소를 QR에 넣기 전, 제조 서버가 아닌 **교실 PC 또는 외부 네트워크**에서 다음 항목을 확인합니다.

1. 첫 화면과 실습 1·2·3 접속
2. 영상 재생·탐색과 PDF·WASM 로딩
3. 회사 자료 ZIP, 슬라이드 PDF·PPTX, 전체 실습팩 다운로드
4. 보류 질문 → 답변 → 판정 → 보고서 저장
5. `/../`, 숨김 파일, 디렉터리 목록과 POST 요청의 차단
6. 종료 후 해당 실습 주소가 더 이상 내용을 제공하지 않는지 확인

다른 주소로 이동하면 브라우저 저장 영역도 달라집니다. 진행하던 기록은 **진행 내보내기 → 새 주소에서 가져오기**로 옮깁니다. 기존 GitHub Pages의 기록이 자동으로 중계 주소에 나타나지는 않습니다.

현재 기본 세 실습은 `authored_demo` 예시입니다. `app.mjs`의 `crypto.subtle` 무결성 검증은 별도 과거 실제 응답팩(`electronics`, `recorded` 경로)에 사용됩니다. 이 경로는 HTTPS 또는 localhost가 필요하며 HTTP에서 무결성 검증을 생략하지 않습니다. 기본 예시가 HTTP에서 열리는 것과 전체 기능이 안전한 문맥에서 검수되었다는 것은 구분합니다. 최종 배포는 HTTPS로 통일하는 구성이 좋습니다. 강의 PC의 음성 출력은 별도로 확인합니다.

## 5. 공개 서버 연결이 어려운 경우

현재 제조 서버는 사설 네트워크 주소를 사용합니다. 8921을 수신하도록 실행하는 것만으로 교실 인터넷에서 접속할 수 있지는 않습니다. 공개 중계 서버의 SSH 인증·프록시·외부 방화벽 경로를 별도로 확인합니다.

강사는 미리 `workshop-offline.zip`을 받아 둡니다. 압축을 푼 강사 PC에서 기존 `python scripts/serve.py --port 8921`로 실행할 수 있습니다. 교실 LAN 공유는 그 PC의 학교 네트워크 정책과 연결을 확인한 뒤 진행하며, 개인 폴더 대신 제공된 실습 폴더만 사용합니다. 수강생에게 서버 계정이나 SSH 키를 전달할 필요는 없습니다.

## 운영자 검증 명령

```sh
python -m unittest discover -s tests -p 'test_classroom_*.py' -v
```

이 검사는 임시 파일·루프백 임시 포트와 무해한 CPU 자식 프로세스만 사용합니다. 실제 SSH 로그인, 공개 프록시 설치, 외부 방화벽 변경 또는 GPU 실행을 수행하지 않습니다.
