import json
import unittest

from radar.analysis.history import History
from radar.analysis.runner import Context, run_analyzers
from radar.analysis.util import percentiles
from radar.core.registry import SOURCES, load_plugins
from radar.core.store import Store
from radar.site import build_site
from tests.helpers import snapshot, temp_config

load_plugins()


def item(title, heat, fav, tags, first_visible="2026-09-01", **kw):
    return {"title": title, "heat": heat, "fav": fav, "like": fav * 2, "rating": kw.pop("rating", 8.5), "tags": tags,
            "status_tags": kw.pop("status_tags", []), "first_visible": first_visible, "episodes": 80, **kw}


def history_fixture():
    """三天：A 一直第一；B 第二天掉榜；C 第二天新上榜并在第三天冲到第二；D 是新剧。"""
    d1 = snapshot("2026-10-15", {"hot": [("A", 900), ("B", 800), ("D", 300)]}, {
        "A": item("剧A", 900, 1000, ["穿越", "逆袭", "漫剧"]),
        "B": item("剧B", 800, 500, ["甜宠", "都市"]),
        "D": item("剧D", 300, 100, ["穿越", "系统"], first_visible="2026-10-14", rating=9.5),
    })
    d2 = snapshot("2026-10-16", {"hot": [("A", 950), ("D", 500), ("C", 400)]}, {
        "A": item("剧A", 950, 1100, ["穿越", "逆袭", "漫剧"]),
        "B": item("剧B", 700, 510, ["甜宠", "都市"]),
        "C": item("剧C", 400, 300, ["穿越", "重生"], first_visible="2026-10-10"),
        "D": item("剧D", 500, 400, ["穿越", "系统"], first_visible="2026-10-14", rating=9.5),
    })
    d3 = snapshot("2026-10-17", {"hot": [("A", 1000), ("C", 800), ("D", 600)]}, {
        "A": item("剧A", 1000, 1150, ["穿越", "逆袭", "漫剧"]),
        "C": item("剧C", 800, 900, ["穿越", "重生"], first_visible="2026-10-10"),
        "D": item("剧D", 600, 600, ["穿越", "系统"], first_visible="2026-10-14", rating=9.5),
    })
    return [d1, d2, d3]


class TestAnalysis(unittest.TestCase):
    def setUp(self):
        self.config = temp_config({"analysis": {"min_tag_count": 1, "min_heat_for_rate": 0, "tag_momentum_days": 2}})
        store = Store(self.config.paths, "hongguo")
        source = SOURCES.get("hongguo").obj(self.config, store, log=lambda m: None)
        self.ctx = Context(source=source, history=History("hongguo", history_fixture(), {}), config=self.config)
        run_analyzers(self.ctx, self.config.paths.root / "_out", log=lambda m: None)
        self.r = self.ctx.results

    def test_board_moves(self):
        hot = self.r["metrics"]["boards"]["hot"]
        rows = {e["id"]: e for e in hot["entries"]}
        self.assertEqual(rows["A"]["streak"], 3)
        self.assertEqual(rows["C"]["delta"], 1)       # 第 3 → 第 2
        self.assertIsNone(rows["C"]["badge"])          # 昨天已经上过榜
        self.assertEqual(rows["D"]["delta"], -1)
        self.assertEqual(hot["dropped"], [])
        prev_day = History("hongguo", history_fixture()[:2], {})
        self.ctx.history = prev_day
        from radar.analysis.metrics import metrics
        m2 = metrics(self.ctx)
        e2 = {e["id"]: e for e in m2["boards"]["hot"]["entries"]}
        self.assertEqual(e2["C"]["badge"], "new")
        self.assertEqual(m2["boards"]["hot"]["dropped"], [{"id": "B", "last_rank": 2}])

    def test_growth(self):
        d = self.r["metrics"]["dramas"]
        self.assertEqual(d["C"]["d_heat"], 400)
        self.assertEqual(d["C"]["d_fav"], 600)
        self.assertAlmostEqual(d["C"]["r_heat"], 1.0)
        self.assertEqual(d["D"]["age_days"], 3)
        self.assertTrue(d["D"]["is_new"])
        self.assertFalse(d["A"]["is_new"])
        self.assertEqual(self.r["movers"]["lists"]["fav"]["items"][0]["id"], "C")

    def test_potential(self):
        items = self.r["potential"]["items"]
        self.assertEqual({i["id"] for i in items}, {"C", "D"})  # 上线不超过 14 天的两部；A 是老剧
        self.assertEqual(items[0]["id"], "C")  # 收藏、热度增速、名次都领先，只有评分不如 D
        self.assertEqual(items[0]["score"], 80.0)
        self.assertEqual(sum(self.r["potential"]["by_kind"].values()), len(items))
        self.assertEqual([i["kind_rank"] for i in items if i["kind"] == items[0]["kind"]][0], 1)

    def test_tags(self):
        hot = self.r["tags"]["boards"]["hot"]
        tags = {t["tag"]: t for t in hot["tags"]}
        self.assertNotIn("漫剧", tags)  # 形式标签不算题材
        self.assertEqual(tags["穿越"]["count"], 3)
        self.assertAlmostEqual(tags["穿越"]["heat_share"], 1.0)
        self.assertEqual(self.r["tags"]["baseline_date"], "2026-10-15")
        falling = {t["tag"] for t in hot["falling"]}
        self.assertIn("甜宠", falling)

    def test_percentiles(self):
        p = percentiles({"a": 1, "b": 2, "c": 2, "d": None, "e": 3})
        self.assertEqual(p["a"], 0.0)
        self.assertEqual(p["b"], p["c"])
        self.assertEqual(p["e"], 1.0)
        self.assertNotIn("d", p)

    def test_outputs_written(self):
        out = self.config.paths.root / "_out"
        for name in ("status", "metrics", "boards", "movers", "potential", "tags", "lifecycle", "dramas", "exports", "insights"):
            self.assertTrue((out / f"{name}.json").exists(), name)
        self.assertTrue((out / "dramas" / "C.json").exists())
        csv = (out / "exports" / "drama_daily.csv").read_text(encoding="utf-8-sig")
        self.assertTrue(csv.startswith("date,id,title"))
        insights = json.loads((out / "insights.json").read_text(encoding="utf-8"))
        self.assertTrue(insights["items"])


class TestBuildSite(unittest.TestCase):
    def test_build_with_snapshots(self):
        config = temp_config({"reporters": {"markdown": {"enabled": True}}})
        store = Store(config.paths, "hongguo")
        for snap in history_fixture():
            store.save(snap)
        out = config.paths.root / "_site"
        manifest = build_site(config, out, ["hongguo"], log=lambda m: None)
        self.assertEqual(manifest["sources"][0]["latest_date"], "2026-10-17")
        self.assertTrue((out / "index.html").exists())
        self.assertTrue((out / "data" / "manifest.json").exists())
        self.assertTrue((out / "reports" / "hongguo" / "2026-10-17.md").exists())

    def test_build_without_data(self):
        config = temp_config()
        manifest = build_site(config, config.paths.root / "_site", ["hongguo"], log=lambda m: None)
        self.assertIsNone(manifest["sources"][0]["latest_date"])


if __name__ == "__main__":
    unittest.main()
