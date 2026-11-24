"""Tell this repository's data apart from the demo data that a copy of the template starts with.

The template repository runs its own digest every day to keep its demo archive current, and it
commits the archive pages and the 7-day memory like any copy does. "Use this template" and forks
copy those files too. A copy must not skip items because the demo sent them, and its archive must
not list the demo's days, so a run in a copy ignores both.
"""

import os

TEMPLATE_REPOSITORY = "everyinfra/trend-digest"


def current():
    """owner/name of the repository this runs in (GitHub Actions sets it), or ''."""
    return (os.environ.get("GITHUB_REPOSITORY") or "").strip()


def from_demo(owner, here=None):
    """True when data written in `owner` is the template's demo data and this run is in a copy."""
    here = (current() if here is None else here).lower()
    return bool(here) and here != TEMPLATE_REPOSITORY and (owner or "").lower() == TEMPLATE_REPOSITORY
