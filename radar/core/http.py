"""礼貌的 HTTP GET：如实的 User-Agent、全局限速、重试与退避（只用标准库）。"""

from __future__ import annotations

import gzip
import time
import urllib.error
import urllib.request
import zlib
from typing import Callable, Dict, Optional, Tuple

Response = Tuple[int, Dict[str, str], bytes]
Opener = Callable[[str, Dict[str, str], float], Response]


class FetchError(Exception):
    """请求最终失败：重试用尽，或遇到不值得重试的状态码。"""


def _urllib_open(url: str, headers: Dict[str, str], timeout: float) -> Response:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as exc:
        hdrs = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        return exc.code, hdrs, b""


def _decode(headers: Dict[str, str], body: bytes) -> str:
    encoding = headers.get("content-encoding", "").lower()
    if encoding == "gzip":
        body = gzip.decompress(body)
    elif encoding == "deflate":
        body = zlib.decompress(body)
    return body.decode("utf-8", errors="replace")


class Fetcher:
    def __init__(
        self,
        user_agent: str,
        min_interval: float = 1.0,
        timeout: float = 20,
        backoff: Tuple[float, ...] = (2, 5, 10),
        max_retry_after: float = 60,
        opener: Optional[Opener] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.timeout = timeout
        self.backoff = backoff
        self.max_retry_after = max_retry_after
        self._open = opener or _urllib_open
        self._sleep = sleep
        self._clock = clock
        self._next_at = 0.0
        self.requests = 0

    def get(self, url: str) -> str:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip",
        }
        last = "no attempt"
        for attempt in range(len(self.backoff) + 1):
            self._throttle()
            extra = 0.0
            self.requests += 1
            try:
                status, resp_headers, body = self._open(url, headers, self.timeout)
            except OSError as exc:  # URLError、超时、连接重置都是 OSError
                last = f"{type(exc).__name__}: {exc}"
            else:
                if status == 200:
                    return _decode(resp_headers, body)
                last = f"HTTP {status}"
                if status == 429 or status >= 500:
                    extra = self._retry_after(resp_headers)
                else:
                    raise FetchError(f"{url}: {last}")
            if attempt < len(self.backoff):
                self._sleep(self.backoff[attempt] + extra)
        raise FetchError(f"{url}: {last}")

    def _throttle(self) -> None:
        now = self._clock()
        wait = self._next_at - now
        if wait > 0:
            self._sleep(wait)
            now = self._clock()
        self._next_at = now + self.min_interval

    def _retry_after(self, headers: Dict[str, str]) -> float:
        try:
            return min(float(headers.get("retry-after", 0)), self.max_retry_after)
        except ValueError:
            return 0.0
