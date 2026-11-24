"""Slack incoming-webhook body (Block Kit).

Layout: header block (title), context block (keywords), then for each section a
section block (mrkdwn list) followed by a divider, a context block with the
footer, and an actions block with two URL buttons. `text` is the plain-text
version Slack uses for notifications.

Limits (Slack docs): 50 blocks per message, section text 3,000 characters,
header text 150 characters. Slack mrkdwn needs &, < and > escaped.
"""

from .common import links_for, shrink_until, why_label

MAX_BLOCKS = 50
MAX_SECTION_TEXT = 3000
MAX_HEADER = 150


def escape(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def link(url, label):
    label = escape(label).replace("|", "¦")
    return f"<{url}|{label}>"


def item_lines(number, item, why):
    head = f"{number}. {link(item['url'], item['title'])}"
    if item.get("metric_text"):
        head += f" · {escape(item['metric_text'])}"
    lines = [head]
    if item.get("summary"):
        lines.append(f"      {escape(item['summary'])}")
    if item.get("why"):
        lines.append(f"      _{why}:_ {escape(item['why'])}")
    return "\n".join(lines)


def section_block(section, why):
    body = "\n".join(item_lines(n, item, why) for n, item in enumerate(section["items"], 1))
    return {"type": "section", "text": {"type": "mrkdwn", "text": f"*{escape(section['label'])}*\n{body}"}}


def build(message):
    why = why_label(message)
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": message["title"][:MAX_HEADER]}}]
    if message.get("subtitle"):
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": escape(message["subtitle"])}]})
    for section in message["sections"]:
        blocks.append(section_block(section, why))
        blocks.append({"type": "divider"})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": escape(message["footer"])}]})
    buttons = [{"type": "button", "text": {"type": "plain_text", "text": label}, "url": url,
                "action_id": f"link_{n}"} for n, (label, url) in enumerate(links_for(message, "slack"))]
    blocks.append({"type": "actions", "elements": buttons})
    text = message["title"] + (f"\n{message['subtitle']}" if message.get("subtitle") else "")
    return {"text": text, "blocks": blocks}


def fits(body):
    sections = [b for b in body["blocks"] if b["type"] == "section"]
    return len(body["blocks"]) <= MAX_BLOCKS and all(
        len(b["text"]["text"]) <= MAX_SECTION_TEXT for b in sections)


def render(message):
    return shrink_until(message, build, fits)
