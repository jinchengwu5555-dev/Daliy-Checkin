#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
名称：今日汇率
定时：0 9 * * 1-5
"""

import requests
from datetime import datetime, timezone, timedelta


def main():
    now = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')
    lines = [f'### 💱 今日汇率  {now}\n']

    try:
        r = requests.get('https://open.er-api.com/v6/latest/CNY', timeout=10)
        rates = r.json().get('rates', {})

        def to_cny(code):
            rate = rates.get(code)
            return round(1 / rate, 4) if rate else None

        lines.append('| 货币 | 1 外币 → 人民币 |')
        lines.append('|:---|:---:|')
        for code, name, flag in [
            ('MYR', '马币', '🇲🇾'),
            ('USD', '美元', '🇺🇸'),
            ('EUR', '欧元', '🇪🇺'),
            ('SGD', '新币', '🇸🇬'),
        ]:
            val = to_cny(code)
            if val:
                lines.append(f"| {flag} {name} | **{val}** 元 |")

        lines.append('\n| 货币 | 1 人民币 → 外币 |')
        lines.append('|:---|:---:|')
        for code, name, flag in [
            ('JPY', '日元', '🇯🇵'),
            ('KRW', '韩元', '🇰🇷'),
            ('HKD', '港元', '🇭🇰'),
        ]:
            rate = rates.get(code)
            if rate:
                lines.append(f"| {flag} {name} | **{round(rate, 4)}** |")

    except Exception as e:
        lines.append(f"\n⚠️ 获取失败: {e}")

    result = '\n'.join(lines)
    print(result)


if __name__ == '__main__':
    main()
