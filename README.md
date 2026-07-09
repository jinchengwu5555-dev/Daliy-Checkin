# 📋 Daily Checkin — GitHub Actions 版

将原青龙面板的每日任务迁移至 GitHub Actions，无需服务器，完全免费运行。

每天早晨通过 Server酱 推送一条微信消息，包含：签到结果、B站等级进度、NBA 赛程、ETF 行情、汇率（含 1/3/5/10 年历史对比）、每日 60s 新闻、双语 RSS 资讯摘要。

## 📁 目录结构

```
.github/
  workflows/
    daily_summary.yml        # 主工作流：每天 07:50 (北京时间) 运行全部任务并汇总推送
    rss_digest.yml           # 单独工作流：每天 10:00 (北京时间) RSS 摘要
scripts/
  daily_checkin/
    baiduwangpan_checkin.py  # 百度网盘签到
    bilibili_checkin.py      # B站签到（观看/投币/分享 + 今日成长值 + 升级进度）
    juejin_checkin.js        # 掘金签到
    nba_schedule.py          # NBA 赛程
    etf_stock.py             # ETF 行情
    exchange_rates.py        # 汇率（今日 + 1/3/5/10 年前对比）
    news_60s.py              # 每日 60s 新闻
    rss_digest.py            # RSS 聚合摘要（英文标题自动翻译，双语显示）
    package.json
  summary_push.py            # 汇总推送脚本
```

## 🔑 GitHub Secrets 配置

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加以下 Secret：

| Secret 名称 | 说明 | 多账号格式 |
|:---|:---|:---|
| `BAIDU_COOKIE` | 百度网盘 Cookie | 换行分隔 |
| `BILIBILI_COOKIE` | Bilibili Cookie | `&` 或换行分隔 |
| `JUEJIN_COOKIES` | 掘金 Cookie | `#` 分隔 |
| `SERVERCHAN_KEY` | Server酱推送 Key（可选） | 单值 |

> 未配置对应 Secret 的任务会以 `❌ 未设置 XXX Secret` 提示并退出，**不会导致整个工作流失败**。

## ⏰ 定时说明

| 工作流 | cron (UTC) | 北京时间 | 内容 |
|:---|:---|:---|:---|
| `daily_summary.yml` | `50 23 * * *` | 每天 07:50 | 签到 + NBA + ETF + 汇率 + 新闻 + RSS，汇总为一条推送 |
| `rss_digest.yml` | `0 2 * * *` | 每天 10:00 | RSS 资讯摘要单独推送 |

> GitHub Actions 的 cron 使用 UTC 时间（北京时间 = UTC+8），触发有约 ±15 分钟延迟，属正常现象。

## 📰 RSS 订阅源

| 板块 | 来源 |
|:---|:---|
| 🌍 世界 / 🇺🇸 美国 | BBC News |
| 🇨🇳 中国 | BBC 中文 |
| 🇲🇾 马来西亚 | Free Malaysia Today |
| 💰 财经 | BBC Business、CNA Asia Business |
| 💻 科技 | BBC Tech、Hacker News、TechCrunch |

英文标题自动翻译为中文，原文以斜体附在译文下方；调整订阅源直接修改 `rss_digest.py` 中的 `FEEDS` 列表即可。

## 🚀 快速开始

1. Fork 或 Clone 本仓库到你的 GitHub 账号
2. 按上表配置所需的 Secrets
3. 进入 **Actions** 页签，选择 `📋 每日任务汇总`，点击 **Run workflow** 手动测试
4. 确认无误后，定时任务将自动每日执行

## 📲 通知推送

配置 `SERVERCHAN_KEY` 后，每日汇总结果会通过 [Server酱](https://sct.ftqq.com/) 推送到微信。

推送内容包括：

- 各任务执行状态一览表
- ☁️ 百度网盘 / 📺 Bilibili / 🪙 掘金签到结果
- 📈 B站今日成长值、当前等级与升级进度（如 `Lv5（25105/28800），距离 Lv6 还需 3695`）
- 🏀 NBA 当日赛程与比分
- 📊 ETF 行情
- 💱 汇率对照表（马币/美元/欧元/新币 → 人民币；人民币 → 日元/韩元/港元，各含 1/3/5/10 年前历史值）
- 📰 每日 60s 新闻
- 📡 双语 RSS 资讯

> Server酱 免费版每天限 5 条推送、单条约 5000 字，本项目默认每天占用 2 条（汇总 + RSS）。

## ⚠️ 注意事项

- Actions 免费额度：公开仓库无限制；私有仓库每月 2000 分钟（本项目每天约消耗 5~8 分钟）
- 建议使用**私有仓库**存放含 Cookie 的 Secrets，安全性更高
- Cookie 有效期有限，若推送中出现 `Cookie 失效` 提示请及时更新对应 Secret
- 汇率历史数据来自欧洲央行（Frankfurter API），遇周末/节假日自动取最近交易日
- RSS 英文翻译使用 Google 翻译免费接口，单条失败时自动回退显示英文原文

## 📝 更新日志

- **2026-07**：B站签到新增今日成长值与升级进度；汇率新增 1/3/5/10 年历史对比；RSS 移除失效源（Malay Mail）、新增英文标题中文翻译双语显示；移除京东、天翼云盘、夸克网盘任务
- **2026-06**：从青龙面板迁移至 GitHub Actions
