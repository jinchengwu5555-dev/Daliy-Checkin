#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
天翼云盘签到 - GitHub Actions 版
使用已知可用的天翼云盘签到接口
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
        self.username   = username
        self.password   = password
        self.index      = index
        self.access_token = ""
        self.session    = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; Redmi Note 8) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/91.0.4472.120 Mobile Safari/537.36",
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

    # ── 登录，同时尝试获取 access_token ──────────────────────

    def login(self):
        try:
            print(f"👤 账号{self.index}: 登录 {self._mask(self.username)}")
            login_ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/76.0"}

            r    = self.session.get(
                "https://m.cloud.189.cn/udb/udb_login.jsp"
                "?pageId=1&pageKey=default&clientType=wap"
                "&redirectURL=https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html",
                headers=login_ua, timeout=15
            )
            url  = re.search(r"https?://[^\s'\"]+", r.text).group()
            r    = self.session.get(url, headers=login_ua, timeout=15)
            href = re.search(r'<a id="j-tab-login-link"[^>]*href="([^"]+)"', r.text).group(1)
            r    = self.session.get(href, headers=login_ua, timeout=15)

            captchaToken = re.findall(r"captchaToken' value='(.+?)'", r.text)[0]
            lt           = re.findall(r'lt = "(.+?)"', r.text)[0]
            returnUrl    = re.findall(r"returnUrl= '(.+?)'", r.text)[0]
            paramId      = re.findall(r'paramId = "(.+?)"', r.text)[0]
            j_rsakey     = re.findall(r'j_rsaKey" value="(\S+)"', r.text, re.M)[0]

            data = {
                "appKey": "cloud", "accountType": "01",
                "userName":     f"{{RSA}}{self._rsa_encode(j_rsakey, self.username)}",
                "password":     f"{{RSA}}{self._rsa_encode(j_rsakey, self.password)}",
                "validateCode": "", "captchaToken": captchaToken,
                "returnUrl": returnUrl, "mailSuffix": "@189.cn", "paramId": paramId,
            }
            r = self.session.post(
                "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do",
                data=data, headers={**login_ua, "Referer": "https://open.e.189.cn/"}, timeout=15
            )
            result = r.json()
            if result.get("result") != 0:
                print(f"❌ 登录失败 - {result.get('msg', '未知')}")
                return False

            # 跟随跳转
            redirect = self.session.get(result["toUrl"], timeout=15, allow_redirects=True)

            # 尝试从重定向 URL 或响应里取 accessToken
            for pat in [r'accessToken=([^&"\']+)', r'"accessToken"\s*:\s*"([^"]+)"',
                        r'access_token=([^&"\']+)']:
                m = re.search(pat, redirect.url + redirect.text)
                if m:
                    self.access_token = m.group(1)
                    print(f"  accessToken 长度: {len(self.access_token)}")
                    break

            # 也从 cookie 里找
            for c in self.session.cookies:
                if 'token' in c.name.lower() or c.name == 'COOKIE_LOGIN_USER':
                    print(f"  Cookie: {c.name}={c.value[:20]}...")

            print(f"✅ 账号{self.index}: 登录成功")
            return True
        except Exception as e:
            print(f"❌ 登录异常 - {e}")
            return False

    # ── 签到：依次尝试所有已知可用接口 ───────────────────────

    def sign_in(self):
        rand      = str(round(time.time() * 1000))
        sign_date = datetime.now().strftime("%Y-%m-%d")

        # 按优先级排列的签到接口列表
        attempts = [

            # ① 天翼云盘 2023+ 新版签到接口（家庭云任务）
            {
                "desc": "新版家庭云签到",
                "method": "GET",
                "url": "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action",
                "params": {"taskId": "SIGN_IN", "activityId": ""},
                "data": None,
                "headers": {"Referer": "https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html",
                            "Accept": "application/json, text/plain, */*",
                            "X-Requested-With": "XMLHttpRequest"},
            },

            # ② 同接口换 activityId
            {
                "desc": "新版家庭云签到(activityId=1)",
                "method": "POST",
                "url": "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action",
                "params": None,
                "data": {"taskId": "SIGN_IN", "activityId": "1", "rand": rand},
                "headers": {"Referer": "https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html",
                            "Content-Type": "application/x-www-form-urlencoded",
                            "X-Requested-With": "XMLHttpRequest"},
            },

            # ③ 个人云签到 (cloud.189.cn)
            {
                "desc": "个人云签到",
                "method": "GET",
                "url": "https://cloud.189.cn/api/mkt/userSign.action",
                "params": {"rand": rand, "clientType": "TELEANDROID", "version": "8.6.3"},
                "data": None,
                "headers": {"Referer": "https://cloud.189.cn/web/main",
                            "Accept": "application/json"},
            },

            # ④ 旧版 wap 签到
            {
                "desc": "旧版wap签到",
                "method": "GET",
                "url": f"https://api.cloud.189.cn/mkt/userSign.action",
                "params": {"rand": rand, "clientType": "TELEANDROID",
                           "version": "8.6.3", "model": "SM-G930K"},
                "data": None,
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 5.1.1; SM-G930K Build/NRD90M; wv) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
                                  "Chrome/74.0.3729.136 Mobile Safari/537.36 "
                                  "Ecloud/8.6.3 Android/22 clientId/355325117317828 "
                                  "clientModel/SM-G930K imsi/460071114317824 "
                                  "clientChannelId/qq proVersion/1.0.6",
                    "Referer": "https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1",
                },
            },

            # ⑤ 天翼云盘 APP 接口（需要 Authorization header）
            {
                "desc": "APP接口(Bearer Token)",
                "method": "GET",
                "url": "https://cloud.189.cn/api/portal/v2/getUserSignInfo.action",
                "params": None,
                "data": None,
                "headers": {
                    "Authorization": f"Bearer {self.access_token}" if self.access_token else "",
                    "Accept": "application/json",
                },
            },
        ]

        for attempt in attempts:
            desc = attempt["desc"]
            try:
                h = {**self.session.headers, **attempt.get("headers", {})}
                # 过滤空 header
                h = {k: v for k, v in h.items() if v}

                if attempt["method"] == "GET":
                    r = self.session.get(attempt["url"], params=attempt["params"],
                                         headers=h, timeout=12)
                else:
                    r = self.session.post(attempt["url"], data=attempt["data"],
                                          params=attempt["params"],
                                          headers=h, timeout=12)

                body = r.text[:200]
                print(f"\n  [{desc}] {r.status_code}")
                print(f"  响应: {body[:150]}")

                # 判断成功
                try:
                    j = r.json()
                except Exception:
                    j = {}

                # 成功标志
                if j.get("result") == "ok" or j.get("prizeName") or j.get("netdiskBonus") is not None:
                    bonus   = j.get("netdiskBonus", 0)
                    prize   = j.get("prizeName", "")
                    is_sign = str(j.get("isSign", "false")).lower() == "true"
                    reward  = prize or f"{bonus}M空间"
                    if is_sign and bonus == 0 and not prize:
                        print(f"📅 账号{self.index}: 今日已签到")
                    else:
                        print(f"✅ 账号{self.index}: 签到成功，获得 {reward}")
                    return True

                # 已签到
                if any(k in str(j) for k in ["已签到", "isSign", "today"]) and \
                   any(k in str(j) for k in ["true", "已"]):
                    print(f"📅 账号{self.index}: 今日已签到")
                    return True

                # 失败，继续下一个
                err = j.get("errorMsg") or j.get("message") or j.get("msg") or "未知"
                print(f"  → 失败: {err}，尝试下一个接口")

            except Exception as e:
                print(f"  [{desc}] 异常: {e}")

        print(f"\n❌ 账号{self.index}: 所有接口均失败")
        return False

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
    if len(usernames) != len(passwords):
        print("❌ 用户名和密码数量不匹配"); raise SystemExit(1)
    print(f"📝 共 {len(usernames)} 个账号")
    for i, (u, p) in enumerate(zip(usernames, passwords)):
        if i > 0: time.sleep(random.uniform(5, 10))
        TianYiYunPan(u, p, i + 1).run()
    print(f"\n==== 完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")

if __name__ == "__main__":
    main()
