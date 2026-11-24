"""build_digest() on the saved API responses."""

import json
import unittest

from helpers import at, charged, default_config_path, every_source_config, fixture_fetch, load_fixture

from trend_digest import build_digest
from trend_digest.config import load_config


def items_of(digest):
    return [item for section in digest["sections"] for item in section["items"]]


class DefaultConfigTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.digest = build_digest(default_config_path(), fetch=fixture_fetch(calls=self.calls),
                                   now=at("2026-11-24"))

    def test_ten_to_twelve_items_when_product_hunt_is_empty(self):
        # The saved Product Hunt answer is empty, as it was on the first live run (9 items then).
        # The other sources fill the gap: each [[sources]] entry may add at most 2 over its limit.
        self.assertGreaterEqual(len(items_of(self.digest)), 10)
        self.assertLessEqual(len(items_of(self.digest)), 12)
        limits = {"github": 3 + 2, "reddit": (2 + 2) + (1 + 2), "google_news": (2 + 2) + (1 + 2)}
        for section in self.digest["sections"]:
            self.assertLessEqual(len(section["items"]), limits[section["id"]], section["id"])

    def test_no_fill_up_when_min_items_is_one(self):
        config = {**load_config(default_config_path()), "min_items": 1}
        digest = build_digest(config, fetch=fixture_fetch(), now=at("2026-11-24"))
        limits = {"github": 3, "reddit": 3, "google_news": 3}
        for section in digest["sections"]:
            self.assertLessEqual(len(section["items"]), limits[section["id"]], section["id"])

    def test_every_item_has_a_link_and_a_prefixed_id(self):
        for item in items_of(self.digest):
            self.assertTrue(item["url"].startswith("https://"), item)
            self.assertIn(":", item["id"])

    def test_empty_product_hunt_is_left_out_and_recorded(self):
        self.assertNotIn("producthunt", [s["id"] for s in self.digest["sections"]])
        self.assertEqual(self.digest["usage"]["failed"],
                         [{"source": "producthunt/trending", "reason": "empty"}])

    def test_calls_and_cost_match_billing(self):
        expected = (charged("github.trending.json") + charged("producthunt.trending.json")
                    + 2 * charged("reddit.subreddit_posts.json") + 2 * charged("google_news.search.json"))
        self.assertEqual(self.digest["usage"]["calls"], 6)
        self.assertEqual(len(self.calls), 6)
        self.assertAlmostEqual(self.digest["usage"]["charged_usd"], expected, places=6)

    def test_two_subreddits_share_one_section(self):
        labels = [s["label"] for s in self.digest["sections"]]
        self.assertIn("Reddit · r/LocalLLaMA, r/MachineLearning", labels)
        self.assertIn("Google News", labels)

    def test_result_is_json_and_has_the_documented_keys(self):
        text = json.dumps(self.digest)
        self.assertTrue(text)
        for key in ("version", "date", "title", "keywords", "sections", "weekly", "usage",
                    "payloads", "page", "index_entry", "state"):
            self.assertIn(key, self.digest)
        self.assertEqual(len(self.digest["keywords"]), 3)
        self.assertEqual(self.digest["title"], "EveryInfra Trend Digest · Tue, Nov 24")

    def test_footer_text(self):
        footer = self.digest["payloads"]["discord"][0]["embeds"][-1]["footer"]["text"]
        self.assertEqual(footer, "Data via EveryInfra · 6 API calls · $0.004 today")


class EverySourceTest(unittest.TestCase):
    def setUp(self):
        self.digest = build_digest(every_source_config(), fetch=fixture_fetch(), now=at("2026-11-24"))
        self.by_id = {s["id"]: s for s in self.digest["sections"]}

    def test_charged_sum_of_six_english_sources(self):
        names = ["github.trending.json", "producthunt.trending.json", "reddit.trending_posts.json",
                 "reddit.subreddit_posts.json", "twitter.trending.json", "google_news.search.json"]
        self.assertAlmostEqual(self.digest["usage"]["charged_usd"], sum(charged(n) for n in names), places=6)

    def test_x_trends_get_a_search_link_and_rank(self):
        first = self.by_id["twitter"]["items"][0]
        self.assertEqual(first["url"], "https://x.com/search?q=Tom%20Jackson")
        self.assertEqual(first["id"], "x:tom jackson")
        self.assertEqual(first["metric_text"], "#1 in US trends")
        self.assertEqual(self.by_id["twitter"]["label"], "X trends (US)")

    def test_github_without_stars_shows_rank(self):
        first = self.by_id["github"]["items"][0]
        self.assertEqual(first["metric_text"], "#1 on GitHub trending")
        self.assertEqual(first["id"], "github:elementalsouls/Claude-BugHunter")

    def test_reddit_counts(self):
        texts = [i["metric_text"] for i in self.by_id["reddit"]["items"]]
        self.assertTrue(any("upvotes" in t and "comments" in t for t in texts), texts)

    def test_news_shows_outlet_and_age(self):
        first = self.by_id["google_news"]["items"][0]
        self.assertEqual(first["metric_text"], "WIRED · 2d ago")
        self.assertTrue(first["id"].startswith("gnews:") and len(first["id"]) == 18)


class GithubStarsTest(unittest.TestCase):
    def test_star_fields_are_used_when_present(self):
        response = {"results": [{"rank": 1, "full_name": "acme/rocket", "url": "https://github.com/acme/rocket",
                                 "description": "A rocket.", "star_count": 12480, "stars_today": 1240,
                                 "language": "Python"}],
                    "billing": {"charged_usd": 0.0008}}
        config = {"sources": [{"use": "github/trending", "limit": 3}]}
        digest = build_digest(config, fetch=fixture_fetch({"github.trending": response}), now=at("2026-11-24"))
        item = digest["sections"][0]["items"][0]
        self.assertEqual(item["metric_text"], "★ 12,480 (+1,240 today) · Python")
        self.assertIn("★ 12,480 (+1,240 today)", digest["payloads"]["discord"][0]["embeds"][1]["description"])


class ChinesePresetTest(unittest.TestCase):
    def test_zh_preset_builds(self):
        config = load_config(default_config_path().replace("digest.toml", "presets/zh.toml"))
        digest = build_digest(config, fetch=fixture_fetch(), now=at("2026-11-24"))
        labels = [s["label"] for s in digest["sections"]]
        self.assertEqual(labels, ["微博热搜", "抖音热榜", "GitHub 趋势"])
        douyin = digest["sections"][1]["items"]
        self.assertTrue(all(not i["title"].startswith("深圳小渔村") for i in douyin), "pinned item skipped")
        self.assertTrue(douyin[0]["url"].startswith("https://www.douyin.com/search/"))
        self.assertTrue(douyin[0]["id"].startswith("douyin:"))
        self.assertIn("热度", douyin[0]["metric_text"])
        self.assertIn("Data via EveryInfra", digest["payloads"]["wecom"][0]["markdown"]["content"])


class FailureTest(unittest.TestCase):
    def test_a_failing_source_is_recorded_and_others_continue(self):
        from trend_digest.client import ApiError
        fetch = fixture_fetch({"github.trending": ApiError(422, "unknown parameter 'foo'")})
        digest = build_digest(default_config_path(), fetch=fetch, now=at("2026-11-24"))
        failed = {f["source"]: f for f in digest["usage"]["failed"]}
        self.assertEqual(failed["github/trending"]["reason"], "http_422")
        self.assertEqual(failed["github/trending"]["detail"], "unknown parameter 'foo'")
        self.assertTrue(digest["sections"])

    def test_missing_key_without_fetch_is_a_clear_error(self):
        with self.assertRaises(ValueError) as caught:
            build_digest(default_config_path(), api_key="", now=at("2026-11-24"))
        self.assertIn("EVERYINFRA_API_KEY", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
