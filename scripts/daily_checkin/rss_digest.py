#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSS 每日摘要 - GitHub Actions 版
聚合多个 RSS 源，每源取前 N 条，推送 Server酱
cron: 0 2 * * *（北京时间 10:00）
"""

import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from html import unescape

CST = timezone(timedelta(hours=8))

# ── RSS 源配置 ──────────────────────────────────────────────
# (分组名, 显示标签, RSS URL, 每组最多条数)
FEEDS = [
    # ── 世界实时 ──────────────────────────────────────────
    ("world", "🌍 世界",
     "https://feeds.bbci.co.uk/news/world/rss.xml", 4),

    ("world_reuters", "🌍 路透社",
     "https://feeds.reuters.com/reuters/topNews", 4),

    # ── 中国 ──────────────────────────────────────────────
    ("china_bbc", "🇨🇳 中国 (BBC)",
     "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml", 4),

    ("china_reuters", "🇨🇳 中国 (Reuters)",
     "https://feeds.reuters.com/reuters/CNTopNews", 3),

    # ── 美国 ──────────────────────────────────────────────
    ("us_npr", "🇺🇸 美国 (NPR)",
     "https://feeds.npr.org/1001/rss.xml", 3),

    ("us_reuters", "🇺🇸 美国 (Reuters)",
     "https://feeds.reuters.com/Reuters/domesticNews", 3),

    # ── 马来西亚 ──────────────────────────────────────────
    ("my_star", "🇲🇾 马来西亚 (The Star)",
     "https://www.thestar.com.my/rss/news", 4),

    ("my_fmt", "🇲🇾 马来西亚 (FMT)",
     "https://www.freemalaysiatoday.com/category/nation/feed/", 3),

    ("my_cna", "🇲🇾 东南亚 (CNA)",
     "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511", 3),

    # ── 财经 ──────────────────────────────────────────────
    ("finance_reuters", "💰 财经 (Reuters)",
     "https://feeds.reuters.com/reuters/businessNews", 4),

    ("finance_cnbc", "💰 财经 (CNBC)",
     "https://www.cnbc.com/id/100003114/device/rss/rss.html", 3),

    # ── 科技 ──────────────────────────────────────────────
    ("tech_hn", "💻 科技 (Hacker News)",
     "https://hnrss.org/frontpage?count=8", 5),

    ("tech_tc", "💻 科技 (TechCrunch)",
     "https://techcrunch.com/feed/", 4),

    ("tech_ars", "💻 科技 (Ars Technica)",
     "https://feeds.arstechnica.com/arstechnica/index", 3),
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
    """清理 HTML 标签和 CDATA"""
    text = re.sub(r'<!\[CDATA\[|\]\]>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text).strip()
    return text


def fetch_feed(url: str, max_items: int) -> list[dict]:
    """拉取 RSS，返回文章列表"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return []

        root = ET.fromstring(r.content)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}

        items = []

        # RSS 2.0
        for item in root.findall(".//item")[:max_items]:
            title = item.findtext("title", "")
            link  = item.findtext("link", "")
            desc  = item.findtext("description", "")
            pub   = item.findtext("pubDate", "")
            items.append({
                "title": clean(title),
                "link":  link.strip(),
                "desc":  clean(desc)[:80] if desc else "",
                "pub":   pub[:16],
            })

        # Atom
        if not items:
            for entry in root.findall("atom:entry", ns)[:max_items]:
                title = entry.findtext("atom:title", "", ns)
                link_el = entry.find("atom:link", ns)
                link  = link_el.get("href", "") if link_el is not None else ""
                pub   = entry.findtext("atom:published", "", ns)
                items.append({
                    "title": clean(title),
                    "link":  link,
                    "desc":  "",
                    "pub":   pub[:16],
                })

        return items

    except Exception as e:
        print(f"  ERR {url[:50]}: {e}")
        return []


def build_digest() -> str:
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    lines = [f"# 📰 每日资讯  {now}\n"]

    total = 0
    failed = []

    for key, label, url, max_items in FEEDS:
        items = fetch_feed(url, max_items)

        if not items:
            failed.append(label)
            continue

        lines.append(f"\n### {label}\n")
        for item in items:
            title = item["title"]
            link  = item["link"]
            if link:
                lines.append(f"- [{title}]({link})")
            else:
                lines.append(f"- {title}")
        total += len(items)

    if failed:
        lines.append(f"\n> ⚠️ 以下源获取失败: {', '.join(failed)}")

    lines.append(f"\n---\n共 {total} 条资讯")
    return "\n".join(lines)


def push_serverchan(title: str, content: str):
    key = os.environ.get("SERVERCHAN_KEY", "").strip()
    if not key:
        print("⚠️ 未设置 SERVERCHAN_KEY，跳过推送")
        return
    try:
        r = requests.post(
            f"https://sctapi.ftqq.com/{key}.send",
            data={"title": title, "desp": content},
            timeout=10,
        )
        print(f"✅ Server酱推送: {r.json()}")
    except Exception as e:
        print(f"❌ 推送失败: {e}")


def main():
    print(f"==== RSS 摘要 {datetime.now(CST).strftime('%Y-%m-%d %H:%M:%S')} ====")
    digest = build_digest()
    print(digest[:500], "...")

    now   = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    title = f"📰 每日资讯 {now}"
    push_serverchan(title, digest)
    print("==== 完成 ====")


if __name__ == "__main__":
    main()
