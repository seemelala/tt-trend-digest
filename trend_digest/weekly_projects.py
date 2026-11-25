"""从《科技爱好者周刊》挑选尚未推荐的 GitHub 项目。"""

import logging
import re
from urllib.request import urlopen

SOURCE = "ruanyf_weekly"
DAILY_LIMIT = 3
ISSUE_LOOKBACK = 6
RAW_URL = "https://raw.githubusercontent.com/ruanyf/weekly/master/"
ISSUE_LINK = re.compile(r"\(docs/issue-(\d+)\.md\)")
HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
ENTRY = re.compile(r"^\d+[、.][ \t]*\[([^\]\n]+)\]\(([^)\s]+)\)[^\n]*$", re.MULTILINE)
REPO_URL = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)(?:/)?(?:[?#][^\s]*)?", re.ASCII | re.IGNORECASE)
LINK = re.compile(r"!?\[([^\]]*)\]\([^)]+\)")


def read_markdown(path):
    with urlopen(RAW_URL + path, timeout=10) as response:
        return response.read().decode("utf-8")


def repo_path(url):
    match = REPO_URL.fullmatch(url or "")
    return match.group(1).lower().removesuffix(".git") if match else None


def projects_from_issue(markdown, issue):
    headings = list(HEADING.finditer(markdown))
    for index, heading in enumerate(headings):
        if heading[1] not in {"工具", "资源"}:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        section = markdown[heading.end():end]
        entries = list(ENTRY.finditer(section))
        for position, entry in enumerate(entries):
            title, url = entry.groups()
            path = repo_path(url)
            if not path or path == "ruanyf/weekly":
                continue
            end = entries[position + 1].start() if position + 1 < len(entries) else len(section)
            body = section[entry.end():end]
            summary = " ".join(LINK.sub(r"\1", body).replace("`", "").split())
            if len(summary) > 100:
                summary = summary[:99] + "…"
            yield {"id": f"{SOURCE}:{path}", "source": SOURCE, "title": title,
                   "url": f"https://github.com/{path}", "summary": summary,
                   "metric_text": f"周刊第 {issue} 期", "metrics": [], "why": "",
                   "extra": {"platform": SOURCE, "issue": issue}}


def recommend(history, today, existing_items, exclude_ids=()):
    remaining = DAILY_LIMIT - sum(day == today for day in history.values())
    if remaining <= 0:
        return []
    seen = set(history) | set(exclude_ids)
    seen.update(f"{SOURCE}:{path}" for item in existing_items if (path := repo_path(item["url"])))
    chosen = []
    try:
        issues = sorted(set(map(int, ISSUE_LINK.findall(read_markdown("README.md")))), reverse=True)
        for issue in issues[:ISSUE_LOOKBACK]:
            for item in projects_from_issue(read_markdown(f"docs/issue-{issue}.md"), issue):
                if item["id"] in seen:
                    continue
                chosen.append(item)
                seen.add(item["id"])
                if len(chosen) == remaining:
                    return chosen
    except (OSError, UnicodeError) as error:
        logging.getLogger("trend_digest").warning("周刊项目精选取数失败：%s", error)
    return chosen
