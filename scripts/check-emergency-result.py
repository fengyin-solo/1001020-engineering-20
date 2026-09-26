#!/usr/bin/env python3
"""处置结论复核：确认接口返回与场景记录里的处置结论一致，且事件确实已闭环。

默认读取 .dev/emergency-seed.json（由 seed-emergency-scenario.py 生成）；
加 --new 时自行跑一遍三段链路再复核，可独立复现。

用法：
    python3 scripts/check-emergency-result.py [--record PATH] [--new]
退出码：全部一致返回 0，任一不一致返回 1。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECORD = ROOT / ".dev" / "emergency-seed.json"
EXPECTED_STATUS = "已处置"


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
        print(f"[check] 错误：接口请求失败 {url}（{exc.reason}）", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="应急抢险处置结论复核")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端地址")
    parser.add_argument("--record", default=str(DEFAULT_RECORD), help="场景记录路径")
    parser.add_argument("--new", action="store_true", help="先重新跑一遍三段链路再复核")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    record_path = Path(args.record)

    if args.new:
        print(f"[check] --new：先驱动一遍三段链路（记录写入 {record_path}）")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "seed-emergency-scenario.py"),
             "--base-url", base, "--output", str(record_path)],
            check=True,
        )

    if not record_path.exists():
        print(f"[check] 错误：场景记录不存在（{record_path}），请先运行 seed-emergency-scenario.py 或加 --new", file=sys.stderr)
        sys.exit(1)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    entry_id = int(record["entry_id"])
    print(f"[check] 复核事件 id={entry_id}（{record['事件编号']}），记录文件：{record_path}")

    failures: list[str] = []

    # 1) 明细接口：状态、事件状态、出动班组、处置结果都要与场景记录一致。
    status, detail = request_json("GET", f"{base}/api/emergency/{entry_id}")
    if status != 200:
        failures.append(f"明细接口返回 HTTP {status}，事件可能已被清空")
        detail = {}
    recorded_final = record.get("final", {})
    for field in ("status", "事件状态", "出动班组", "处置结果", "响应等级", "事件编号"):
        expected = recorded_final.get(field)
        actual = detail.get(field)
        if actual != expected:
            failures.append(f"明细接口字段「{field}」不一致：接口={actual!r}，场景记录={expected!r}")
    if detail.get("status") != EXPECTED_STATUS:
        failures.append(f"明细接口状态不是「{EXPECTED_STATUS}」，处置未闭环")

    # 2) 列表接口：按已处置状态过滤必须能查到该事件，且结论字段一致。
    query = urllib.parse.urlencode({"status": EXPECTED_STATUS, "size": 200})
    status, page = request_json("GET", f"{base}/api/emergency?{query}")
    if status != 200:
        failures.append(f"列表接口返回 HTTP {status}")
        page = {"items": []}
    listed = [item for item in page.get("items", []) if int(item.get("id", 0)) == entry_id]
    if not listed:
        failures.append(f"列表接口按「{EXPECTED_STATUS}」过滤查不到事件 {entry_id}，处置结论未生效")
    else:
        row = listed[0]
        for field in ("事件状态", "出动班组", "处置结果"):
            if row.get(field) != detail.get(field):
                failures.append(f"列表接口字段「{field}」={row.get(field)!r} 与明细接口={detail.get(field)!r} 不一致")

    # 3) 闭环保护：已处置事件再执行任何动作都应被拒绝（不能重复处置）。
    payload = {"values": {"action": "结束处置", "处置结果": "重复提交的处置结论"}}
    status, result = request_json("POST", f"{base}/api/emergency/{entry_id}/actions", payload)
    if result.get("ok"):
        failures.append("已处置事件仍能再次执行「结束处置」，闭环保护失效")
    else:
        print(f"[check] 闭环保护生效：重复动作被拒绝（{result.get('message')}）")

    if failures:
        print("[check] 复核未通过：", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        sys.exit(1)

    print("[check] 复核通过：处置结论与接口返回一致，事件已闭环")
    print(f"[check]   状态：{detail.get('status')}")
    print(f"[check]   出动班组：{detail.get('出动班组')}")
    print(f"[check]   处置结果：{detail.get('处置结果')}")


if __name__ == "__main__":
    main()
