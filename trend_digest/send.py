"""send(): post the rendered bodies to each configured channel.

    targets = {"discord": url, "slack": url, "telegram": {"token", "chat_id"},
               "feishu": url or {"url", "secret"}, "dingtalk": url or {"url", "secret"},
               "wecom": url}

Only channels present in `targets` are sent. One failing channel does not stop
the others. Returns one result per channel:
{"channel", "ok", "status", "error"}.

Webhook addresses are secrets: logs and errors show only the host name.
Some services answer HTTP 200 even when the message was refused, so the body is
checked too (DingTalk/WeCom `errcode`, Feishu `code`, Telegram `ok`).
"""

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.error
from urllib.parse import quote_plus, urlsplit

from .client import post_json

log = logging.getLogger("trend_digest")
ORDER = ("discord", "slack", "telegram", "feishu", "dingtalk", "wecom")
TELEGRAM_API = "https://api.telegram.org"


def host_of(url):
    try:
        return urlsplit(url).hostname or "?"
    except ValueError:
        return "?"


def add_query(url, extra):
    return url + ("&" if "?" in url else "?") + extra


def dingtalk_url(url, secret):
    """DingTalk signature: HmacSHA256(secret, f"{ms}\\n{secret}"), base64, url-encoded."""
    if not secret:
        return url
    stamp = str(int(time.time() * 1000))
    digest = hmac.new(secret.encode(), f"{stamp}\n{secret}".encode(), hashlib.sha256).digest()
    return add_query(url, f"timestamp={stamp}&sign={quote_plus(base64.b64encode(digest))}")


def feishu_signed(body, secret):
    """Feishu signature: HmacSHA256 with key f"{s}\\n{secret}" over an empty message."""
    if not secret:
        return body
    stamp = str(int(time.time()))
    digest = hmac.new(f"{stamp}\n{secret}".encode(), b"", hashlib.sha256).digest()
    return {"timestamp": stamp, "sign": base64.b64encode(digest).decode(), **body}


def split_target(target):
    """A target is a URL string or {"url", "secret"}."""
    if isinstance(target, dict):
        return target.get("url") or "", target.get("secret") or ""
    return target or "", ""


def requests_for(channel, target, bodies):
    """[(url, body)] to post for one channel."""
    if channel == "telegram":
        base = (target.get("api_base") or TELEGRAM_API).rstrip("/")
        url = f"{base}/bot{target['token']}/sendMessage"
        return [(url, {"chat_id": target["chat_id"], **body}) for body in bodies]
    url, secret = split_target(target)
    if channel == "discord":
        return [(add_query(url, "with_components=true"), body) for body in bodies]
    if channel == "feishu":
        return [(url, feishu_signed(body, secret)) for body in bodies]
    if channel == "dingtalk":
        return [(dingtalk_url(url, secret), body) for body in bodies]
    return [(url, body) for body in bodies]


def refused(channel, text):
    """Return the service's error message when a 2xx answer still means failure."""
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    if channel in ("dingtalk", "wecom") and data.get("errcode", 0) != 0:
        return f"errcode {data.get('errcode')}: {data.get('errmsg')}"
    if channel == "feishu" and data.get("code", 0) != 0:
        return f"code {data.get('code')}: {data.get('msg')}"
    if channel == "telegram" and data.get("ok") is False:
        return str(data.get("description"))
    return None


def post_once(channel, url, body):
    """Post one body, retrying once on 429 or 5xx. Returns (ok, status, error)."""
    for attempt in range(2):
        try:
            status, text = post_json(url, body, {}, timeout=30)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            error.close()
            if attempt == 0 and (error.code == 429 or error.code >= 500):
                time.sleep(2)
                continue
            return False, error.code, f"HTTP {error.code} from {host_of(url)}: {detail}"
        except (urllib.error.URLError, OSError) as error:
            reason = getattr(error, "reason", error)
            return False, 0, f"could not reach {host_of(url)}: {reason}"
        problem = refused(channel, text)
        return (False, status, problem) if problem else (True, status, None)
    return False, 0, "gave up after retry"


def send_channel(channel, target, bodies):
    status = None
    for url, body in requests_for(channel, target, bodies):
        ok, status, error = post_once(channel, url, body)
        log.info("%s -> %s: %s", channel, host_of(url), "ok" if ok else error)
        if not ok:
            return {"channel": channel, "ok": False, "status": status, "error": error}
    return {"channel": channel, "ok": True, "status": status, "error": None}


def send(digest, targets, *, dry_run=False):
    """Send every rendered body to the given targets. See the module docstring."""
    results = []
    for channel in ORDER:
        target = targets.get(channel)
        bodies = digest["payloads"].get(channel) or []
        if not target or not bodies:
            continue
        if dry_run:
            results.append({"channel": channel, "ok": True, "status": "dry-run", "error": None})
            continue
        try:
            results.append(send_channel(channel, target, bodies))
        except Exception as error:  # a broken target must not stop other channels
            # Do not print the error text: it can contain the secret webhook URL.
            problem = f"{type(error).__name__}; check the {channel} address or token"
            results.append({"channel": channel, "ok": False, "status": None, "error": problem})
    return results
