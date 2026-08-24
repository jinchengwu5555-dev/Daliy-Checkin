#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日 60s 新闻（静态数据仓库直读版）
数据源：vikiboss/60s-static-host 的每日 JSON，经 CDN 分发
优势：绕过官方 API 的限流，直接读 CDN 静态文件，稳定可靠
"""

import requests
from datetime import datetime, timezone, timedelta

# 同一份数据的多个 CDN 镜像，按顺序尝试
# {date} 会被替换为 YYYY-MM-DD
CDN_TEMPLATES = [
    'https://cdn.jsdelivr.net/gh/vikiboss/60s-static-host@main/static/60s/{date}.json',
    'https://cdn.jsdmirror.com/gh/vikiboss/60s-static-host@main/static/60s/{date}.json',
    'https://raw.githubusercontent.com/vikiboss/60s-static-host/main/static/60s/{date}.json',
    'https://60s-static.viki.moe/60s/{date}.json',
]

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/126.0.0.0 Safari/537.36'),
}


SCRIPT_VERSION = 'news-v3-20260824'


def fetch_one_date(date_str):
    """尝试所有 CDN 获取指定日期数据；成功返回 dict，全失败返回 None"""
    for tpl in CDN_TEMPLATES:
        url = tpl.format(date=date_str)
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200 or '<html' in r.text[:200].lower():
                continue
            d = r.json()
            if d.get('news'):
                return d
        except Exception:
            continue
    return None


def fetch_news():
    """优先取今天，取不到则回退到昨天（数据最晚上午更新，凌晨可能还没出）"""
    now = datetime.now(timezone(timedelta(hours=8)))
    for delta in (0, 1):
        date_str = (now - timedelta(days=delta)).strftime('%Y-%m-%d')
        data = fetch_one_date(date_str)
        if data:
            return data
    return None


def main():
    print(f'🔖 脚本版本: {SCRIPT_VERSION}')
    data = fetch_news()
    if not data:
        print("⚠️ 今日新闻暂未更新，稍后再试")
        return

    date = data.get('date', '')
    news = data.get('news', [])
    tip = data.get('tip', '')

    print(f"每天 60 秒读懂世界 · {date}")
    half = (len(news) + 1) // 2
    for item in news[:half]:
        print(item)
    print('---')
    for item in news[half:]:
        print(item)
    if tip:
        print(f"【微语】{tip}")


if __name__ == '__main__':
    main()
