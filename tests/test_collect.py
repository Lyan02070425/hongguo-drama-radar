import unittest

from radar.core.http import Fetcher
from radar.core.store import Store
from radar.sources.base import CollectError
from radar.sources.hongguo import HongguoSource
from tests.helpers import fixture, temp_config

RANK = fixture("hongguo_rank_ai_p2.html")
DETAIL = fixture("hongguo_detail.html")
SEARCH = fixture("hongguo_search.html")


def make_opener(calls, fail_rank=False):
    def opener(url, headers, timeout):
        calls.append((url, headers["User-Agent"]))
        if "/rank/" in url:
            return (500, {}, b"") if fail_rank else (200, {}, RANK.encode("utf-8"))
        if "/detail" in url:
            return 200, {}, DETAIL.encode("utf-8")
        if "/search/" in url:
            return 200, {}, SEARCH.encode("utf-8")
        return 404, {}, b""
    return opener


def make_source(config, calls, **kw):
    store = Store(config.paths, "hongguo")
    fetcher = Fetcher("drama-radar-test", min_interval=0, backoff=(0,), opener=make_opener(calls, **kw), sleep=lambda s: None)
    return HongguoSource(config, store, log=lambda m: None, fetcher=fetcher), store


class TestCollect(unittest.TestCase):
    def setUp(self):
        self.config = temp_config({"sources": {"hongguo": {"min_items_per_board": 10, "watchlist": ["首辅娇娘"]}}})
        self.calls = []

    def test_first_collect_then_stale(self):
        source, store = make_source(self.config, self.calls)
        result = source.collect("2026-10-17")
        self.assertEqual(result.status, "new")
        snap = result.snapshot
        self.assertEqual(set(snap["boards"]), {"hot", "real", "ai", "comic"})
        self.assertEqual(len(snap["boards"]["hot"]["items"]), 20)
        self.assertEqual(snap["boards"]["hot"]["items"][0]["rank"], 21)
        # 观察列表里的剧不在榜上，也会被追踪
        self.assertIn("7686713195246930968", snap["items"])
        self.assertEqual(snap["watchlist"][0]["status"], "ok")
        item = snap["items"]["7693840102283299902"]
        self.assertTrue(item["heat_exact"])
        self.assertEqual(item["tags"], ["脑洞", "系统", "逆袭"])
        self.assertEqual(item["episodes"], 222)
        self.assertTrue(all(ua == "drama-radar-test" for _, ua in self.calls))  # 不冒充爬虫
        store.save(snap)
        catalog = store.load_catalog()
        self.assertEqual(catalog["7693840102283299902"]["first_seen"], "2026-10-17")

        again = source.collect("2026-10-17")
        self.assertEqual(again.status, "exists")
        stale = source.collect("2026-10-18")
        self.assertEqual(stale.status, "stale")
        forced = source.collect("2026-10-18", allow_stale=True)
        self.assertEqual(forced.status, "new")
        self.assertTrue(forced.snapshot["stale"])

    def test_rank_failure_raises(self):
        source, _ = make_source(self.config, self.calls, fail_rank=True)
        with self.assertRaises(CollectError):
            source.collect("2026-10-17")


if __name__ == "__main__":
    unittest.main()
