#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
天翼云盘签到 - GitHub Actions 版
使用真实抓包的 UA 和 Referer
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

# 从抓包拿到的真实 UA 和页面地址
ECLOUD_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "Ecloud/11.0.2 iOS/26.3 clientId/02B2318892-4E8D-4705-"
    "A2DB-1D674BD6DE99 clientModel/iPhone proVersion/1.0.5"
)
GROW_GUIDE_URL = "https://m.cloud.189.cn/zt/2024/grow-guide/index.html"


class TianYiYunPan:
    def __init__(self, username, password, index):
        self.username = username
        self.password = password
        self.index    = index
        self.session  = requests.Session()
        self.session.headers.update({
            "User-Agent":   ECLOUD_UA,
            "Referer":      GROW_GUIDE_URL,
            "Accept":       "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
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

            # redirectURL 改为新版 grow-guide 页面
            r = self.session.get(
                "https://m.cloud.189.cn/udb/udb_login.jsp"
                "?pageId=1&pageKey=default&clientType=wap"
                f"&redirectURL={GROW_GUIDE_URL}",
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
                print(f"❌ 登录失败 - {result.get('msg', '未知')}")
                return False

            # 跟随跳转，让 Cookie 写入
            self.session.get(result["toUrl"], timeout=15, allow_redirects=True)

            # 打印 Cookie 确认
            cookie_names = [c.name for c in self.session.cookies]
            print(f"  Cookie: {cookie_names}")
            print(f"✅ 账号{self.index}: 登录成功")
            return True

        except Exception as e:
            print(f"❌ 登录异常 - {e}")
            return False

    def sign_in(self):
        rand = str(round(time.time() * 1000))

        # 先验证 Session 是否有效（getUserBriefInfo 从抓包里看到能通）
        try:
            r = self.session.get(
                "https://m.cloud.189.cn/v2/getUserBriefInfo.action",
                timeout=10
            )
            info = r.json()
            print(f"  用户信息: {json.dumps(info, ensure_ascii=False)[:100]}")
        except Exception as e:
            print(f"  ⚠️ 获取用户信息失败: {e}")

        # 签到接口候选（新版 grow-guide 页面用的接口，待确认具体路径）
        sign_attempts = [
            # 新版 grow-guide 下的签到接口
            ("GET",  "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action",
             {"taskId": "SIGN_IN"}, None),

            ("GET",  "https://m.cloud.189.cn/zt/2024/grow-guide/api/sign",
             None, None),

            ("POST", "https://m.cloud.189.cn/zt/2024/grow-guide/api/sign",
             None, {"rand": rand}),

            # grow-guide 对应的后端接口（猜测路径）
            ("GET",  "https://m.cloud.189.cn/v2/growGuideSign.action",
             {"rand": rand}, None),

            ("POST", "https://m.cloud.189.cn/v2/growGuideSign.action",
             None, {"rand": rand}),

            ("GET",  "https://m.cloud.189.cn/v2/userSign.action",
             {"rand": rand}, None),

            # 2024 新版签到
            ("GET",  "https://m.cloud.189.cn/zt/2024/sign/index.html",
             None, None),
        ]

        print(f"\n  --- 签到接口探测 ---")
        for method, url, params, data in sign_attempts:
            try:
                if method == "GET":
                    r = self.session.get(url, params=params, timeout=10)
                else:
                    r = self.session.post(url, data=data, params=params,
                                          headers={"Content-Type": "application/x-www-form-urlencoded"},
                                          timeout=10)
                body = r.text[:150].replace('\n', ' ')
                ok = "★" if r.status_code == 200 and len(r.text) > 30 and (
                    'sign' in r.text.lower() or 'prize' in r.text.lower() or
                    'bonus' in r.text.lower() or 'result' in r.text.lower()
                ) else " "
                print(f"{ok}[{r.status_code}] {url.split('/')[-1][:40]} → {body[:100]}")
            except Exception as e:
                print(f"  ERR {url.split('/')[-1][:30]}: {e}")
            time.sleep(0.3)

    @staticmethod
    def _mask(s):
        if len(s) <= 4: return "***"
        return s[:2] + "***" + s[-2:]

    def run(self):
        print(f"\n==== 天翼云盘 账号{self.index} ====")
        if not self.login():
            return
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
    print(f"📝 共 {len(usernames)} 个账号")
    for i, (u, p) in enumerate(zip(usernames, passwords)):
        if i > 0:
            time.sleep(random.uniform(5, 10))
        TianYiYunPan(u, p, i + 1).run()
    print(f"\n==== 完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")

if __name__ == "__main__":
    main()
