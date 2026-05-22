#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
天翼云盘签到 - GitHub Actions 版
Secrets: TY_USERNAME / TY_PASSWORD
"""

import time
import re
import base64
import random
import requests
import rsa
import os
import json
from datetime import datetime

BI_RM  = list("0123456789abcdefghijklmnopqrstuvwxyz")
B64MAP = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


class TianYiYunPan:
    def __init__(self, username, password, index):
        self.username = username
        self.password = password
        self.index    = index
        self.session  = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/76.0",
        })

    def _int2char(self, a): return BI_RM[a]

    def _b64tohex(self, a):
        d = ""; e = c = 0
        for ch in a:
            if ch != "=":
                v = B64MAP.index(ch)
                if e == 0:   e=1; d+=self._int2char(v>>2);              c=3&v
                elif e == 1: e=2; d+=self._int2char(c<<2|v>>4);         c=15&v
                elif e == 2: e=3; d+=self._int2char(c); d+=self._int2char(v>>2); c=3&v
                else:        e=0; d+=self._int2char(c<<2|v>>4); d+=self._int2char(15&v)
        if e == 1: d += self._int2char(c << 2)
        return d

    def _rsa_encode(self, j_rsakey, string):
        pem    = f"-----BEGIN PUBLIC KEY-----\n{j_rsakey}\n-----END PUBLIC KEY-----"
        pubkey = rsa.PublicKey.load_pkcs1_openssl_pem(pem.encode())
        return self._b64tohex(base64.b64encode(rsa.encrypt(str(string).encode(), pubkey)).decode())

    def login(self):
        try:
            print(f"👤 账号{self.index}: 登录 {self._mask(self.username)}")

            r    = self.session.get(
                "https://m.cloud.189.cn/udb/udb_login.jsp"
                "?pageId=1&pageKey=default&clientType=wap"
                "&redirectURL=https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html",
                timeout=15
            )
            url  = re.search(r"https?://[^\s'\"]+", r.text).group()
            r    = self.session.get(url, timeout=15)
            href = re.search(r'<a id="j-tab-login-link"[^>]*href="([^"]+)"', r.text).group(1)
            r    = self.session.get(href, timeout=15)

            captchaToken = re.findall(r"captchaToken' value='(.+?)'", r.text)[0]
            lt           = re.findall(r'lt = "(.+?)"', r.text)[0]
            returnUrl    = re.findall(r"returnUrl= '(.+?)'", r.text)[0]
            paramId      = re.findall(r'paramId = "(.+?)"', r.text)[0]
            j_rsakey     = re.findall(r'j_rsaKey" value="(\S+)"', r.text, re.M)[0]

            self.session.headers.update({"lt": lt})

            data = {
                "appKey":       "cloud",
                "accountType":  "01",
                "userName":     f"{{RSA}}{self._rsa_encode(j_rsakey, self.username)}",
                "password":     f"{{RSA}}{self._rsa_encode(j_rsakey, self.password)}",
                "validateCode": "",
                "captchaToken": captchaToken,
                "returnUrl":    returnUrl,
                "mailSuffix":   "@189.cn",
                "paramId":      paramId,
            }
            r = self.session.post(
                "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do",
                data=data,
                headers={"Referer": "https://open.e.189.cn/"},
                timeout=15
            )
            result = r.json()

            if result.get("result") != 0:
                print(f"❌ 账号{self.index}: 登录失败 - {result.get('msg', '未知')}")
                return False

            self.session.get(result["toUrl"], timeout=15, allow_redirects=True)
            print(f"✅ 账号{self.index}: 登录成功")
            return True

        except Exception as e:
            print(f"❌ 账号{self.index}: 登录异常 - {e}")
            return False

    def probe_sign_apis(self):
        """逐一探测所有已知签到接口，打印完整响应"""
        rand = str(round(time.time() * 1000))

        apis = [
            # ── 当前主流签到接口候选 ──────────────────────────────
            ("GET",  "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action",
             {"taskId": "SIGN_IN"}, None),

            ("POST", "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action",
             None, {"taskId": "SIGN_IN", "rand": rand}),

            # 新版每日任务接口
            ("GET",  "https://m.cloud.189.cn/v2/taskAction.action",
             {"taskId": "SIGN_IN", "clientType": "wap"}, None),

            ("POST", "https://m.cloud.189.cn/v2/taskAction.action",
             None, {"taskId": "SIGN_IN", "clientType": "wap"}),

            # 用户任务列表（看有哪些任务及状态）
            ("GET",  "https://m.cloud.189.cn/v2/userTaskList.action",
             {"clientType": "wap"}, None),

            # 旧版 mkt 签到
            ("GET",  f"https://api.cloud.189.cn/mkt/userSign.action"
                     f"?rand={rand}&clientType=TELEANDROID&version=8.6.3&model=SM-G930K",
             None, None),

            # 用户信息（验证 session 是否有效）
            ("GET",  "https://m.cloud.189.cn/v2/getUserInfoForPortal.action",
             None, None),

            # 新版签到
            ("GET",  "https://m.cloud.189.cn/api/portal/signIn.action",
             {"rand": rand}, None),

            ("POST", "https://m.cloud.189.cn/api/portal/signIn.action",
             None, {"rand": rand}),

            # 积分/成长任务
            ("GET",  "https://m.cloud.189.cn/v2/signInInfo.action",
             None, None),
        ]

        print("\n==== 接口探测开始 ====")
        for method, url, params, data in apis:
            try:
                if method == "GET":
                    r = self.session.get(url, params=params, timeout=10)
                else:
                    r = self.session.post(url, data=data, params=params,
                                          headers={"Content-Type": "application/x-www-form-urlencoded"},
                                          timeout=10)
                # 截取响应（最多200字符）
                body = r.text[:200].replace('\n', ' ')
                print(f"[{method}] {r.status_code} {url.split('/')[-1].split('?')[0]}")
                print(f"  → {body}")
            except Exception as e:
                print(f"[{method}] ERR {url.split('/')[-1].split('?')[0]}: {e}")
        print("==== 接口探测结束 ====")

    @staticmethod
    def _mask(s):
        if len(s) <= 4: return "***"
        return s[:2] + "***" + s[-2:]

    def run(self):
        print(f"\n==== 天翼云盘 账号{self.index} ====")
        if not self.login():
            return
        self.probe_sign_apis()
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

    print(f"📝 共 {len(usernames)} 个账号")
    TianYiYunPan(usernames[0], passwords[0], 1).run()

    print(f"\n==== 完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")


if __name__ == "__main__":
    main()
