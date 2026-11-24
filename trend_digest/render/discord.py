"""Discord message body: works for a webhook and for `POST /channels/{id}/messages`.

Only fields both endpoints accept are used: `embeds`, `components`,
`allowed_mentions` (no `content`).

- Embed 1 holds the title and the keyword line.
- Then one embed per section: author.name = section name, author.icon_url = its
  icon, and the items in the description:
      1\\. **[title](link)** · ★ 12,480 (+1,240 today)
      summary
      *Why it matters:* ...
- The last embed has the footer, and its description ends with text links, so
  the links still show if the buttons are dropped.
- `components` holds two link buttons (style 5).

Limits (Discord docs, "Embed Limits"): at most 10 embeds, title 256, description
4,096, author name 256, footer 2,048, and all of those together 6,000 characters.
Each embed gets a different `url`, because Discord shows only the first of
several embeds that share one.
"""

import re

from .common import links_for, shrink_until, why_label

BRAND_COLOR = 0x0ACAB5
MAX_EMBEDS = 10
MAX_TOTAL = 6000
MAX_DESCRIPTION = 4096
MAX_TITLE = 256
MAX_FOOTER = 2048

MARKDOWN_SPECIAL = re.compile(r"([\\*_~`|\[\]<>#])")


def escape(text):
    """Escape Discord markdown so titles show literally."""
    return MARKDOWN_SPECIAL.sub(r"\\\1", text or "")


def link_target(url):
    return url.replace("(", "%28").replace(")", "%29").replace(" ", "%20")


def link_text(text):
    """Text for the inside of a masked link `[text](url)`.

    Discord shows backslash escapes literally inside link text, so nothing is
    escaped here. Square brackets would end the link early and `*` would break
    the bold around it, so they are swapped for look-alikes.
    """
    text = " ".join((text or "").split())
    return text.replace("[", "(").replace("]", ")").replace("*", "∗")


def item_block(number, item, why):
    # "1\." and not "1.": a line that starts with "1. " becomes a list, and the
    # rest of the line (the metric) then drops to the next line.
    head = f"{number}\\. **[{link_text(item['title'])}]({link_target(item['url'])})**"
    if item.get("metric_text"):
        head += f" · {escape(item['metric_text'])}"
    lines = [head]
    if item.get("summary"):
        lines.append(escape(item["summary"]))
    if item.get("why"):
        lines.append(f"*{why}:* {escape(item['why'])}")
    return "\n".join(lines)


def section_embed(section, anchor, why):
    blocks = [item_block(n, item, why) for n, item in enumerate(section["items"], 1)]
    return {
        "author": {"name": section["label"][:MAX_TITLE], "icon_url": section["icon_url"]},
        "url": f"{anchor}#{section['id']}",
        "color": BRAND_COLOR,
        "description": "\n\n".join(blocks),
    }


def build(message):
    links = links_for(message, "discord")
    anchor = links[-1][1]
    header = {"title": message["title"][:MAX_TITLE], "url": anchor, "color": BRAND_COLOR}
    if message.get("subtitle"):
        header["description"] = escape(message["subtitle"])
    embeds = [header]
    for section in message["sections"][: MAX_EMBEDS - 1]:
        embeds.append(section_embed(section, anchor, why_label(message)))
    last = embeds[-1]
    text_links = " · ".join(f"[{label}]({url})" for label, url in links)
    last["description"] = (last.get("description", "") + "\n\n" + text_links).strip()
    last["footer"] = {"text": message["footer"][:MAX_FOOTER]}
    buttons = [{"type": 2, "style": 5, "label": label, "url": url} for label, url in links]
    return {"embeds": embeds,
            "components": [{"type": 1, "components": buttons}],
            "allowed_mentions": {"parse": []}}


def embed_text_size(embed):
    """Characters Discord counts toward the 6,000 total for one embed."""
    size = len(embed.get("title", "")) + len(embed.get("description", ""))
    size += len(embed.get("author", {}).get("name", ""))
    size += len(embed.get("footer", {}).get("text", ""))
    for field in embed.get("fields", []):
        size += len(field.get("name", "")) + len(field.get("value", ""))
    return size


def fits(body):
    embeds = body["embeds"]
    return (len(embeds) <= MAX_EMBEDS
            and sum(embed_text_size(e) for e in embeds) <= MAX_TOTAL
            and all(len(e.get("description", "")) <= MAX_DESCRIPTION for e in embeds))


def render(message):
    return shrink_until(message, build, fits)
