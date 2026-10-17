"""按依赖顺序运行分析器，把结果写成看板读取的 JSON / CSV。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List

from radar.analysis.history import History
from radar.core.config import Config
from radar.core.registry import ANALYZERS
from radar.core.store import write_json
from radar.sources.base import Source


@dataclass
class Context:
    source: Source
    history: History
    config: Config
    results: Dict[str, Any] = field(default_factory=dict)  # 分析器名 → 主输出
    shared: Dict[str, Any] = field(default_factory=dict)   # 分析器之间传递的中间结果（不写文件）
    files: Dict[str, str] = field(default_factory=dict)    # 额外输出：相对路径 → 文本内容

    @property
    def params(self) -> Dict[str, Any]:
        return self.config.analysis

    def emit(self, relpath: str, content: str) -> None:
        self.files[relpath] = content

    def board_label(self, board: str) -> str:
        return self.source.board_labels().get(board) or self.history.board_label(board)


def _order(names: List[str]) -> List[str]:
    """拓扑排序：保证每个分析器在它依赖的分析器之后运行。"""
    ordered: List[str] = []
    visiting: set = set()

    def visit(name: str) -> None:
        if name in ordered:
            return
        if name in visiting:
            raise ValueError(f"分析器依赖出现循环：{name}")
        visiting.add(name)
        for dep in ANALYZERS.get(name).meta.get("depends", []):
            visit(dep)
        visiting.discard(name)
        ordered.append(name)

    for name in sorted(names, key=lambda n: (ANALYZERS.get(n).meta.get("order", 50), n)):
        visit(name)
    return ordered


def run_analyzers(ctx: Context, out_dir: Path, log: Callable[[str], None] = print) -> Dict[str, Any]:
    disabled = set(ctx.params.get("disabled", []))
    names = [n for n in ANALYZERS.names() if n not in disabled]
    for name in _order(names):
        entry = ANALYZERS.get(name)
        result = entry.obj(ctx)
        ctx.results[name] = result
        if result is not None and entry.meta.get("write", True):
            write_json(out_dir / f"{name}.json", result, compact=True, sort_keys=False)  # 保留榜单等的顺序
    for relpath, content in ctx.files.items():
        path = out_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        encoding = "utf-8-sig" if relpath.endswith(".csv") else "utf-8"  # 带 BOM，Excel 打开中文不乱码
        path.write_text(content, encoding=encoding)
    log(f"  分析完成：{len(ctx.results)} 个分析器，{len(ctx.files)} 个附加文件")
    return ctx.results


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
