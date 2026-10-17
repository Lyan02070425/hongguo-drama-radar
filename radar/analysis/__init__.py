"""内置分析器。每个模块用 @ANALYZERS.register 注册自己，输出写到 _site/data/<source>/<名字>.json。

新增分析器：在这个目录加一个模块并在下面 import，或者写在别处、把模块路径加到
config.toml 的 general.plugins 里。详见 docs/EXTENDING.md。
"""

from radar.analysis import (  # noqa: F401
    boards,
    dramas,
    exports,
    insights,
    lifecycle,
    metrics,
    movers,
    potential,
    status,
    tags,
)
