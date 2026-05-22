#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
天翼云盘签到 - GitHub Actions 版（接口参数穷举版）
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
                data=data, headers={"Referer": "https://open.e.189.cn/"}, timeout=15
            )
            result = r.json()
            if result.get("result") != 0:
                print(f"❌ 登录失败 - {result.get('msg', '未知')}")
                return False
            self.session.get(result["toUrl"], timeout=15, allow_redirects=True)
            print(f"✅ 账号{self.index}: 登录成功")
            return True
        except Exception as e:
            print(f"❌ 登录异常 - {e}")
            return False

    def probe_draw_prize(self):
        """对 drawPrizeMarketDetails.action 穷举不同参数组合"""
        url  = "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action"
        rand = str(round(time.time() * 1000))

        # 不同的 taskId 候选值
        task_ids = [
            "SIGN_IN",
            "sign_in",
            "SignIn",
            "daily_sign",
            "DAILY_SIGN",
            "SIGNIN",
            "1",
            "sign",
        ]

        # 不同请求头组合
        header_variants = [
            # wap UA
            {"User-Agent": "Mozilla/5.0 (Linux; Android 11; Redmi Note 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
             "Referer": "https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html"},
            # 默认 UA（已有）
            {},
        ]

        print("\n==== drawPrizeMarketDetails 参数穷举 ====")

        # 1. 先试不同 taskId（GET）
        print("\n--- GET taskId 穷举 ---")
        for tid in task_ids:
            try:
                r = self.session.get(url, params={"taskId": tid}, timeout=8)
                body = r.text[:120].replace('\n', ' ')
                marker = "★" if '"result":"ok"' in r.text or '"prizeName"' in r.text else " "
                print(f"{marker}[{r.status_code}] taskId={tid} → {body}")
            except Exception as e:
                print(f"  ERR taskId={tid}: {e}")
            time.sleep(0.3)

        # 2. 再试不同 taskId（POST）
        print("\n--- POST taskId 穷举 ---")
        for tid in task_ids[:4]:  # 只试前4个避免太慢
            try:
                r = self.session.post(url,
                    data={"taskId": tid, "rand": rand},
                    headers={"Content-Type": "application/x-www-form-urlencoded",
                             "Referer": "https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html"},
                    timeout=8)
                body = r.text[:120].replace('\n', ' ')
                marker = "★" if '"result":"ok"' in r.text or '"prizeName"' in r.text else " "
                print(f"{marker}[{r.status_code}] POST taskId={tid} → {body}")
            except Exception as e:
                print(f"  ERR POST taskId={tid}: {e}")
            time.sleep(0.3)

        # 3. 试 GET 带不同额外参数
        print("\n--- GET 额外参数穷举 ---")
        extra_params = [
            {"taskId": "SIGN_IN", "clientType": "wap"},
            {"taskId": "SIGN_IN", "clientType": "TELEANDROID"},
            {"taskId": "SIGN_IN", "rand": rand},
            {"taskId": "SIGN_IN", "type": "1"},
            {"taskId": "SIGN_IN", "actionType": "sign"},
        ]
        for params in extra_params:
            try:
                r = self.session.get(url, params=params, timeout=8)
                body = r.text[:120].replace('\n', ' ')
                marker = "★" if '"result":"ok"' in r.text or '"prizeName"' in r.text else " "
                print(f"{marker}[{r.status_code}] {params} → {body}")
            except Exception as e:
                print(f"  ERR {params}: {e}")
            time.sleep(0.3)

        # 4. 试 shakeLottery 相关接口（登录重定向就到这个页面）
        print("\n--- shakeLottery 相关接口 ---")
        shake_urls = [
            "https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html",
            "https://m.cloud.189.cn/v2/shakeLottery.action",
            "https://m.cloud.189.cn/v2/getUserSignInfo.action",
            "https://m.cloud.189.cn/v2/userSign.action",
            "https://m.cloud.189.cn/v2/doSignIn.action",
        ]
        for su in shake_urls:
            try:
                r = self.session.get(su, timeout=8)
                body = r.text[:150].replace('\n', ' ')
                print(f"[{r.status_code}] {su.split('/')[-1]} → {body}")
            except Exception as e:
                print(f"  ERR {su.split('/')[-1]}: {e}")
            time.sleep(0.3)

        print("==== 穷举结束 ====")

    @staticmethod
    def _mask(s):
        if len(s) <= 4: return "***"
        return s[:2] + "***" + s[-2:]

    def run(self):
        print(f"\n==== 天翼云盘 账号{self.index} ====")
        if not self.login():
            return
        self.probe_draw_prize()


def main():
    print(f"==== 天翼云盘签到 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    ty_username_env = os.getenv("TY_USERNAME", "")
    ty_password_env = os.getenv("TY_PASSWORD", "")
    if not ty_username_env or not ty_password_env:
        print("❌ 未设置 TY_USERNAME / TY_PASSWORD Secret")
        raise SystemExit(1)
    usernames = [u.strip() for u in ty_username_env.split('\n') if u.strip()]
    passwords = [p.strip() for p in ty_password_env.split('\n') if p.strip()]
    TianYiYunPan(usernames[0], passwords[0], 1).run()
    print(f"\n==== 完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")

if __name__ == "__main__":
    main()
