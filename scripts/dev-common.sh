#!/usr/bin/env bash
# 公共配置与工具函数：被 dev-up / dev-down / check-local-env 复用，端口等默认值只在这里改。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
LOG_DIR="$ROOT_DIR/.dev"
SEED_RECORD="$LOG_DIR/emergency-seed.json"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BASE_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"

log() { printf '[dev] %s\n' "$*"; }
fail() { printf '[dev] 错误：%s\n' "$*" >&2; exit 1; }

# 端口是否已被占用：占用返回 0（true），空闲返回 1。
port_in_use() {
  local port="$1"
  python3 - "$port" <<'PY'
import socket, sys
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", int(sys.argv[1])))
    except OSError:
        sys.exit(0)
sys.exit(1)
PY
}

require_port_free() {
  local port="$1" name="$2"
  if port_in_use "$port"; then
    fail "${name}端口 ${port} 已被占用，请先释放（lsof -i :${port} 查看占用进程），或改用其他端口：BACKEND_PORT/FRONTEND_PORT=xxxx make dev"
  fi
}
