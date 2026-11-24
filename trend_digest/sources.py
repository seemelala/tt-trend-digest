"""Supported sources: how to call each one and how to turn its response into Items.

Every source is one `POST /api/v1/social` call with a platform, an action and
params. The response has a `results` list; the functions below map each result
to the same Item shape so the rest of the code does not care where it came from:

    {"id", "source", "title", "url", "summary", "metrics", "metric_text",
     "why", "extra"}

`id` is stable across days and starts with a source prefix, for example
`github:owner/repo` or `reddit:1y2gxo7`. The 7-day de-duplication uses it.
Items without an http(s) link are dropped.
"""

import hashlib
from urllib.parse import quote, urlparse

from .fmt import clip, full_number, relative_time, safe_url, short_number
from .i18n import t

SUMMARY_LIMIT = 220


def make_item(item_id, source, title, url, summary="", metrics=None, extra=None):
    """Build one Item. Returns None when the title or link is missing."""
    url = safe_url(url)
    title = clip(title, 200)
    if not url or not title:
        return None
    return {
        "id": item_id,
        "source": source,
        "title": title,
        "url": url,
        "summary": clip(summary, SUMMARY_LIMIT),
        "metrics": metrics or [],
        "metric_text": "",
        "why": None,
        "extra": extra or {},
    }


def metric(label, value, delta=None):
    return {"label": label, "value": value, "delta": delta}


def as_int(value):
    """Turn 345, '345' or '1,234' into an int; anything else into None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).replace(",", "").strip()
    return int(text) if text.isdigit() else None


# ---------------------------------------------------------------- normalizers

def github_items(results, source, params):
    items = []
    for row in results:
        name = row.get("full_name") or ""
        metrics = [metric("rank", as_int(row.get("rank")))]
        stars = as_int(row.get("star_count"))
        stars_today = as_int(row.get("stars_today"))
        if stars is not None:
            metrics.append(metric("stars", stars, stars_today))
        elif stars_today is not None:
            metrics.append(metric("stars_today", stars_today))
        extra = {"platform": "github", "rank": as_int(row.get("rank"))}
        if row.get("language"):
            extra["language"] = row["language"]
        items.append(make_item(f"github:{name}", source, name, row.get("url"),
                               row.get("description"), metrics, extra))
    return items


def producthunt_slug(url):
    path = urlparse(url or "").path.rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def producthunt_items(results, source, params):
    items = []
    for row in results:
        url = row.get("url") or row.get("product_url")
        metrics = [metric("rank", as_int(row.get("rank")))]
        votes = as_int(row.get("vote_count"))
        if votes is not None:
            metrics.append(metric("votes", votes))
        comments = as_int(row.get("comment_count"))
        if comments is not None:
            metrics.append(metric("comments", comments))
        title = row.get("name") or row.get("product_name") or row.get("title")
        items.append(make_item(f"producthunt:{producthunt_slug(url)}", source, title, url,
                               row.get("tagline") or row.get("description"), metrics,
                               {"platform": "producthunt"}))
    return items


def reddit_items(results, source, params):
    items = []
    for row in results:
        metrics = []
        upvotes = as_int(row.get("like_count"))
        if upvotes is not None:
            metrics.append(metric("upvotes", upvotes))
        comments = as_int(row.get("comment_count"))
        if comments is not None:
            metrics.append(metric("comments", comments))
        extra = {"platform": "reddit", "community": row.get("community") or ""}
        if row.get("flair"):
            extra["flair"] = row["flair"]
        items.append(make_item(f"reddit:{row.get('id')}", source, row.get("title"),
                               row.get("url"), row.get("text"), metrics, extra))
    return items


def twitter_items(results, source, params):
    country = str(params.get("country") or "us").upper()
    items = []
    for row in results:
        name = row.get("name") or ""
        url = "https://x.com/search?q=" + quote(name, safe="")
        metrics = [metric("rank", as_int(row.get("rank")))]
        if str(row.get("volume") or "").strip():
            metrics.append(metric("volume", str(row["volume"]).strip()))
        extra = {"platform": "twitter", "country": country, "rank": as_int(row.get("rank"))}
        items.append(make_item(f"x:{name.lower()}", source, name, url, "", metrics, extra))
    return items


def google_news_items(results, source, params):
    items = []
    for row in results:
        url = row.get("url") or ""
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        extra = {"platform": "google_news", "outlet": row.get("source") or "",
                 "published_at": row.get("published_at"),
                 "keyword": params.get("keyword") or ""}
        items.append(make_item(f"gnews:{digest}", source, row.get("title"), url,
                               row.get("text"), [], extra))
    return items


def weibo_items(results, source, params):
    items = []
    for row in results:
        metrics = [metric("rank", as_int(row.get("rank")))]
        heat = as_int(row.get("hot_value"))
        if heat is not None:
            metrics.append(metric("hot", heat))
        items.append(make_item(f"weibo:{row.get('title')}", source, row.get("title"),
                               row.get("url"), row.get("category"), metrics,
                               {"platform": "weibo"}))
    return items


def douyin_items(results, source, params):
    items = []
    for row in results:
        if row.get("is_pinned"):
            continue
        keyword = row.get("keyword") or ""
        url = "https://www.douyin.com/search/" + quote(keyword, safe="")
        metrics = [metric("rank", as_int(row.get("rank")))]
        heat = as_int(row.get("hot_value"))
        if heat is not None:
            metrics.append(metric("hot", heat))
        videos = as_int(row.get("video_count"))
        if videos is not None:
            metrics.append(metric("videos", videos))
        items.append(make_item(f"douyin:{row.get('sentence_id') or keyword}", source,
                               keyword, url, "", metrics, {"platform": "douyin"}))
    return items


def xiaohongshu_items(results, source, params):
    items = []
    for position, row in enumerate(results, start=1):
        metrics = [metric("rank", as_int(row.get("rank")) or position)]
        items.append(make_item(f"xhs:{row.get('id')}", source, row.get("title"), row.get("url"),
                               row.get("author_name"), metrics, {"platform": "xiaohongshu"}))
    return items


# --------------------------------------------------------------- source table

SOURCES = {
    "github/trending": github_items,
    "producthunt/trending": producthunt_items,
    "reddit/trending_posts": reddit_items,
    "reddit/subreddit_posts": reddit_items,
    "twitter/trending": twitter_items,
    "google_news/search": google_news_items,
    "weibo/trending": weibo_items,
    "douyin/trending": douyin_items,
    "xiaohongshu/trending": xiaohongshu_items,
}

SUPPORTED = tuple(SOURCES)

# Price per 1,000 calls in USD, for the README cost table only. The code always
# uses `billing.charged_usd` from each response for the real cost.
PRICE_PER_1K_USD = {
    "github/trending": 0.81,
    "producthunt/trending": 1.39,
    "reddit/trending_posts": 0.56,
    "reddit/subreddit_posts": 0.56,
    "twitter/trending": 0.56,
    "google_news/search": 0.79,
    "weibo/trending": 0.56,
    "douyin/trending": 0.56,
    "xiaohongshu/trending": 5.56,
}

ICON_DOMAINS = {
    "github": "github.com",
    "producthunt": "producthunt.com",
    "reddit": "reddit.com",
    "twitter": "x.com",
    "google_news": "news.google.com",
    "weibo": "weibo.com",
    "douyin": "douyin.com",
    "xiaohongshu": "xiaohongshu.com",
}


def platform_of(use):
    return use.split("/", 1)[0]


def icon_url(platform):
    domain = ICON_DOMAINS.get(platform, "everyinfra.com")
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"


def normalize(use, response, params):
    """Turn one API response into a list of Items (bad rows are skipped)."""
    results = response.get("results") or []
    rows = [row for row in results if isinstance(row, dict)]
    return [item for item in SOURCES[use](rows, use, params) if item]


# --------------------------------------------------------------- metric text

def value_of(item, label):
    for m in item["metrics"]:
        if m["label"] == label:
            return m
    return None


def has_number(item):
    """True when the item shows a count, not just its position on a list."""
    return any(m["label"] != "rank" and m["value"] is not None for m in item["metrics"])


def rank_part(item, lang):
    """['#3 on the list'], or [] when the source gave no position."""
    rank = value_of(item, "rank")
    return [t(lang, "rank", n=rank["value"])] if rank and rank["value"] is not None else []


def with_delta(text, m, lang):
    if m and m.get("delta"):
        return f"{text} ({t(lang, 'delta_today', n=full_number(m['delta']))})"
    return text


def github_text(item, lang, now):
    stars, today = value_of(item, "stars"), value_of(item, "stars_today")
    if stars:
        text = with_delta(t(lang, "stars", n=full_number(stars["value"])), stars, lang)
    elif today:
        text = "★ " + t(lang, "delta_today", n=full_number(today["value"]))
    else:
        text = t(lang, "github_rank", n=item["extra"]["rank"]) if item["extra"].get("rank") else ""
    return " · ".join(part for part in (text, item["extra"].get("language")) if part)


def producthunt_text(item, lang, now):
    parts = []
    votes, comments = value_of(item, "votes"), value_of(item, "comments")
    if votes:
        parts.append(with_delta(t(lang, "votes", n=full_number(votes["value"])), votes, lang))
    if comments:
        parts.append(t(lang, "comments", n=short_number(comments["value"], lang)))
    if not parts:
        parts += rank_part(item, lang)
    return " · ".join(parts)


def reddit_text(item, lang, now):
    parts = []
    upvotes, comments = value_of(item, "upvotes"), value_of(item, "comments")
    if upvotes:
        parts.append(with_delta(t(lang, "upvotes", n=short_number(upvotes["value"], lang)), upvotes, lang))
    if comments:
        parts.append(t(lang, "comments", n=short_number(comments["value"], lang)))
    community = item["extra"].get("community")
    if community:
        parts.append(f"r/{community}")
    return " · ".join(parts)


def twitter_text(item, lang, now):
    volume = value_of(item, "volume")
    if volume:
        return t(lang, "x_volume", n=volume["value"])
    if not item["extra"].get("rank"):
        return ""
    return t(lang, "x_rank", n=item["extra"]["rank"], country=item["extra"]["country"])


def google_news_text(item, lang, now):
    parts = [item["extra"].get("outlet") or ""]
    parts.append(relative_time(item["extra"].get("published_at"), now, lang))
    return " · ".join(p for p in parts if p)


def heat_text(item, lang, now):
    parts = []
    heat, videos = value_of(item, "hot"), value_of(item, "videos")
    if heat:
        parts.append(with_delta(t(lang, "hot", n=short_number(heat["value"], lang)), heat, lang))
    if videos:
        parts.append(t(lang, "videos", n=full_number(videos["value"])))
    if not parts:
        parts += rank_part(item, lang)
    return " · ".join(parts)


TEXT_BY_PLATFORM = {
    "github": github_text,
    "producthunt": producthunt_text,
    "reddit": reddit_text,
    "twitter": twitter_text,
    "google_news": google_news_text,
    "weibo": heat_text,
    "douyin": heat_text,
    "xiaohongshu": heat_text,
}


def describe(item, lang, now):
    """Fill item['metric_text'], e.g. '★ 12,480 (+1,240 today)'."""
    platform = item["extra"].get("platform") or platform_of(item["source"])
    item["metric_text"] = TEXT_BY_PLATFORM[platform](item, lang, now)
    return item


# Which metric gets a "+N today" from yesterday's snapshot.
TRACKED_METRIC = {"github": "stars", "producthunt": "votes", "reddit": "upvotes",
                  "weibo": "hot", "douyin": "hot"}
