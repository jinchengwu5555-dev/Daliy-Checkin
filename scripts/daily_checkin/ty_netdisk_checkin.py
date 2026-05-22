#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
天翼云盘签到 - GitHub Actions 版
Secrets: TY_USERNAME（多账号换行分隔）
         TY_PASSWORD（多账号换行分隔，与用户名一一对应）
"""

import time
import re
import base64
import random
import requests
import rsa
import os
from datetime import datetime

BI_RM = list("0123456789abcdefghijklmnopqrstuvwxyz")
B64MAP = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


class TianYiYunPan:
    def __init__(self, username, password, index):
        self.username = username
        self.password = password
        self.index = index
        self.session = requests.Session()

    def int2char(self, a):
        return BI_RM[a]

    def b64tohex(self, a):
        d = ""
        e = c = 0
        for ch in a:
            if ch != "=":
                v = B64MAP.index(ch)
                if e == 0:
                    e = 1; d += self.int2char(v >> 2); c = 3 & v
                elif e == 1:
                    e = 2; d += self.int2char(c << 2 | v >> 4); c = 15 & v
                elif e == 2:
                    e = 3; d += self.int2char(c); d += self.int2char(v >> 2); c = 3 & v
                else:
                    e = 0; d += self.int2char(c << 2 | v >> 4); d += self.int2char(15 & v)
        if e == 1:
            d += self.int2char(c << 2)
        return d

    def rsa_encode(self, j_rsakey, string):
        rsa_key = f"-----BEGIN PUBLIC KEY-----\n{j_rsakey}\n-----END PUBLIC KEY-----"
        pubkey = rsa.PublicKey.load_pkcs1_openssl_pem(rsa_key.encode())
        return self.b64tohex((base64.b64encode(rsa.encrypt(f'{string}'.encode(), pubkey))).decode())

    def login(self):
        try:
            print(f"👤 账号{self.index}: 登录 {self.username}")
            urlToken = "https://m.cloud.189.cn/udb/udb_login.jsp?pageId=1&pageKey=default&clientType=wap&redirectURL=https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html"
            r = self.session.get(urlToken, timeout=15)
            url = re.search(r"https?://[^\s'\"]+", r.text).group()
            r = self.session.get(url, timeout=15)
            href = re.search(r'<a id="j-tab-login-link"[^>]*href="([^"]+)"', r.text).group(1)
            r = self.session.get(href, timeout=15)
            captchaToken = re.findall(r"captchaToken' value='(.+?)'", r.text)[0]
            lt = re.findall(r'lt = "(.+?)"', r.text)[0]
            returnUrl = re.findall(r"returnUrl= '(.+?)'", r.text)[0]
            paramId = re.findall(r'paramId = "(.+?)"', r.text)[0]
            j_rsakey = re.findall(r'j_rsaKey" value="(\S+)"', r.text, re.M)[0]
            self.session.headers.update({"lt": lt})
            data = {
                "appKey": "cloud", "accountType": '01',
                "userName": f"{{RSA}}{self.rsa_encode(j_rsakey, self.username)}",
                "password": f"{{RSA}}{self.rsa_encode(j_rsakey, self.password)}",
                "validateCode": "", "captchaToken": captchaToken,
                "returnUrl": returnUrl, "mailSuffix": "@189.cn", "paramId": paramId
            }
            r = self.session.post(
                "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do",
                data=data,
                headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://open.e.189.cn/'},
                timeout=15
            )
            result = r.json()
            if result['result'] == 0:
                print(f"✅ 账号{self.index}: 登录成功")
                self.session.get(result['toUrl'], timeout=15)
                return True
            print(f"❌ 账号{self.index}: 登录失败 - {result['msg']}")
            return False
        except Exception as e:
            print(f"❌ 账号{self.index}: 登录异常 - {e}")
            return False

    def sign_in(self):
        try:
            rand = str(round(time.time() * 1000))
            url = f'https://api.cloud.189.cn/mkt/userSign.action?rand={rand}&clientType=TELEANDROID&version=8.6.3&model=SM-G930K'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 5.1.1; SM-G930K Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/74.0.3729.136 Mobile Safari/537.36 Ecloud/8.6.3 Android/22',
                "Referer": "https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1",
            }
            result = self.session.get(url, headers=headers, timeout=15).json()
            bonus = result.get('netdiskBonus', 0)
            is_sign = result.get('isSign', 'true')
            if is_sign == "false":
                msg = f"✅ 签到成功，获得 {bonus}M 空间"
            else:
                msg = f"📅 今日已签到，获得 {bonus}M 空间"
            print(f"账号{self.index}: {msg}")
            return msg
        except Exception as e:
            msg = f"签到异常: {e}"
            print(f"❌ 账号{self.index}: {msg}")
            return msg

    def run(self):
        print(f"\n==== 天翼云盘 账号{self.index} ====")
        if self.login():
            self.sign_in()
        print(f"⏰ {datetime.now().strftime('%m-%d %H:%M')}")


def main():
    print(f"==== 天翼云盘签到 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    ty_username_env = os.getenv("TY_USERNAME", "")
    ty_password_env = os.getenv("TY_PASSWORD", "")

    if not ty_username_env or not ty_password_env:
        print("❌ 未设置 TY_USERNAME / TY_PASSWORD Secret")
        raise SystemExit(1)

    usernames = [u.strip() for u in ty_username_env.split('\n') if u.strip()]
    passwords = [p.strip() for p in ty_password_env.split('\n') if p.strip()]

    if len(usernames) != len(passwords):
        print("❌ 用户名和密码数量不匹配")
        raise SystemExit(1)

    print(f"📝 共 {len(usernames)} 个账号")
    for i, (u, p) in enumerate(zip(usernames, passwords)):
        if i > 0:
            time.sleep(random.uniform(8, 15))
        TianYiYunPan(u, p, i + 1).run()

    print(f"\n==== 完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")


if __name__ == "__main__":
    main()
