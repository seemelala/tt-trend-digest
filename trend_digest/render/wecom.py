"""WeCom (企业微信) group bot body: `msgtype: "markdown"`.

The WeCom docs ("消息推送配置说明") say markdown `content` is at most 4,096 bytes
of UTF-8. Supported markdown is a small set: headings, bold, links, quotes,
inline code and three font colours. When the digest is longer, items are
removed until it fits.
"""

from .common import links_for, shrink_until, utf8_size, why_label

MAX_CONTENT_BYTES = 4096


def escape(text):
    return (text or "").replace("[", "［").replace("]", "］").replace("*", "＊")


def section_lines(section, why):
    lines = [f"**{escape(section['label'])}**"]
    for n, item in enumerate(section["items"], 1):
        line = f"{n}. [{escape(item['title'])}]({item['url']})"
        if item.get("metric_text"):
            line += f' <font color="comment">{escape(item["metric_text"])}</font>'
        lines.append(line)
        if item.get("why"):
            lines.append(f"> {escape(why)}: {escape(item['why'])}")
    return "\n".join(lines)


def build(message):
    parts = [f"## {escape(message['title'])}"]
    if message.get("subtitle"):
        parts.append(escape(message["subtitle"]))
    parts += [section_lines(s, why_label(message)) for s in message["sections"]]
    links = " · ".join(f"[{label}]({url})" for label, url in links_for(message, "wecom"))
    parts.append(f'<font color="comment">{escape(message["footer"])}</font>\n{links}')
    return {"msgtype": "markdown", "markdown": {"content": "\n\n".join(parts)}}


def fits(body):
    return utf8_size(body["markdown"]["content"]) <= MAX_CONTENT_BYTES


def render(message):
    return shrink_until(message, build, fits)
