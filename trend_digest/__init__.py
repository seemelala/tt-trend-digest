"""trend-digest: build a daily trend digest and send it to chat apps.

Two public functions:

    build_digest(config, api_key=..., state=None, now=None, llm=None, fetch=None)
        Calls the EveryInfra API once per configured source, picks 10-12 items,
        and returns a JSON-ready dict with every channel's message body.

    send(digest, targets, dry_run=False)
        Posts the message bodies to the webhooks you pass in.

The command line (`python -m trend_digest`) is a thin wrapper around these two.
"""

__version__ = "0.1.0"

from .digest import build_digest, NotEnoughHistory  # noqa: E402
from .send import send  # noqa: E402

__all__ = ["__version__", "build_digest", "send", "NotEnoughHistory"]
