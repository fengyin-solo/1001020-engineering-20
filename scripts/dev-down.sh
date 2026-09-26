#!/usr/bin/env bash
# 停止 dev-up 拉起的前后端：按 PID 递归结束子进程（npm 会派生 vite，只杀父进程会留下孤儿）。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/dev-common.sh"

kill_tree() {
  local pid="$1"
  [ -z "$pid" ] && return 0
  local children
  children="$(pgrep -P "$pid" 2>/dev/null || true)"
  for child in $children; do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

stopped=0
for service in backend frontend; do
  pid_file="$LOG_DIR/${service}.pid"
  if [ -f "$pid_file" ]; then
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill_tree "$pid"
      log "已停止 ${service}（PID ${pid}）"
    else
      log "${service} 进程（PID ${pid}）已不在运行"
    fi
    rm -f "$pid_file"
    stopped=1
  fi
done

# 兜底：脚本第一次运行前如果有残留的 vite/uvicorn 占着端口，按端口兜底清理。
for spec in "${BACKEND_PORT}:uvicorn" "${FRONTEND_PORT}:vite"; do
  port="${spec%%:*}"
  if port_in_use "$port"; then
    pids="$(lsof -ti "tcp:${port}" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      # shellcheck disable=SC2086
      kill $pids 2>/dev/null || true
      log "已按端口 ${port} 清理残留进程：$(echo "$pids" | tr '\n' ' ')"
      stopped=1
    fi
  fi
done

[ "$stopped" -eq 1 ] && log "本地服务已全部停止" || log "没有正在运行的本地服务"
