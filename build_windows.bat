@echo off
rem Windows 실행파일(.exe) 빌드 — 더블클릭으로 실행 (Python 3 설치 필요)
chcp 65001 > nul
cd /d "%~dp0"
if not exist .venv py -3 -m venv .venv || goto :error
.venv\Scripts\pip install -q -r requirements-build.txt || goto :error
.venv\Scripts\pyinstaller --noconfirm --clean app.spec || goto :error
echo 완료: dist\수학의힘 행정도우미.exe
pause
exit /b 0

:error
echo 빌드 실패
pause
exit /b 1
