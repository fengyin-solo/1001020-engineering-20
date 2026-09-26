#!/usr/bin/env bash
# 手工启动后端：虚拟环境缺失或损坏（例如从别的机器拷来）时自动重建。
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
  echo "[run] 后端虚拟环境缺失或已损坏，重建 .venv …"
  rm -rf .venv
  if ! python3 -m venv .venv 2>/dev/null; then
    # 系统 python 不带 ensurepip 时（部分 Debian/Ubuntu），退回 get-pip 引导。
    rm -rf .venv
    python3 -m venv --without-pip .venv
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    .venv/bin/python /tmp/get-pip.py -q
  fi
  .venv/bin/pip install -q -r requirements.txt
fi

exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${BACKEND_PORT:-8000}"
