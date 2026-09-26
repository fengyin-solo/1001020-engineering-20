#!/usr/bin/env python3
"""应急抢险三段链路场景驱动：事件上报 → 班组出动 → 处置结果。

通过后端接口把一条事件从「待响应」推进到「已处置」，并把全过程落盘成
可复现的记录文件（默认 .dev/emergency-seed.json），供 check-emergency-result.py 复核。

用法：
    python3 scripts/seed-emergency-scenario.py [--base-url http://127.0.0.1:8000] [--output PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / ".dev" / "emergency-seed.json"

# 场景事件：编号固定，便于复跑时按编号找回同一条记录；字段覆盖 事件编号/响应等级/出动班组。
SCENARIO = {
    "事件编号": "EMER-DEV-0001",
    "事件类型": "边坡塌方",
    "发生地点": "绕城高速 K45+300 路段",
    "影响范围": "应急车道封闭",
    "响应等级": "Ⅲ级（较大）",
    "出动班组": "道路应急一班",
    "处置结果": "塌方体已清运，边坡临时支护完成，道路恢复通行",
}


def request_json(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"[seed] 错误：接口请求失败 {url}（{exc.reason}），请确认后端已启动", file=sys.stderr)
        sys.exit(1)


def fail(message: str) -> None:
    print(f"[seed] 错误：{message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="应急抢险三段链路场景驱动")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端地址")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="场景记录输出路径")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    # 第 0 步：健康检查，确认后端在跑。
    status, health = request_json("GET", f"{base}/api/health")
    if status != 200 or not health.get("ok"):
        fail(f"后端健康检查未通过（HTTP {status}），请先启动后端服务")
    print(f"[seed] 后端健康检查通过：{health.get('app')}")

    # 第 1 步：事件上报。若同编号事件已存在（复跑场景），直接复用，保证脚本可重复执行。
    query = urllib.parse.urlencode({"keyword": SCENARIO["事件编号"]})
    status, page = request_json("GET", f"{base}/api/emergency?{query}")
    if status != 200:
        fail(f"按编号检索失败（HTTP {status}）")
    existing = [item for item in page.get("items", []) if item.get("事件编号") == SCENARIO["事件编号"]]
    if existing:
        entry = existing[0]
        print(f"[seed] 事件已存在（id={entry['id']}，状态={entry['status']}），跳过上报直接复用")
    else:
        payload = {key: SCENARIO[key] for key in ("事件编号", "事件类型", "发生地点", "影响范围", "响应等级")}
        status, result = request_json("POST", f"{base}/api/emergency", {"values": payload})
        if status != 200 or not result.get("ok"):
            fail(f"事件上报失败：{result.get('message', result)}")
        entry = result["entry"]
        print(f"[seed] ① 事件上报成功：{entry['事件编号']}（id={entry['id']}，状态={entry['status']}）")

    entry_id = int(entry["id"])
    record: dict[str, object] = {"entry_id": entry_id, "事件编号": SCENARIO["事件编号"], "steps": []}

    # 第 2 步：启动响应 → 调集力量（班组出动）→ 结束处置（处置结果）。
    # 已推进过的事件复跑时，动作接口会返回失败说明，这里按当前状态补齐剩余步骤。
    plan = [
        ("启动响应", {}),
        ("调集力量", {"出动班组": SCENARIO["出动班组"]}),
        ("结束处置", {"处置结果": SCENARIO["处置结果"]}),
    ]
    for action, extra in plan:
        values = {"action": action, **extra}
        status, result = request_json("POST", f"{base}/api/emergency/{entry_id}/actions", {"values": values})
        if status != 200 or not result.get("ok"):
            # 状态已越过该动作时允许跳过（复跑），否则视为失败。
            detail = result.get("message", result)
            print(f"[seed]   动作「{action}」未执行：{detail}")
            record["steps"].append({"action": action, "ok": False, "message": detail})
            continue
        entry = result["entry"]
        record["steps"].append({"action": action, "ok": True, "message": result["message"]})
        print(f"[seed] ② 动作「{action}」完成：状态={entry['status']}")

    # 第 3 步：回读最终状态，校验三段链路的结论字段。
    status, final = request_json("GET", f"{base}/api/emergency/{entry_id}")
    if status != 200:
        fail(f"回读事件 {entry_id} 失败（HTTP {status}）")
    checks = {
        "status": final.get("status") == "已处置",
        "事件状态": final.get("事件状态") == "已处置",
        "出动班组": final.get("出动班组") == SCENARIO["出动班组"],
        "处置结果": final.get("处置结果") == SCENARIO["处置结果"],
    }
    record["final"] = final
    record["checks"] = checks
    for name, ok in checks.items():
        print(f"[seed] ③ 校验 {name}: {'通过' if ok else '不一致 -> ' + str(final.get(name))}")
    if not all(checks.values()):
        fail("场景推进完成但结论字段与预期不一致，请检查后端状态流转")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[seed] 场景记录已写入 {output}")
    print(f"[seed] 完成：{SCENARIO['事件编号']} 已从待出动推进到已处置")


if __name__ == "__main__":
    main()
