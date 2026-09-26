"""应急抢险业务规则：状态流转、字段校验与筛选口径都收在这里。

链路三段：事件上报（登记）→ 班组出动（调集力量）→ 处置结果（结束处置）。
状态只能按 待响应 → 响应中 → 处置中 → 已处置 顺序前进，不允许跳步或重复处置。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "emergency"
# 事件上报时必须填写的字段；响应等级决定后续出动力量的规模，所以登记时就要明确。
REQUIRED_FIELDS = ["事件编号", "事件类型", "发生地点", "响应等级"]
# 允许落库的业务字段，前端多传的未知字段不静默写入。
KNOWN_FIELDS = REQUIRED_FIELDS + ["影响范围", "出动班组", "处置结果"]
# 登记时可缺省的字段及默认值：新事件还没出动班组，也没有处置结果。
DEFAULT_VALUES = {"影响范围": "—", "出动班组": "待出动", "处置结果": "—"}
STATUS_ORDER = ["待响应", "响应中", "处置中", "已处置"]
# 动作对应的目标状态下标；「出动班组」「处置结果」在对应动作里随表单提交。
ACTION_TARGET = {"启动响应": 1, "调集力量": 2, "结束处置": 3}
PREV_ACTION = {1: "启动响应", 2: "调集力量", 3: "结束处置"}


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
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in KNOWN_FIELDS:
            value = str(values.get(field) or "").strip()
            entry[field] = value or DEFAULT_VALUES.get(field, "")
        entry["status"] = STATUS_ORDER[0]
        # 「事件状态」展示列与内部状态保持一致，避免列表里两套状态对不上。
        entry["事件状态"] = entry["status"]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"应急事件 {entry_id} 不存在或已归档"
        if action not in ACTION_TARGET:
            return None, f"动作「{action}」不属于应急抢险可执行范围"

        target = ACTION_TARGET[action]
        current = STATUS_ORDER.index(entry["status"]) if entry.get("status") in STATUS_ORDER else -1
        if current == len(STATUS_ORDER) - 1:
            return None, "应急事件已处置结束，不能重复执行动作"
        if target != current + 1:
            return None, f"当前状态为「{entry['status']}」，请先执行「{PREV_ACTION[current + 1]}」，不能跳到「{action}」"

        if action == "调集力量":
            crew = str(values.get("出动班组") or "").strip()
            if not crew or crew == DEFAULT_VALUES["出动班组"]:
                return None, "调集力量必须明确出动班组，请填写实际出动的班组"
            entry["出动班组"] = crew
        elif action == "结束处置":
            result = str(values.get("处置结果") or "").strip()
            if not result or result == DEFAULT_VALUES["处置结果"]:
                return None, "结束处置必须填写处置结果，请说明现场处置结论"
            entry["处置结果"] = result

        entry["status"] = STATUS_ORDER[target]
        entry["事件状态"] = entry["status"]
        entry["pending"] = target != len(STATUS_ORDER) - 1
        return entry, f"应急事件已{action}"
