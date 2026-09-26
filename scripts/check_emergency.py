#!/usr/bin/env python3
"""应急抢险链路检查脚本：确认示例数据、状态流转与处置结论和接口返回一致。

用法：
    python3 scripts/check_emergency.py            # 默认打 http://127.0.0.1:8000
    API_BASE=http://127.0.0.1:8001 python3 scripts/check_emergency.py

脚本只依赖标准库，可重复执行：每次运行都会新登记一条 EMER-CHK 事件，
走一遍 上报 → 启动响应 → 调集力量 → 结束处置，再回读接口逐字段核对。
任何一步不一致都会以非 0 退出码结束，并打印差异。
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")

FAILURES: list[str] = []
CHECKS = 0


def request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    url = f"{API_BASE}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"detail": body}
    except urllib.error.URLError as exc:
        print(f"✗ 无法连接后端 {API_BASE}：{exc.reason}")
        print("  请先执行 make up 拉起前后端，再运行本检查脚本。")
        sys.exit(2)


def check(label: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"✓ {label}")
    else:
        print(f"✗ {label}" + (f" —— {detail}" if detail else ""))
        FAILURES.append(label)


def main() -> int:
    print(f"应急抢险链路检查（目标 {API_BASE}）\n")

    # 1. 服务可用性
    status, health = request("GET", "/api/health")
    check("后端健康检查 /api/health", status == 200 and health.get("ok") is True,
          f"HTTP {status} {health}")

    # 2. 示例数据：从待响应到已处置全生命周期都在，且关键字段不为空
    _, page = request("GET", "/api/emergency?size=200")
    items = page.get("items", [])
    statuses = {row.get("status") for row in items}
    for expected in ["待响应", "响应中", "处置中", "已处置"]:
        check(f"示例数据覆盖状态「{expected}」", expected in statuses,
              f"当前只有 {sorted(str(s) for s in statuses)}")
    missing_fields = [
        f"{row.get('事件编号', '?')} 缺 {field}"
        for row in items
        for field in ["事件编号", "响应等级", "出动班组"]
        if not str(row.get(field) or "").strip()
    ]
    check("示例数据的事件编号/响应等级/出动班组均已填写", not missing_fields,
          "；".join(missing_fields))
    disposed = [row for row in items if row.get("status") == "已处置"]
    check("已处置事件带有处置结果",
          bool(disposed) and all(str(row.get("处置结果") or "").strip() for row in disposed),
          "已处置事件的处置结果为空")

    # 3. 全链路演练：上报 → 启动响应 → 调集力量 → 结束处置
    event_no = f"EMER-CHK-{time.strftime('%Y%m%d%H%M%S')}"
    team = "应急抢险二班"
    conclusion = "现场处置完毕，道路恢复通行（检查脚本写入）"

    _, created = request("POST", "/api/emergency", {"values": {
        "事件编号": event_no,
        "事件类型": "检查脚本演练事件",
        "发生地点": "联调演练路段",
        "影响范围": "无实际影响",
        "响应等级": "Ⅲ级",
    }})
    entry = created.get("entry") or {}
    entry_id = entry.get("id")
    check("事件上报成功并返回编号", created.get("ok") is True and entry_id is not None,
          str(created))
    check("上报时写入的响应等级被保留", entry.get("响应等级") == "Ⅲ级",
          f"实际为 {entry.get('响应等级')!r}")

    def act(action: str, extra: dict | None = None) -> dict:
        values = {"action": action}
        values.update(extra or {})
        _, result = request("POST", f"/api/emergency/{entry_id}/actions", {"values": values})
        return result

    result = act("启动响应")
    check("启动响应后状态为响应中",
          result.get("ok") is True and (result.get("entry") or {}).get("status") == "响应中",
          str(result.get("message")))

    result = act("调集力量", {"出动班组": team})
    check("调集力量后状态为处置中且记下出动班组",
          result.get("ok") is True
          and (result.get("entry") or {}).get("status") == "处置中"
          and (result.get("entry") or {}).get("出动班组") == team,
          str(result.get("message")))

    # 结束处置不带处置结果必须被拦下，且给出可读原因
    rejected = act("结束处置")
    check("缺少处置结果时结束处置被拦下",
          rejected.get("ok") is False and "处置结果" in str(rejected.get("message")),
          str(rejected))

    result = act("结束处置", {"处置结果": conclusion})
    check("结束处置后状态为已处置",
          result.get("ok") is True and (result.get("entry") or {}).get("status") == "已处置",
          str(result.get("message")))

    # 4. 回读核对：详情与列表两条接口返回的处置结论必须一致
    _, detail = request("GET", f"/api/emergency/{entry_id}")
    check("详情接口返回的处置结果与提交一致", detail.get("处置结果") == conclusion,
          f"接口返回 {detail.get('处置结果')!r}")
    check("详情接口返回的事件状态为已处置", detail.get("事件状态") == "已处置",
          f"接口返回 {detail.get('事件状态')!r}")
    check("详情接口返回的出动班组与调集时一致", detail.get("出动班组") == team,
          f"接口返回 {detail.get('出动班组')!r}")

    _, listing = request("GET", f"/api/emergency?keyword={event_no}")
    listed = (listing.get("items") or [{}])[0]
    check("列表接口按事件编号可检索到该事件", listed.get("事件编号") == event_no,
          str(listing))
    check("列表与详情返回的处置结论一致", listed.get("处置结果") == detail.get("处置结果"),
          f"列表 {listed.get('处置结果')!r} / 详情 {detail.get('处置结果')!r}")

    print()
    if FAILURES:
        print(f"检查未通过：{len(FAILURES)}/{CHECKS} 项失败：{'、'.join(FAILURES)}")
        return 1
    print(f"全部 {CHECKS} 项检查通过：处置结论与接口返回一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
