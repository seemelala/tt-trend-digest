"""Read and check digest.toml.

`load_config(path)` returns a plain dict with defaults filled in. Mistakes in the
file raise ConfigError with a message that says what to change, for example an
unknown `use` lists every supported source.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .i18n import LANGUAGES
from .sources import SUPPORTED

try:
    import tomllib
except ImportError:  # Python 3.10
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

DEFAULTS = {
    "language": "en",
    "timezone": "America/New_York",
    "title": "EveryInfra Trend Digest",
    "site_url": "",
    "max_items": 12,
    "min_items": 10,
    "llm_model": "gemini-3.6-flash",
}
TOP_LEVEL_KEYS = set(DEFAULTS) | {"sources"}
SOURCE_KEYS = {"use", "params", "limit", "label", "icon_url", "backfill"}


class ConfigError(ValueError):
    """The config file has a problem the user needs to fix."""


def load_config(path):
    """Read a TOML file and return the checked config dict."""
    if tomllib is None:
        raise ConfigError("Reading digest.toml needs Python 3.11 or newer (or `pip install tomli`).")
    try:
        with open(path, "rb") as handle:
            raw = tomllib.load(handle)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}") from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} is not valid TOML: {error}") from None
    return check_config(raw)


def check_config(raw):
    """Fill defaults and check every field. Accepts a dict, returns a new dict."""
    if not isinstance(raw, dict):
        raise ConfigError("The config must be a table of settings.")
    unknown = sorted(set(raw) - TOP_LEVEL_KEYS)
    if unknown:
        raise ConfigError(f"Unknown setting(s): {', '.join(unknown)}. "
                          f"Allowed: {', '.join(sorted(TOP_LEVEL_KEYS))}.")
    config = {**DEFAULTS, **raw}
    check_language(config["language"])
    check_timezone(config["timezone"])
    config["max_items"] = check_positive_int("max_items", config["max_items"])
    config["min_items"] = check_positive_int("min_items", config["min_items"])
    config["sources"] = [check_source(i, s) for i, s in enumerate(raw.get("sources") or [], 1)]
    if not config["sources"]:
        raise ConfigError("Add at least one [[sources]] entry. Supported: " + ", ".join(SUPPORTED))
    return config


def check_language(language):
    if language not in LANGUAGES:
        raise ConfigError(f"language = {language!r} is not supported. Use one of: {', '.join(LANGUAGES)}.")


def check_timezone(name):
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigError(f"timezone = {name!r} is not a known time zone. "
                          "Use a name like 'UTC', 'America/New_York' or 'Asia/Shanghai'.") from None


def check_positive_int(name, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"{name} must be a whole number of 1 or more, got {value!r}.")
    return value


def check_source(position, source):
    where = f"[[sources]] #{position}"
    if not isinstance(source, dict):
        raise ConfigError(f"{where} must be a table.")
    unknown = sorted(set(source) - SOURCE_KEYS)
    if unknown:
        raise ConfigError(f"{where} has unknown key(s): {', '.join(unknown)}. "
                          f"Allowed: {', '.join(sorted(SOURCE_KEYS))}.")
    use = source.get("use")
    if use not in SUPPORTED:
        raise ConfigError(f"{where}: unknown source use = {use!r}. "
                          f"Supported sources: {', '.join(SUPPORTED)}.")
    params = source.get("params") or {}
    if not isinstance(params, dict):
        raise ConfigError(f"{where}: params must be a table, like params = {{ key = \"value\" }}.")
    limit = check_positive_int(f"{where} limit", source.get("limit", 3))
    backfill = source.get("backfill", True)
    if not isinstance(backfill, bool):
        raise ConfigError(f"{where}: backfill must be true or false.")
    checked = {"use": use, "params": dict(params), "limit": limit,
               "label": source.get("label") or "", "icon_url": source.get("icon_url") or ""}
    if not backfill:
        checked["backfill"] = False
    return checked
