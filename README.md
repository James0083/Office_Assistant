# 수학의힘 행정도우미

(Office_Assistant)

학원 행정용 데스크톱 앱. 수강료 일할 계산, 문자 템플릿, 메모를 한 창에서 다룬다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `app.py` | 창 띄우기(pywebview), 데이터 저장·잠금 |
| `ui.html` | 화면 전체 (HTML/CSS/JS) |
| `app.spec` | PyInstaller 빌드 설정 (macOS·Windows 공용) |
| `실행.command` | 개발용: 빌드 없이 소스에서 바로 실행 (macOS) |
| `build_mac.command` / `build_windows.bat` | 각 OS 에서 앱 빌드 |
| `.github/workflows/build.yml` | GitHub 에 올리면 두 OS 용 앱을 자동 빌드 |

## 실행

- 개발: `실행.command` 더블클릭
- 빌드: macOS 는 `build_mac.command`, Windows 는 `build_windows.bat` → `dist/` 에 결과물

## 데이터

앱과 같은 폴더의 `data.json` 에 저장된다. 공유 폴더에 두고 여러 명이 함께 써도
항목 단위 저장과 잠금 파일(`data.json.lock`)로 서로의 변경을 덮어쓰지 않는다.
