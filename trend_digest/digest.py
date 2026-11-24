"""build_digest(): fetch every source, pick items, and render every channel.

This is the library entry point; the CLI and our own bot both call it. Steps:

1. Call each [[sources]] entry once, one after another (fetch failures and empty
   answers are recorded in usage.failed and do not stop the run).
2. Save today's numbers for every fetched item in state["snapshots"], then add
   "+N today" from yesterday's snapshot.
3. Pick items (see select.py), pick 3 keywords, and add "Why it matters" if a
   model function was given.
4. On Mondays (in the configured time zone) add the weekly list.
5. Render each channel's message body and the archive page.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .client import ApiError, api_fetcher
from .config import check_config, load_config
from .fmt import title_date, short_date
from .i18n import t
from .keywords import pick_keywords
from .render import render_payloads
from .render.html import day_page
from .select import add_deltas, all_items, cap_total, group_sections, pick_items
from .sources import describe, normalize
from .state import (mark_seen, normalize_state, previous_snapshot, prune,
                    record_snapshot, seen_ids)
from .weekly import build_weekly
from .why import add_why


class NotEnoughHistory(Exception):
    """A weekly digest was asked for but there are fewer than 2 days of snapshots."""


def resolve_config(config):
    return load_config(config) if isinstance(config, str) else check_config(config)


def local_now(now, config):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(ZoneInfo(config["timezone"]))


def failure(use, error):
    if isinstance(error, ApiError):
        return {"source": use, "reason": f"http_{error.status}" if error.status else "error",
                "detail": str(error.detail)}
    return {"source": use, "reason": "error", "detail": str(error)}


def fetch_all(config, fetch):
    """Call every source. Returns (fetched, usage)."""
    fetched, failed, calls, charged = [], [], 0, 0.0
    for source in config["sources"]:
        platform, action = source["use"].split("/", 1)
        calls += 1
        try:
            response = fetch(platform, action, source["params"])
        except Exception as error:  # one bad source must not stop the digest
            failed.append(failure(source["use"], error))
            continue
        charged += float((response.get("billing") or {}).get("charged_usd") or 0)
        items = normalize(source["use"], response, source["params"])
        if not items:
            failed.append({"source": source["use"], "reason": "empty"})
        fetched.append((source, items))
    usage = {"calls": calls, "charged_usd": round(charged, 6), "failed": failed}
    return fetched, usage


def daily_sections(config, fetched, state, today, local, exclude_ids):
    every_item = [item for _, items in fetched for item in items]
    add_deltas(every_item, previous_snapshot(state, today))
    record_snapshot(state, today, every_item)
    picks = pick_items(fetched, seen_ids(state, today) | set(exclude_ids or ()), config["min_items"])
    sections = cap_total(group_sections(picks, config["language"]), config["max_items"])
    for item in all_items(sections):
        describe(item, config["language"], local)
    return sections


def daily_message(config, digest):
    lang = config["language"]
    subtitle = ""
    if digest["keywords"]:
        subtitle = f"{t(lang, 'today')}: " + " · ".join(digest["keywords"])
    usage = digest["usage"]
    return {"lang": lang, "title": digest["title"], "subtitle": subtitle,
            "sections": digest["sections"], "site_url": config["site_url"],
            "footer": t(lang, "footer", calls=usage["calls"], usd=usage["charged_usd"])}


def weekly_message(config, weekly):
    lang = config["language"]
    start, end = (datetime.fromisoformat(d) for d in (weekly["start"], weekly["end"]))
    title = t(lang, "title_weekly", title=config["title"],
              start=short_date(start, lang), end=short_date(end, lang))
    sections = [{"id": "weekly-repos", "label": weekly["repos_label"],
                 "icon_url": "", "items": weekly["repos"]},
                {"id": "weekly-posts", "label": t(lang, "section.weekly_posts"),
                 "icon_url": "", "items": weekly["posts"]}]
    return {"lang": lang, "title": title, "subtitle": "", "site_url": config["site_url"],
            "sections": [s for s in sections if s["items"]],
            "footer": t(lang, "footer_weekly", days=weekly["days"])}


def wants_weekly(kind, local):
    return kind == "weekly" or (kind == "auto" and local.weekday() == 0)


def build_digest(config, api_key=None, state=None, now=None, llm=None, fetch=None,
                 *, kind="auto", exclude_ids=None):
    """Build one digest. See README "Use it as a library" for the returned dict.

    kind: "auto" (daily, plus the weekly list on Mondays), "daily" (never the
    weekly list) or "weekly" (only the weekly list, no API calls; raises
    NotEnoughHistory with under 2 days of snapshots).
    exclude_ids: extra item ids to leave out, on top of the 7-day memory.
    """
    config = resolve_config(config)
    local = local_now(now, config)
    today = local.date().isoformat()
    state = prune(normalize_state(state), today)
    if fetch is None and kind != "weekly":
        if not api_key:
            raise ValueError("EVERYINFRA_API_KEY is missing. Get a key at "
                             "https://everyinfra.com/?utm_source=github-template")
        fetch = api_fetcher(api_key)

    digest = {"version": 1, "date": today, "language": config["language"],
              "title": f"{config['title']} · {title_date(local, config['language'])}",
              "keywords": [], "sections": [], "weekly": None,
              "usage": {"calls": 0, "charged_usd": 0.0, "failed": []}}
    messages = []
    if kind != "weekly":
        fetched, digest["usage"] = fetch_all(config, fetch)
        digest["sections"] = daily_sections(config, fetched, state, today, local, exclude_ids)
        items = all_items(digest["sections"])
        digest["keywords"] = pick_keywords(items, llm, config["language"])
        add_why(items, llm, config["language"])
        mark_seen(state, items, today)
        messages.append(daily_message(config, digest))
    if wants_weekly(kind, local):
        digest["weekly"] = build_weekly(state, today, config["language"])
        if digest["weekly"]:
            messages.append(weekly_message(config, digest["weekly"]))
        elif kind == "weekly":
            raise NotEnoughHistory("not enough history for a weekly digest")

    digest["payloads"] = render_payloads(messages)
    digest["index_entry"] = {"date": today, "title": digest["title"], "keywords": digest["keywords"],
                             "count": len(all_items(digest["sections"]))}
    digest["page"] = {"path": f"archive/{today}.html", "html": day_page(digest)}
    digest["state"] = state
    digest["messages"] = messages
    return digest
