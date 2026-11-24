"""Feishu (Lark) custom bot body: an interactive card.

Card JSON 2.0 as in the Feishu "custom bot" guide: a header (title and the
keyword line as subtitle), one markdown element per section, then two buttons
that open URLs. Custom bots can only open URLs from buttons; they cannot call
back. The whole request body must be at most 20 KB.

`send` adds `timestamp` and `sign` when FEISHU_SECRET is set (signature check
in the bot's security settings).
"""

import json

from .common import links_for, shrink_until, utf8_size, why_label

MAX_BODY_BYTES = 20 * 1024 - 512  # leave room for timestamp and sign

SPECIAL = {"<": "&lt;", ">": "&gt;", "*": "&#42;", "[": "&#91;", "]": "&#93;", "~": "&#126;", "`": "&#96;"}


def escape(text):
    return "".join(SPECIAL.get(ch, ch) for ch in (text or ""))


def section_markdown(section, why):
    lines = [f"**{escape(section['label'])}**"]
    for n, item in enumerate(section["items"], 1):
        line = f"{n}. [{escape(item['title'])}]({item['url']})"
        if item.get("metric_text"):
            line += f" · {escape(item['metric_text'])}"
        lines.append(line)
        if item.get("summary"):
            lines.append(escape(item["summary"]))
        if item.get("why"):
            lines.append(f"*{escape(why)}:* {escape(item['why'])}")
    return {"tag": "markdown", "content": "\n".join(lines)}


def button(label, url):
    return {"tag": "button", "text": {"tag": "plain_text", "content": label}, "type": "default",
            "behaviors": [{"type": "open_url", "default_url": url}]}


def build(message):
    elements = [section_markdown(s, why_label(message)) for s in message["sections"]]
    elements.append({"tag": "markdown", "content": escape(message["footer"])})
    elements += [button(label, url) for label, url in links_for(message, "feishu")]
    header = {"title": {"tag": "plain_text", "content": message["title"]}, "template": "turquoise"}
    if message.get("subtitle"):
        header["subtitle"] = {"tag": "plain_text", "content": message["subtitle"]}
    return {"msg_type": "interactive",
            "card": {"schema": "2.0", "header": header, "body": {"elements": elements}}}


def fits(body):
    return utf8_size(json.dumps(body, ensure_ascii=False)) <= MAX_BODY_BYTES


def render(message):
    return shrink_until(message, build, fits)
