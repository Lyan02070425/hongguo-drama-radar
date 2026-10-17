"""解析红果官网页面（纯函数，不发请求）。

榜单页对普通访客直接输出渲染好的 HTML。CSS 类名带随机后缀、会随前端发版变化，
所以这里优先认语义属性（aria-label、aria-labelledby、id），类名只按稳定的前缀片段匹配，
每个字段还有按文字规律兜底的办法。

详情页和搜索页的数据在内嵌的 `window._ROUTER_DATA` JSON 里。
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

from radar.core.text import clean_tags, norm_space, parse_count, to_float, to_int
from radar.core.timeutil import month_day_to_date, ts_to_date


class ParseError(Exception):
    pass


HEAT_RE = re.compile(r"(\d+(?:\.\d+)?\s*(?:万|亿)?)\s*热度")
RATING_RE = re.compile(r"评分\s*(\d+(?:\.\d+)?)")
FAV_RE = re.compile(r"(\d+(?:\.\d+)?\s*(?:万|亿)?)\s*收藏")
LIKE_RE = re.compile(r"(\d+(?:\.\d+)?\s*(?:万|亿)?)\s*点赞")
UPDATED_RE = re.compile(r"(\d{1,2})月(\d{1,2})日已更新")

_VOID = {"img", "source", "br", "hr", "input", "meta", "link", "wbr", "area", "base", "col", "embed", "param", "track"}
_TEXT_ROLES = {"title", "badge", "metrics", "eng_li", "category", "desc", "page_link"}


class _RankPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: List[Dict[str, Any]] = []
        self.board_label: Optional[str] = None
        self.pages: set = set()
        self.current_page: Optional[int] = None
        self._regions: List[list] = []  # [tag, role, depth, text_parts, attrs]
        self._item: Optional[Dict[str, Any]] = None
        self._item_text: List[str] = []

    def _has(self, role: str) -> bool:
        return any(r[1] == role for r in self._regions)

    def _role_for(self, tag: str, a: Dict[str, str]) -> Optional[str]:
        cls = a.get("class") or ""
        label = a.get("aria-label") or ""
        if tag == "nav" and "分页" in label:
            return "pagination"
        if tag in ("a", "span") and self._has("pagination"):
            return "page_link"
        if tag == "ol" and label and self._item is None:
            return "list"
        if tag == "article" and (a.get("aria-labelledby") or "").startswith("rank-title-"):
            return "article"
        if self._item is None:
            return None
        if (a.get("id") or "").startswith("rank-title-"):
            return "title"
        if tag == "span" and "badge-number" in cls:
            return "badge"
        if tag == "p" and "metrics" in cls:
            return "metrics"
        if tag == "ul" and ("互动" in label or "engagement" in cls):
            return "engagement"
        if tag == "li" and self._has("engagement"):
            return "eng_li"
        if tag == "p" and "categor" in cls:
            return "categories"
        if tag == "span" and self._has("categories"):
            return "category"
        if tag == "p" and "description" in cls:
            return "desc"
        if tag == "div" and "episode" in cls:
            return "episodes"
        if tag == "a" and "cover" in cls:
            return "cover"
        return None

    def handle_starttag(self, tag: str, attrs) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag in _VOID:
            if tag == "img" and self._item is not None and self._has("cover"):
                self._item.setdefault("cover", a.get("src") or None)
            return
        for region in self._regions:
            if region[0] == tag:
                region[2] += 1
        role = self._role_for(tag, a)
        if not role:
            return
        self._regions.append([tag, role, 1, [], a])
        if role == "list" and not self.board_label:
            self.board_label = a.get("aria-label")
        elif role == "article":
            self._item = {"id": a["aria-labelledby"][len("rank-title-"):], "tags": [], "status_tags": []}
            self._item_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID:
            return
        closing = []
        for region in self._regions:
            if region[0] == tag:
                region[2] -= 1
                if region[2] == 0:
                    closing.append(region)
        for region in reversed(closing):
            self._regions.remove(region)
            self._close(region)

    def handle_data(self, data: str) -> None:
        if self._has("episodes"):
            return
        if self._item is not None:
            self._item_text.append(data)
        for region in reversed(self._regions):
            if region[1] in _TEXT_ROLES:
                region[3].append(data)
                return

    def _close(self, region: list) -> None:
        _tag, role, _depth, parts, attrs = region
        text = norm_space("".join(parts))
        item = self._item
        if role == "page_link":
            if text.isdigit():
                self.pages.add(int(text))
                if attrs.get("aria-current") == "page":
                    self.current_page = int(text)
            return
        if role == "article":
            if item is not None:
                self._finish(item)
            self._item = None
            return
        if item is None:
            return
        if role == "title":
            item["title"] = text
        elif role == "badge" and text.isdigit():
            item["rank"] = int(text)
        elif role == "metrics":
            match = HEAT_RE.search(text)
            if match:
                item["heat"] = parse_count(match.group(1))
        elif role == "eng_li":
            cls = attrs.get("class") or ""
            rating = RATING_RE.search(text)
            if rating:
                item["rating"] = float(rating.group(1))
            elif "收藏" in text:
                item["fav"] = parse_count(FAV_RE.search(text).group(1)) if FAV_RE.search(text) else None
            elif "点赞" in text:
                item["like"] = parse_count(LIKE_RE.search(text).group(1)) if LIKE_RE.search(text) else None
            elif text and ("status" in cls or not re.search(r"\d", text)):
                item["status_tags"].append(text)
        elif role == "category" and text:
            item["tags"].append(text)
        elif role == "desc":
            item["synopsis"] = text

    def _finish(self, item: Dict[str, Any]) -> None:
        # 按文字规律兜底：前端改版、类名失效时也能拿到核心字段
        full = norm_space("".join(self._item_text))
        if item.get("heat") is None and HEAT_RE.search(full):
            item["heat"] = parse_count(HEAT_RE.search(full).group(1))
        if item.get("fav") is None and FAV_RE.search(full):
            item["fav"] = parse_count(FAV_RE.search(full).group(1))
        if item.get("like") is None and LIKE_RE.search(full):
            item["like"] = parse_count(LIKE_RE.search(full).group(1))
        if item.get("rating") is None and RATING_RE.search(full):
            item["rating"] = float(RATING_RE.search(full).group(1))
        item["tags"] = clean_tags(item["tags"])
        if item.get("title"):
            self.items.append(item)


def parse_rank_page(html: str, ref_date: str) -> Dict[str, Any]:
    """返回 {"label", "label_date", "items", "pages", "current_page"}。

    items 里每部剧：id、rank、title、heat（取整到万）、rating、fav、like、tags（题材）、
    status_tags（新剧/爆剧等）、synopsis、cover。
    """
    parser = _RankPageParser()
    parser.feed(html)
    parser.close()
    if not parser.items:
        raise ParseError("榜单页里没有找到任何作品，页面结构可能变了")
    updated = UPDATED_RE.search(html)
    label_date = month_day_to_date(int(updated.group(1)), int(updated.group(2)), ref_date) if updated else None
    return {
        "label": parser.board_label,
        "label_date": label_date,
        "items": parser.items,
        "pages": max(parser.pages) if parser.pages else None,
        "current_page": parser.current_page,
    }


def parse_router_data(html: str) -> Dict[str, Any]:
    marker = "_ROUTER_DATA"
    start = html.find(marker)
    if start < 0:
        raise ParseError("页面里没有 _ROUTER_DATA")
    eq = html.find("=", start)
    brace = html.find("{", eq)
    if eq < 0 or brace < 0:
        raise ParseError("_ROUTER_DATA 格式不对")
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[brace:])
    except json.JSONDecodeError as exc:
        raise ParseError(f"_ROUTER_DATA 不是合法 JSON：{exc}") from exc
    return obj.get("loaderData") or {}


def _find_loader(loader: Dict[str, Any], prefix: str, key: str) -> Dict[str, Any]:
    for name, value in loader.items():
        if name.startswith(prefix) and isinstance(value, dict) and key in value:
            return value
    raise ParseError(f"_ROUTER_DATA 里没有 {prefix}*.{key}")


def parse_detail_page(html: str, tz_offset: int = 8) -> Dict[str, Any]:
    """详情页：精确热度、收藏、点赞、评分人数、评论数、集数、上线时间。

    评论内容和评论者信息不保存。
    """
    page = _find_loader(parse_router_data(html), "detail", "seriesDetail")
    detail = page.get("seriesDetail") or {}
    social = page.get("seriesSocialInfo") or {}
    if not detail.get("series_id"):
        raise ParseError("详情页没有 series_id，作品可能已下架")
    ep_info = detail.get("series_episode_info") or {}
    cast = []
    for person in detail.get("celebrities") or []:
        if isinstance(person, dict):
            name = person.get("name") or person.get("nickname") or person.get("celebrity_name")
            if name:
                cast.append(str(name))
    return {
        "id": str(detail["series_id"]),
        "title": detail.get("series_name"),
        "episodes": to_int(detail.get("episode_cnt")),
        "episodes_total": to_int(ep_info.get("episode_total_cnt")),
        "status_code": to_int(ep_info.get("series_status")),
        "first_visible": ts_to_date(detail.get("first_visible_time"), tz_offset),
        "detail_tags": clean_tags(detail.get("tags")),
        "pay_type": to_int(detail.get("pay_type")),
        "cast": cast,
        "synopsis": detail.get("series_intro"),
        "cover": detail.get("series_cover"),
        "heat": to_int((social.get("hot_score_data") or {}).get("score")),
        "fav": to_int(social.get("series_favorite_count")),
        "like": to_int(social.get("series_like_count")),
        "rating": to_float(social.get("rating")),
        "rating_count": to_int(social.get("rating_count")),
        "review_count": to_int((social.get("reviews") or {}).get("total_count")),
        "rank_label": social.get("rank_label"),
    }


def parse_search_page(html: str) -> List[Dict[str, str]]:
    """搜索结果里的短剧（doc_type == 23）：[{"id", "title"}]。"""
    page = _find_loader(parse_router_data(html), "search", "searchList")
    out = []
    for entry in page.get("searchList") or []:
        if entry.get("doc_type") == 23 and entry.get("keyword") and entry.get("name"):
            out.append({"id": str(entry["keyword"]), "title": str(entry["name"])})
    return out


_ID_PATTERNS = [re.compile(r"series_id=(\d+)"), re.compile(r"/player/(\d+)"), re.compile(r"^(\d{15,})$")]


def extract_id(entry: str) -> Optional[str]:
    for pattern in _ID_PATTERNS:
        match = pattern.search(entry.strip())
        if match:
            return match.group(1)
    return None
