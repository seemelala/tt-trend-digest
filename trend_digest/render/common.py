"""Helpers shared by the channel renderers."""

import copy

from ..i18n import t
from ..links import footer_links


def shrink_until(message, build, fits):
    """Build the body; while it does not fit, drop one item and build again.

    The item comes off the end of the section that has the most items left
    (the later section when two are equal), so every section keeps some items.
    """
    message = copy.deepcopy(message)
    body = build(message)
    while not fits(body):
        sections = [s for s in message["sections"] if s["items"]]
        if not sections:
            return body
        largest = max(range(len(sections)), key=lambda i: (len(sections[i]["items"]), i))
        sections[largest]["items"].pop()
        message["sections"] = [s for s in sections if s["items"]]
        body = build(message)
    return body


def links_for(message, channel):
    """[(label, url)] for 'Run your own digest' and, if configured, 'Web archive'."""
    lang = message["lang"]
    return footer_links(message.get("site_url"), channel, (t(lang, "run_own"), t(lang, "archive")))


def why_label(message):
    return t(message["lang"], "why")


def utf8_size(text):
    return len(text.encode("utf-8"))


def utf16_size(text):
    return len(text.encode("utf-16-le")) // 2
