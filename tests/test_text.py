"""Keywords and the optional "Why it matters" sentence."""

import json
import unittest

from trend_digest.fmt import clip
from trend_digest.keywords import pick_keywords
from trend_digest.sources import describe, google_news_items, producthunt_items
from trend_digest.why import add_why, llm_from_env


def item(item_id, title, summary=""):
    return {"id": item_id, "title": title, "summary": summary, "source": "x/y", "why": None}


class KeywordTest(unittest.TestCase):
    def test_words_used_by_several_items_come_first(self):
        items = [item("a", "Rust compiler gets faster"), item("b", "Why Rust beats Go"),
                 item("c", "Agents in Rust"), item("d", "Agents everywhere"), item("e", "Compiler news")]
        self.assertEqual(pick_keywords(items), ["Rust", "compiler", "Agents"])

    def test_all_unique_words_fall_back_to_one_word_per_item(self):
        items = [item("a", "Quantum supremacy"), item("b", "Penguins migrate"), item("c", "Volcano erupts")]
        self.assertEqual(pick_keywords(items), ["supremacy", "Penguins", "Volcano"])

    def test_model_answer_is_used_and_bad_answer_falls_back(self):
        items = [item("a", "Quantum supremacy"), item("b", "Penguins migrate"), item("c", "Volcano erupts")]
        self.assertEqual(pick_keywords(items, lambda p: '["one", "two", "three"]'), ["one", "two", "three"])
        self.assertEqual(pick_keywords(items, lambda p: "sorry"), ["supremacy", "Penguins", "Volcano"])


class MetricTextTest(unittest.TestCase):
    def test_no_rank_text_when_the_source_gives_no_rank(self):
        # From a live run: Product Hunt rows had no rank and no votes; the line said "#None on the list".
        rows = [{"name": "TeaserKit", "url": "https://www.producthunt.com/products/teaserkit",
                 "tagline": "your coding agent directs your launch video"}]
        one = describe(producthunt_items(rows, "producthunt/trending", {})[0], "en", None)
        self.assertEqual(one["metric_text"], "")


class GluedTextTest(unittest.TestCase):
    def test_year_glued_to_the_next_sentence_gets_a_space(self):
        # From a live google_news/search row (keyword "AI agents", 2026-11-23). The publisher's own meta
        # description reads "...by 2028Getting AI agents live...", and the digest showed it that way.
        row = {"title": "Gartner Report: Critical Success Measures to Drive Your Customer Service AI Agent Strategy",
               "url": "https://www.destinationcrm.com/ReportsandResearch/15008-Gartner%C2%AE-Report-Critical-"
                      "Success-Measures-to-Drive-Your-Customer-Service-AI-Agent-Strategy.htm",
               "source": "Destination CRM", "published_at": "2026-11-22T15:22:17Z",
               "text": "50% of customer service orgs will fail to effectively scale AI agents by 2028Getting AI "
                       "agents live is only the beginning."}
        one = google_news_items([row], "google_news/search", {"keyword": "AI agents"})[0]
        self.assertEqual(one["summary"], "50% of customer service orgs will fail to effectively scale AI agents "
                                         "by 2028 Getting AI agents live is only the beginning.")

    def test_names_with_digits_and_capitals_stay_as_they_are(self):
        for text in ("1Password adds passkeys", "New iPhone and YouTube features", "Windows2000Server",
                     "4K video at 2028 prices", "Released in 2028."):
            self.assertEqual(clip(text, 220), text)


class WhyTest(unittest.TestCase):
    def test_good_sentences_kept_long_ones_dropped(self):
        items = [item("a", "A"), item("b", "B"), item("c", "C")]
        answer = json.dumps({"a": "Short and useful.", "b": " ".join(["word"] * 26)})
        prompts = []
        add_why(items, lambda p: prompts.append(p) or f"Here you go: {answer}")
        self.assertEqual([i["why"] for i in items], ["Short and useful.", None, None])
        self.assertEqual(len(prompts), 1, "one request for the whole digest")

    def test_sentence_that_repeats_the_summary_is_dropped(self):
        # From the first live digest: the summary and the model's sentence said the same thing.
        one = item("a", "claude-skills")
        one["summary"] = "82 skills, 15 slash commands, 681 patterns for coding agents"
        two = item("b", "claude-skills")
        two["summary"] = one["summary"]
        two["metric_text"] = "★ 12,480 (+1,240 today)"
        answer = json.dumps({"a": "It offers 82 skills, 15 slash commands, 681 patterns to developers.",
                             "b": "Most starred repository on today's list, with 1,240 new stars."})
        add_why([one, two], lambda p: answer)
        self.assertIsNone(one["why"])
        self.assertEqual(two["why"], "Most starred repository on today's list, with 1,240 new stars.")

    def test_number_from_another_item_is_dropped(self):
        # From a live run: a Reddit post got the star count of the GitHub item above it.
        repo = item("a", "elementalsouls/Claude-BugHunter")
        repo["metric_text"] = "★ 17,327 (+1,721 today) · Python"
        repo["metrics"] = [{"label": "stars", "value": 17327, "delta": 1721}]
        post = item("b", "Inkling absolutely rips. ~200 tok/s decode, ~6,700 prefill on 2x3090s")
        post["metric_text"] = "380 upvotes · 90 comments · r/LocalLLaMA"
        prompts = []
        answer = json.dumps({"a": "A tenth of its stars came today, so 10% in one day.",
                             "b": "It leads the digest with 1,721 new stars today."})
        add_why([repo, post], lambda p: prompts.append(p) or answer)
        self.assertIn("10% of its stars came today", prompts[0])
        self.assertEqual(repo["why"], "A tenth of its stars came today, so 10% in one day.")
        self.assertIsNone(post["why"])

    def test_null_answer_leaves_no_sentence(self):
        items = [item("a", "A")]
        add_why(items, lambda p: '{"a": null}')
        self.assertIsNone(items[0]["why"])

    def test_broken_model_leaves_no_sentences(self):
        items = [item("a", "A")]

        def broken(prompt):
            raise RuntimeError("down")

        add_why(items, broken)
        self.assertIsNone(items[0]["why"])

    def test_model_is_off_without_key(self):
        self.assertIsNone(llm_from_env({"llm_model": "m"}, environ={}))
        self.assertIsNotNone(llm_from_env({"llm_model": "m"}, environ={"LLM_API_KEY": "k"}))


if __name__ == "__main__":
    unittest.main()
