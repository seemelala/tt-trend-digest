# tt-trend-digest 记忆索引

## 项目入口

- 远端为 `seemelala/tt-trend-digest`，默认分支 `main`。
- GitHub Actions 调用 `python -m trend_digest`，每日北京时间 09:07。运行时间由 cron 决定，报表日期由配置时区决定。
- 飞书凭据由 GitHub Actions Secrets 注入。每次运行生成飞书卡片、网页存档以及下一次使用的 `state/state.json`。
- 现有趋势来源使用 EveryInfra；周刊 Markdown 来自公开 GitHub 仓库。
- `--weekly-projects` 打开周刊栏目。周刊条目历史存于 `weekly_project_history`，不受普通条目七天窗口影响。
