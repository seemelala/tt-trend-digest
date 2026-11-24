"""覆盖周刊 Markdown、跨日状态和飞书卡片的实际集成入口。"""

import json
import unittest
from unittest.mock import patch

from helpers import at, fixture_fetch
from trend_digest.__main__ import all_failed
from trend_digest.digest import build_digest
from trend_digest.weekly_projects import SOURCE, projects_from_issue

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
        self.assertEqual([item["title"] for item in items], ["Alpha", "Beta", "Gamma"])
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

        same_day = build("2026-11-24", first["state"])
        self.assertNotIn(SOURCE, [section["id"] for section in same_day["sections"]])
        self.assertEqual(read_markdown.call_count, 2)

        later = build("2026-12-02", same_day["state"])
        projects = later["sections"][0]["items"]
        self.assertEqual([item["title"] for item in projects], ["Gamma", "Delta"])
        self.assertEqual([item["extra"]["issue"] for item in projects], [10, 9])

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
