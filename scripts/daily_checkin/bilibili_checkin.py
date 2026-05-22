#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bilibili 签到 - GitHub Actions 版
Secrets: BILIBILI_COOKIE（多账号用 & 或换行分隔）
"""

import os
import requests
import time
import sys


def get_csrf(cookie):
    for item in cookie.split(';'):
        if 'bili_jct' in item:
            return item.split('=')[1].strip()
    return ''


def checkin(cookie: str, index: int = 0):
    tag = f"账号{index + 1}"
    print(f"\n📺 Bilibili [{tag}]")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Cookie': cookie,
        'Referer': 'https://www.bilibili.com/'
    }

    # 验证 Cookie
    try:
        r = requests.get('https://api.bilibili.com/x/web-interface/nav', headers=headers, timeout=10)
        d = r.json()
        if d['code'] == 0:
            print(f"用户: {d['data']['uname']}")
        else:
            print("❌ 签到失败: Cookie 失效")
            return
    except Exception as e:
        print(f"❌ 签到失败: {e}")
        return

    print("✅ 签到成功")

    # 获取推荐视频
    videos = []
    try:
        r = requests.get(
            'https://api.bilibili.com/x/web-interface/index/top/rcmd',
            headers=headers, params={'fresh_type': 3, 'ps': 10}, timeout=10
        )
        d = r.json()
        if d['code'] == 0:
            videos = [item['id'] for item in d['data']['item'] if 'id' in item][:5]
    except Exception:
        pass

    if not videos:
        return

    # 观看视频
    try:
        r = requests.get(f'https://api.bilibili.com/x/web-interface/view?aid={videos[0]}', headers=headers, timeout=10)
        d = r.json()
        if d['code'] == 0:
            cid = d['data']['cid']
            requests.post(
                'https://api.bilibili.com/x/click-interface/web/heartbeat',
                headers=headers,
                data={'aid': videos[0], 'cid': cid, 'played_time': 60, 'csrf': get_csrf(cookie)},
                timeout=10
            )
            print("✅ 观看视频成功")
    except Exception as e:
        print(f"⚠️ 观看视频异常: {e}")

    # 投币
    coin_ok = 0
    for aid in videos[:2]:
        try:
            r = requests.post(
                'https://api.bilibili.com/x/web-interface/coin/add',
                headers=headers,
                data={'aid': aid, 'multiply': 1, 'select_like': 1, 'cross_domain': 'true', 'csrf': get_csrf(cookie)},
                timeout=10
            )
            if r.json().get('code') == 0:
                coin_ok += 1
            time.sleep(2)
        except Exception:
            pass
    print(f"✅ 投币成功: {coin_ok} 枚")

    # 分享
    try:
        r = requests.post(
            'https://api.bilibili.com/x/web-interface/share/add',
            headers=headers,
            data={'aid': videos[0], 'csrf': get_csrf(cookie)},
            timeout=10
        )
        if r.json().get('code') == 0:
            print("✅ 分享视频成功")
    except Exception:
        pass


def main():
    raw = os.environ.get('BILIBILI_COOKIE', '').strip()
    if not raw:
        print("📺 Bilibili\n❌ 签到失败: 未设置 BILIBILI_COOKIE Secret")
        sys.exit(1)

    cookies = [c.strip() for c in raw.replace('\n', '&').split('&') if c.strip()]
    for i, cookie in enumerate(cookies):
        if i > 0:
            print('-' * 30)
            time.sleep(3)
        checkin(cookie, i)


if __name__ == '__main__':
    main()
