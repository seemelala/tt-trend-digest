# 当前任务

在北京时间 09:07 的现有日报中加入周刊项目精选，每日最多两条。

## 状态

- [x] 以远端 `e5e4d907` 为基线，工作流 UTC 01:07，日报日期统一使用 `Asia/Shanghai`。
- [x] 从最近六期周刊的「工具」「资源」提取 GitHub 项目，按新到旧补足，每日最多两条。
- [x] 日报复用飞书卡片和存档。周刊历史跨日保留，排队运行会读取当前分支状态。周刊访问失败时普通日报仍可生成。

## 阻塞 / 待确认

- 待本地改动进入远端 `main`，然后用仓库的现有 Secrets 做一次飞书验收。当前仅在本地生成卡片。

## 本轮验证记录

- `python3.12 -m unittest discover -s tests`：`Ran 74 tests`，`OK`。
- `TREND_DIGEST_FIXTURES=tests/fixtures python3.12 -m trend_digest --config digest.toml --weekly-projects --dry-run --state /dev/null`：读取真实周刊，生成第 420 期两条推荐，飞书卡片一张。

## 下一圈从这里开始

应用本轮提交到远端后，在 Actions 手动运行 `Trend digest`，确认飞书「周刊项目精选」栏目及存档写回成功。随后检查北京时间 09:07 的 Scheduled 运行。
