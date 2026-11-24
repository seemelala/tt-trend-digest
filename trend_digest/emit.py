"""`--emit` output: build the digest, send nothing, write one JSON document.

Made for callers that run this tool as a subprocess and do the sending
themselves. The JSON is the build_digest() result plus these top-level keys:

    date, kind, items [{id, platform, url, title}], discord (one body),
    telegram (the first body), telegram_parts (every body, in sending order),
    calls, cost_usd, skipped_platforms

A long digest is more than one Telegram message, so a caller that sends to
Telegram sends every body in `telegram_parts`, in order.
"""

import json
import sys
from datetime import datetime, timezone

from .render import bodies_for


def used_items(digest, kind):
    if kind == "weekly":
        weekly = digest.get("weekly") or {}
        items = weekly.get("repos", []) + weekly.get("posts", [])
    else:
        items = [item for section in digest["sections"] for item in section["items"]]
    return [{"id": i["id"], "platform": i["extra"].get("platform", ""), "url": i["url"],
             "title": i["title"]} for i in items]


def emit_document(digest, kind, date=None):
    """Return the emit JSON as a dict."""
    usage = digest["usage"]
    telegram = bodies_for("telegram", digest["messages"][0])
    doc = dict(digest)
    doc.update({
        "date": date or datetime.now(timezone.utc).date().isoformat(),
        "kind": kind,
        "items": used_items(digest, kind),
        "discord": digest["payloads"]["discord"][0],
        "telegram": telegram[0],
        "telegram_parts": telegram,
        "calls": usage["calls"],
        "cost_usd": usage["charged_usd"],
        "skipped_platforms": [f["source"] for f in usage["failed"]],
    })
    return doc


def write_document(doc, target):
    """Write to a file path, or to stdout when target is '-'."""
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    if target == "-":
        sys.stdout.write(text)
        sys.stdout.flush()
        return
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)


def why_empty(digest, kind):
    """A reason to refuse output (exit 1), or None when the digest is usable."""
    usage = digest["usage"]
    if (kind != "weekly" and not digest["sections"] and usage["calls"]
            and len(usage["failed"]) == usage["calls"]):
        return "every source failed or came back empty: " + ", ".join(
            f"{f['source']} ({f['reason']})" for f in usage["failed"])
    if not used_items(digest, kind):
        return "no items to send (everything was sent in the last 7 days, or nothing came back)"
    return None
