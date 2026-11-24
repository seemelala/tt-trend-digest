"""The Monday weekly list, built only from the saved daily snapshots.

- Repositories: the 10 with the most stars gained over the last 7 days. When the
  snapshots have no star counts (the GitHub source does not always send them),
  rank by the number of days each repository was on GitHub trending instead.
- Posts: the 5 with the most comments (Reddit and Product Hunt).

No weekly list is made with fewer than 2 days of snapshots.
"""

from datetime import date, timedelta

from .fmt import full_number, short_number
from .i18n import t
from .sources import make_item

REPO_COUNT = 10
POST_COUNT = 5
MIN_DAYS = 2


def week_days(state, today):
    """Snapshot dates within the 7 days ending today, oldest first."""
    end = date.fromisoformat(today)
    start = end - timedelta(days=6)
    return sorted(d for d in state["snapshots"] if start <= date.fromisoformat(d) <= end)


def history(state, days, platforms):
    """id -> list of (day, row) for rows of the given platforms."""
    rows = {}
    for day in days:
        for item_id, row in state["snapshots"][day].items():
            if row.get("platform") in platforms:
                rows.setdefault(item_id, []).append((day, row))
    return rows


def star_gain(points):
    stars = [row["values"]["stars"] for _, row in points if "stars" in row["values"]]
    today_counts = [row["values"].get("stars_today", 0) for _, row in points]
    if len(stars) >= 2:
        return max(stars) - min(stars)
    return sum(today_counts) or None


def as_item(item_id, row, metric_text):
    item = make_item(item_id, row.get("source", ""), row.get("title"), row.get("url"))
    if item:
        item["metric_text"] = metric_text
        item["extra"]["platform"] = row.get("platform", "")
    return item


def top_repos(state, days, lang):
    rows = history(state, days, {"github"})
    gains = {i: star_gain(p) for i, p in rows.items()}
    if any(gains.values()):
        ranked = sorted((i for i in rows if gains[i]), key=lambda i: -gains[i])[:REPO_COUNT]
        label = t(lang, "section.weekly_repos")
        texts = {i: t(lang, "stars_week", n=full_number(gains[i])) for i in ranked}
    else:
        ranked = sorted(rows, key=lambda i: -len(rows[i]))[:REPO_COUNT]
        label = t(lang, "section.weekly_repos_days")
        texts = {i: t(lang, "days_on_list", n=len(rows[i]), total=len(days)) for i in ranked}
    items = [as_item(i, rows[i][-1][1], texts[i]) for i in ranked]
    return label, [item for item in items if item]


def top_posts(state, days, lang):
    rows = history(state, days, {"reddit", "producthunt"})
    comments = {i: max(r["values"].get("comments", 0) for _, r in p) for i, p in rows.items()}
    ranked = sorted((i for i in rows if comments[i]), key=lambda i: -comments[i])[:POST_COUNT]
    items = [as_item(i, rows[i][-1][1], t(lang, "comments", n=short_number(comments[i], lang)))
             for i in ranked]
    return [item for item in items if item]


def build_weekly(state, today, lang):
    """Return {"repos", "posts", "repos_label", "days"} or None if history is short."""
    days = week_days(state, today)
    if len(days) < MIN_DAYS:
        return None
    repos_label, repos = top_repos(state, days, lang)
    posts = top_posts(state, days, lang)
    if not repos and not posts:
        return None
    return {"repos": repos, "posts": posts, "repos_label": repos_label,
            "start": days[0], "end": days[-1], "days": len(days)}
