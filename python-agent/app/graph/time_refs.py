"""相对时间解析：把「昨天收到/上周买的」转成绝对日期区间。

只在 Python 侧做，工具只收 yyyy-MM-dd；解析不出来就不传，交给 Agent 追问。
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")


def _today() -> date:
    return datetime.now(TZ).date()


def _month_range(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    return first, next_first - timedelta(days=1)


def parse_time_reference(text: str, today: date | None = None) -> dict[str, str] | None:
    """返回 {field, from, to, label}；field 为 created 或 delivered。"""
    if not text:
        return None
    base = today or _today()
    field = "delivered" if any(word in text for word in ("收到", "签收", "到货")) else "created"

    def result(start: date, end: date, label: str) -> dict[str, str]:
        return {"field": field, "from": start.isoformat(), "to": end.isoformat(), "label": label}

    if "大前天" in text:
        day = base - timedelta(days=3)
        return result(day, day, "大前天")
    if "前天" in text:
        day = base - timedelta(days=2)
        return result(day, day, "前天")
    if "昨天" in text:
        day = base - timedelta(days=1)
        return result(day, day, "昨天")
    if "今天" in text:
        return result(base, base, "今天")

    week_start = base - timedelta(days=base.weekday())
    if "上周" in text:
        start = week_start - timedelta(days=7)
        return result(start, start + timedelta(days=6), "上周")
    if "这周" in text or "本周" in text:
        return result(week_start, base, "本周")

    if "上个月" in text:
        year, month = (base.year, base.month - 1) if base.month > 1 else (base.year - 1, 12)
        start, end = _month_range(year, month)
        return result(start, end, "上个月")
    if "这个月" in text or "本月" in text:
        start, _ = _month_range(base.year, base.month)
        return result(start, base, "本月")

    recent = re.search(r"最近\s*(\d+)\s*天", text)
    if recent:
        days = max(1, min(365, int(recent.group(1))))
        return result(base - timedelta(days=days - 1), base, f"最近{days}天")

    days_ago = re.search(r"(\d+)\s*天前", text)
    if days_ago:
        days = max(0, min(365, int(days_ago.group(1))))
        day = base - timedelta(days=days)
        return result(day, day, f"{days}天前")

    if any(word in text for word in ("刚买", "刚刚", "刚才", "刚下单")):
        return result(base, base, "今天")

    return None
