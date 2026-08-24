#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日 60s 新闻（多镜像容错版）
数据源：vikiboss/60s 项目公共实例，按顺序轮询
"""

import requests

# 按顺序尝试的镜像列表（都是同一项目的公共部署）
ENDPOINTS = [
    'https://60s.viki.moe/v2/60s',
    'https://60s-api.viki.moe/v2/60s',
    'https://60s-api-cf.viki.moe/v2/60s',
]

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/126.0.0.0 Safari/537.36'),
    'Accept': 'application/json',
}


SCRIPT_VERSION = 'news-v2-20260710'


def fetch_news():
    """返回 (date, news_list, tip)；全部失败返回 None"""
    for url in ENDPOINTS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            # 反爬拦截页 / 非 JSON 一律跳过
            if r.status_code != 200 or '<html' in r.text[:500].lower():
                print(f"⚙️ 跳过 {url}: HTTP {r.status_code} 或返回 HTML")
                continue
            d = r.json()
            data = d.get('data') or {}
            news = data.get('news') or []
            if not news:
                print(f"⚙️ 跳过 {url}: 无新闻数据")
                continue
            return data.get('date', ''), news, data.get('tip', '')
        except Exception as e:
            print(f"⚙️ 跳过 {url}: {e}")
    return None


def main():
    print(f'🔖 脚本版本: {SCRIPT_VERSION}')
    result = fetch_news()
    if not result:
        print("⚠️ 今日新闻源全部不可用（可能被反爬拦截），暂无内容")
        return

    date, news, tip = result
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
