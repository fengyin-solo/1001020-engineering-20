# 市政道路桥梁养护管理平台

面向市政道路桥梁日常巡查、定期检测、病害维修、除雪防汛与占道施工的一体化养护管理后台。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/            每个业务模块一个页面
│   ├── src/api/              统一请求封装
│   ├── src/stores/           会话与筛选状态
│   └── vite.config.ts        dev server 与 preview 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/          每个业务模块一组接口
│   ├── app/services/         业务规则与状态流转
│   └── app/store.py          内存数据仓库与示例数据
├── scripts/
│   ├── start.sh              一键拉起前后端（含依赖与端口检查）
│   └── check_emergency.py    应急抢险链路检查脚本
├── Makefile
├── .gitignore
└── docker-compose.yml
```

## 快速开始（推荐）

```bash
make install   # 安装前后端依赖（会重建 backend/.venv）
make build     # 构建前端产物 frontend/dist
make up        # 一条命令拉起后端 + 前端预览，并写入示例数据
```

`make up` 启动后：

- 前端页面：`http://127.0.0.1:5173/`（`vite preview` 提供构建产物，`/api` 代理到后端）
- 后端接口：`http://127.0.0.1:8000/api/health`
- 示例数据随后端启动写入内存库，应急抢险模块自带 `EMER-2026-0001 ~ 0004`
  四条事件，覆盖 待响应 → 响应中 → 处置中 → 已处置 全生命周期，
  事件编号、响应等级、出动班组、处置结果均已填写。
- 数据存在内存里，重启服务即重新加载 `backend/app/seed.py`，
  本地开发不需要手工同步数据库；改完 seed 重启即生效。

`make up` 在前置条件不满足时会直接报错并退出，不会带病启动：

- 缺少 python3 / node / npm，或 `backend/.venv`、`frontend/node_modules`、
  `frontend/dist` 缺失（含虚拟环境损坏）时，会提示先执行 `make install` 或 `make build`；
- 8000 / 5173 端口被占用时，会说明是哪个端口、可用
  `BACKEND_PORT=8001 FRONTEND_PORT=5174 make up` 换端口启动。

两个服务的日志写在 `logs/backend.log`、`logs/frontend.log`，按 `Ctrl+C` 同时停止。

### 应急抢险链路验收

服务起来后，另开一个终端执行：

```bash
make check
```

检查脚本（`scripts/check_emergency.py`，只依赖 Python 标准库，可重复执行）会：

1. 校验示例数据覆盖 待响应/响应中/处置中/已处置 四种状态，
   且事件编号、响应等级、出动班组均已填写；
2. 现场登记一条 `EMER-CHK-<时间戳>` 事件，依次执行
   启动响应 → 调集力量（登记出动班组）→ 结束处置（登记处置结果）；
3. 分别回读详情接口与列表接口，确认处置结论与接口返回一致，
   并验证「缺少处置结果时结束处置会被拦下」。

全部通过时退出码为 0；任何一项不一致都会打印差异并以非 0 退出。

### 分开启动（调试用）

后端：

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8000/api/health`

前端（开发模式，改动即时生效）：

```bash
cd frontend
npm install
npm run dev
```

前端默认监听 `http://127.0.0.1:5173/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8000`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 设施台账 | `facility` | 设施 | 设施编号、设施名称、设施类型 |
| 桥梁档案 | `bridge` | 桥梁 | 桥梁编号、桥梁名称、桥型结构 |
| 隧道管理 | `tunnel` | 隧道 | 隧道编号、隧道名称、隧道长度 |
| 路面状况 | `pavement` | 路面评价 | 评价编号、道路名称、评价路段 |
| 日常巡查 | `patrol` | 巡查记录 | 巡查编号、巡查路段、巡查人员 |
| 病害记录 | `disease` | 病害 | 病害编号、所属设施、病害类型 |
| 养护维修 | `repair` | 维修任务 | 任务编号、任务类型、维修对象 |
| 养护材料 | `material2` | 养护材料 | 材料编号、材料名称、规格型号 |
| 养护机械 | `machine` | 养护机械 | 机械编号、机械名称、规格型号 |
| 应急抢险 | `emergency` | 应急事件 | 事件编号、事件类型、发生地点、响应等级、出动班组、处置结果 |
| 除雪防汛 | `deicing` | 除雪防汛 | 作业编号、作业类型、作业路段 |
| 占道施工 | `occupy` | 占道施工 | 施工编号、施工位置、占用范围 |
| 绿化管护 | `greening` | 绿化管护 | 管护编号、管护区域、植被类型 |
| 交安设施 | `safety2` | 交安设施 | 设施编号、设施类型、所在路段 |
| 边坡挡墙 | `geom` | 边坡挡墙 | 边坡编号、所属路段、边坡类型 |
| 路灯管养 | `light` | 路灯设施 | 灯杆编号、所在路段、灯型类别 |
| 排水设施 | `drain` | 排水设施 | 设施编号、设施类型、所在路段 |
| 养护计划 | `plan` | 养护计划 | 计划编号、计划周期、计划类型 |
| 市民热线 | `complaint` | 热线记录 | 记录编号、来电人、来电内容 |
| 车辆超限 | `load` | 超限记录 | 记录编号、抓拍路段、车辆类型 |

## 约定

- 每个模块的前端页面在 `frontend/src/views/<模块>/index.vue`，后端接口在
  `backend/app/routers/<模块>.py`，业务规则在 `backend/app/services/<模块>.py`。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。
