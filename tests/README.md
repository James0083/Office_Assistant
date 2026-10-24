# 테스트

모든 테스트는 임시 폴더를 `TUITION_DATA_DIR` 로 써서 프로젝트의 `data.json` 을 건드리지 않는다.

| 파일 | 내용 | 필요한 것 |
|---|---|---|
| `test_backend.py` | `app.Api` 를 직접 호출: 첫 실행, 손상·예전 형식 파일, 이름 중복, 두 사람 동시 편집·충돌, 잠금 파일 | 표준 라이브러리만 |
| `test_ui.py` | `ui.html` 을 Chromium 으로 띄워 클릭: 수강료 계산, 템플릿·자동변수·미리보기, 메모, 저장 안 한 내용 확인, 두 사람 충돌 | Playwright (없으면 건너뜀) |
| `_common.py` | 공용 준비 (임시 데이터 폴더, webview 가 없으면 빈 모듈로 대신) | |

## 실행

```sh
# 백엔드만 (UI 테스트는 skip 으로 표시됨)
.venv/bin/python -m unittest discover tests

# UI 까지 — 처음 한 번 설치
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium   # 설치된 Google Chrome 이 있으면 생략 가능
.venv/bin/python -m unittest discover tests -v
```

UI 테스트는 `window.pywebview.api` 를 흉내 내는 스크립트를 넣고, 그 호출을 같은 프로세스의 진짜 `app.Api` 로 넘긴다.
두 사람 상황은 브라우저 창 두 개가 같은 임시 폴더를 쓰는 식으로 만든다. `confirm()` 은 가짜로 바꿔 답을 정해 둔다.
창 닫기 확인(pywebview 의 `confirm_close`)과 OS 클립보드 복사는 실제로 확인하지 못한다.

## 알려진 버그

`@unittest.expectedFailure` 가 붙은 테스트는 지금 코드에 있는 버그를 나타낸다 (주석에 원인·위치).
결과에 `expected failures=N` 으로 나오고, 고치면 `unexpected success` 로 바뀌니 그때 데코레이터를 지운다.
