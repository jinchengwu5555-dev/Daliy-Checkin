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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/76.0',
        })

    # ── RSA 加密 ────────────────────────────────

    def _int2char(self, a):
        return BI_RM[a]

    def _b64tohex(self, a):
        d = ""; e = c = 0
        for ch in a:
            if ch != "=":
                v = B64MAP.index(ch)
                if e == 0:   e=1; d+=self._int2char(v>>2);         c=3&v
                elif e == 1: e=2; d+=self._int2char(c<<2|v>>4);    c=15&v
                elif e == 2: e=3; d+=self._int2char(c); d+=self._int2char(v>>2); c=3&v
                else:        e=0; d+=self._int2char(c<<2|v>>4);    d+=self._int2char(15&v)
        if e == 1: d += self._int2char(c << 2)
        return d

    def _rsa_encode(self, j_rsakey, string):
        rsa_key = f"-----BEGIN PUBLIC KEY-----\n{j_rsakey}\n-----END PUBLIC KEY-----"
        pubkey  = rsa.PublicKey.load_pkcs1_openssl_pem(rsa_key.encode())
        return self._b64tohex(base64.b64encode(rsa.encrypt(str(string).encode(), pubkey)).decode())

    # ── 登录 ────────────────────────────────────

    def login(self):
        try:
            print(f"👤 账号{self.index}: 登录 {self._mask(self.username)}")

            # 1. 获取登录入口 URL
            r = self.session.get(
                "https://m.cloud.189.cn/udb/udb_login.jsp"
                "?pageId=1&pageKey=default&clientType=wap"
                "&redirectURL=https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html",
                timeout=15
            )
            url = re.search(r"https?://[^\s'\"]+", r.text).group()
            r   = self.session.get(url, timeout=15)

            href = re.search(r'<a id="j-tab-login-link"[^>]*href="([^"]+)"', r.text).group(1)
            r    = self.session.get(href, timeout=15)

            captchaToken = re.findall(r"captchaToken' value='(.+?)'", r.text)[0]
            lt           = re.findall(r'lt = "(.+?)"', r.text)[0]
            returnUrl    = re.findall(r"returnUrl= '(.+?)'", r.text)[0]
            paramId      = re.findall(r'paramId = "(.+?)"', r.text)[0]
            j_rsakey     = re.findall(r'j_rsaKey" value="(\S+)"', r.text, re.M)[0]

            self.session.headers.update({"lt": lt})

            # 2. 提交登录
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
                print(f"❌ 账号{self.index}: 登录失败 - {result.get('msg', '未知错误')}")
                return False

            # 3. 跟随跳转，获取 sessionKey
            redirect_url = result["toUrl"]
            r = self.session.get(redirect_url, timeout=15)

            # 从 cookie 或 URL 中提取 sessionKey
            self.session_key = ""
            for cookie in self.session.cookies:
                if cookie.name in ("COOKIE_LOGIN_USER", "sessionKey", "accessToken"):
                    self.session_key = cookie.value
                    break

            print(f"✅ 账号{self.index}: 登录成功")
            return True

        except Exception as e:
            print(f"❌ 账号{self.index}: 登录异常 - {e}")
            return False

    # ── 签到（新接口） ───────────────────────────

    def sign_in(self):
        """
        天翼云盘目前有两套签到接口，优先用新接口，失败降级到旧接口
        """
        bonus = 0
        already_signed = False

        # ── 新接口 ──────────────────────────────
        try:
            rand = str(round(time.time() * 1000))
            url  = (
                "https://api.cloud.189.cn/mkt/userSign.action"
                f"?rand={rand}&clientType=TELEANDROID&version=8.6.3&model=SM-G930K"
            )
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
            result = self.session.get(url, headers=headers, timeout=15).json()
            print(f"  [签到原始响应] {json.dumps(result, ensure_ascii=False)}")

            bonus          = int(result.get("netdiskBonus", 0))
            is_sign        = str(result.get("isSign", "")).lower()
            already_signed = (is_sign == "true")

            if already_signed and bonus == 0:
                # isSign=true 且 bonus=0 → 确认已签到但拿不到今日奖励
                print(f"📅 账号{self.index}: 今日已签到（netdiskBonus=0，可能接口已改版）")
            elif not already_signed:
                print(f"✅ 账号{self.index}: 签到成功，获得 {bonus}M 空间")
            else:
                print(f"📅 账号{self.index}: 今日已签到，获得 {bonus}M 空间")

            return already_signed, bonus

        except Exception as e:
            print(f"⚠️ 账号{self.index}: 旧签到接口异常 - {e}，尝试新接口")

        # ── 降级：family 签到接口 ───────────────
        try:
            rand = str(round(time.time() * 1000))
            url  = (
                "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action"
                f"?taskId=SIGN_IN&rand={rand}"
            )
            result = self.session.get(url, timeout=15).json()
            print(f"  [降级接口响应] {json.dumps(result, ensure_ascii=False)}")
            desc = result.get("description", "")
            if "成功" in desc or "奖励" in desc:
                print(f"✅ 账号{self.index}: 签到成功 - {desc}")
                return False, 0
            print(f"⚠️ 账号{self.index}: 签到结果不明 - {desc}")
            return False, 0
        except Exception as e2:
            print(f"❌ 账号{self.index}: 降级接口也失败 - {e2}")
            return False, 0

    # ── 工具 ────────────────────────────────────

    @staticmethod
    def _mask(s):
        if len(s) <= 4:
            return "***"
        return s[:2] + "***" + s[-2:]

    def run(self):
        print(f"\n==== 天翼云盘 账号{self.index} ====")
        if not self.login():
            return
        already, bonus = self.sign_in()
        if already:
            print(f"📊 账号{self.index}: 今日已签到，积累空间 {bonus}M")
        else:
            print(f"📊 账号{self.index}: 签到完成，本次获得 {bonus}M 空间")
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
