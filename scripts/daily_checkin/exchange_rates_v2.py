#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
名称：今日汇率（含 1/3/5/10 年前对比）
数据源：今日 open.er-api.com；历史 api.frankfurter.dev（欧洲央行）
"""

import requests
from datetime import datetime, timezone, timedelta

# 外币 → 人民币（1 外币值多少元）
TO_CNY = [
    ('MYR', '马币', '🇲🇾'),
    ('USD', '美元', '🇺🇸'),
    ('EUR', '欧元', '🇪🇺'),
    ('SGD', '新币', '🇸🇬'),
]
# 人民币 → 外币（1 元换多少外币）
FROM_CNY = [
    ('JPY', '日元', '🇯🇵'),
    ('KRW', '韩元', '🇰🇷'),
    ('HKD', '港元', '🇭🇰'),
]
ALL_CODES = [c for c, _, _ in TO_CNY + FROM_CNY]
YEARS_AGO = [1, 3, 5, 10]


SCRIPT_VERSION = 'exchange-v2-20260709'


def fetch_history(now_dt):
    """返回 {年数: {code: CNY→code 汇率}}，失败的年份为 None"""
    hist = {}
    for y in YEARS_AGO:
        try:
            date = (now_dt - timedelta(days=365 * y)).strftime('%Y-%m-%d')
            r = requests.get(
                f'https://api.frankfurter.dev/v1/{date}',
                params={'base': 'CNY', 'symbols': ','.join(ALL_CODES)},
                timeout=10
            )
            hist[y] = r.json().get('rates', {}) if r.status_code == 200 else None
        except Exception:
            hist[y] = None
    return hist


def fmt(val, invert=False):
    """格式化汇率；invert=True 表示取倒数（CNY→X 转成 X→CNY）"""
    if not val:
        return '—'
    v = 1 / val if invert else val
    return f'{v:.4f}' if v < 100 else f'{v:.2f}'


def main():
    now_dt = datetime.now(timezone(timedelta(hours=8)))
    print(f'🔖 脚本版本: {SCRIPT_VERSION}', flush=True)
    lines = [f"🕘 更新于 {now_dt.strftime('%Y-%m-%d %H:%M')}", '']

    try:
        # 今日实时汇率（CNY 为基准，值为 CNY→X）
        r = requests.get('https://open.er-api.com/v6/latest/CNY', timeout=10)
        today = r.json().get('rates', {})
        hist = fetch_history(now_dt)

        header = '| 货币 | 今日 | 1年前 | 3年前 | 5年前 | 10年前 |'
        sep = '|:---|:---:|:---:|:---:|:---:|:---:|'

        # 表一：1 外币 → 人民币
        lines.append('**1 外币 → 人民币（元）**')
        lines.append('')
        lines.append(header)
        lines.append(sep)
        for code, name, flag in TO_CNY:
            cells = [fmt(today.get(code), invert=True)]
            for y in YEARS_AGO:
                h = hist.get(y) or {}
                cells.append(fmt(h.get(code), invert=True))
            lines.append(f"| {flag} {name} | **{cells[0]}** | {' | '.join(cells[1:])} |")

        # 表二：1 人民币 → 外币
        lines.append('')
        lines.append('**1 人民币 → 外币**')
        lines.append('')
        lines.append(header)
        lines.append(sep)
        for code, name, flag in FROM_CNY:
            cells = [fmt(today.get(code))]
            for y in YEARS_AGO:
                h = hist.get(y) or {}
                cells.append(fmt(h.get(code)))
            lines.append(f"| {flag} {name} | **{cells[0]}** | {' | '.join(cells[1:])} |")

        lines.append('')
        lines.append('> 历史数据来自欧洲央行（取最近交易日）')

    except Exception as e:
        lines.append(f"⚠️ 获取失败: {e}")

    print('\n'.join(lines))


if __name__ == '__main__':
    main()
