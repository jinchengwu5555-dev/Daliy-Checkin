#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
天翼云盘签到 - 抓取 shakeLottery SPA 的 API 接口
"""

import time
import re
import base64
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

    def find_apis_from_spa(self):
        base = "https://m.cloud.189.cn/zhuanti/2021/shakeLottery"

        # 1. 拉取 index.html，找 JS 文件列表
        print("\n=== 解析 SPA JS 文件 ===")
        r = self.session.get(f"{base}/index.html", timeout=15)
        html = r.text

        # 找所有 <script src="..."> 和 JS 文件引用
        js_files = re.findall(r'src=["\']([^"\']*\.js[^"\']*)["\']', html)
        print(f"发现 JS 文件: {js_files}")

        # 2. 逐个拉取 JS，搜索 API 路径
        api_candidates = set()
        for js in js_files:
            if not js.startswith('http'):
                js_url = f"{base}/{js.lstrip('/')}"
            else:
                js_url = js
            try:
                rj = self.session.get(js_url, timeout=15)
                content = rj.text

                # 提取所有像 API 路径的字符串
                # 匹配 /v2/xxx.action 或 /api/xxx 或 action 相关
                paths = re.findall(r'["\'](/[a-zA-Z0-9/_\-\.]*(?:action|sign|task|prize|lottery)[a-zA-Z0-9/_\-\.]*)["\']', content)
                for p in paths:
                    api_candidates.add(p)

                # 也找完整 URL
                full_urls = re.findall(r'https?://[a-zA-Z0-9\-\.]+\.cloud\.189\.cn[/a-zA-Z0-9/_\-\.?=&]*', content)
                for u in full_urls:
                    if any(k in u for k in ['sign', 'action', 'task', 'prize', 'lottery']):
                        api_candidates.add(u)

                print(f"  {js_url.split('/')[-1]}: {len(content)} bytes, 找到 {len(paths)} 个路径")
            except Exception as e:
                print(f"  ERR {js_url}: {e}")

        print(f"\n=== 提取到的 API 候选路径 ({len(api_candidates)}个) ===")
        for p in sorted(api_candidates):
            print(f"  {p}")

        # 3. 逐一请求这些接口
        print(f"\n=== 逐一探测候选接口 ===")
        for path in sorted(api_candidates):
            if path.startswith('/'):
                url = f"https://m.cloud.189.cn{path}"
            else:
                url = path
            try:
                r = self.session.get(url, timeout=8)
                body = r.text[:100].replace('\n', ' ')
                marker = "★" if r.status_code == 200 and '{' in r.text else " "
                print(f"{marker}[{r.status_code}] {path.split('/')[-1][:40]} → {body[:80]}")
            except Exception as e:
                print(f"  ERR {path}: {e}")

    @staticmethod
    def _mask(s):
        if len(s) <= 4: return "***"
        return s[:2] + "***" + s[-2:]

    def run(self):
        print(f"\n==== 天翼云盘 账号{self.index} ====")
        if not self.login():
            return
        self.find_apis_from_spa()

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
