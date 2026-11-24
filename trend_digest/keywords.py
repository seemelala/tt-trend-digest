"""The three keywords on the first line of the digest ("Today: a · b · c").

Without a model: take words from the titles and summaries of today's items, drop
common words, and rank them by how many different items use them. When no word
appears in more than one item, take one distinctive word (the longest) from each
of the first items instead.

Chinese titles have no spaces between words, so counting words does not work.
For a Chinese digest the keywords are the (shortened) titles of the top item in
each of the first three sections.

With a model (`llm`): ask it to pick three, and fall back to the counting method
if the answer cannot be used.
"""

import json
import re

STOPWORDS = set("""
a about above after again against all also am an and any are as at be because been
before being below between both but by can could did do does doing down during each
few for from further had has have having he her here hers him his how i if in into is
it its itself just me more most my new no nor not now of off on once only or other our
out over own same she should so some such than that the their them then there these
they this those through to too under until up very was we were what when where which
while who whom why will with would you your yours via vs using use used make makes made
get gets got one two three first best top latest today week day days year years way
like than want wants need needs open built build based work works working really still
every much many make via its it's i'm don't can't won't isn't new now how what why
post posts show ask help anyone thoughts question discussion source official free
""".split())

WORD = re.compile(r"[A-Za-z][A-Za-z0-9+#]*(?:\.[A-Za-z0-9]+)*")
CJK = re.compile(r"[㐀-鿿]")


def fold_plural(key):
    """'agents' -> 'agent', so singular and plural count as one word."""
    if len(key) > 4 and key.endswith("s") and not key.endswith("ss"):
        return key[:-1]
    return key


def words_in(text):
    """Lowercase key -> original spelling, for every non-stopword in text."""
    found = {}
    for match in WORD.finditer(text or ""):
        word = match.group(0)
        key = fold_plural(word.lower())
        if len(key) >= 3 and key not in STOPWORDS and not key.isdigit():
            found.setdefault(key, word)
    return found


def item_words(item):
    return words_in(f"{item['title']} {item.get('summary') or ''}")


def is_cjk(text):
    return len(CJK.findall(text or "")) >= 2


def count_words(items):
    """Return [(key, spelling, item_count, first_position)] sorted by count."""
    counts, spelling, first = {}, {}, {}
    for position, item in enumerate(items):
        for key, word in item_words(item).items():
            counts[key] = counts.get(key, 0) + 1
            spelling.setdefault(key, word)
            first.setdefault(key, position)
    rows = [(key, spelling[key], counts[key], first[key]) for key in counts]
    rows.sort(key=lambda row: (-row[2], row[3]))
    return rows


def short_title(title, limit=16):
    return title if len(title) <= limit else title[: limit - 1] + "…"


def distinctive_word(item, taken):
    """The longest word of the title that is not already used, or None."""
    if is_cjk(item["title"]):
        short = short_title(item["title"])
        return None if short.lower() in taken else short
    candidates = [w for k, w in words_in(item["title"]).items() if k not in taken]
    return max(candidates, key=len) if candidates else None


def counted_keywords(items, how_many=3):
    picked = [word for key, word, count, _ in count_words(items) if count >= 2][:how_many]
    taken = {w.lower() for w in picked}
    for item in items:
        if len(picked) >= how_many:
            break
        word = distinctive_word(item, taken)
        if word:
            picked.append(word)
            taken.add(word.lower())
    return picked


def model_keywords(items, llm, how_many=3):
    """Ask the model for keywords. Returns a list or None if the answer is unusable."""
    lines = [f"- {item['title']}: {item.get('summary') or ''}" for item in items]
    prompt = ("Pick the 3 keywords that best describe today's list. Use words that appear "
              "in the list. Answer with a JSON array of 3 short strings only.\n\n" + "\n".join(lines))
    try:
        answer = llm(prompt)
        match = re.search(r"\[.*\]", answer or "", re.S)
        words = json.loads(match.group(0)) if match else None
    except Exception:  # the model is optional; any failure falls back
        return None
    if not isinstance(words, list):
        return None
    words = [str(w).strip() for w in words if str(w).strip()][:how_many]
    return words if len(words) == how_many and all(len(w) <= 40 for w in words) else None


def top_titles(items, how_many=3):
    """Shortened title of the first item from each source, for Chinese digests."""
    picked, sources = [], set()
    for item in items:
        if item["source"] in sources or len(picked) >= how_many:
            continue
        sources.add(item["source"])
        title = item["title"] if is_cjk(item["title"]) else item["title"].rsplit("/", 1)[-1]
        picked.append(short_title(title, 20))
    return picked


def pick_keywords(items, llm=None, lang="en"):
    if not items:
        return []
    if llm:
        words = model_keywords(items, llm)
        if words:
            return words
    if lang == "zh":
        return top_titles(items)
    return counted_keywords(items)
