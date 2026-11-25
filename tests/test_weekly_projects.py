"""覆盖周刊 Markdown、跨日状态和飞书卡片的实际集成入口。"""

import json
import unittest
from unittest.mock import patch

from helpers import ROOT, at, fixture_fetch
from trend_digest.__main__ import all_failed
from trend_digest.digest import build_digest
from trend_digest.weekly_projects import SOURCE, projects_from_issue, recommend

INDEX = """
- 第 9 期：[旧一期](docs/issue-9.md)
- 第 10 期：[新一期](docs/issue-10.md)
"""
NEW = """
## 文章

1、[普通文章](https://github.com/example/article)

## 工具

1、[Alpha](https://github.com/Example/Alpha/)

![](https://example.com/screenshot.png)

分析本地日志。

2、[Beta](https://github.com/example/beta)

整理文件。

3、[项目官网](https://example.com)

## 资源

1、[Gamma](https://github.com/example/gamma)

绘制图表。

2、[Epsilon](https://github.com/example/epsilon)

检查链接。

3、[Zeta](https://github.com/example/zeta)

整理截图。
"""
OLD = """
## 工具

1、[Alpha 再次出现](https://github.com/example/alpha?ref=weekly)

2、[Delta](https://github.com/example/delta)

管理书签。
"""
CONFIG = {"timezone": "Asia/Shanghai", "sources": [{"use": "github/trending", "limit": 3}]}


def read_issue(path):
    return {"README.md": INDEX, "docs/issue-10.md": NEW, "docs/issue-9.md": OLD}[path]


class WeeklyProjectsTest(unittest.TestCase):
    def test_parses_projects_and_issue_without_images_or_articles(self):
        items = list(projects_from_issue(NEW, 10))
        self.assertEqual([item["title"] for item in items], ["Alpha", "Beta", "Gamma", "Epsilon", "Zeta"])
        self.assertEqual(items[0]["summary"], "分析本地日志。")
        self.assertEqual(items[0]["metric_text"], "周刊第 10 期")

    @patch("trend_digest.weekly_projects.read_markdown", side_effect=read_issue)
    def test_daily_quota_and_cross_week_history_reach_feishu(self, read_markdown):
        def build(day, state=None):
            return build_digest(CONFIG, state=state, now=at(day), fetch=fixture_fetch(),
                                kind="daily", weekly_projects=True)

        first = build("2026-11-24")
        card = json.dumps(first["payloads"]["feishu"], ensure_ascii=False)
        self.assertIn("周刊项目精选", card)
        self.assertIn("https://github.com/example/alpha", card)
        self.assertEqual(first["usage"]["calls"], 1)
        self.assertEqual(read_markdown.call_count, 2)
        self.assertEqual(len(first["sections"][0]["items"]), 5)

        same_day = build("2026-11-24", first["state"])
        self.assertNotIn(SOURCE, [section["id"] for section in same_day["sections"]])
        self.assertEqual(read_markdown.call_count, 2)

        later = build("2026-12-02", same_day["state"])
        projects = later["sections"][0]["items"]
        self.assertEqual([item["title"] for item in projects], ["Delta"])
        self.assertEqual([item["extra"]["issue"] for item in projects], [9])

    @patch("trend_digest.weekly_projects.read_markdown", side_effect=read_issue)
    def test_projects_preset_reserves_five_slots_and_backfills_shortfall(self, _read_markdown):
        config = f"{ROOT}/presets/projects.toml"
        github = {"results": [{"full_name": f"example/repo-{i}",
                               "url": f"https://github.com/example/repo-{i}"}
                              for i in range(12)]}
        producthunt = {"results": [{"name": f"Product {i}",
                                    "url": f"https://www.producthunt.com/products/item-{i}"}
                                   for i in range(6)]}

        news = {"results": [{"title": f"News {i}", "url": f"https://example.com/news-{i}"}
                            for i in range(6)]}

        def build(overrides, state=None):
            return build_digest(config, state=state, now=at("2026-11-25"),
                                fetch=fixture_fetch(overrides), kind="daily", weekly_projects=True)

        def counts(digest):
            return {section["id"]: len(section["items"]) for section in digest["sections"]}

        sources = {"github.trending": github, "producthunt.trending": producthunt,
                   "google_news.search": news}
        regular = build(sources)
        self.assertEqual(counts(regular), {SOURCE: 5, "github": 4, "producthunt": 1, "google_news": 2})
        self.assertEqual(regular["usage"]["calls"], 3)

        history = {SOURCE + ":example/" + name: "2026-11-24"
                   for name in ("alpha", "beta", "gamma", "delta", "epsilon", "zeta")}
        without_weekly = build(sources, {"weekly_project_history": history})
        self.assertEqual(counts(without_weekly), {"github": 7, "producthunt": 3, "google_news": 2})

        without_producthunt = build({**sources, "producthunt.trending": {"results": []}})
        self.assertEqual(counts(without_producthunt), {SOURCE: 5, "github": 5, "google_news": 2})

    @patch("trend_digest.weekly_projects.read_markdown", side_effect=read_issue)
    def test_raising_quota_only_adds_two_after_three_already_sent_today(self, _read_markdown):
        history = {SOURCE + ":example/" + name: "2026-11-25"
                   for name in ("alpha", "beta", "gamma")}
        projects = recommend(history, "2026-11-25", [])
        self.assertEqual([item["title"] for item in projects], ["Epsilon", "Zeta"])

    @patch("trend_digest.weekly_projects.read_markdown", side_effect=OSError("offline"))
    def test_weekly_unavailable_keeps_normal_digest(self, _read_markdown):
        with self.assertLogs("trend_digest", level="WARNING"):
            digest = build_digest(CONFIG, now=at("2026-11-24"), fetch=fixture_fetch(),
                                  weekly_projects=True)
        self.assertIn("github", [section["id"] for section in digest["sections"]])
        self.assertNotIn("weekly_project_history", digest["state"])

    @patch("trend_digest.weekly_projects.read_markdown", side_effect=read_issue)
    def test_weekly_projects_sendable_when_paid_source_fails(self, _read_markdown):
        fetch = fixture_fetch({"github.trending": OSError("offline")})
        digest = build_digest(CONFIG, now=at("2026-11-24"), fetch=fetch, weekly_projects=True)
        self.assertEqual([section["id"] for section in digest["sections"]], [SOURCE])
        self.assertFalse(all_failed(digest))


if __name__ == "__main__":
    unittest.main()
