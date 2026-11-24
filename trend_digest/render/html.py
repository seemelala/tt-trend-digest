"""Static HTML pages for the web archive (GitHub Pages).

- `day_page(data)`: one digest, saved as docs/archive/YYYY-MM-DD.html.
- `index_page(entries, latest)`: docs/index.html, newest day shown in full and a
  list of earlier days below.

Every text is HTML-escaped and only http/https links are written. The pages use
one small stylesheet (docs/assets/style.css), system fonts, and no scripts.
"""

from html import escape

from ..fmt import safe_url
from ..i18n import t
from ..links import TEMPLATE_URL, tracked


def link_or_text(url, label):
    url = safe_url(url)
    if not url:
        return escape(label)
    return f'<a href="{escape(url)}" rel="noopener">{escape(label)}</a>'


def item_html(item, lang):
    parts = [f'<li><p class="item-title">{link_or_text(item.get("url"), item.get("title", ""))}']
    if item.get("metric_text"):
        parts.append(f' <span class="metric">{escape(item["metric_text"])}</span>')
    parts.append("</p>")
    if item.get("summary"):
        parts.append(f'<p class="summary">{escape(item["summary"])}</p>')
    if item.get("why"):
        parts.append(f'<p class="why"><strong>{escape(t(lang, "why"))}:</strong> {escape(item["why"])}</p>')
    parts.append("</li>")
    return "".join(parts)


def section_html(section, lang):
    items = "\n".join(item_html(item, lang) for item in section["items"])
    return (f'<section id="{escape(section["id"])}">\n<h2>{escape(section["label"])}</h2>\n'
            f"<ol>\n{items}\n</ol>\n</section>")


def weekly_sections(data):
    weekly = data.get("weekly")
    if not weekly:
        return []
    lang = data["language"]
    found = [("weekly-repos", weekly.get("repos_label") or t(lang, "section.weekly_repos"), weekly["repos"]),
             ("weekly-posts", t(lang, "section.weekly_posts"), weekly["posts"])]
    return [{"id": i, "label": label, "items": items} for i, label, items in found if items]


def digest_body(data, heading_level="h1"):
    lang = data["language"]
    keywords = " · ".join(data.get("keywords") or [])
    header = f'<header>\n<{heading_level}>{escape(data["title"])}</{heading_level}>\n'
    if keywords:
        header += f'<p class="keywords">{escape(t(lang, "today"))}: {escape(keywords)}</p>\n'
    header += "</header>"
    sections = [section_html(s, lang) for s in data["sections"] + weekly_sections(data)]
    return header + "\n" + "\n".join(sections)


def footer_html(data):
    lang = data["language"]
    usage = data.get("usage") or {}
    note = t(lang, "footer", calls=usage.get("calls", 0), usd=usage.get("charged_usd", 0.0))
    run_own = link_or_text(tracked(TEMPLATE_URL, "web"), t(lang, "run_own"))
    return f'<footer>\n<p>{escape(note)}</p>\n<p>{run_own}</p>\n</footer>'


def page(title, description, lang, css_href, body):
    html_lang = "zh-CN" if lang == "zh" else "en"
    return f"""<!doctype html>
<html lang="{html_lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<link rel="stylesheet" href="{escape(css_href)}">
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""


def describe(data):
    keywords = ", ".join(data.get("keywords") or []) or data["title"]
    return t(data["language"], "page_description", date=data["date"], keywords=keywords)


def day_page(data):
    back = f'<nav class="archive"><a href="../index.html">{escape(t(data["language"], "archive"))}</a></nav>'
    body = digest_body(data) + "\n" + back + "\n" + footer_html(data)
    return page(data["title"], describe(data), data["language"], "../assets/style.css", body)


def archive_list(entries, lang):
    rows = []
    for entry in entries:
        href = f'archive/{escape(entry["date"])}.html'
        keywords = " · ".join(entry.get("keywords") or [])
        count = t(lang, "items", n=entry.get("count", 0))
        rows.append(f'<li><a href="{href}">{escape(entry["date"])}</a> '
                    f'<span class="metric">{escape(keywords)} · {escape(count)}</span></li>')
    return "\n".join(rows)


def index_page(entries, latest, lang="en", site_title="EveryInfra Trend Digest"):
    """`entries` newest first; `latest` is the newest day's data or None."""
    if not latest:
        body = f"<header><h1>{escape(site_title)}</h1></header>\n<p>{escape(t(lang, 'archive_empty'))}</p>"
        return page(site_title, site_title, lang, "assets/style.css", body)
    lang = latest["language"]
    body = digest_body(latest)
    earlier = [e for e in entries if e["date"] != latest["date"]]
    if earlier:
        body += (f'\n<nav class="archive">\n<h2>{escape(t(lang, "archive_heading"))}</h2>\n'
                 f"<ul>\n{archive_list(earlier, lang)}\n</ul>\n</nav>")
    body += "\n" + footer_html(latest)
    return page(latest["title"], describe(latest), lang, "assets/style.css", body)
