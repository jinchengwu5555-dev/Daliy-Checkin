#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总推送脚本 - GitHub Actions 版
从各 job 上传的 artifact 文件中读取输出，提炼关键信息，推送 Server酱
输出格式参考原 daily_summary.py 的 extract_summary() 逻辑
"""

import os
import re
import requests
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

# (job key, 显示标签, artifact 子目录名)
TASKS = [
    ("baidu",     "☁️ 百度网盘",  "output-baidu"),
    ("tianyiyun", "☁️ 天翼云盘",  "output-tianyiyun"),
    ("quark",     "🟠 夸克网盘",  "output-quark"),
    ("bilibili",  "📺 Bilibili",  "output-bilibili"),
    ("juejin",    "🪙 掘金",      "output-juejin"),
    ("jd",        "🛒 京东",      "output-jd"),
    ("nba",       "🏀 NBA赛程",   "output-nba"),
    ("etf",       "📊 ETF行情",   "output-etf"),
    ("exchange",  "💱 今日汇率",  "output-exchange"),
    ("news",      "📰 每日60s",   "output-news"),
]

RESULT_ICON = {
    "success":   "✅",
    "failure":   "❌",
    "skipped":   "⏭️",
    "cancelled": "🚫",
}

# artifact 下载后的根目录
ARTIFACT_ROOT = "/tmp/job_outputs"


# ── 输出清洗 ────────────────────────────────────────────────

def clean_output(output: str) -> list[str]:
    """去掉空行和青龙/tee 产生的噪音行"""
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


# ── 各任务关键信息提炼 ──────────────────────────────────────

def extract_summary(label: str, output: str) -> list[str]:
    lines = clean_output(output)

    if "百度网盘" in label:
        keys = ["👤 账号:", "🏆 等级:", "💎 会员:", "📝 签到:", "🤔 答题:"]
        return [l for l in lines if any(k in l for k in keys)]

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
                # 去掉行首时间戳 "2025-06-01 09:10:00 "
                cleaned = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s*', '', l)
                result.append(cleaned)
        return result

    if "Bilibili" in label:
        keys = ["用户:", "签到", "观看", "投币", "分享"]
        return [l for l in lines if any(k in l for k in keys)]

    if "掘金" in label:
        keys = ["用户:", "签到", "矿石", "连续", "沾喜气", "免费抽奖", "当前矿石"]
        return [l for l in lines if any(k in l for k in keys)]

    if "京东" in label:
        keys = ["签到", "积分", "京豆", "连续", "失败", "已签到"]
        return [l for l in lines if any(k in l for k in keys)]

    if "NBA" in label:
        skip = ["ESPN让分数据获取成功", "[信息]", "[警告]"]
        return [l for l in lines if l.strip() and not any(k in l for k in skip)]

    if "ETF" in label:
        return [l for l in lines if l.strip()]

    if "汇率" in label:
        # 去掉 markdown 表格分隔行 "|:---|:---:|"
        return [l for l in lines if l.strip() and not re.match(r'^\|[-: |]+\|$', l)]

    if "60s" in label:
        return [l for l in lines if l.strip()]

    return [l for l in lines if l.strip()]


# ── 读取 artifact 文件 ──────────────────────────────────────

def read_artifact(artifact_dir: str, filename: str) -> str:
    """
    actions/download-artifact@v4 with merge-multiple:false
    会把每个 artifact 解压到 <path>/<artifact-name>/<文件名>
    """
    path = os.path.join(ARTIFACT_ROOT, artifact_dir, filename)
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    # 兼容：有时文件直接在 artifact_dir 目录下（无子文件夹层）
    alt = os.path.join(ARTIFACT_ROOT, filename)
    if os.path.exists(alt):
        with open(alt, encoding="utf-8", errors="replace") as f:
            return f.read()
    return ""


# ── 主逻辑 ──────────────────────────────────────────────────

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

        # 文件名与 job key 保持一致
        raw_output = read_artifact(artifact_dir, f"{key}.txt")

        if raw_output.strip():
            summary_lines = extract_summary(label, raw_output)
            content = "\n".join(summary_lines) if summary_lines else "(无关键输出)"
        else:
            content = f"{status_icon} {job_result}（无输出文件）"

        sections.append(f"### {label}\n\n{content}")

    # 组合完整报告
    header = (
        f"# 📋 每日任务汇总  {now}\n\n"
        f"**共 {total} 个任务　✅ 成功 {success_count}　❌ 失败 {total - success_count}**"
    )
    if run_url:
        header += f"\n\n🔗 [查看详细日志]({run_url})"

    desp = header + "\n\n---\n\n" + "\n\n---\n\n".join(sections)
    print(desp)

    # 推送 Server酱
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
