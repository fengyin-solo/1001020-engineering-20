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
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/          每个业务模块一组接口
│   ├── app/services/         业务规则与状态流转
│   └── app/store.py          内存数据仓库与示例数据
├── scripts/                  本地链路工程化脚本
│   ├── dev-up.sh             一条命令：预检+构建+拉起前后端+写场景数据+复核
│   ├── dev-down.sh           停止本地前后端
│   ├── check-local-env.sh    依赖与端口预检（缺失自动装、占用明确报错）
│   ├── seed-emergency-scenario.py   应急抢险三段链路场景驱动
│   └── check-emergency-result.py    处置结论与接口返回一致性复核
├── .gitignore
└── docker-compose.yml
```

## 启动

### 一条命令（推荐）

```bash
make dev
```

依次完成：本地环境预检 → 前端构建（vue-tsc 类型检查 + vite build）→ 拉起前后端 →
写入应急抢险场景数据（事件上报 → 班组出动 → 处置结果，从待出动推进到已处置）→
复核处置结论与接口返回一致。

- 前端：`http://127.0.0.1:5173/emergency`，后端：`http://127.0.0.1:8000/api/emergency`
- 依赖缺失（venv、node_modules）会自动安装；python3/node 未安装或端口被占用会直接报错并给出处理方式
- 后端是内存数据仓库，每次 `make dev` 重启后示例数据自动回到最新口径，不需要手工同步数据库
- 换端口：`BACKEND_PORT=8001 FRONTEND_PORT=5174 make dev`
- 快速重启（跳过前端构建）：`make dev-fast`
- 停止服务：`make dev-down`

### 应急抢险三段链路的单独操作

```bash
make seed          # 只重跑场景：事件上报 → 班组出动 → 处置结果
make check-result  # 处置完成后复核：处置结论与接口返回是否一致
scripts/check-emergency-result.py --new   # 重跑场景并复核（可独立复现）
```

场景记录写在 `.dev/emergency-seed.json`，复核脚本以它为准对照接口返回。

### 手工分步启动

```bash
# 后端（虚拟环境损坏时会自动重建）
cd backend && ./run.sh
# 前端
cd frontend && npm install && npm run dev
```

健康检查：`curl http://127.0.0.1:8000/api/health`

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
| 应急抢险 | `emergency` | 应急事件 | 事件编号、事件类型、发生地点 |
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
- 登记与动作的提交体统一放在 `values` 里（`{ "values": { ... } }`），与后端 `EntryPayload` 对齐；
  应急抢险的动作会随附字段：`调集力量` 带 `出动班组`，`结束处置` 带 `处置结果`。
- 应急抢险状态只能按 待响应 → 响应中 → 处置中 → 已处置 顺序前进，已处置的事件不能再执行动作。
