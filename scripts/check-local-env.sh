#!/usr/bin/env bash
# 本地环境预检：系统依赖缺失直接报错并给出安装提示；项目依赖缺失自动安装；端口被占用明确报错。
# 用法：scripts/check-local-env.sh
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/dev-common.sh"

log "检查系统依赖…"
if ! command -v python3 >/dev/null 2>&1; then
  fail "未找到 python3，请先安装 Python 3.10 及以上版本（Debian/Ubuntu：apt install python3 python3-venv）"
fi
PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  fail "Python 版本过低（当前 ${PY_VERSION}），需要 3.10 及以上"
fi
log "python3 ${PY_VERSION} ✓"

if ! command -v node >/dev/null 2>&1; then
  fail "未找到 node，请先安装 Node.js 18 及以上版本（https://nodejs.org/）"
fi
NODE_MAJOR="$(node -e 'console.log(process.versions.node.split(".")[0])')"
if [ "$NODE_MAJOR" -lt 18 ]; then
  fail "Node.js 版本过低（当前 $(node --version)），需要 18 及以上"
fi
if ! command -v npm >/dev/null 2>&1; then
  fail "未找到 npm，请确认 Node.js 安装完整"
fi
log "node $(node --version) / npm $(npm --version) ✓"

# 后端虚拟环境：缺失或损坏（例如从别的机器拷来的 venv，python 软链失效）就重建。
need_rebuild=0
if [ ! -x "$VENV_DIR/bin/python" ]; then
  need_rebuild=1
elif ! "$VENV_DIR/bin/python" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
  need_rebuild=1
fi
if [ "$need_rebuild" -eq 1 ]; then
  log "后端虚拟环境缺失或已损坏，重建 $VENV_DIR …"
  rm -rf "$VENV_DIR"
  if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
    # 部分发行版默认不带 ensurepip，退回 --without-pip 再手工引导 pip。
    log "系统 python 缺少 ensurepip，改用 get-pip 引导…"
    rm -rf "$VENV_DIR"
    python3 -m venv --without-pip "$VENV_DIR"
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
      || fail "下载 get-pip.py 失败，请检查网络后重试"
    "$VENV_DIR/bin/python" /tmp/get-pip.py -q || fail "引导 pip 失败，请检查网络后重试"
  fi
  log "安装后端依赖…"
  "$VENV_DIR/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt" \
    || fail "后端依赖安装失败，请检查网络或 requirements.txt 后重试"
fi
log "后端依赖 ✓"

if [ ! -x "$FRONTEND_DIR/node_modules/.bin/vite" ]; then
  install_frontend=1
else
  # node_modules 从别的机器拷来时 bin 还在，但 rollup 等原生包会缺当前平台的二进制，
  # 构建期才报 “Cannot find module @rollup/rollup-xxx”。用平台标记提前发现。
  platform_marker="$FRONTEND_DIR/node_modules/.install-platform"
  current_platform="$(node -e 'console.log(process.platform + "-" + process.arch)')"
  if [ "$(cat "$platform_marker" 2>/dev/null || true)" != "$current_platform" ]; then
    log "前端依赖的安装平台（$(cat "$platform_marker" 2>/dev/null || echo '未知')）与当前（${current_platform}）不一致，重新安装…"
    install_frontend=1
  else
    install_frontend=0
  fi
fi
if [ "$install_frontend" -eq 1 ]; then
  rm -rf "$FRONTEND_DIR/node_modules"
  (cd "$FRONTEND_DIR" && npm install --no-fund --no-audit) \
    || fail "前端依赖安装失败，请检查网络后重试"
  (cd "$FRONTEND_DIR" && node -e 'require("fs").writeFileSync("node_modules/.install-platform", process.platform+"-"+process.arch)')
fi
log "前端依赖 ✓"

require_port_free "$BACKEND_PORT" "后端"
require_port_free "$FRONTEND_PORT" "前端"
log "端口 ${BACKEND_PORT}（后端）/ ${FRONTEND_PORT}（前端）可用 ✓"

log "本地环境检查通过"
