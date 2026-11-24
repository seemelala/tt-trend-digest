"""The command line, run as a subprocess the way callers use it."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser

from helpers import FIXTURES, ROOT

EMIT_KEYS = {"date", "kind", "items", "discord", "telegram", "telegram_parts", "calls", "cost_usd",
             "skipped_platforms"}


def run_cli(args, fixtures=FIXTURES, extra_env=None):
    env = {k: v for k, v in os.environ.items()
           if not k.endswith("_WEBHOOK_URL") and not k.startswith(("TELEGRAM_", "LLM_", "EVERYINFRA_"))
           and k != "GITHUB_REPOSITORY"}
    env["TREND_DIGEST_FIXTURES"] = fixtures
    env.update(extra_env or {})
    return subprocess.run([sys.executable, "-m", "trend_digest", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state = os.path.join(self.tmp, "state.json")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_dry_run_prints_a_digest(self):
        result = run_cli(["--dry-run", "--state", self.state, "--date", "2026-11-24"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("EveryInfra Trend Digest · Tue, Nov 24", result.stdout)
        self.assertIn("Message body sizes:", result.stdout)
        self.assertFalse(os.path.exists(self.state), "dry run writes no state")

    def test_dry_run_chinese_preset(self):
        result = run_cli(["--dry-run", "--config", "presets/zh.toml", "--state", self.state])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("微博热搜", result.stdout)

    def test_normal_run_writes_site_and_state(self):
        site = os.path.join(self.tmp, "docs")
        result = run_cli(["--state", self.state, "--site", site, "--date", "2026-11-24"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.path.exists(self.state))
        for path in ("index.html", "archive/2026-11-24.html", "data/2026-11-24.json",
                     "data/index.json", "assets/style.css", ".nojekyll"):
            self.assertTrue(os.path.exists(os.path.join(site, path)), path)
        with open(os.path.join(site, "index.html"), encoding="utf-8") as handle:
            HTMLParser().feed(handle.read())

    def test_emit_to_file(self):
        out = os.path.join(self.tmp, "out.json")
        result = run_cli(["--emit", out, "--state", self.state, "--date", "2026-11-24"])
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(out, encoding="utf-8") as handle:
            doc = json.load(handle)
        self.assertTrue(EMIT_KEYS <= set(doc), EMIT_KEYS - set(doc))
        self.assertEqual(doc["kind"], "daily")
        self.assertEqual(doc["date"], "2026-11-24")
        self.assertIsInstance(doc["discord"], dict)
        self.assertNotIn("content", doc["discord"])
        self.assertEqual(doc["telegram"]["parse_mode"], "HTML")
        self.assertEqual(doc["telegram_parts"], [doc["telegram"]])
        self.assertEqual(doc["skipped_platforms"], ["producthunt/trending"])
        self.assertEqual(doc["calls"], 6)
        self.assertEqual(doc["cost_usd"], doc["usage"]["charged_usd"])
        self.assertTrue(all(":" in item["id"] and item["platform"] for item in doc["items"]))
        self.assertTrue(os.path.exists(self.state), "emit writes state back")

    def test_seen_ids_are_left_out(self):
        first = os.path.join(self.tmp, "first.json")
        run_cli(["--emit", first, "--state", os.path.join(self.tmp, "a.json"), "--date", "2026-11-24"])
        with open(first, encoding="utf-8") as handle:
            seen = [item["id"] for item in json.load(handle)["items"]][:4]
        seen_file = os.path.join(self.tmp, "seen.json")
        with open(seen_file, "w", encoding="utf-8") as handle:
            json.dump(seen, handle)
        out = os.path.join(self.tmp, "out.json")
        result = run_cli(["--emit", out, "--seen", seen_file, "--state", self.state, "--date", "2026-11-24"])
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(out, encoding="utf-8") as handle:
            emitted = {item["id"] for item in json.load(handle)["items"]}
        self.assertEqual(emitted & set(seen), set())

    def test_all_sources_empty_exits_1_without_output(self):
        empty_dir = os.path.join(self.tmp, "empty")
        os.makedirs(empty_dir)
        with open(os.path.join(FIXTURES, "producthunt.trending.json"), encoding="utf-8") as handle:
            empty = handle.read()
        for name in ("github.trending", "producthunt.trending", "reddit.subreddit_posts", "google_news.search"):
            with open(os.path.join(empty_dir, f"{name}.json"), "w", encoding="utf-8") as handle:
                handle.write(empty)
        out = os.path.join(self.tmp, "out.json")
        result = run_cli(["--emit", out, "--state", self.state], fixtures=empty_dir)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(os.path.exists(out))
        self.assertIn("every source failed or came back empty", result.stderr)

    def test_emit_to_stdout_is_json_only(self):
        result = run_cli(["--emit", "-", "--state", self.state, "--date", "2026-11-24"])
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = json.loads(result.stdout)
        self.assertTrue(EMIT_KEYS <= set(doc))
        self.assertIn("producthunt/trending", result.stderr)

    def test_weekly_without_history_exits_1(self):
        out = os.path.join(self.tmp, "out.json")
        result = run_cli(["--emit", out, "--kind", "weekly", "--state", self.state])
        self.assertEqual(result.returncode, 1)
        self.assertIn("not enough history for a weekly digest", result.stderr)
        self.assertFalse(os.path.exists(out))

    def test_missing_key_message(self):
        result = run_cli(["--dry-run", "--state", self.state], fixtures="")
        self.assertEqual(result.returncode, 1)
        self.assertIn("EVERYINFRA_API_KEY is not set", result.stderr)


class TemplateCopyTest(unittest.TestCase):
    """The template repository commits its demo archive and 7-day memory; copies get those files."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state = os.path.join(self.tmp, "state.json")
        self.site = os.path.join(self.tmp, "docs")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_in(self, repository, day):
        result = run_cli(["--state", self.state, "--site", self.site, "--date", day],
                         extra_env={"GITHUB_REPOSITORY": repository})
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(self.state, encoding="utf-8") as handle:
            state = json.load(handle)
        with open(os.path.join(self.site, "data", "index.json"), encoding="utf-8") as handle:
            index = json.load(handle)
        return state, index

    def test_a_copy_drops_the_demo_memory_and_archive(self):
        self.run_in("everyinfra/trend-digest", "2026-11-24")
        state, index = self.run_in("someone/my-digest", "2026-11-25")
        self.assertEqual(state["repository"], "someone/my-digest")
        self.assertEqual(set(state["seen"].values()), {"2026-11-25"})
        self.assertEqual([(e["date"], e["repository"]) for e in index], [("2026-11-25", "someone/my-digest")])
        self.assertFalse(os.path.exists(os.path.join(self.site, "archive", "2026-11-24.html")))
        self.assertFalse(os.path.exists(os.path.join(self.site, "data", "2026-11-24.json")))
        self.assertTrue(os.path.exists(os.path.join(self.site, "archive", "2026-11-25.html")))

    def test_the_same_repository_keeps_its_memory_and_archive(self):
        self.run_in("someone/my-digest", "2026-11-24")
        state, index = self.run_in("someone/my-digest", "2026-11-25")
        self.assertIn("2026-11-24", set(state["seen"].values()))
        self.assertEqual([e["date"] for e in index], ["2026-11-25", "2026-11-24"])
        self.assertTrue(os.path.exists(os.path.join(self.site, "archive", "2026-11-24.html")))


if __name__ == "__main__":
    unittest.main()
