# 📋 Daily Checkin — GitHub Actions 版

将原青龙面板的每日任务迁移至 GitHub Actions，无需服务器，完全免费运行。

## 📁 目录结构

```
.github/
  workflows/
    daily_summary.yml      # 主工作流：每日 09:10 (北京时间) 运行全部任务
    etf_stock.yml          # 单独工作流：工作日 09:30 / 15:00 运行行情
    exchange_rates.yml     # 单独工作流：工作日 09:00 运行汇率
scripts/
  daily_checkin/
    baiduwangpan_checkin.py
    bilibili_checkin.py
    ty_netdisk_checkin.py
    quark_sign.py
    nba_schedule.py
    etf_stock.py
    exchange_rates.py
    news_60s.py
    jd_sign.js
    juejin_checkin.js
    package.json
  summary_push.py          # 汇总推送脚本
```

## 🔑 GitHub Secrets 配置

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加以下 Secret：

| Secret 名称 | 说明 | 多账号格式 |
|:---|:---|:---|
| `BAIDU_COOKIE` | 百度网盘 Cookie | 换行分隔 |
| `TY_USERNAME` | 天翼云盘用户名 | 换行分隔（与密码一一对应） |
| `TY_PASSWORD` | 天翼云盘密码 | 换行分隔 |
| `QUARK_COOKIE` | 夸克网盘 Cookie | 换行分隔 |
| `BILIBILI_COOKIE` | Bilibili Cookie | `&` 或换行分隔 |
| `JUEJIN_COOKIES` | 掘金 Cookie | `#` 分隔 |
| `JD_COOKIE` | 京东 Cookie | `&` 或换行分隔 |
| `SERVERCHAN_KEY` | Server酱推送 Key（可选） | 单值 |

> 未配置对应 Secret 的任务会以 `❌ 未设置 XXX Secret` 提示并退出，**不会导致整个工作流失败**。

## ⏰ 定时说明

| 工作流 | 北京时间 | 备注 |
|:---|:---|:---|
| `daily_summary.yml` | 每天 09:10 | 签到类 + NBA + 新闻 |
| `etf_stock.yml` | 工作日 09:30 / 15:00 | 开盘 + 收盘行情 |
| `exchange_rates.yml` | 工作日 09:00 | 早间汇率 |

> GitHub Actions 的 cron 使用 UTC 时间，北京时间 = UTC+8。

## 🚀 快速开始

1. Fork 或 Clone 本仓库到你的 GitHub 账号
2. 按上表配置所需的 Secrets
3. 进入 **Actions** 页签，选择 `📋 每日任务汇总`，点击 **Run workflow** 手动测试
4. 确认无误后，定时任务将自动每日执行

## 📲 通知推送

配置 `SERVERCHAN_KEY` 后，每日汇总结果会通过 [Server酱](https://sct.ftqq.com/) 推送到微信。

推送内容示例：
```
# 📋 每日任务汇总  2025-06-01 09:12

| 任务 | 状态 |
|:---|:---:|
| ☁️ 百度网盘 | ✅ success |
| ☁️ 天翼云盘 | ✅ success |
| 🟠 夸克网盘 | ✅ success |
...

共 10 个任务，成功 9 个，失败 1 个

🔗 查看详细日志
```

## ⚠️ 注意事项

- Actions 免费额度：公开仓库无限制；私有仓库每月 2000 分钟（本项目每天约消耗 5~8 分钟）
- 建议使用**私有仓库**存放含 Cookie 的 Secrets，安全性更高
- Cookie 有效期有限，定期检查并更新 Secrets
- GitHub Actions 的 cron 触发有约 ±15 分钟的延迟，属正常现象
