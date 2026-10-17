"""插件注册表。数据源、分析器、报告器都通过装饰器注册，新增功能不用改主流程。

    from radar.core.registry import ANALYZERS

    @ANALYZERS.register("my_metric", depends=["metrics"])
    def my_metric(ctx):
        ...
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List


@dataclass
class Entry:
    name: str
    obj: Any
    meta: Dict[str, Any] = field(default_factory=dict)


class Registry:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._entries: Dict[str, Entry] = {}

    def register(self, name: str, **meta: Any) -> Callable[[Any], Any]:
        def decorator(obj: Any) -> Any:
            if name in self._entries:
                raise ValueError(f"{self.kind} '{name}' 重复注册")
            self._entries[name] = Entry(name, obj, meta)
            return obj

        return decorator

    def get(self, name: str) -> Entry:
        if name not in self._entries:
            raise KeyError(f"未知的 {self.kind}：{name}（已注册：{', '.join(self.names()) or '无'}）")
        return self._entries[name]

    def names(self) -> List[str]:
        return list(self._entries)

    def entries(self) -> Iterable[Entry]:
        return list(self._entries.values())


SOURCES = Registry("数据源")
ANALYZERS = Registry("分析器")
REPORTERS = Registry("报告器")


def load_plugins(modules: Iterable[str] = ()) -> None:
    """导入内置插件和配置里声明的额外插件，触发它们的注册。"""
    importlib.import_module("radar.sources")
    importlib.import_module("radar.analysis")
    importlib.import_module("radar.reporters")
    for module in modules:
        importlib.import_module(module)
