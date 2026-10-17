import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("import_hongguo_radar", Path(__file__).parents[1] / "scripts" / "import_hongguo_radar.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SRC = {
    "date": "2026-10-16",
    "fetched_at": "2026-10-16T02:54:39Z",
    "ranks": {"hot": {"rank_date": "2026-10-16", "label_date": "2026-10-16",
                      "items": [{"id": "1", "rank": 1, "status_tags": ["新剧"]}, {"id": "2", "rank": 2, "status_tags": []}]}},
    "series": {
        "1": {"title": "甲", "tags": ["剧情", "穿越", "逆袭", "年代"], "eps": 80, "first_visible": 1791107884, "status": 1,
              "hot": 75551014, "fav": 2864000, "like": 4995000, "rating_cnt": 100, "review_cnt": 20, "score": 9.0},
        "2": None,
    },
    "errors": [{"stage": "detail", "id": "2", "message": "HTTP 500"}],
}


class TestImport(unittest.TestCase):
    def test_convert(self):
        snap = mod.convert(SRC, {}, 8)
        self.assertEqual(snap["imported_from"], "hongguo-radar")
        self.assertEqual(snap["boards"]["hot"]["items"][0], {"id": "1", "rank": 1, "heat": 75550000})
        self.assertEqual(snap["boards"]["hot"]["items"][1]["heat"], None)  # 详情失败的剧保留名次
        self.assertNotIn("2", snap["items"])
        item = snap["items"]["1"]
        self.assertEqual(item["tags"], ["剧情", "穿越", "逆袭"])  # 取前 3 个，和榜单页分类口径一致
        self.assertEqual(item["status_tags"], ["新剧"])
        self.assertEqual(item["rating_count"], 100)
        self.assertTrue(item["first_visible"].startswith("2026-"))

    def test_catalog_tags_win(self):
        snap = mod.convert(SRC, {"1": {"tags": ["剧情", "穿越", "漫剧"]}}, 8)
        self.assertEqual(snap["items"]["1"]["tags"], ["剧情", "穿越", "漫剧"])


if __name__ == "__main__":
    unittest.main()
