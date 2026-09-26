#!/usr/bin/env bash
# 一条命令拉起本地前后端：预检 → （默认）前端构建 → 起两个服务 → 写入待出动到已处置的场景数据 → 复核处置结论。
# 用法：
#   scripts/dev-up.sh              默认先构建前端，校验全链路
#   SKIP_BUILD=1 scripts/dev-up.sh 跳过构建快速重启
#   KEEP_SERVICES=1 ...           不执行场景写入与复核（只起服务）
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/dev-common.sh"

log "第 1 步：本地环境预检（依赖缺失自动安装，端口占用直接报错）"
"$ROOT_DIR/scripts/check-local-env.sh"

mkdir -p "$LOG_DIR"
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"

if [ "${SKIP_BUILD:-0}" != "1" ]; then
  log "第 2 步：构建前端（vue-tsc 类型检查 + vite build）"
  (cd "$FRONTEND_DIR" && npm run build) || fail "前端构建失败，请先修复类型或编译错误"
  log "前端构建通过 ✓"
else
  log "第 2 步：SKIP_BUILD=1，跳过前端构建"
fi

log "第 3 步：启动后端 http://${BACKEND_HOST}:${BACKEND_PORT}"
(
  cd "$BACKEND_DIR"
  exec "$VENV_DIR/bin/uvicorn" app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT"
) >"$LOG_DIR/backend.log" 2>&1 &
echo $! >"$BACKEND_PID_FILE"

log "第 4 步：启动前端 http://${FRONTEND_HOST}:${FRONTEND_PORT}"
(
  cd "$FRONTEND_DIR"
  exec npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" --strictPort
) >"$LOG_DIR/frontend.log" 2>&1 &
echo $! >"$FRONTEND_PID_FILE"

# 等服务起来：后端探 /api/health，前端探 HTTP 200；进程提前退出则直接报日志位置。
wait_for() {
  local url="$1" name="$2" pid_file="$3" log_file="$4"
  for _ in $(seq 1 60); do
    if ! kill -0 "$(cat "$pid_file")" 2>/dev/null; then
      fail "${name}进程已提前退出，详见日志：$log_file"
    fi
    if curl -sf -o /dev/null --max-time 2 "$url"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

log "第 5 步：等待服务就绪…"
if ! wait_for "$BASE_URL/api/health" "后端" "$BACKEND_PID_FILE" "$LOG_DIR/backend.log"; then
  fail "后端健康检查超时，详见日志：$LOG_DIR/backend.log"
fi
if ! wait_for "http://${FRONTEND_HOST}:${FRONTEND_PORT}" "前端" "$FRONTEND_PID_FILE" "$LOG_DIR/frontend.log"; then
  fail "前端启动超时，详见日志：$LOG_DIR/frontend.log"
fi
log "前后端均已就绪 ✓"

if [ "${KEEP_SERVICES:-0}" != "1" ]; then
  log "第 6 步：写入应急抢险场景数据（事件上报 → 班组出动 → 处置结果）"
  python3 "$ROOT_DIR/scripts/seed-emergency-scenario.py" --base-url "$BASE_URL" --output "$SEED_RECORD"

  log "第 7 步：复核处置结论与接口返回一致"
  python3 "$ROOT_DIR/scripts/check-emergency-result.py" --base-url "$BASE_URL" --record "$SEED_RECORD"
else
  log "KEEP_SERVICES=1，跳过场景写入与复核（可手动执行 scripts/check-emergency-result.py --new）"
fi

cat <<EOF

[dev] ============================================================
[dev] 应急抢险本地链路已就绪：
[dev]   前端：      http://${FRONTEND_HOST}:${FRONTEND_PORT}/emergency
[dev]   后端 API：  $BASE_URL/api/emergency
[dev]   健康检查：  $BASE_URL/api/health
[dev]   场景记录：  $SEED_RECORD
[dev]   后端日志：  $LOG_DIR/backend.log
[dev]   前端日志：  $LOG_DIR/frontend.log
[dev] 停止服务：    make dev-down（或 scripts/dev-down.sh）
[dev] 单独复核：    scripts/check-emergency-result.py --new
[dev] ============================================================
EOF
