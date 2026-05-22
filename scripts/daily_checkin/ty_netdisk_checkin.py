#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
天翼云盘签到 - GitHub Actions 版
Secrets: TY_USERNAME（多账号换行分隔）
         TY_PASSWORD（多账号换行分隔）
"""

import time
import re
import base64
import random
import hashlib
import hmac
import requests
import rsa
import os
import json
from datetime import datetime, timezone, timedelta

BI_RM  = list("0123456789abcdefghijklmnopqrstuvwxyz")
B64MAP = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

APP_ID     = "8025431004"
APP_SECRET = "469a2536f8db3fcb"


class TianYiYunPan:
    def __init__(self, username, password, index):
        self.username    = username
        self.password    = password
        self.index       = index
        self.session_key = ""
        self.session     = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/76.0",
        })

    # ── RSA 加密 ────────────────────────────────────────────

    def _int2char(self, a):
        return BI_RM[a]

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

    # ── 签名生成 ─────────────────────────────────────────────

    def _sign(self, params: dict) -> str:
        """
        天翼云盘 API 签名：
        1. 参数按 key 字典序排列
        2. 拼成 key=value&key=value
        3. HMAC-SHA1，key = APP_SECRET
        4. Base64 编码
        """
        sorted_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        mac = hmac.new(APP_SECRET.encode(), sorted_str.encode(), hashlib.sha1)
        return base64.b64encode(mac.digest()).decode()

    def _build_params(self, extra: dict = None) -> dict:
        params = {
            "appId":      APP_ID,
            "sessionKey": self.session_key,
            "timeStamp":  str(int(time.time() * 1000)),
        }
        if extra:
            params.update(extra)
        params["signature"] = self._sign(params)
        return params

    # ── 登录 ─────────────────────────────────────────────────

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
            r      = self.session.post(
                "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do",
                data=data,
                headers={"Referer": "https://open.e.189.cn/"},
                timeout=15
            )
            result = r.json()

            if result.get("result") != 0:
                print(f"❌ 账号{self.index}: 登录失败 - {result.get('msg', '未知')}")
                return False

            # 跟随跳转，写入 Cookie
            self.session.get(result["toUrl"], timeout=15)

            # 提取 sessionKey（COOKIE_LOGIN_USER 或直接从 URL 里找）
            for cookie in self.session.cookies:
                if cookie.name in ("COOKIE_LOGIN_USER", "accessToken"):
                    self.session_key = cookie.value
                    break

            # 如果 cookie 里没有，尝试从 getUserInfoForPortal 接口拿
            if not self.session_key:
                self.session_key = self._get_session_key_from_api()

            if not self.session_key:
                print(f"⚠️  账号{self.index}: 未能获取 sessionKey，签到可能失败")
            else:
                print(f"✅ 账号{self.index}: 登录成功（sessionKey 长度={len(self.session_key)}）")
            return True

        except Exception as e:
            print(f"❌ 账号{self.index}: 登录异常 - {e}")
            return False

    def _get_session_key_from_api(self) -> str:
        """通过用户信息接口换取 sessionKey"""
        try:
            r = self.session.get(
                "https://m.cloud.189.cn/v2/getUserInfoForPortal.action",
                timeout=10
            )
            data = r.json()
            return data.get("sessionKey", "")
        except Exception:
            return ""

    # ── 签到 ─────────────────────────────────────────────────

    def sign_in(self):
        # 方案 A：带签名的新接口
        try:
            params = self._build_params({"clientType": "TELEANDROID", "version": "8.6.3"})
            url    = "https://api.cloud.189.cn/mkt/userSign.action"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 5.1.1; SM-G930K Build/NRD90M; wv) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
                    "Chrome/74.0.3729.136 Mobile Safari/537.36 "
                    "Ecloud/8.6.3 Android/22 clientId/355325117317828 "
                    "clientModel/SM-G930K imsi/460071114317824 "
                    "clientChannelId/qq proVersion/1.0.6"
                ),
                "Referer": "https://m.cloud.189.cn/zhuanti/2016/sign/index.jsp?albumBackupOpened=1",
            }
            r      = self.session.get(url, params=params, headers=headers, timeout=15)
            result = r.json()
            print(f"  [签到响应A] {json.dumps(result, ensure_ascii=False)}")

            if result.get("errorCode") or result.get("success") is None:
                raise ValueError(f"接口A失败: {result}")

            bonus    = int(result.get("netdiskBonus", 0))
            is_sign  = str(result.get("isSign", "false")).lower()
            if is_sign == "false":
                print(f"✅ 账号{self.index}: 签到成功，获得 {bonus}M 空间")
            else:
                print(f"📅 账号{self.index}: 今日已签到，获得 {bonus}M 空间")
            return bonus, is_sign == "true"

        except Exception as e:
            print(f"  接口A异常: {e}，降级到方案B")

        # 方案 B：wap 签到接口（无需签名，依赖 Session Cookie）
        try:
            rand    = str(round(time.time() * 1000))
            url     = f"https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action?taskId=SIGN_IN&rand={rand}"
            r       = self.session.get(url, timeout=15)
            result  = r.json()
            print(f"  [签到响应B] {json.dumps(result, ensure_ascii=False)}")

            desc = result.get("description", "")
            prize = result.get("prizeName", "")
            if result.get("result") == "ok" or "成功" in desc or prize:
                reward = prize or desc or "未知奖励"
                print(f"✅ 账号{self.index}: 签到成功，获得 {reward}")
                return 0, False
            if "已" in desc or "重复" in desc:
                print(f"📅 账号{self.index}: 今日已签到")
                return 0, True
            print(f"⚠️  账号{self.index}: 签到结果不明 - {desc}")
            return 0, False

        except Exception as e:
            print(f"❌ 账号{self.index}: 方案B也失败 - {e}")
            return 0, False

    # ── 工具 ─────────────────────────────────────────────────

    @staticmethod
    def _mask(s):
        if len(s) <= 4:
            return "***"
        return s[:2] + "***" + s[-2:]

    def run(self):
        print(f"\n==== 天翼云盘 账号{self.index} ====")
        if not self.login():
            return
        bonus, already = self.sign_in()
        if not already:
            print(f"📊 账号{self.index}: 本次获得 {bonus}M 空间")
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
            time.sleep(random.uniform(5, 10))
        TianYiYunPan(u, p, i + 1).run()

    print(f"\n==== 完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")


if __name__ == "__main__":
    main()
