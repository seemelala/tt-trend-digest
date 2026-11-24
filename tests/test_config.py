"""Config loading and the error messages users see."""

import os
import tempfile
import unittest

from helpers import ROOT

from trend_digest.config import ConfigError, check_config, load_config
from trend_digest.sources import SUPPORTED


class ConfigTest(unittest.TestCase):
    def test_shipped_configs_load(self):
        english = load_config(os.path.join(ROOT, "digest.toml"))
        self.assertEqual(len(english["sources"]), 6)
        chinese = load_config(os.path.join(ROOT, "presets", "zh.toml"))
        self.assertEqual(chinese["language"], "zh")
        self.assertEqual([s["use"] for s in chinese["sources"]],
                         ["weibo/trending", "douyin/trending", "github/trending"])

    def test_unknown_source_lists_supported_ones(self):
        with self.assertRaises(ConfigError) as caught:
            check_config({"sources": [{"use": "myspace/trending"}]})
        message = str(caught.exception)
        self.assertIn("myspace/trending", message)
        for use in SUPPORTED:
            self.assertIn(use, message)

    def test_unknown_key_and_bad_values(self):
        with self.assertRaises(ConfigError):
            check_config({"sorces": [], "sources": [{"use": "github/trending"}]})
        with self.assertRaises(ConfigError):
            check_config({"timezone": "Mars/Base", "sources": [{"use": "github/trending"}]})
        with self.assertRaises(ConfigError):
            check_config({"sources": [{"use": "github/trending", "limit": 0}]})

    def test_broken_toml_names_the_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as handle:
            handle.write("language = \n")
        try:
            with self.assertRaises(ConfigError) as caught:
                load_config(handle.name)
            self.assertIn(handle.name, str(caught.exception))
        finally:
            os.unlink(handle.name)


if __name__ == "__main__":
    unittest.main()
