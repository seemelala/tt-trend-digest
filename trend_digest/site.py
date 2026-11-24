"""Write the web archive into the GitHub Pages folder (default: docs/).

Files written on each run:
    docs/archive/YYYY-MM-DD.html   the day's page
    docs/index.html                newest day in full, earlier days listed
    docs/data/YYYY-MM-DD.json      the day's data (no message bodies, no state)
    docs/data/index.json           one entry per day, newest first
    docs/assets/style.css, docs/.nojekyll   created when missing

Each index entry records the repository that wrote it. In a copy of the template, the days that
the template's demo wrote are deleted on the first run (see origin.py).
"""

import json
import os

from . import origin
from .render.html import index_page
from .style import STYLE_CSS

DROPPED_KEYS = ("payloads", "page", "state", "messages")


def page_data(digest):
    """The digest without message bodies, page HTML and state."""
    return {k: v for k, v in digest.items() if k not in DROPPED_KEYS}


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def write_json(path, data):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, ValueError):
        return default


def drop_demo_days(site_dir, entries):
    """Delete the pages of the days the template's demo wrote; return the other entries."""
    kept = []
    for entry in entries:
        if not origin.from_demo(entry.get("repository")):
            kept.append(entry)
            continue
        for path in (os.path.join(site_dir, "archive", f"{entry.get('date')}.html"),
                     os.path.join(site_dir, "data", f"{entry.get('date')}.json")):
            if os.path.exists(path):
                os.remove(path)
    return kept


def merged_index(old, entry):
    entries = [e for e in old if e.get("date") != entry["date"]]
    entries.append(entry)
    return sorted(entries, key=lambda e: e["date"], reverse=True)


def ensure_static_files(site_dir):
    css = os.path.join(site_dir, "assets", "style.css")
    if not os.path.exists(css):
        write_text(css, STYLE_CSS)
    nojekyll = os.path.join(site_dir, ".nojekyll")
    if not os.path.exists(nojekyll):
        write_text(nojekyll, "")


def write_site(digest, site_dir, site_title):
    """Write all archive files for this digest. Returns the paths written."""
    ensure_static_files(site_dir)
    index_file = os.path.join(site_dir, "data", "index.json")
    # Before today's page is written: the demo may have written a page for the same date.
    old = drop_demo_days(site_dir, [e for e in read_json(index_file, []) if isinstance(e, dict)])
    day = digest["date"]
    day_path = os.path.join(site_dir, digest["page"]["path"])
    write_text(day_path, digest["page"]["html"])
    write_json(os.path.join(site_dir, "data", f"{day}.json"), page_data(digest))
    entry = dict(digest["index_entry"])
    if origin.current():
        entry["repository"] = origin.current()
    entries = merged_index(old, entry)
    write_json(index_file, entries)
    latest = read_json(os.path.join(site_dir, "data", f"{entries[0]['date']}.json"), None)
    index_path = os.path.join(site_dir, "index.html")
    write_text(index_path, index_page(entries, latest, digest["language"], site_title))
    return [day_path, index_path]
