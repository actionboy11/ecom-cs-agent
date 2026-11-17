"""评测时钟：生产用真实时间，设置 EVAL_TODAY 后固定到指定日期。"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.config import settings

TZ = ZoneInfo("Asia/Shanghai")


def _fixed() -> date | None:
    raw = (settings.eval_today or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def today() -> date:
    fixed = _fixed()
    return fixed if fixed else datetime.now(TZ).date()


def now(tz=UTC) -> datetime:
    fixed = _fixed()
    if fixed:
        return datetime.combine(fixed, time(12, 0), tzinfo=tz)
    return datetime.now(tz)
