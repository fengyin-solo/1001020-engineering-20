#!/usr/bin/env bash
# 本地一键启动：构建产物 + 后端接口 + 示例数据，一条命令拉起应急抢险联调环境。
#
# 用法：
#   ./scripts/start.sh            # 校验依赖与端口后，同时拉起后端与前端预览服务
#   BACKEND_PORT=8001 ./scripts/start.sh
#
# 退出码非 0 时表示前置条件不满足，报错信息会说明缺什么、怎么补。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
LOG_DIR="$ROOT_DIR/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

fail() {
  echo "启动失败：$1" >&2
  exit 1
}

# 端口探测：能绑定说明空闲，绑定失败说明被占用
port_in_use() {
  python3 - "$1" <<'PY'
import socket
import sys

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(0)
finally:
    sock.close()
sys.exit(1)
PY
}

# 服务探活：循环等待某个 URL 返回 200
wait_for_url() {
  local name="$1" url="$2" attempts=30
  while [ "$attempts" -gt 0 ]; do
    if python3 - "$url" <<'PY'
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as resp:
        sys.exit(0 if resp.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
    then
      return 0
    fi
    sleep 1
    attempts=$((attempts - 1))
  done
  return 1
}

# ---------- 1. 依赖检查：缺什么直接报什么 ----------
command -v python3 >/dev/null 2>&1 || fail "未找到 python3，请先安装 Python 3.10+ 再执行 make install"
command -v node >/dev/null 2>&1 || fail "未找到 node，请先安装 Node.js 18+ 再执行 make install"
command -v npm >/dev/null 2>&1 || fail "未找到 npm，请先安装 Node.js（自带 npm）再执行 make install"

if [ ! -x "$ROOT_DIR/backend/.venv/bin/python" ]; then
  fail "后端虚拟环境缺失或已损坏（backend/.venv），请先执行 make install 重建依赖"
fi
if ! "$ROOT_DIR/backend/.venv/bin/python" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  fail "后端依赖不完整（fastapi/uvicorn 导入失败），请先执行 make install 重新安装"
fi
if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  fail "前端依赖未安装（frontend/node_modules 不存在），请先执行 make install"
fi
if [ ! -f "$ROOT_DIR/frontend/dist/index.html" ]; then
  fail "前端尚未构建（frontend/dist 不存在），请先执行 make build"
fi

# ---------- 2. 端口检查：被占用时不抢端口，直接报清楚 ----------
if port_in_use "$BACKEND_PORT"; then
  fail "后端端口 $BACKEND_PORT 已被占用（可能是上次启动的服务未停止），请先释放端口或用 BACKEND_PORT=其他端口 重新启动"
fi
if port_in_use "$FRONTEND_PORT"; then
  fail "前端端口 $FRONTEND_PORT 已被占用（可能是上次启动的服务未停止），请先释放端口或用 FRONTEND_PORT=其他端口 重新启动"
fi

mkdir -p "$LOG_DIR"

# ---------- 3. 拉起两个服务，退出时一起回收 ----------
BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> 启动后端（127.0.0.1:$BACKEND_PORT，日志 $BACKEND_LOG）"
(
  cd "$ROOT_DIR/backend"
  exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
) >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

if ! wait_for_url "后端" "http://127.0.0.1:$BACKEND_PORT/api/health"; then
  fail "后端 30 秒内未就绪，请查看日志 $BACKEND_LOG"
fi
echo "    后端就绪，示例数据已随启动写入内存库（应急抢险 EMER-2026-0001 ~ 0004，覆盖 待响应/响应中/处置中/已处置）"

echo "==> 启动前端预览（127.0.0.1:$FRONTEND_PORT，日志 $FRONTEND_LOG）"
(
  cd "$ROOT_DIR/frontend"
  exec env VITE_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT" \
    npx vite preview --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

if ! wait_for_url "前端" "http://127.0.0.1:$FRONTEND_PORT/"; then
  fail "前端 30 秒内未就绪，请查看日志 $FRONTEND_LOG"
fi

echo ""
echo "联调环境已就绪："
echo "  前端页面  http://127.0.0.1:$FRONTEND_PORT/"
echo "  后端接口  http://127.0.0.1:$BACKEND_PORT/api/health"
echo "  应急抢险  前端进入「应急抢险管理」页，或直接调 http://127.0.0.1:$BACKEND_PORT/api/emergency"
echo ""
echo "另开一个终端执行 make check，可对应急抢险链路（上报→出动→处置）做自动核验。"
echo "按 Ctrl+C 同时停止两个服务。"

wait
