"""The two links at the bottom of every digest, with a per-channel utm tag.

`Run your own digest` points to the template repository. `Web archive` points to
the `site_url` in the config and is left out when that is empty.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TEMPLATE_URL = "https://github.com/everyinfra/trend-digest"


def tracked(url, channel):
    """Add `utm_source=<channel>-digest` to a URL, e.g. channel 'discord'."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "utm_source"]
    query.append(("utm_source", f"{channel}-digest"))
    return urlunsplit(parts._replace(query=urlencode(query)))


def footer_links(site_url, channel, labels):
    """Return [(label, url), ...] for one channel. `labels` = (run_own, archive)."""
    run_own, archive = labels
    links = [(run_own, tracked(TEMPLATE_URL, channel))]
    if site_url:
        links.append((archive, tracked(site_url, channel)))
    return links
