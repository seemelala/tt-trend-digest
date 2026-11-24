"""Call the EveryInfra API: `POST https://api.everyinfra.com/api/v1/social`.

`api_fetcher(api_key)` returns a function `fetch(platform, action, params)` that
returns the parsed JSON response. It waits up to 120 seconds per call and retries
429 and 5xx answers twice. Other errors raise ApiError with the `detail` text the
API sent back, so the message can be shown to the user unchanged.
"""

import json
import os
import time
import urllib.error
import urllib.request

from . import __version__

API_URL = "https://api.everyinfra.com/api/v1/social"
TIMEOUT_SECONDS = 120
RETRY_WAITS = (3, 10)


class ApiError(Exception):
    """A call failed. `status` is the HTTP status (0 for network errors)."""

    def __init__(self, status, detail):
        super().__init__(f"HTTP {status}: {detail}" if status else str(detail))
        self.status = status
        self.detail = detail


def user_agent():
    return f"trend-digest/{__version__}"


def post_json(url, body, headers, timeout=TIMEOUT_SECONDS):
    """POST a JSON body. Returns (status, text). Raises urllib errors."""
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": user_agent(), **headers})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", "replace")


def error_detail(text):
    """Pull the `detail` field out of an error body, or return the body itself."""
    try:
        body = json.loads(text)
    except ValueError:
        return text.strip()[:500]
    if isinstance(body, dict) and "detail" in body:
        detail = body["detail"]
        return detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
    return text.strip()[:500]


def retry_wait(error, attempt):
    header = error.headers.get("Retry-After") if error.headers else None
    if header and header.strip().isdigit():
        return min(int(header), 60)
    return RETRY_WAITS[attempt]


def api_fetcher(api_key, url=API_URL):
    """Return fetch(platform, action, params) that calls the real API."""

    def fetch(platform, action, params):
        body = {"platform": platform, "action": action, "params": params}
        headers = {"Authorization": f"Bearer {api_key}"}
        for attempt in range(len(RETRY_WAITS) + 1):
            try:
                _, text = post_json(url, body, headers)
                return json.loads(text)
            except urllib.error.HTTPError as error:
                text = error.read().decode("utf-8", "replace")
                error.close()
                retryable = error.code == 429 or error.code >= 500
                if not retryable or attempt == len(RETRY_WAITS):
                    raise ApiError(error.code, error_detail(text)) from None
                time.sleep(retry_wait(error, attempt))
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                if attempt == len(RETRY_WAITS):
                    raise ApiError(0, f"network error: {error}") from None
                time.sleep(RETRY_WAITS[attempt])
            except ValueError:
                raise ApiError(0, "the API answered with something that is not JSON") from None
        raise ApiError(0, "unreachable")

    return fetch


def fixture_fetcher(directory):
    """Return fetch() that reads saved responses named `<platform>.<action>.json`.

    Used by the tests and for offline demos (env TREND_DIGEST_FIXTURES=<dir>).
    """

    def fetch(platform, action, params):
        path = os.path.join(directory, f"{platform}.{action}.json")
        if not os.path.exists(path):
            raise ApiError(404, f"no saved response at {path}")
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    return fetch
