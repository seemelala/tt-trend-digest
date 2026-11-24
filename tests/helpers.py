"""Shared test helpers: saved API responses and a fake fetch()."""

import copy
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


def fixture_fetch(overrides=None, calls=None):
    """fetch() that answers from tests/fixtures; `overrides` maps 'platform.action' -> response."""
    overrides = overrides or {}

    def fetch(platform, action, params):
        key = f"{platform}.{action}"
        if calls is not None:
            calls.append((platform, action, dict(params)))
        if key in overrides:
            value = overrides[key]
            if isinstance(value, Exception):
                raise value
            return copy.deepcopy(value)
        return load_fixture(f"{key}.json")

    return fetch


def at(day, hour=13):
    """A UTC datetime on 'YYYY-MM-DD'."""
    year, month, date = (int(x) for x in day.split("-"))
    return datetime(year, month, date, hour, tzinfo=timezone.utc)


def default_config_path():
    return os.path.join(ROOT, "digest.toml")


def every_source_config():
    """A config that uses all eight saved responses."""
    return {
        "language": "en",
        "max_items": 12,
        "sources": [
            {"use": "github/trending", "limit": 3},
            {"use": "producthunt/trending", "limit": 3},
            {"use": "reddit/trending_posts", "limit": 1},
            {"use": "reddit/subreddit_posts", "limit": 2,
             "params": {"subreddit": "LocalLLaMA", "sort": "top", "date_range": "past_day"}},
            {"use": "twitter/trending", "limit": 3, "params": {"country": "us"}},
            {"use": "google_news/search", "limit": 2,
             "params": {"keyword": "AI agents", "time_window": "day"}},
        ],
    }


def charged(name):
    return load_fixture(name)["billing"]["charged_usd"]
