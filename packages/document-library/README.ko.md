# 실습 문서함

현재 실습 세션과 별도의 IndexedDB `state` 저장소 키 `documentLibrary`에 사용자 생성 파일의 원본 Blob을 보관합니다. 저장소 스키마를 바꾸거나 `current` 키를 수정하지 않습니다. 서버 전송, 자동 삭제, 이전 파일 덮어쓰기는 없습니다.

```js
import {DocumentLibrary} from './packages/document-library/ui.mjs';
const library = new DocumentLibrary({
  main: document.querySelector('#main'),
  read: async () => /* documentLibrary 키를 읽은 값 또는 null */ null,
  write: async state => { /* documentLibrary 키에 state 저장 */ },
  toast: message => { /* 사용자에게 저장 실패 알림 */ },
});
const result = await library.capture({
  filename: '검수조서.html', content: originalBlob, mime: 'text/html',
  scenarioId: 'measurement_input_demo', title: '계측 검수조서', summary: '충족 3 / 불일치 0',
});
await library.render();
library.leave();
```

호스트에서 `style.css`를 연결합니다. 기존 다운로드를 먼저 유지하면서 `capture`를 비동기로 호출합니다. 결과는 `{ok:true,id}` 또는 `{ok:false,error}`이며, 보관에 실패해도 원래 다운로드가 중단되지 않습니다. `capture`가 반환된 뒤 현재 화면이 문서함이면 호스트가 `render()`를 호출할 수 있습니다. 문서함 내부 다운로드는 호스트의 capture hook을 다시 호출하지 않습니다.

파일 형식은 HTML, DOCX, CSV, JSON, SQLite입니다. 회사 자료 ZIP, 입력 PDF, 글꼴 등은 자동 보관하지 않습니다. 파일당 25 MB, 총 100 MB, 100개가 한도입니다. 초과 시 사용자가 직접 삭제하도록 안내하며 기존 파일을 자동으로 지우지 않습니다. 동일한 파일 이름도 저장 시각과 별도 식별자로 구분합니다.

HTML은 스크립트 실행 권한이 없는 sandbox iframe에서 표시합니다. 미리보기 전용 CSP로 외부 이미지·통신·스크립트·중첩 프레임·폼을 차단하고 내장 이미지와 글꼴을 허용합니다. HTML 원본 Blob은 변경하지 않습니다. JSON·CSV는 `textContent`로 표시하고, DOCX·SQLite는 다운로드만 제공합니다. 사용자 제목·파일 이름·요약도 DOM 텍스트로 삽입합니다.

수업 제공 예제 카드는 사용자 문서와 분리하며 저장 용량에 포함하지 않습니다. LAB1의 HTML/DOCX/PDF, LAB2 표준형·정밀형, LAB3 검수조서·보고서를 연결합니다. 삭제 버튼은 명시적 확인을 거치며 브라우저의 사본만 삭제합니다. 현재 실습 기록 및 이미 다운로드한 파일에는 영향을 주지 않습니다.

`node --test tests/document-library.test.mjs`에서 원본 바이트 보존, 안전한 경로, 용량 제한, 중복 저장, 동시 저장, 저장소 오류를 검증합니다. 실제 브라우저 동작은 호스트의 메뉴·다운로드 hook 연결 이후 별도로 확인해야 합니다.
