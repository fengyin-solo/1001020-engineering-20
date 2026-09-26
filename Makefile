.PHONY: install build backend frontend up check

install:
	cd backend && rm -rf .venv && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

build:
	cd frontend && npm run build

backend:
	cd backend && ./run.sh

frontend:
	cd frontend && npm run dev

# 一条命令拉起前端预览与后端，并写入全生命周期示例数据
up:
	./scripts/start.sh

# 应急抢险链路核验：上报 → 出动 → 处置，确认处置结论与接口返回一致
check:
	python3 scripts/check_emergency.py
