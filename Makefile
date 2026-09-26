.PHONY: install check dev dev-fast dev-down seed check-result backend frontend

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

# 只做本地环境预检：系统依赖缺失报错，项目依赖缺失自动安装，端口占用报错
check:
	scripts/check-local-env.sh

# 一条命令：预检 + 前端构建 + 拉起前后端 + 写入待出动到已处置场景数据 + 复核处置结论
dev:
	scripts/dev-up.sh

# 跳过前端构建的快速重启
dev-fast:
	SKIP_BUILD=1 scripts/dev-up.sh

dev-down:
	scripts/dev-down.sh

# 单独重跑应急抢险三段链路（事件上报 → 班组出动 → 处置结果）
seed:
	python3 scripts/seed-emergency-scenario.py

# 处置完成后复核处置结论与接口返回是否一致（--new 先重跑场景再复核）
check-result:
	python3 scripts/check-emergency-result.py

backend:
	cd backend && ./run.sh

frontend:
	cd frontend && npm run dev
