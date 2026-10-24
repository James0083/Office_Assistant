# 수학의힘 행정도우미

(Office_Assistant)

학원 행정용 데스크톱 앱. 수강료 일할 계산, 문자 템플릿, 메모를 한 창에서 다룬다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `app.py` | 창 띄우기(pywebview), 데이터 저장·잠금 |
| `ui.html` | 화면 전체 (HTML/CSS/JS) |
| `app.spec` | PyInstaller 빌드 설정 (macOS·Windows 공용), 버전·저작권 정보 |
| `LICENSE` | 저작권·이용 조건 |
| `실행.command` | 개발용: 빌드 없이 소스에서 바로 실행 (macOS) |
| `build_mac.command` / `build_windows.bat` | 각 OS 에서 앱 빌드 |
| `.github/workflows/build.yml` | GitHub 에 올리면 두 OS 용 앱을 자동 빌드 + Windows exe 실행 테스트 |

## 실행

- 개발: `실행.command` 더블클릭
- 빌드: macOS 는 `build_mac.command`, Windows 는 `build_windows.bat` → `dist/` 에 결과물
- 자동 빌드: GitHub Actions 탭 → 실행 결과 → Artifacts 에서 `macOS`, `Windows` 를 받는다.
  `Windows-screenshot` 은 빌드 서버에서 exe 를 띄워 찍은 화면이다.

### macOS 에서 받은 앱이 "손상되었기 때문에 열 수 없습니다" 로 뜰 때

Apple 서명이 없는 앱이라 생기는 경고다. 앱을 쓸 폴더로 옮긴 뒤 한 번 실행한다.

```sh
xattr -cr "/경로/수학의힘 행정도우미.app"
```

Actions 빌드는 Apple Silicon 용이라 인텔 맥에서는 실행되지 않는다.

## 데이터

앱과 같은 폴더의 `data.json` 에 저장된다. 파일이 없으면 기본 항목으로 시작하고, 처음 저장할 때 생긴다.

공유 폴더에 두고 여러 명이 함께 써도 항목 단위 저장과 잠금 파일(`data.json.lock`)로
서로의 변경을 덮어쓰지 않는다. 같은 항목을 다른 사람이 먼저 고쳤으면 저장할 때
"최신 내용 불러오기 / 내 내용으로 덮어쓰기 / 취소" 중에서 고른다.

## 라이선스

Copyright (c) 2026 유재원 ([James0083](https://github.com/James0083)). All rights reserved.

저작권자의 허락 없이 복제·수정·배포할 수 없다. 자세한 내용은 [LICENSE](LICENSE) 참고.
빌드한 앱에도 LICENSE 파일과 저작권 정보(macOS '정보 가져오기', Windows 파일 속성 → 자세히)가 들어간다.
