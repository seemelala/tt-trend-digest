"""Pick which items go into today's digest and group them into sections.

Rules (from the digest spec):
- each [[sources]] entry gives at most its `limit` items;
- items sent in the last 7 days are skipped, and so are repeats within one run;
- inside a source, items that show a count come before items that only show a rank;
- sources of the same platform share one section (two subreddits = one Reddit section);
- when a source comes back empty or short, the other sources may each add up to
  EXTRA_PER_SOURCE more items, one per source per round in config order, until the
  digest holds `min_items` (or as many as the limits add up to, if that is less);
- the whole digest holds at most `max_items` items; an empty section is left out.
"""

from .i18n import t
from .sources import TRACKED_METRIC, has_number, icon_url, platform_of


def add_deltas(items, yesterday):
    """Set the "+N today" delta from yesterday's snapshot, unless the API gave one."""
    for item in items:
        label = TRACKED_METRIC.get(item["extra"].get("platform"))
        old = yesterday.get(item["id"], {}).get("values", {})
        for m in item["metrics"]:
            if m["label"] != label or m["delta"] is not None or m["value"] is None:
                continue
            if label in old and m["value"] > old[label]:
                m["delta"] = m["value"] - old[label]


EXTRA_PER_SOURCE = 2


def fresh_items(items, skip_ids):
    """New items only, items with a count first, original order kept."""
    seen, fresh = set(skip_ids), []
    for item in items:
        if item["id"] not in seen:
            seen.add(item["id"])
            fresh.append(item)
    fresh.sort(key=lambda item: not has_number(item))
    return fresh


def fill_up(picks, spare, taken, goal):
    """Add spare items, one per source per round in config order, until `goal` items."""
    total = sum(len(chosen) for _, chosen in picks)
    added = True
    while total < goal and added:
        added = False
        for (_, chosen), more in zip(picks, spare):
            while more and total < goal:
                item = more.pop(0)
                if item["id"] in taken:
                    continue
                chosen.append(item)
                taken.add(item["id"])
                total += 1
                added = True
                break


def pick_items(fetched, skip_ids, min_items=0, *, fill_to=None):
    """`fetched` = [(source_config, items)]. Returns [(source_config, picked)]."""
    taken = set(skip_ids)
    picks, spare = [], []
    for source, items in fetched:
        fresh = fresh_items(items, taken)
        limit = source["limit"]
        chosen = fresh[:limit]
        taken.update(item["id"] for item in chosen)
        picks.append((source, chosen))
        spare_limit = EXTRA_PER_SOURCE if fill_to is None else fill_to
        spare.append(fresh[limit:limit + spare_limit])
    goal = min(min_items, sum(source["limit"] for source, _ in fetched)) if fill_to is None else fill_to
    fill_up(picks, spare, taken, goal)
    return picks


def reddit_label(sources, lang):
    names = []
    for source in sources:
        if source["use"] == "reddit/trending_posts":
            names.append(t(lang, "section.reddit_trending"))
        elif source["params"].get("subreddit"):
            names.append("r/" + str(source["params"]["subreddit"]))
    base = t(lang, "section.reddit")
    return f"{base} · {', '.join(names)}" if names else base


def section_label(platform, sources, lang):
    """A section title such as 'Reddit · r/LocalLLaMA, r/MachineLearning'."""
    custom = next((s["label"] for s in sources if s["label"]), "")
    if custom:
        return custom
    if platform == "reddit":
        return reddit_label(sources, lang)
    if platform == "twitter":
        country = str(sources[0]["params"].get("country") or "us").upper()
        return t(lang, "section.twitter", country=country)
    if platform == "google_news" and len(sources) == 1 and sources[0]["params"].get("keyword"):
        return f'{t(lang, "section.google_news")} · "{sources[0]["params"]["keyword"]}"'
    return t(lang, f"section.{platform}")


def group_sections(picks, lang):
    """Merge picks of the same platform into sections, in config order."""
    order, grouped = [], {}
    for source, items in picks:
        platform = platform_of(source["use"])
        if platform not in grouped:
            order.append(platform)
            grouped[platform] = {"sources": [], "items": []}
        grouped[platform]["sources"].append(source)
        grouped[platform]["items"].extend(items)
    sections = []
    for platform in order:
        group = grouped[platform]
        if not group["items"]:
            continue
        icon = next((s["icon_url"] for s in group["sources"] if s["icon_url"]), "") or icon_url(platform)
        sections.append({"id": platform, "label": section_label(platform, group["sources"], lang),
                         "icon_url": icon, "items": group["items"]})
    return sections


def cap_total(sections, max_items):
    """Drop items from the end of the digest until it holds at most max_items."""
    total = sum(len(s["items"]) for s in sections)
    for section in reversed(sections):
        while total > max_items and section["items"]:
            section["items"].pop()
            total -= 1
    return [s for s in sections if s["items"]]


def all_items(sections):
    return [item for section in sections for item in section["items"]]
