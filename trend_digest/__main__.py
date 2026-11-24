"""Command line: `python -m trend_digest [options]`.

Normal run: build the digest, write the web archive, send to every channel
that has a secret set, save the state file.

    --config digest.toml    which config to use
    --dry-run               print the digest and body sizes; send and save nothing
    --state state/state.json
    --site docs / --no-site where to write the web archive, or skip it
    --date YYYY-MM-DD       build as if it were that day
    --emit FILE|-           build only, write JSON (see emit.py); add --kind, --seen

Exit codes: 0 ok, 1 every source failed (or emit had nothing), 2 a channel failed.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from . import origin
from .client import fixture_fetcher
from .config import ConfigError, load_config
from .digest import NotEnoughHistory, build_digest
from .emit import emit_document, why_empty, write_document
from .render.text import render as render_text
from .send import send
from .site import write_site
from .state import empty_state, load_state, save_state
from .why import llm_from_env

log = logging.getLogger("trend_digest")


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="python -m trend_digest",
                                     description="Build a trend digest and send it to chat apps.")
    parser.add_argument("--config", default="digest.toml")
    parser.add_argument("--dry-run", action="store_true", help="print only; send and save nothing")
    parser.add_argument("--state", default=os.path.join("state", "state.json"))
    parser.add_argument("--site", default="docs", help="web archive folder (GitHub Pages)")
    parser.add_argument("--no-site", action="store_true", help="do not write the web archive")
    parser.add_argument("--date", help="build for this day, YYYY-MM-DD")
    parser.add_argument("--emit", metavar="FILE", help="write JSON to FILE ('-' = stdout), send nothing")
    parser.add_argument("--kind", choices=("daily", "weekly"), default="daily", help="with --emit")
    parser.add_argument("--seen", help="with --emit: JSON array of item ids to leave out")
    return parser.parse_args(argv)


def env(name):
    return (os.environ.get(name) or "").strip()


def targets_from_env():
    targets = {}
    for channel in ("discord", "slack", "feishu", "dingtalk", "wecom"):
        url = env(f"{channel.upper()}_WEBHOOK_URL")
        if url:
            targets[channel] = url
    for channel in ("feishu", "dingtalk"):
        secret = env(f"{channel.upper()}_SECRET")
        if channel in targets and secret:
            targets[channel] = {"url": targets[channel], "secret": secret}
    if env("TELEGRAM_BOT_TOKEN") and env("TELEGRAM_CHAT_ID"):
        targets["telegram"] = {"token": env("TELEGRAM_BOT_TOKEN"), "chat_id": env("TELEGRAM_CHAT_ID")}
    return targets


def run_time(day, config):
    """--date YYYY-MM-DD -> noon of that day in the config's time zone, as UTC."""
    if not day:
        return None
    try:
        local = datetime.combine(datetime.strptime(day, "%Y-%m-%d").date(), time(12),
                                 ZoneInfo(config["timezone"]))
    except ValueError:
        raise ConfigError(f"--date must look like 2026-11-23, got {day!r}") from None
    return local.astimezone(timezone.utc)


def read_seen(path):
    if not path:
        return []
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ConfigError(f"--seen {path} must hold a JSON array of item ids")
    return [str(x) for x in data]


def load_own_state(path):
    """The state file, or an empty state when the file is the template demo's memory (see origin.py)."""
    state = load_state(path)
    if origin.from_demo(state.get("repository")):
        log.info("This repository is a copy of the template: starting with an empty 7-day memory.")
        return empty_state()
    return state


def save_own_state(path, state):
    if origin.current():
        state["repository"] = origin.current()
    save_state(path, state)


def build(args, config, kind, exclude_ids=()):
    fixtures = env("TREND_DIGEST_FIXTURES")
    fetch = fixture_fetcher(fixtures) if fixtures else None
    api_key = env("EVERYINFRA_API_KEY")
    if not fetch and not api_key and kind != "weekly":
        raise ConfigError("EVERYINFRA_API_KEY is not set. Add it as a repository secret "
                          "(Settings > Secrets and variables > Actions). "
                          "Get a key at https://everyinfra.com/?utm_source=github-template")
    return build_digest(config, api_key=api_key, state=load_own_state(args.state),
                        now=run_time(args.date, config), llm=llm_from_env(config),
                        fetch=fetch, kind=kind, exclude_ids=exclude_ids)


def report_failures(digest):
    for failed in digest["usage"]["failed"]:
        if failed["reason"] == "empty":
            log.warning("%s: nothing came back today; that section is left out", failed["source"])
        else:
            log.error("%s failed (%s): %s", failed["source"], failed["reason"], failed.get("detail", ""))
            if failed["reason"] == "http_401":
                log.error("The API key was not accepted. Check the EVERYINFRA_API_KEY secret.")


def all_failed(digest):
    usage = digest["usage"]
    return usage["calls"] > 0 and len(usage["failed"]) == usage["calls"]


def print_dry_run(digest):
    for message in digest["messages"]:
        print(render_text(message))
        print()
    print("Message body sizes:")
    for channel, bodies in digest["payloads"].items():
        sizes = ", ".join(f"{len(json.dumps(b, ensure_ascii=False)):,} chars" for b in bodies)
        print(f"  {channel}: {len(bodies)} message(s), {sizes}")


def run_emit(args, config):
    try:
        digest = build(args, config, args.kind, read_seen(args.seen))
    except NotEnoughHistory as error:
        log.error("%s", error)
        return 1
    report_failures(digest)
    problem = why_empty(digest, args.kind)
    if problem:
        log.error("No output written: %s", problem)
        return 1
    write_document(emit_document(digest, args.kind, args.date), args.emit)
    save_own_state(args.state, digest["state"])
    return 0


def run_normal(args, config):
    digest = build(args, config, "auto")
    report_failures(digest)
    if all_failed(digest):
        log.error("Every source failed, so nothing was sent.")
        return 1
    if args.dry_run:
        print_dry_run(digest)
        return 0
    if not args.no_site:
        for path in write_site(digest, args.site, config["title"]):
            log.info("wrote %s", path)
    targets = targets_from_env()
    if not targets:
        log.warning("No channel is set up (for example DISCORD_WEBHOOK_URL), so nothing was sent.")
    results = send(digest, targets)
    save_own_state(args.state, digest["state"])
    failed = [r for r in results if not r["ok"]]
    for result in failed:
        log.error("%s: not sent: %s", result["channel"], result["error"])
    log.info("sent to: %s", ", ".join(r["channel"] for r in results if r["ok"]) or "nothing")
    return 2 if failed else 0


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = load_config(args.config)
        if env("SITE_URL"):  # lets one config file serve several deployments
            config["site_url"] = env("SITE_URL")
        return run_emit(args, config) if args.emit else run_normal(args, config)
    except (ConfigError, ValueError, OSError) as error:
        log.error("%s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
