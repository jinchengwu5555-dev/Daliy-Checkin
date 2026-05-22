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

    # ── RSA 加密 ─────────────────────────────────────────────

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

            # 跟随跳转写入 Cookie
            self.session.get(result["toUrl"], timeout=15, allow_redirects=True)

            # 打印所有 cookie 名称（调试用）
            cookie_names = [c.name for c in self.session.cookies]
            print(f"  [Cookie列表] {cookie_names}")

            print(f"✅ 账号{self.index}: 登录成功")
            return True

        except Exception as e:
            print(f"❌ 账号{self.index}: 登录异常 - {e}")
            return False

    # ── 签到（家庭云抽奖接口，只需 Session Cookie） ──────────

    def sign_in(self):
        """
        使用家庭云每日签到抽奖接口
        POST https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action
        参数: taskId=SIGN_IN
        该接口只需要登录后的 Session Cookie，无需 APP 签名
        """
        rand = str(round(time.time() * 1000))
        url  = "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action"

        # 先 GET 检查是否已签到
        try:
            r_check = self.session.get(
                "https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action",
                params={"taskId": "SIGN_IN"},
                timeout=15
            )
            check = r_check.json()
            print(f"  [签到检查] {json.dumps(check, ensure_ascii=False)}")
        except Exception as e:
            print(f"  [签到检查] 异常: {e}")
            check = {}

        # POST 执行签到
        try:
            r = self.session.post(
                url,
                data={"taskId": "SIGN_IN", "rand": rand},
                headers={
                    "Referer": "https://m.cloud.189.cn/zhuanti/2021/shakeLottery/index.html",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=15
            )
            result = r.json()
            print(f"  [签到响应] {json.dumps(result, ensure_ascii=False)}")

            # 解析结果
            res_code  = str(result.get("result", result.get("code", "")))
            prize     = result.get("prizeName", "")
            desc      = result.get("description", result.get("message", ""))
            bonus_mb  = result.get("netdiskBonus", result.get("prize", 0))

            if res_code == "ok" or prize:
                reward = prize or f"{bonus_mb}M" or desc or "奖励"
                print(f"✅ 账号{self.index}: 签到成功，获得 {reward}")
                return reward, False

            if res_code in ("1", "error") or "失败" in desc or "操作失败" in desc:
                # code=1 有时是"今日已签到"，有时是真正失败
                # 结合 check 结果判断
                if check.get("isSign") or check.get("signed"):
                    print(f"📅 账号{self.index}: 今日已签到")
                    return "今日已签到", True
                print(f"❌ 账号{self.index}: 签到失败 - {desc or res_code}")
                return f"失败({desc or res_code})", False

            if "已" in desc or "重复" in desc or "today" in desc.lower():
                print(f"📅 账号{self.index}: 今日已签到")
                return "今日已签到", True

            print(f"⚠️  账号{self.index}: 未知结果 - {result}")
            return str(result), False

        except Exception as e:
            print(f"❌ 账号{self.index}: 签到异常 - {e}")
            return f"异常({e})", False

    # ── 工具 ─────────────────────────────────────────────────

    @staticmethod
    def _mask(s):
        if len(s) <= 4: return "***"
        return s[:2] + "***" + s[-2:]

    def run(self):
        print(f"\n==== 天翼云盘 账号{self.index} ====")
        if not self.login():
            return
        reward, already = self.sign_in()
        if not already:
            print(f"📊 账号{self.index}: {reward}")
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
