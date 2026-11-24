"""Small formatting helpers: numbers, relative times, dates, safe links.

Kept separate so every renderer formats the same number the same way.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

WEEKDAYS_ZH = "一二三四五六日"

# Some publishers' own descriptions glue a year to the next sentence: "scale AI agents by 2028Getting
# AI agents live". Only a four-digit year that starts a word and is followed by a capitalised word gets
# a space; names such as 1Password, iPhone or YouTube stay as they are.
YEAR_GLUED_TO_WORD = re.compile(r"(?<![0-9A-Za-z])((?:19|20)\d\d)(?=[A-Z][a-z]{2,})")


def full_number(n):
    """12480 -> '12,480'."""
    return f"{int(n):,}"


def short_number(n, lang="en"):
    """Shorten big counts: 1240 -> '1.2k' (en) or 12103012 -> '1210.3 万' (zh)."""
    n = int(n)
    if lang == "zh":
        if n >= 100_000_000:
            return f"{n / 100_000_000:.1f} 亿"
        if n >= 10_000:
            return f"{n / 10_000:.1f} 万"
        return full_number(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def parse_time(value):
    """Parse an ISO 8601 time from the API. Returns an aware datetime or None."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def relative_time(value, now, lang="en"):
    """'2026-11-22T11:00:00Z' -> '3h ago'. Returns '' when the time is unknown."""
    from .i18n import t

    moment = parse_time(value)
    if moment is None:
        return ""
    minutes = int((now - moment).total_seconds() // 60)
    if minutes < 1:
        return t(lang, "just_now")
    if minutes < 60:
        return t(lang, "ago_minutes", n=minutes)
    if minutes < 48 * 60:
        return t(lang, "ago_hours", n=minutes // 60)
    return t(lang, "ago_days", n=minutes // (24 * 60))


def title_date(day, lang="en"):
    """A date for the digest title: 'Sun, Nov 23' or '11月23日 周日'."""
    if lang == "zh":
        return f"{day.month}月{day.day}日 周{WEEKDAYS_ZH[day.weekday()]}"
    return day.strftime("%a, %b ") + str(day.day)


def short_date(day, lang="en"):
    """'Nov 17' or '11月17日'."""
    if lang == "zh":
        return f"{day.month}月{day.day}日"
    return day.strftime("%b ") + str(day.day)


def safe_url(url):
    """Return the URL if it is http or https, otherwise None."""
    if not isinstance(url, str):
        return None
    url = url.strip()
    try:
        scheme = urlparse(url).scheme.lower()
    except ValueError:
        return None
    if scheme in ("http", "https") and "://" in url:
        return url
    return None


def clip(text, limit):
    """Cut text to `limit` characters, adding '…' when it was cut."""
    text = YEAR_GLUED_TO_WORD.sub(r"\1 ", " ".join(str(text or "").split()))
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"
