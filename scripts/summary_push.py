#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总推送脚本
由 GitHub Actions summary job 调用
读取各 job 的执行结果状态，生成汇总报告并推送 Server酱
"""

import os
import requests
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

TASKS = [
    ("baidu",     "☁️ 百度网盘"),
    ("tianyiyun", "☁️ 天翼云盘"),
    ("quark",     "🟠 夸克网盘"),
    ("bilibili",  "📺 Bilibili"),
    ("juejin",    "🪙 掘金"),
    ("jd",        "🛒 京东"),
    ("nba",       "🏀 NBA赛程"),
    ("etf",       "📊 ETF行情"),
    ("exchange",  "💱 今日汇率"),
    ("news",      "📰 每日60s"),
]

ICON = {
    "success": "✅",
    "failure": "❌",
    "skipped": "⏭️",
    "cancelled": "🚫",
}


def main():
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    run_url = os.environ.get("GITHUB_RUN_URL", "")

    lines = [f"# 📋 每日任务汇总  {now}\n"]
    lines.append("| 任务 | 状态 |")
    lines.append("|:---|:---:|")

    success_count = 0
    total = len(TASKS)

    for key, label in TASKS:
        result = os.environ.get(f"RESULT_{key.upper()}", "unknown")
        icon = ICON.get(result, "❓")
        if result == "success":
            success_count += 1
        lines.append(f"| {label} | {icon} {result} |")

    lines.append(f"\n**共 {total} 个任务，成功 {success_count} 个，失败 {total - success_count} 个**")

    if run_url:
        lines.append(f"\n🔗 [查看详细日志]({run_url})")

    desp = "\n".join(lines)
    print(desp)

    # 推送 Server酱
    key = os.environ.get("SERVERCHAN_KEY", "").strip()
    if not key:
        print("\n⚠️ 未设置 SERVERCHAN_KEY，跳过推送")
        return

    title = f"📋 每日汇总 {now} （{success_count}/{total}）"
    try:
        r = requests.post(
            f"https://sctapi.ftqq.com/{key}.send",
            data={"title": title, "desp": desp},
            timeout=10,
        )
        print(f"\n✅ Server酱推送结果: {r.json()}")
    except Exception as e:
        print(f"\n❌ Server酱推送失败: {e}")


if __name__ == "__main__":
    main()
