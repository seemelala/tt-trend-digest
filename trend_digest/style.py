"""The archive stylesheet. Written to docs/assets/style.css when that file is missing.

Light and dark colours follow the reader's system setting. System fonts only,
no web fonts, no scripts. Long words wrap so phones never scroll sideways.
"""

STYLE_CSS = """\
:root {
  color-scheme: light dark;
  --bg: #ffffff;
  --text: #1a1d1f;
  --muted: #5b6470;
  --accent: #26756e;
  --line: #e3e6e8;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111418;
    --text: #e6e8ea;
    --muted: #9aa3ad;
    --accent: #3fbfb4;
    --line: #2a2f35;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
}
main { max-width: 46rem; margin: 0 auto; padding: 24px 16px 48px; overflow-wrap: anywhere; }
h1 { font-size: 1.6rem; line-height: 1.25; margin: 0 0 6px; }
h2 { font-size: 1.1rem; margin: 32px 0 8px; padding-top: 16px; border-top: 1px solid var(--line); }
a { color: var(--accent); }
ol, ul { padding-left: 1.4rem; margin: 0; }
li { margin: 0 0 14px; }
p { margin: 0; }
.keywords, .metric, .summary, footer { color: var(--muted); }
.metric { font-size: 0.92em; white-space: normal; }
.summary, .why { margin-top: 2px; }
.archive ul { list-style: none; padding: 0; }
footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--line); font-size: 0.92em; }
footer p + p { margin-top: 6px; }
"""
