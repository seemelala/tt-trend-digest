# 当前任务

把北京时间 09:07 的飞书日报收为三个项目栏目，每日目标 12 条。

## 状态

- [x] 日常配额为周刊 3、GitHub 6、Product Hunt 3。
- [x] 工作流只查询两项 EveryInfra 来源，减少新闻和论坛讨论。
- [x] GitHub 和 Product Hunt 的未推候选可补位。候选不足时允许少于 12 条。
- [x] 定时只发一张日报，星期一也使用同一个上限。

## 阻塞 / 待确认

- 本地已改，待合入远端后用飞书群做真实推送验收。

## 本轮验证记录

- `python3.12 -m unittest discover -s tests`：`Ran 75 tests`，`OK`。
- `TREND_DIGEST_FIXTURES=tests/fixtures python3.12 -m trend_digest --config presets/projects.toml --weekly-projects --daily-only --dry-run --state /dev/null`：真实周刊加本地 API 样本，Product Hunt 为空时仍生成 12 条、一张飞书卡片。
- 与远端 `0723912` 核对，补丁涉及的七个既有文件均与本地基线一致。

## 下一圈从这里开始

把配额补丁应用到 GitHub 的 `main`，手动执行 `Trend digest` 验收飞书推送。后续观察 09:07 的定时运行。
