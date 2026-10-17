"""分析器共用的小工具。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def percentiles(values: Dict[str, Optional[float]]) -> Dict[str, float]:
    """每个值在这一组里的百分位（0~1，并列取平均名次）。值为 None 的不参与。"""
    present = [(k, v) for k, v in values.items() if v is not None]
    n = len(present)
    if n == 0:
        return {}
    if n == 1:
        return {present[0][0]: 1.0}
    present.sort(key=lambda kv: kv[1])
    out: Dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and present[j + 1][1] == present[i][1]:
            j += 1
        pct = ((i + j) / 2) / (n - 1)
        for k in range(i, j + 1):
            out[present[k][0]] = pct
        i = j + 1
    return out


def fmt_count(value: Optional[float], signed: bool = False) -> str:
    """报告里用的中文计数：12345678 → 1234.6万。"""
    if value is None:
        return "—"
    sign = ""
    if signed:
        sign = "+" if value > 0 else ("-" if value < 0 else "")
        value = abs(value)
    if abs(value) >= 100_000_000:
        text = f"{value / 100_000_000:.2f}亿"
    elif abs(value) >= 10_000:
        text = f"{value / 10_000:.1f}万"
    else:
        text = f"{value:.0f}"
    return sign + text


def top(rows: Iterable[Dict[str, Any]], key: str, n: int, reverse: bool = True, positive_only: bool = False) -> List[Dict[str, Any]]:
    items = [r for r in rows if r.get(key) is not None]
    if positive_only:
        items = [r for r in items if (r[key] > 0 if reverse else r[key] < 0)]
    items.sort(key=lambda r: r[key], reverse=reverse)
    return items[:n]


def pick(row: Dict[str, Any], keys: Iterable[str]) -> Dict[str, Any]:
    return {k: row.get(k) for k in keys if row.get(k) is not None}


def ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or not b:
        return None
    return a / b


def rounded(value: Optional[float], digits: int = 4) -> Optional[float]:
    return None if value is None else round(value, digits)
