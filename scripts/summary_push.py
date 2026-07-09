#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总推送脚本 - GitHub Actions 版
"""

import os
import re
import requests
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

TASKS = [
    ("baidu",     "☁️ 百度网盘",  "output-baidu"),
    ("bilibili",  "📺 Bilibili",  "output-bilibili"),
    ("juejin",    "🪙 掘金",      "output-juejin"),
    ("nba",       "🏀 NBA赛程",   "output-nba"),
    ("etf",       "📊 ETF行情",   "output-etf"),
    ("exchange",  "💱 今日汇率",  "output-exchange"),
    ("news",      "📰 每日60s",   "output-news"),
    ("rss",       "📡 RSS资讯",    "output-rss"),
]

RESULT_ICON = {
    "success":   "✅",
    "failure":   "❌",
    "skipped":   "⏭️",
    "cancelled": "🚫",
}

ARTIFACT_ROOT = "/tmp/job_outputs"


def clean_output(output):
    skip_patterns = [
        r"^##\s*(开始执行|执行结束)",
        r"^tee:",
        r"^\s*$",
    ]
    lines = []
    for line in output.splitlines():
        if any(re.match(p, line) for p in skip_patterns):
            continue
        lines.append(line)
    return lines


def normalize_signin_msg(line):
    """把 API 返回的英文错误码统一转为中文"""
    line = re.sub(r'repeat\s*signin', '今日已签到', line, flags=re.IGNORECASE)
    line = re.sub(r'already\s*signed', '今日已签到', line, flags=re.IGNORECASE)
    return line


def extract_summary(label, output):
    lines = clean_output(output)

    if "百度网盘" in label:
        keys = ["👤 用户:", "📊 成长值:", "📝 签到:", "🤔 答题:"]
        result = []
        for l in lines:
            if any(k in l for k in keys):
                result.append(normalize_signin_msg(l))
        return result

    if "天翼云盘" in label:
        keys = ["账号信息", "签到状态", "签到成功", "已签到", "登录失败"]
        seen, result = set(), []
        for l in lines:
            if any(k in l for k in keys) and l not in seen:
                seen.add(l)
                result.append(l)
        return result

    if "夸克" in label:
        keys = ["签到成功", "签到记录", "签到失败"]
        result = []
        for l in lines:
            if any(k in l for k in keys):
                # 去掉行首时间戳和账号前缀
                cleaned = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s*', '', l)
                cleaned = re.sub(r'^\[账号\d+\]\s*', '', cleaned)
                result.append(cleaned)
        return result

    if "Bilibili" in label:
        keys = ["用户:", "签到", "观看", "投币", "分享",
                "今日成长值", "当前等级", "还需"]
        return [l for l in lines if any(k in l for k in keys)]

    if "掘金" in label:
        keys = ["用户:", "签到", "矿石", "连续", "沾喜气", "免费抽奖", "当前矿石"]
        return [l for l in lines if any(k in l for k in keys)]

    if "NBA" in label:
        skip = ["ESPN让分数据获取成功", "[信息]", "[警告]"]
        return [l for l in lines if l.strip() and not any(k in l for k in skip) and not re.match(r'^\|[-: |]+\|$', l)]

    if "ETF" in label:
        # 保留表格分隔行，markdown 表格渲染需要它
        return [l for l in lines if l.strip()]

    if "汇率" in label:
        # 原样保留（含空行），两张表之间必须有空行才能正确渲染
        return lines

    if "60s" in label:
        # 每条新闻后插入空行，Server酱 markdown 需要 \n\n 才能换行
        result = []
        for l in lines:
            if l.strip():
                result.append(l)
                result.append("")
        return result

    if "RSS" in label:
        result = []
        for l in lines:
            if l.strip() and not l.startswith("# 📰"):
                result.append(l)
        return result

    return [l for l in lines if l.strip()]


def read_artifact(artifact_dir, filename):
    path = os.path.join(ARTIFACT_ROOT, artifact_dir, filename)
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    alt = os.path.join(ARTIFACT_ROOT, filename)
    if os.path.exists(alt):
        with open(alt, encoding="utf-8", errors="replace") as f:
            return f.read()
    return ""


def main():
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    run_url = os.environ.get("GITHUB_RUN_URL", "")

    sections = []
    success_count = 0
    total = len(TASKS)

    for key, label, artifact_dir in TASKS:
        job_result = os.environ.get(f"RESULT_{key.upper()}", "unknown")
        status_icon = RESULT_ICON.get(job_result, "❓")
        if job_result == "success":
            success_count += 1

        raw_output = read_artifact(artifact_dir, f"{key}.txt")

        if raw_output.strip():
            summary_lines = extract_summary(label, raw_output)
            content = "\n".join(summary_lines) if summary_lines else "(无关键输出)"
        else:
            content = f"{status_icon} {job_result}（无输出文件）"

        sections.append(f"### {label}\n\n{content}")

    header = (
        f"# 📋 每日任务汇总  {now}\n\n"
        f"**共 {total} 个任务　✅ 成功 {success_count}　❌ 失败 {total - success_count}**"
    )
    if run_url:
        header += f"\n\n🔗 [查看详细日志]({run_url})"

    desp = header + "\n\n---\n\n" + "\n\n---\n\n".join(sections)
    print(desp)

    sc_key = os.environ.get("SERVERCHAN_KEY", "").strip()
    if not sc_key:
        print("\n⚠️ 未设置 SERVERCHAN_KEY，跳过推送")
        return

    title = f"📋 每日汇总 {now}（{success_count}/{total}）"
    try:
        r = requests.post(
            f"https://sctapi.ftqq.com/{sc_key}.send",
            data={"title": title, "desp": desp},
            timeout=10,
        )
        print(f"\n✅ Server酱推送: {r.json()}")
    except Exception as e:
        print(f"\n❌ Server酱推送失败: {e}")


if __name__ == "__main__":
    main()
