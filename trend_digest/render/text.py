"""Plain-text version of a message, printed by `--dry-run` and used in tests."""

from .common import links_for, why_label


def render(message, channel="text"):
    lines = [message["title"]]
    if message.get("subtitle"):
        lines.append(message["subtitle"])
    why = why_label(message)
    for section in message["sections"]:
        lines += ["", section["label"]]
        for n, item in enumerate(section["items"], 1):
            head = f"{n}. {item['title']}"
            if item.get("metric_text"):
                head += f" · {item['metric_text']}"
            lines.append(head)
            lines.append(f"   {item['url']}")
            if item.get("summary"):
                lines.append(f"   {item['summary']}")
            if item.get("why"):
                lines.append(f"   {why}: {item['why']}")
    lines += ["", message["footer"]]
    lines += [f"{label}: {url}" for label, url in links_for(message, channel)]
    return "\n".join(lines)
