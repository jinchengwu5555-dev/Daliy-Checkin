#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSS 每日摘要 - GitHub Actions 版
聚合多个 RSS 源推送 Server酱
注意：Server酱免费版每天限 5 次推送，本脚本合并为 1 次推送
"""

import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from html import unescape

CST = timezone(timedelta(hours=8))

# ── RSS 源配置 ──────────────────────────────────────────────
# (key, 显示标签, URL, 条数)
FEEDS = [
    # 🌍 世界
    ("world",    "🌍 世界",         "https://feeds.bbci.co.uk/news/world/rss.xml",              4),
    # 🇨🇳 中国
    ("china",    "🇨🇳 中国",         "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml",            4),
    # 🇺🇸 美国
    ("us",       "🇺🇸 美国",         "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", 3),
    # 🇲🇾 马来西亚
    ("my_star",  "🇲🇾 马来 (Star)",  "https://www.thestar.com.my/rss/news",                       3),
    ("my_fmt",   "🇲🇾 马来 (FMT)",   "https://www.freemalaysiatoday.com/category/nation/feed/",   3),
    # 💰 财经
    ("biz",      "💰 财经",          "https://feeds.bbci.co.uk/news/business/rss.xml",             4),
    ("asia_biz", "💰 亚洲财经 (CNA)","https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6936", 3),
    # 💻 科技
    ("tech_bbc", "💻 科技 (BBC)",    "https://feeds.bbci.co.uk/news/technology/rss.xml",           3),
    ("tech_hn",  "💻 科技 (HN)",     "https://hnrss.org/frontpage?count=8",                        5),
    ("tech_tc",  "💻 科技 (TC)",     "https://techcrunch.com/feed/",                               3),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def clean(text: str) -> str:
    text = re.sub(r'<!\[CDATA\[|\]\]>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    return unescape(text).strip()


def fetch_feed(url: str, max_items: int) -> list[dict]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            print(f"  ⚠️ {url.split('/')[2]} → {r.status_code}")
            return []
        root   = ET.fromstring(r.content)
        items  = []
        for item in root.findall(".//item")[:max_items]:
            title = clean(item.findtext("title", ""))
            link  = (item.findtext("link") or "").strip()
            if title:
                items.append({"title": title, "link": link})
        # Atom fallback
        if not items:
            ns = "http://www.w3.org/2005/Atom"
            for entry in root.findall(f"{{{ns}}}entry")[:max_items]:
                title  = clean(entry.findtext(f"{{{ns}}}title", ""))
                link_el = entry.find(f"{{{ns}}}link")
                link   = link_el.get("href", "") if link_el is not None else ""
                if title:
                    items.append({"title": title, "link": link})
        return items
    except Exception as e:
        print(f"  ❌ {url.split('/')[2]}: {e}")
        return []


def build_digest() -> tuple[str, int]:
    now    = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    lines  = [f"# 📰 每日资讯  {now}\n"]
    total  = 0
    failed = []

    for key, label, url, max_items in FEEDS:
        items = fetch_feed(url, max_items)
        if not items:
            failed.append(label)
            continue
        lines.append(f"\n### {label}\n")
        for item in items:
            t = item["title"]
            l = item["link"]
            # Server酱 Markdown 支持链接，但太长会截断
            # 标题超过 60 字符截断
            t_short = t[:58] + "…" if len(t) > 60 else t
            if l:
                lines.append(f"- [{t_short}]({l})")
            else:
                lines.append(f"- {t_short}")
        total += len(items)

    if failed:
        lines.append(f"\n> ⚠️ 获取失败: {', '.join(failed)}")

    lines.append(f"\n\n---\n共 **{total}** 条  |  {now}")
    return "\n".join(lines), total


def push_serverchan(title: str, content: str):
    key = os.environ.get("SERVERCHAN_KEY", "").strip()
    if not key:
        print("⚠️ 未设置 SERVERCHAN_KEY，跳过推送")
        return

    # Server酱 免费版单条限 5000 字，超出截断
    MAX_LEN = 4800
    if len(content) > MAX_LEN:
        content = content[:MAX_LEN] + "\n\n…(内容已截断)"

    try:
        r = requests.post(
            f"https://sctapi.ftqq.com/{key}.send",
            data={"title": title, "desp": content},
            timeout=10,
        )
        result = r.json()
        code   = result.get("code", result.get("errno", 0))
        msg    = result.get("message", result.get("errmsg", ""))
        if code == 0:
            print(f"✅ 推送成功")
        else:
            print(f"❌ 推送失败: {msg}")
    except Exception as e:
        print(f"❌ 推送异常: {e}")


def main():
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"==== RSS 摘要 {now} ====")

    digest, total = build_digest()

    # 打印摘要预览
    for line in digest.split("\n")[:6]:
        print(line)
    print(f"... 共 {total} 条")

    title = f"📰 每日资讯 {datetime.now(CST).strftime('%Y-%m-%d')}"
    push_serverchan(title, digest)
    print("==== 完成 ====")


if __name__ == "__main__":
    main()
