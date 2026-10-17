"""批次日期与日期运算。所有日期在数据里都用 ISO 字符串（YYYY-MM-DD）。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp(now: Optional[datetime] = None) -> str:
    return (now or now_utc()).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_now(offset_hours: int, now: Optional[datetime] = None) -> datetime:
    return (now or now_utc()).astimezone(timezone(timedelta(hours=offset_hours)))


def batch_date(offset_hours: int = 8, cutoff_hour: int = 9, now: Optional[datetime] = None) -> str:
    """这次抓到的数据属于哪一天的批次。

    官方榜单每天上午批量刷新一次。截止钟点之前抓到的仍是前一天的数据；
    GitHub 的定时任务经常推迟几个小时，晚上的任务可能拖到第二天凌晨，靠这条规则才不会记错日期。
    """
    local = local_now(offset_hours, now)
    day = local.date()
    if local.hour < cutoff_hour:
        day -= timedelta(days=1)
    return day.isoformat()


def to_date(value: str) -> date:
    return date.fromisoformat(value)


def days_between(earlier: str, later: str) -> int:
    return (to_date(later) - to_date(earlier)).days


def shift(day: str, days: int) -> str:
    return (to_date(day) + timedelta(days=days)).isoformat()


def ts_to_date(ts, offset_hours: int = 8) -> Optional[str]:
    """Unix 时间戳（秒，可以是字符串）转为当地日期。"""
    try:
        value = int(ts)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return datetime.fromtimestamp(value, timezone(timedelta(hours=offset_hours))).date().isoformat()


def month_day_to_date(month: int, day: int, ref: str) -> Optional[str]:
    """把页面上的「10月17日」补全年份：取离参考日期最近的那一年。"""
    ref_d = to_date(ref)
    try:
        candidate = date(ref_d.year, month, day)
    except ValueError:
        return None
    if candidate - ref_d > timedelta(days=180):
        candidate = date(ref_d.year - 1, month, day)
    elif ref_d - candidate > timedelta(days=180):
        candidate = date(ref_d.year + 1, month, day)
    return candidate.isoformat()
