#!/bin/bash
# macOS 앱(.app) 빌드 — 더블클릭 또는 터미널에서 실행
set -e
cd "$(dirname "$0")"
PY=/opt/homebrew/bin/python3
[ -x "$PY" ] || PY=python3
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q -r requirements-build.txt
.venv/bin/pyinstaller --noconfirm --clean app.spec
echo "완료: dist/수학의힘 행정도우미.app"
