"""Telegram Bot API `sendMessage` bodies (without chat_id, which `send` adds).

`render(message)` returns a list: usually one body, more when the digest does
not fit in one Telegram message. Bodies use `parse_mode: "HTML"` with link
previews off, and the last one carries the two URL buttons in
`reply_markup.inline_keyboard`.

Telegram allows 4,096 characters per message, counted after it has parsed the
tags away ("1-4096 characters after entities parsing" in the Bot API docs).
`visible_size` counts that visible text in UTF-16 code units, which is never
fewer than Telegram's count. A digest that is longer goes out as several
messages in reading order, split between items, and a section that continues
in the next message repeats its heading there. No item is dropped.

Telegram's HTML mode accepts only a few tags (b, i, a, ...) and needs <, > and
& written as &lt; &gt; &amp; everywhere else.
"""

import html
import re

from .common import links_for, utf16_size, why_label

MAX_TEXT = 4096
TAG = re.compile(r"<[^>]*>")


def esc(text):
    return html.escape(text or "", quote=True)


def visible_size(text):
    """The length Telegram checks against MAX_TEXT: the text without its tags, entities decoded."""
    return utf16_size(html.unescape(TAG.sub("", text)))


def item_lines(number, item, why):
    head = f'{number}. <a href="{esc(item["url"])}">{esc(item["title"])}</a>'
    if item.get("metric_text"):
        head += f" · {esc(item['metric_text'])}"
    lines = [head]
    if item.get("summary"):
        lines.append(esc(item["summary"]))
    if item.get("why"):
        lines.append(f"<i>{esc(why)}:</i> {esc(item['why'])}")
    return "\n".join(lines)


def header_block(message):
    head = f"<b>{esc(message['title'])}</b>"
    if message.get("subtitle"):
        head += "\n" + esc(message["subtitle"])
    return head


def footer_block(message, links):
    return esc(message["footer"]) + "\n" + " · ".join(
        f'<a href="{esc(url)}">{esc(label)}</a>' for label, url in links)


def fits(blocks):
    return visible_size("\n\n".join(blocks)) <= MAX_TEXT


def texts(message, links):
    """The text of each message to send. Blocks (title, sections, footer) are separated by a blank line."""
    why = why_label(message)
    done, blocks = [], [header_block(message)]
    for section in message["sections"]:
        lines = [f"<b>{esc(section['label'])}</b>"]
        for number, item in enumerate(section["items"], 1):
            line = item_lines(number, item, why)
            if fits(blocks + ["\n".join(lines + [line])]):
                lines.append(line)
                continue
            if len(lines) > 1:
                blocks.append("\n".join(lines))
            done.append("\n\n".join(blocks))
            blocks, lines = [], [lines[0], line]   # the next message goes on with this section, heading first
        if len(lines) > 1:
            blocks.append("\n".join(lines))
    tail = footer_block(message, links)
    if blocks and not fits(blocks + [tail]):
        done.append("\n\n".join(blocks))
        blocks = []
    done.append("\n\n".join(blocks + [tail]))
    return done


def render(message):
    links = links_for(message, "telegram")
    bodies = [{"text": text, "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}}
              for text in texts(message, links)]
    bodies[-1]["reply_markup"] = {"inline_keyboard": [[{"text": label, "url": url} for label, url in links]]}
    return bodies
