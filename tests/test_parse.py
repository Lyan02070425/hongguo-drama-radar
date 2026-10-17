import unittest

from radar.core.text import clean_tags, parse_adaptation, parse_count
from radar.core.timeutil import batch_date, month_day_to_date
from radar.sources.hongguo.parse import ParseError, extract_id, parse_detail_page, parse_rank_page, parse_search_page
from tests.helpers import fixture

from datetime import datetime, timezone


class TestText(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(parse_count("5462万热度"), 54_620_000)
        self.assertEqual(parse_count("1.2亿"), 120_000_000)
        self.assertEqual(parse_count("24.2万收藏"), 242_000)
        self.assertEqual(parse_count("4347"), 4347)
        self.assertIsNone(parse_count("无"))

    def test_clean_tags(self):
        self.assertEqual(clean_tags(["萌宝\x00助攻", "205", "都市", "都市", " "]), ["萌宝助攻", "都市"])

    def test_adaptation(self):
        a = parse_adaptation("……改编自番茄短篇小说《供妹读博却被断亲，我反手收回房车》，作者龙龙爱写小说。")
        self.assertEqual(a["platform"], "番茄小说")
        self.assertEqual(a["work"], "供妹读博却被断亲，我反手收回房车")
        self.assertEqual(a["author"], "龙龙爱写小说")
        b = parse_adaptation("改编自小说《首辅娇娘》，作者偏方方")
        self.assertEqual(b["platform"], "小说（未注明平台）")
        self.assertEqual(b["author"], "偏方方")
        self.assertIsNone(parse_adaptation("一个普通的简介"))

    def test_dates(self):
        self.assertEqual(month_day_to_date(10, 17, "2026-10-17"), "2026-10-17")
        self.assertEqual(month_day_to_date(12, 31, "2027-01-01"), "2026-12-31")
        early = datetime(2026, 10, 17, 0, 30, tzinfo=timezone.utc)  # 北京时间 08:30
        late = datetime(2026, 10, 17, 3, 0, tzinfo=timezone.utc)    # 北京时间 11:00
        self.assertEqual(batch_date(8, 9, early), "2026-10-16")
        self.assertEqual(batch_date(8, 9, late), "2026-10-17")


class TestHongguoParse(unittest.TestCase):
    def test_rank_page(self):
        page = parse_rank_page(fixture("hongguo_rank_ai_p2.html"), "2026-10-17")
        self.assertEqual(page["label"], "AI剧热播榜")
        self.assertEqual(page["label_date"], "2026-10-17")
        self.assertEqual(page["pages"], 5)
        self.assertEqual(page["current_page"], 2)
        self.assertEqual(len(page["items"]), 20)
        first = page["items"][0]
        self.assertEqual(first["rank"], 21)
        self.assertEqual(first["id"], "7693840102283299902")
        self.assertEqual(first["title"], "深海契约：我出海带全家暴富")
        self.assertEqual(first["heat"], 54_620_000)
        self.assertEqual(first["fav"], 242_000)
        self.assertEqual(first["like"], 838_000)
        self.assertEqual(first["tags"], ["脑洞", "系统", "逆袭"])
        self.assertTrue(first["synopsis"].startswith("赵凡"))
        self.assertEqual(page["items"][1]["rating"], 8.5)
        for item in page["items"]:
            self.assertTrue(1 <= len(item["tags"]) <= 3)
            self.assertFalse(any(t.isdigit() for t in item["tags"]))  # 「205」这类内部编号被去掉
            self.assertIsNotNone(item["heat"])
        self.assertEqual([i["rank"] for i in page["items"]], list(range(21, 41)))

    def test_rank_page_without_items(self):
        with self.assertRaises(ParseError):
            parse_rank_page("<html><body>维护中</body></html>", "2026-10-17")

    def test_detail_page(self):
        d = parse_detail_page(fixture("hongguo_detail.html"))
        self.assertEqual(d["id"], "7695704804978330649")
        self.assertEqual(d["heat"], 68_501_595)
        self.assertEqual(d["episodes"], 222)
        self.assertEqual(d["first_visible"], "2026-10-14")
        self.assertEqual(d["rating_count"], 4347)
        self.assertEqual(d["review_count"], 1458)
        self.assertNotIn("reviews", d)  # 评论内容不保存

    def test_search_page(self):
        hits = parse_search_page(fixture("hongguo_search.html"))
        self.assertEqual(hits[0], {"id": "7686713195246930968", "title": "首辅娇娘"})

    def test_extract_id(self):
        self.assertEqual(extract_id("https://hongguoduanju.com/detail?series_id=7686713195246930968"), "7686713195246930968")
        self.assertEqual(extract_id("https://hongguoduanju.com/player/7693840102283299902/123"), "7693840102283299902")
        self.assertIsNone(extract_id("首辅娇娘"))


if __name__ == "__main__":
    unittest.main()
