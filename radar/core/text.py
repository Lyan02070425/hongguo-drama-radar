"""与平台无关的文本解析：中文计数（万/亿）、改编来源。"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

_COUNT_RE = re.compile(r"([\d]+(?:\.\d+)?)\s*(万|亿|w|W)?")


def parse_count(text: Any) -> Optional[int]:
    """「5462万」→ 54620000，「1.2亿」→ 120000000，「4347」→ 4347。"""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    match = _COUNT_RE.search(str(text).replace(",", ""))
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    if unit in ("万", "w", "W"):
        value *= 10_000
    elif unit == "亿":
        value *= 100_000_000
    return int(round(value))


def to_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def clean_tags(tags) -> list:
    """去掉标签里的控制字符和纯数字的内部编号（官网偶尔会混进「205」这种值），并去重。"""
    out = []
    for tag in tags or []:
        text = _CONTROL_RE.sub("", str(tag)).strip()
        if text and not text.isdigit() and text not in out:
            out.append(text)
    return out


def norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


_ADAPT_RE = re.compile(
    r"改编自\s*(?P<platform>[^《》，。,\s]{0,12}?)\s*《(?P<work>[^》]{1,60})》"
    r"(?:[^。]{0,6}?作者[:：]?\s*(?P<author>[^\s，。,；;！!]{1,30}))?"
)

_PLATFORMS = [
    ("番茄", "番茄小说"),
    ("七猫", "七猫小说"),
    ("起点", "起点中文网"),
    ("晋江", "晋江文学城"),
    ("掌阅", "掌阅"),
    ("漫画", "漫画"),
]


def parse_adaptation(synopsis: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
    """从简介里识别「改编自番茄短篇小说《…》，作者…」这类说明。"""
    if not synopsis:
        return None
    match = _ADAPT_RE.search(synopsis)
    if not match:
        return None
    raw = match.group("platform") or ""
    platform = "小说（未注明平台）"
    for key, label in _PLATFORMS:
        if key in raw:
            platform = label
            break
    else:
        if raw and "小说" not in raw:
            platform = raw
    return {
        "platform": platform,
        "platform_raw": raw or None,
        "work": match.group("work"),
        "author": match.group("author"),
    }
