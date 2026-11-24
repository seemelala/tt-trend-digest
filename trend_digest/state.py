"""What the digest remembers between runs, kept in one small JSON file.

    {"version": 1,
     "repository": "owner/name",                          # where it was written (GitHub Actions)
     "seen": {"github:owner/repo": "2026-11-23", ...},   # first day each item was sent
     "snapshots": {"2026-11-23": {"github:owner/repo": {...}, ...}, ...}}

`seen` stops the same item from being sent again within 7 days.
`snapshots` keeps each day's numbers for every fetched item (not only the ones
sent), so tomorrow can show "+N today" and Monday can build the weekly list.
`repository` lets a copy of the template tell the demo's memory from its own.
"""

import copy
import json
import os
from datetime import date, timedelta

SEEN_DAYS = 7
SNAPSHOT_DAYS = 8


def empty_state():
    return {"version": 1, "seen": {}, "snapshots": {}}


def load_state(path):
    """Read the state file. A missing or broken file gives an empty state."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, ValueError):
        return empty_state()
    return normalize_state(data)


def save_state(path, state):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write("\n")


def normalize_state(data):
    """Return a deep copy with the expected keys, ignoring anything malformed."""
    state = empty_state()
    if isinstance(data, dict):
        if isinstance(data.get("repository"), str) and data["repository"]:
            state["repository"] = data["repository"]
        if isinstance(data.get("seen"), dict):
            state["seen"] = copy.deepcopy(data["seen"])
        if isinstance(data.get("weekly_project_history"), dict):
            state["weekly_project_history"] = {
                key: day for key, day in data["weekly_project_history"].items()
                if isinstance(day, str)
            }
        if isinstance(data.get("snapshots"), dict):
            state["snapshots"] = copy.deepcopy(data["snapshots"])
    return state


def days_between(earlier, later):
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


def prune(state, today):
    """Forget items seen 7 or more days ago and snapshots older than 8 days."""
    state["seen"] = {k: d for k, d in state["seen"].items() if days_between(d, today) < SEEN_DAYS}
    state["snapshots"] = {d: s for d, s in state["snapshots"].items()
                          if 0 <= days_between(d, today) < SNAPSHOT_DAYS or d > today}
    return state


def seen_ids(state, today):
    return {k for k, d in state["seen"].items() if 0 <= days_between(d, today) < SEEN_DAYS}


def mark_seen(state, items, today):
    for item in items:
        state["seen"].setdefault(item["id"], today)


def snapshot_row(item):
    """The few fields of an item worth keeping for tomorrow and the weekly list."""
    values = {m["label"]: m["value"] for m in item["metrics"] if m["value"] is not None}
    return {"title": item["title"], "url": item["url"], "source": item["source"],
            "platform": item["extra"].get("platform", ""), "values": values}


def record_snapshot(state, today, items):
    day = state["snapshots"].setdefault(today, {})
    for item in items:
        day[item["id"]] = snapshot_row(item)


def previous_snapshot(state, today):
    """The snapshot of the day before `today`, or {}."""
    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    return state["snapshots"].get(yesterday, {})
