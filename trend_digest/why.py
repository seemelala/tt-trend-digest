"""The optional "Why it matters" sentence under each item.

One model call covers the whole digest: it gets every item's id, title, summary
and numbers and must answer with a JSON object {id: sentence or null}. The
sentence must say why the item is worth a look today. A sentence is dropped when
it repeats the summary (see `restates`), when it has a number that is not in
the item's own fields (see `invents_number`), or when it is too long. If the
call fails, the digest is sent without any of these sentences.

`llm_from_env(config)` builds the model function from environment variables:
LLM_API_KEY (required to turn this on), LLM_BASE_URL (an OpenAI-compatible
base URL, default https://api.everyinfra.com/api/v1) and LLM_MODEL (default:
`llm_model` in digest.toml).
"""

import json
import os
import re

from .client import post_json

MAX_WORDS = 25
MAX_CHARS_ZH = 50
DEFAULT_BASE_URL = "https://api.everyinfra.com/api/v1"
LENGTH = {"en": "at most 25 words, in English", "zh": "at most 50 characters, in Simplified Chinese"}
CJK = re.compile(r"[\u3400-\u9fff]")
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
DAY_SHARE = 0.05


def day_share(item):
    """'10% of its stars came today' when one day brought 5% or more of a total."""
    for m in item.get("metrics") or []:
        if m.get("value") and m.get("delta") and m["delta"] / m["value"] >= DAY_SHARE:
            return f"{m['delta'] / m['value']:.0%} of its {m['label']} came today"
    return ""


def build_prompt(items, lang="en"):
    rows = [{"id": item["id"], "source": (item.get("extra") or {}).get("platform", ""), "title": item["title"],
             "summary": item.get("summary") or "", "numbers": item.get("metric_text") or "",
             "note": day_share(item)}
            for item in items]
    return (
        'You write the "Why it matters" line of a daily trend digest that developers read. '
        "Each item below has a title, a summary and numbers; all of them come from the source. "
        "The reader sees all three right above your sentence.\n"
        f"For each item, write one sentence ({LENGTH.get(lang, LENGTH['en'])}) that gives the "
        "reader a reason to open it today. A reason is one of these:\n"
        "- who it is useful for and what they can do with it;\n"
        "- what is new or has changed, when the title or summary says so;\n"
        "- a number that is unusual for this kind of item; `note` holds one when there is one.\n"
        "Rules:\n"
        "- Use only facts from the fields below. Add nothing from memory.\n"
        "- Do not say the title or summary again in other words, and do not copy a phrase of "
        "four or more words from them.\n"
        "- Reading the numbers back is not a reason. Do not write who published an item, when it "
        "was posted, or how many votes, stars or comments it has. The `note` is the one exception.\n"
        "- A number in your sentence must be in the fields of that same item. Never take a number "
        "from another item.\n"
        "- The first reason applies to most items that have a summary: name the kind of reader "
        "(for example people who run models locally, security testers, paper authors) and what "
        "they get from it. Write that sentence when you can.\n"
        "- Answer null only when an item has no summary and its title gives you nothing more to "
        "say. Do not answer null for every item.\n"
        "Answer with one JSON object that maps each id to its sentence or to null, and nothing else.\n\n"
        + json.dumps(rows, ensure_ascii=False, indent=1)
    )


def parse_answer(answer):
    """Find the JSON object in the model's answer. Returns a dict or {}."""
    match = re.search(r"\{.*\}", answer or "", re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def units(text):
    """Words for Latin text; single characters for Chinese text."""
    text = (text or "").lower()
    if CJK.search(text):
        return [ch for ch in text if ch.isalnum()], 8
    return re.findall(r"[a-z0-9]+", text), 4


def restates(sentence, item):
    """True when the sentence copies a run of words from the title or the summary."""
    said, run = units(sentence)
    known, _ = units(f"{item.get('title') or ''} \n {item.get('summary') or ''}")
    seen = {tuple(known[i:i + run]) for i in range(len(known) - run + 1)}
    return any(tuple(said[i:i + run]) in seen for i in range(len(said) - run + 1))


def numbers_in(text):
    return {number.replace(",", "") for number in NUMBER.findall(text or "")}


def invents_number(sentence, item):
    """True when the sentence has a number that the item's own fields do not have."""
    known = " ".join([item.get("title") or "", item.get("summary") or "",
                      item.get("metric_text") or "", day_share(item)])
    return not numbers_in(sentence) <= numbers_in(known)


def usable(sentence, item=None):
    if not isinstance(sentence, str):
        return None
    sentence = " ".join(sentence.split())
    too_long = len(sentence) > MAX_CHARS_ZH if CJK.search(sentence) else len(sentence.split()) > MAX_WORDS
    if not sentence or too_long:
        return None
    if item is not None and (restates(sentence, item) or invents_number(sentence, item)):
        return None
    return sentence


def add_why(items, llm, lang="en"):
    """Set item['why'] for every item the model answered well. Returns items."""
    if not llm or not items:
        return items
    try:
        answers = parse_answer(llm(build_prompt(items, lang)))
    except Exception:  # the sentence is optional; never fail the digest over it
        answers = {}
    for item in items:
        item["why"] = usable(answers.get(item["id"]), item)
    return items


def llm_from_env(config, environ=None):
    """Return a callable(prompt) -> str, or None when LLM_API_KEY is not set."""
    environ = os.environ if environ is None else environ
    key = (environ.get("LLM_API_KEY") or "").strip()
    if not key:
        return None
    base = (environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    model = (environ.get("LLM_MODEL") or config.get("llm_model") or "").strip()

    def call(prompt):
        body = {"model": model, "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}]}
        _, text = post_json(base + "/chat/completions", body, {"Authorization": f"Bearer {key}"})
        return json.loads(text)["choices"][0]["message"]["content"]

    return call
