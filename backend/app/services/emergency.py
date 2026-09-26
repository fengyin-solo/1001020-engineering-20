"""应急抢险业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "emergency"
REQUIRED_FIELDS = ["事件编号", "事件类型", "发生地点"]
LIST_FIELDS = ["事件编号", "事件类型", "发生地点", "影响范围", "响应等级", "出动班组", "处置结果", "事件状态"]
STATUS_ORDER = ["待响应", "响应中", "处置中", "已处置"]
ACTION_RULES = {"启动响应": "响应中", "调集力量": "处置中", "结束处置": "已处置"}
# 每个动作允许随报文一并写入的字段：调集力量登记出动班组，结束处置登记处置结果
ACTION_FIELDS = {"调集力量": ["出动班组"], "结束处置": ["处置结果"]}
NEGATIVE_ACTIONS = []


class EmergencyService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("事件编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        # 上报时把列表字段一并落库，响应等级、出动班组等不会在登记环节被丢掉
        for field in LIST_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip():
                entry[field] = value
        entry["status"] = STATUS_ORDER[0]
        entry["事件状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"应急事件 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于应急抢险可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        for field in ACTION_FIELDS.get(action, []):
            value = (values or {}).get(field)
            if value is not None and str(value).strip():
                entry[field] = str(value).strip()
        if action == "结束处置" and not str(entry.get("处置结果") or "").strip():
            return None, "结束处置前请先填写处置结果，处置结论不能为空"
        entry["status"] = target
        entry["事件状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"应急事件已{action}"
