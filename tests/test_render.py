"""Channel bodies stay within each service's limits; HTML is escaped."""

import unittest
from html.parser import HTMLParser

from helpers import at, default_config_path, fixture_fetch

from trend_digest import build_digest
from trend_digest.render import discord, html, slack, telegram, wecom


def long_message(sections=9, items=12, text="word ", lang="en"):
    """A message far over every limit."""
    return {
        "lang": lang, "title": "Big digest", "subtitle": "Today: a · b · c",
        "footer": "Data via EveryInfra · 6 API calls · $0.005 today", "site_url": "https://example.github.io/td/",
        "sections": [{
            "id": f"s{s}", "label": f"Section {s}", "icon_url": "https://example.com/i.png",
            "items": [{"id": f"x:{s}-{i}", "title": text * 30, "url": f"https://example.com/{s}/{i}",
                       "summary": text * 40, "metric_text": "★ 1,000", "why": "short reason",
                       "extra": {}} for i in range(items)],
        } for s in range(sections)],
    }


def item_count(message_sections):
    return sum(len(s["items"]) for s in message_sections)


class DiscordTest(unittest.TestCase):
    def setUp(self):
        self.body = build_digest(default_config_path(), fetch=fixture_fetch(),
                                 now=at("2026-11-24"))["payloads"]["discord"][0]

    def test_shape_and_limits(self):
        embeds = self.body["embeds"]
        self.assertLessEqual(len(embeds), 10)
        self.assertLessEqual(sum(discord.embed_text_size(e) for e in embeds), 6000)
        urls = [e["url"] for e in embeds]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertEqual(self.body["allowed_mentions"], {"parse": []})
        self.assertNotIn("content", self.body)
        self.assertEqual(set(self.body), {"embeds", "components", "allowed_mentions"})

    def test_title_keywords_footer_and_buttons(self):
        first, last = self.body["embeds"][0], self.body["embeds"][-1]
        self.assertTrue(first["title"].startswith("EveryInfra Trend Digest"))
        self.assertTrue(first["description"].startswith("Today: "))
        self.assertIn("Data via EveryInfra", last["footer"]["text"])
        self.assertIn("[Run your own digest](https://github.com/everyinfra/trend-digest?utm_source=discord-digest)",
                      last["description"])
        buttons = self.body["components"][0]["components"]
        self.assertEqual([b["style"] for b in buttons], [5])
        self.assertEqual(self.body["embeds"][1]["author"]["name"], "GitHub trending")

    def test_item_line_as_discord_shows_it(self):
        # Seen in a real channel on 2026-11-23: "**1. [title](url)** · metric" turned
        # into a list and pushed the metric to the next line, and "\\~" and "\\[N\\]"
        # inside link text showed with their backslashes.
        item = {"title": "Score ranked by university [N], ~6,700 rows", "url": "https://example.com/a",
                "metric_text": "72 upvotes"}
        line = discord.item_block(1, item, "Why it matters")
        self.assertEqual(line, "1\\. **[Score ranked by university (N), ~6,700 rows](https://example.com/a)** · 72 upvotes")

    def test_too_long_input_loses_items_until_it_fits(self):
        message = long_message()
        body = discord.render(message)
        self.assertTrue(discord.fits(body))
        shown = sum(e.get("description", "").count("](https://example.com/") for e in body["embeds"])
        self.assertLess(shown, item_count(message["sections"]))
        self.assertGreater(shown, 0)


class TelegramTest(unittest.TestCase):
    def test_tags_and_link_targets_do_not_count_against_the_limit(self):
        # Telegram counts the text after it has parsed the tags away, so long link targets that push the
        # HTML over 4,096 characters still fit in one message, and every item is in it.
        message = long_message(sections=4, items=3, text="w ")
        for section in message["sections"]:
            for item in section["items"]:
                item["url"] += "?ref=" + "x" * 300
        bodies = telegram.render(message)
        self.assertEqual(len(bodies), 1)
        self.assertGreater(len(bodies[0]["text"]), telegram.MAX_TEXT)
        self.assertLessEqual(telegram.visible_size(bodies[0]["text"]), telegram.MAX_TEXT)
        self.assertEqual(sum(bodies[0]["text"].count(f'<a href="{item["url"]}">')
                             for s in message["sections"] for item in s["items"]), 12)

    def test_a_long_digest_is_split_between_items_and_keeps_every_item(self):
        message = long_message(text="<b>A&B</b> ")
        bodies = telegram.render(message)
        self.assertGreater(len(bodies), 1)
        for body in bodies:
            self.assertLessEqual(telegram.visible_size(body["text"]), telegram.MAX_TEXT)
            self.assertEqual(body["parse_mode"], "HTML")
            self.assertNotIn("<b>A&B</b>", body["text"])
        self.assertIn("&lt;b&gt;A&amp;B&lt;/b&gt;", bodies[0]["text"])
        text = "\n".join(body["text"] for body in bodies)
        for section in message["sections"]:
            for item in section["items"]:
                self.assertEqual(text.count(f'<a href="{item["url"]}">'), 1, item["url"])
        self.assertEqual(["reply_markup" in body for body in bodies], [False] * (len(bodies) - 1) + [True])
        self.assertEqual(len(bodies[-1]["reply_markup"]["inline_keyboard"][0]), 2)

    def test_a_section_that_goes_on_in_the_next_message_repeats_its_heading(self):
        bodies = telegram.render(long_message(sections=1, items=40))
        self.assertGreater(len(bodies), 1)
        self.assertTrue(bodies[0]["text"].startswith("<b>Big digest</b>\n"))
        for body in bodies[1:]:
            self.assertTrue(body["text"].startswith("<b>Section 0</b>\n"))
        numbers = [int(line.split(".", 1)[0]) for body in bodies for line in body["text"].split("\n")
                   if line[:1].isdigit() and ". <a href=" in line]
        self.assertEqual(numbers, list(range(1, 41)))

    def test_daily_list_has_one_telegram_message(self):
        digest = build_digest(default_config_path(), fetch=fixture_fetch(), now=at("2026-11-24"))
        self.assertEqual(len(digest["payloads"]["telegram"]), 1)


class WecomTest(unittest.TestCase):
    def test_content_under_4096_bytes(self):
        body = wecom.render(long_message(text="中文标题 ", lang="zh"))
        self.assertLessEqual(len(body["markdown"]["content"].encode("utf-8")), 4096)
        self.assertEqual(body["msgtype"], "markdown")


class SlackTest(unittest.TestCase):
    def test_block_and_text_limits(self):
        body = slack.render(long_message(sections=30, items=12))
        self.assertLessEqual(len(body["blocks"]), 50)
        for block in body["blocks"]:
            if block["type"] == "section":
                self.assertLessEqual(len(block["text"]["text"]), 3000)
        self.assertTrue(body["text"])


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.hrefs = [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.hrefs += [v for k, v in attrs if k == "href"]


class HtmlTest(unittest.TestCase):
    def data(self):
        return {"date": "2026-11-24", "language": "en", "title": "Digest <script>alert(1)</script>",
                "keywords": ["<script>"], "weekly": None, "usage": {"calls": 6, "charged_usd": 0.004},
                "sections": [{"id": "github", "label": "GitHub trending", "items": [
                    {"title": "<script>alert('x')</script>", "url": "javascript:alert(1)",
                     "summary": "a & b", "metric_text": "★ 1", "why": None},
                    {"title": "ok", "url": "https://example.com/ok", "summary": "", "metric_text": "", "why": None}]}]}

    def test_script_escaped_and_javascript_link_dropped(self):
        page = html.day_page(self.data())
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("javascript:", page)
        parser = Collector()
        parser.feed(page)
        self.assertNotIn("script", parser.tags)
        self.assertIn("https://example.com/ok", parser.hrefs)

    def test_page_has_title_description_and_og(self):
        page = html.day_page(self.data())
        for needle in ("<title>", '<meta name="description"', 'property="og:title"', "../assets/style.css"):
            self.assertIn(needle, page)


if __name__ == "__main__":
    unittest.main()
