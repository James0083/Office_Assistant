#!/bin/bash
# 개발용: 빌드 없이 소스에서 바로 실행 (처음 한 번은 환경을 준비하느라 오래 걸림)
cd "$(dirname "$0")"
PY=/opt/homebrew/bin/python3
[ -x "$PY" ] || PY=python3
if [ ! -d .venv ]; then
  "$PY" -m venv .venv && .venv/bin/pip install -q -r requirements.txt
fi
.venv/bin/python app.py
