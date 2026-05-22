#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
夸克网盘签到 - GitHub Actions 版
Secrets: QUARK_COOKIE（多账号换行分隔）
"""

import os
import time
import requests
from datetime import datetime


def format_bytes(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    return f"{size_bytes:.2f} {units[i]}"


class QuarkSign:
    def __init__(self, cookie, account_index=0):
        self.cookie = cookie
        self.account_index = account_index
        self.mobile_params = self._parse_mobile_params(cookie)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11; M2007J3SC) AppleWebKit/537.36 Chrome/92.0.4515.105 Mobile Safari/537.36',
            'Cookie': self.cookie,
            'Referer': 'https://pan.quark.cn/',
            'Content-Type': 'application/json'
        })

    @staticmethod
    def _parse_mobile_params(cookie: str) -> dict:
        params = {}
        for part in cookie.split(';'):
            part = part.strip()
            if '=' in part:
                key, _, val = part.partition('=')
                if key.strip() in ('kps', 'sign', 'vcode'):
                    params[key.strip()] = val.strip()
        return params

    def _build_params(self, extra=None):
        params = {'pr': 'ucpro', 'fr': 'pc', 'uc_param_str': ''}
        params.update(self.mobile_params)
        if extra:
            params.update(extra)
        return params

    def get_growth_info(self):
        try:
            resp = self.session.get(
                'https://drive-m.quark.cn/1/clouddrive/capacity/growth/info',
                params=self._build_params(), timeout=10
            )
            result = resp.json()
            if result.get('code') == 0:
                return result.get('data', {})
        except Exception:
            pass
        return None

    def do_sign(self):
        try:
            resp = self.session.post(
                'https://drive-m.quark.cn/1/clouddrive/capacity/growth/sign',
                params=self._build_params(),
                json={'sign_cyclic': True},
                timeout=10
            )
            result = resp.json()
            if result.get('code') == 0:
                return True, result.get('data', {})
            return False, result.get('message', '未知错误')
        except Exception as e:
            return False, f"请求异常: {e}"

    def run(self):
        tag = f"账号{self.account_index + 1}" if self.account_index >= 0 else ""
        print(f"\n==== 夸克网盘 {tag} ====")
        growth_info = self.get_growth_info()
        success, result = self.do_sign()

        if success:
            reward = format_bytes(result.get('sign_daily_reward', 0))
            cap = result.get('cap_sign', {})
            progress = cap.get('sign_progress', 0)
            target = cap.get('sign_target', 30)
            print(f"✅ 签到成功")
            print(f"📅 签到记录: 今日已签到+{reward}，连续进度({progress}/{target})")
        else:
            if "已签到" in str(result) or "repeat" in str(result).lower():
                progress, target = 0, 30
                if growth_info:
                    cap = growth_info.get('cap_sign', {})
                    progress = cap.get('sign_progress', 0)
                    target = cap.get('sign_target', 30)
                print(f"✅ 签到成功")
                print(f"📅 签到记录: 今日已签到+0 MB，连续进度({progress}/{target})")
            else:
                print(f"❌ 签到失败: {result}")


def main():
    cookie_env = os.getenv('QUARK_COOKIE', '').strip()
    if not cookie_env:
        print("❌ 未设置 QUARK_COOKIE Secret")
        raise SystemExit(1)

    cookies = [c.strip() for c in cookie_env.split('\n') if c.strip()]
    print(f"==== 夸克网盘签到 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    print(f"📝 共 {len(cookies)} 个账号")

    for i, cookie in enumerate(cookies):
        QuarkSign(cookie, i if len(cookies) > 1 else -1).run()
        if i < len(cookies) - 1:
            time.sleep(3)

    print(f"\n==== 完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")


if __name__ == '__main__':
    main()
