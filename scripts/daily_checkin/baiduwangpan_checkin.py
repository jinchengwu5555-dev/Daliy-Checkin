#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
百度网盘签到 - GitHub Actions 版
Secrets: BAIDU_COOKIE（多账号用换行分隔）
         PRIVACY_MODE（可选，默认 true）
"""

import os
import time
import re
import requests
import random
from datetime import datetime

BAIDU_COOKIE = os.environ.get('BAIDU_COOKIE', '')
privacy_mode = os.getenv("PRIVACY_MODE", "true").lower() == "true"

HEADERS = {
    'Connection': 'keep-alive',
    'Accept': 'application/json, text/plain, */*',
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
    ),
    'X-Requested-With': 'XMLHttpRequest',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    'Referer': 'https://pan.baidu.com/wap/svip/growth/task',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}


class BaiduPan:
    def __init__(self, cookie: str, index: int = 1):
        self.cookie = cookie
        self.index = index

    def signin(self):
        url = "https://pan.baidu.com/rest/2.0/membership/level?app_id=250528&web=5&method=signin"
        h = {**HEADERS, 'Cookie': self.cookie}
        try:
            resp = requests.get(url, headers=h, timeout=15)
            if resp.status_code == 200:
                sign_point = re.search(r'points":(\d+)', resp.text)
                error_msg  = re.search(r'"error_msg":"(.*?)"', resp.text)
                if sign_point:
                    pts = sign_point.group(1)
                    print(f"✅ 签到成功，获得积分: {pts}")
                    return True, f"签到成功，获得{pts}积分"
                if error_msg and error_msg.group(1):
                    msg = error_msg.group(1)
                    if any(k in msg for k in ["已签到", "重复签到", "not allow", "repeat"]):
                        print("📅 今日已签到")
                        return True, "今日已签到"
                    print(f"❌ 签到失败: {msg}")
                    return False, f"签到失败: {msg}"
                print("✅ 签到成功（未检索到积分）")
                return True, "签到成功"
            return False, f"签到失败，状态码: {resp.status_code}"
        except Exception as e:
            return False, f"签到异常: {e}"

    def get_daily_question(self):
        url = "https://pan.baidu.com/act/v2/membergrowv2/getdailyquestion?app_id=250528&web=5"
        h = {**HEADERS, 'Cookie': self.cookie}
        try:
            resp = requests.get(url, headers=h, timeout=15)
            if resp.status_code == 200:
                answer = re.search(r'"answer":(\d+)', resp.text)
                ask_id = re.search(r'"ask_id":(\d+)', resp.text)
                question = re.search(r'"question":"(.*?)"', resp.text)
                if answer and ask_id:
                    if question:
                        print(f"❓ 今日问题: {question.group(1)}")
                    return answer.group(1), ask_id.group(1)
        except Exception as e:
            print(f"⚠️ 获取问题异常: {e}")
        return None, None

    def answer_question(self, answer, ask_id):
        url = (
            f"https://pan.baidu.com/act/v2/membergrowv2/answerquestion"
            f"?app_id=250528&web=5&ask_id={ask_id}&answer={answer}"
        )
        h = {**HEADERS, 'Cookie': self.cookie}
        try:
            resp = requests.get(url, headers=h, timeout=15)
            if resp.status_code == 200:
                score = re.search(r'"score":(\d+)', resp.text)
                msg   = re.search(r'"show_msg":"(.*?)"', resp.text)
                if score:
                    print(f"✅ 答题成功，获得积分: {score.group(1)}")
                    return True, f"答题成功，获得{score.group(1)}积分"
                if msg and msg.group(1):
                    m = msg.group(1)
                    if any(k in m for k in ["已回答", "exceeded", "超出", "超限"]):
                        print("📅 今日已答题")
                        return True, "今日已答题"
                    return False, f"答题失败: {m}"
                return True, "答题成功"
        except Exception as e:
            return False, f"答题异常: {e}"

    def get_user_info(self):
        url = "https://pan.baidu.com/rest/2.0/membership/user?app_id=250528&web=5&method=query"
        h = {**HEADERS, 'Cookie': self.cookie}
        try:
            resp = requests.get(url, headers=h, timeout=15)
            if resp.status_code == 200:
                level    = re.search(r'current_level":(\d+)', resp.text)
                value    = re.search(r'current_value":(\d+)', resp.text)
                username = re.search(r'"username":"(.*?)"', resp.text)
                vip_type = re.search(r'"vip_type":(\d+)', resp.text)
                user = username.group(1) if username else "未知用户"
                lv   = level.group(1) if level else "?"
                val  = value.group(1) if value else "?"
                vip_map = {1: "普通会员", 2: "超级会员", 3: "至尊会员"}
                vip_str = vip_map.get(int(vip_type.group(1)), "普通用户") if vip_type else "普通用户"
                if privacy_mode and len(user) > 2:
                    user = f"{user[0]}***{user[-1]}"
                print(f"👤 用户: {user}  Lv.{lv}  {val}成长值  {vip_str}")
                return user, lv, val, vip_str
        except Exception as e:
            print(f"⚠️ 获取用户信息异常: {e}")
        return "未知用户", "?", "?", "未知"

    def run(self):
        print(f"\n==== 百度网盘 账号{self.index} ====")
        signin_ok, signin_msg = self.signin()
        time.sleep(random.uniform(2, 4))
        answer, ask_id = self.get_daily_question()
        answer_msg = ""
        if answer and ask_id:
            _, answer_msg = self.answer_question(answer, ask_id)
        user, lv, val, vip = self.get_user_info()
        print(f"📝 签到: {signin_msg}")
        if answer_msg:
            print(f"🤔 答题: {answer_msg}")
        print(f"⏰ {datetime.now().strftime('%m-%d %H:%M')}")


def main():
    print(f"==== 百度网盘签到 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    if not BAIDU_COOKIE:
        print("❌ 未设置 BAIDU_COOKIE Secret")
        raise SystemExit(1)

    cookies = [c.strip() for c in BAIDU_COOKIE.split('\n') if c.strip()]
    print(f"📝 共 {len(cookies)} 个账号")

    for i, cookie in enumerate(cookies):
        if i > 0:
            time.sleep(random.uniform(8, 15))
        BaiduPan(cookie, i + 1).run()

    print(f"\n==== 完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")


if __name__ == "__main__":
    main()
