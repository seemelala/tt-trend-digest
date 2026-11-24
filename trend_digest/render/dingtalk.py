"""DingTalk custom bot body: `msgtype: "markdown"` with `title` and `text`.

`title` is what the chat list shows; `text` is the markdown body (headings,
bold, links and lists are supported). A markdown message has no buttons, so the
two links are plain markdown links at the end.

DingTalk bots usually need a security setting. With "custom keywords", put a
word from the title (for example "Digest" or "简报") in the bot settings. With
"signature", set DINGTALK_SECRET and `send` signs the request.

Size: we did not find a length limit for markdown in the DingTalk docs we could
read, so the body is kept under 18,000 bytes as a safe margin.
"""

from .common import links_for, shrink_until, utf8_size, why_label

MAX_TEXT_BYTES = 18000


def escape(text):
    return (text or "").replace("[", "［").replace("]", "］").replace("*", "＊")


def section_lines(section, why):
    lines = [f"#### {escape(section['label'])}"]
    for n, item in enumerate(section["items"], 1):
        line = f"{n}. [{escape(item['title'])}]({item['url']})"
        if item.get("metric_text"):
            line += f" · {escape(item['metric_text'])}"
        lines.append(line)
        if item.get("summary"):
            lines.append(f"   {escape(item['summary'])}")
        if item.get("why"):
            lines.append(f"   {escape(why)}: {escape(item['why'])}")
    return "\n".join(lines)


def build(message):
    parts = [f"### {escape(message['title'])}"]
    if message.get("subtitle"):
        parts.append(escape(message["subtitle"]))
    parts += [section_lines(s, why_label(message)) for s in message["sections"]]
    links = " · ".join(f"[{label}]({url})" for label, url in links_for(message, "dingtalk"))
    parts.append(f"{escape(message['footer'])}\n\n{links}")
    return {"msgtype": "markdown",
            "markdown": {"title": message["title"], "text": "\n\n".join(parts)}}


def fits(body):
    return utf8_size(body["markdown"]["text"]) <= MAX_TEXT_BYTES


def render(message):
    return shrink_until(message, build, fits)
