"""7-day memory, "+N today" and the Monday weekly list."""

import copy
import unittest

from helpers import at, default_config_path, fixture_fetch, load_fixture

from trend_digest import NotEnoughHistory, build_digest


def ids(digest):
    return {item["id"] for section in digest["sections"] for item in section["items"]}


def run(day, state, overrides=None, kind="auto"):
    return build_digest(default_config_path(), fetch=fixture_fetch(overrides), state=state,
                        now=at(day), kind=kind)


class SevenDayMemoryTest(unittest.TestCase):
    def test_second_day_repeats_nothing_and_day_nine_may_repeat(self):
        day1 = run("2026-11-17", None)
        day2 = run("2026-11-18", day1["state"])
        self.assertTrue(ids(day1) and ids(day2))
        self.assertEqual(ids(day1) & ids(day2), set())
        day9 = run("2026-11-25", day1["state"])
        self.assertTrue(ids(day1) & ids(day9), "items from 8 days ago can come back")

    def test_x_trends_count_as_seen_too(self):
        config = {"sources": [{"use": "twitter/trending", "limit": 3, "params": {"country": "us"}}]}
        first = build_digest(config, fetch=fixture_fetch(), now=at("2026-11-17"))
        second = build_digest(config, fetch=fixture_fetch(), state=first["state"], now=at("2026-11-18"))
        self.assertEqual(ids(first) & ids(second), set())
        self.assertIn("x:tom jackson", first["state"]["seen"])


class TodayChangeTest(unittest.TestCase):
    def test_second_day_shows_plus_n_today(self):
        day1 = run("2026-11-17", None)
        shown = ids(day1)
        later = copy.deepcopy(load_fixture("reddit.subreddit_posts.json"))
        unseen = [row for row in later["results"] if f"reddit:{row['id']}" not in shown]
        unseen[0]["like_count"] += 57
        day2 = run("2026-11-18", day1["state"], {"reddit.subreddit_posts": later})
        reddit = next(s for s in day2["sections"] if s["id"] == "reddit")
        first = reddit["items"][0]
        self.assertEqual(first["id"], f"reddit:{unseen[0]['id']}")
        self.assertIn("(+57 today)", first["metric_text"])

    def test_no_change_without_yesterday(self):
        day1 = run("2026-11-17", None)
        self.assertNotIn("today)", " ".join(i["metric_text"] for s in day1["sections"] for i in s["items"]))


class WeeklyTest(unittest.TestCase):
    def build_week(self):
        state = None
        for day in ("2026-11-21", "2026-11-22"):  # Saturday, Sunday
            state = run(day, state)["state"]
        return state

    def test_monday_adds_the_weekly_message(self):
        monday = run("2026-11-23", self.build_week())
        self.assertIsNotNone(monday["weekly"])
        self.assertEqual(len(monday["payloads"]["discord"]), 2)
        self.assertTrue(monday["weekly"]["repos"])
        self.assertLessEqual(len(monday["weekly"]["repos"]), 10)
        self.assertLessEqual(len(monday["weekly"]["posts"]), 5)
        self.assertIn("Weekly", monday["payloads"]["discord"][1]["embeds"][0]["title"])

    def test_other_days_have_no_weekly_message(self):
        tuesday = run("2026-11-24", self.build_week())
        self.assertIsNone(tuesday["weekly"])
        self.assertEqual(len(tuesday["payloads"]["discord"]), 1)

    def test_monday_without_history_has_no_weekly(self):
        monday = run("2026-11-23", None)
        self.assertIsNone(monday["weekly"])
        self.assertEqual(len(monday["payloads"]["discord"]), 1)

    def test_weekly_kind_needs_two_days(self):
        with self.assertRaises(NotEnoughHistory):
            run("2026-11-24", None, kind="weekly")

    def test_daily_kind_never_adds_weekly(self):
        monday = run("2026-11-23", self.build_week(), kind="daily")
        self.assertIsNone(monday["weekly"])
        self.assertEqual(len(monday["payloads"]["discord"]), 1)


if __name__ == "__main__":
    unittest.main()
