"""Turn a message into each channel's request bodies.

A "message" is the channel-neutral form of one digest post:

    {"lang", "title", "subtitle", "sections": [{"id", "label", "icon_url", "items"}],
     "footer", "site_url"}

Each module here has `render(message)`. Most return one request body: when it
would be over the channel's size limit, items are removed from the end of the
sections until it fits (see `common.shrink_until`). Telegram's returns a list
of bodies instead, splitting a long digest into several messages, so no item is
dropped there (see `telegram.py`).
"""

from . import dingtalk, discord, feishu, slack, telegram, wecom

RENDERERS = {
    "discord": discord.render,
    "slack": slack.render,
    "telegram": telegram.render,
    "feishu": feishu.render,
    "dingtalk": dingtalk.render,
    "wecom": wecom.render,
}
CHANNELS = tuple(RENDERERS)
SPLITTING = {"telegram"}   # channels whose render() returns a list of bodies


def bodies_for(channel, message):
    """The request bodies for one message on one channel, in sending order."""
    body = RENDERERS[channel](message)
    return body if channel in SPLITTING else [body]


def render_payloads(messages):
    """{channel: [body, ...]} for every channel: each message's bodies in turn, in sending order."""
    return {channel: [body for message in messages for body in bodies_for(channel, message)]
            for channel in RENDERERS}
