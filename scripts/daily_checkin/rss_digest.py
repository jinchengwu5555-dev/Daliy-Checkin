#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSS 每日摘要 - GitHub Actions 版
聚合多个 RSS 源推送 Server酱
注意：Server酱免费版每天限 5 次推送，本脚本合并为 1 次推送
"""

import os
import re
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from html import unescape

CST = timezone(timedelta(hours=8))

# ── RSS 源配置 ──────────────────────────────────────────────
# (key, 显示标签, URL, 条数)
FEEDS = [
    # 🌍 世界
    ("world",    "🌍 世界",         "https://feeds.bbci.co.uk/news/world/rss.xml",              4),
    # 🇨🇳 中国
    ("china",    "🇨🇳 中国",         "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml",            4),
    # 🇺🇸 美国
    ("us",       "🇺🇸 美国",         "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", 3),
    # 🇲🇾 马来西亚
    ("my_fmt",   "🇲🇾 马来 (FMT)",   "https://www.freemalaysiatoday.com/category/nation/feed/",   3),
    # 💰 财经
    ("biz",      "💰 财经",          "https://feeds.bbci.co.uk/news/business/rss.xml",             4),
    ("asia_biz", "💰 亚洲财经 (CNA)","https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6936", 3),
    # 💻 科技
    ("tech_bbc", "💻 科技 (BBC)",    "https://feeds.bbci.co.uk/news/technology/rss.xml",           3),
    ("tech_hn",  "💻 科技 (HN)",     "https://hnrss.org/frontpage?count=8",                        5),
    ("tech_tc",  "💻 科技 (TC)",     "https://techcrunch.com/feed/",                               3),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def clean(text: str) -> str:
    text = re.sub(r'<!\[CDATA\[|\]\]>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    return unescape(text).strip()


CJK_RE = re.compile(r'[\u4e00-\u9fff]')


# 翻译失败诊断计数（仅打印一次，避免刷屏）
_translate_diag_printed = False


def _try_google(text: str) -> str | None:
    """Google 免费翻译接口"""
    r = requests.get(
        'https://translate.googleapis.com/translate_a/single',
        params={'client': 'gtx', 'sl': 'en', 'tl': 'zh-CN', 'dt': 't', 'q': text},
        headers=HEADERS, timeout=8,
    )
    if r.status_code != 200 or '<html' in r.text[:100].lower():
        raise RuntimeError(f'google HTTP {r.status_code}')
    data = r.json()
    zh = ''.join(seg[0] for seg in data[0] if seg and seg[0])
    return zh.strip() or None


def _try_google_clients5(text: str) -> str | None:
    """Google clients5 备用端点（返回结构不同）"""
    r = requests.get(
        'https://clients5.google.com/translate_a/t',
        params={'client': 'dict-chrome-ex', 'sl': 'en', 'tl': 'zh-CN', 'q': text},
        headers=HEADERS, timeout=8,
    )
    if r.status_code != 200:
        raise RuntimeError(f'clients5 HTTP {r.status_code}')
    data = r.json()
    # 结构可能是 [["译文","en"]] 或 {"sentences":[...]}
    if isinstance(data, list) and data and isinstance(data[0], list):
        return str(data[0][0]).strip() or None
    if isinstance(data, dict) and data.get('sentences'):
        return ''.join(s.get('trans', '') for s in data['sentences']).strip() or None
    return None


def _try_mymemory(text: str) -> str | None:
    """MyMemory 免费翻译 API（老牌，无需密钥）"""
    r = requests.get(
        'https://api.mymemory.translated.net/get',
        params={'q': text, 'langpair': 'en|zh-CN'},
        headers=HEADERS, timeout=8,
    )
    if r.status_code != 200:
        raise RuntimeError(f'mymemory HTTP {r.status_code}')
    zh = r.json().get('responseData', {}).get('translatedText', '')
    return zh.strip() or None


def translate_to_zh(text: str) -> str | None:
    """英译中：多接口自动容错，全部失败返回 None"""
    global _translate_diag_printed
    errors = []
    for fn in (_try_google, _try_google_clients5, _try_mymemory):
        try:
            zh = fn(text)
            if zh:
                return zh
        except Exception as e:
            errors.append(str(e))
    # 全挂时，仅第一次打印诊断，方便排查是哪个环节的问题
    if not _translate_diag_printed:
        print(f"⚙️ 翻译接口全部失败，诊断: {'; '.join(errors)}")
        _translate_diag_printed = True
    return None


def fetch_feed(url: str, max_items: int) -> list[dict]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            print(f"  ⚠️ {url.split('/')[2]} → {r.status_code}")
            return []
        root   = ET.fromstring(r.content)
        items  = []
        for item in root.findall(".//item")[:max_items]:
            title = clean(item.findtext("title", ""))
            link  = (item.findtext("link") or "").strip()
            if title:
                items.append({"title": title, "link": link})
        # Atom fallback
        if not items:
            ns = "http://www.w3.org/2005/Atom"
            for entry in root.findall(f"{{{ns}}}entry")[:max_items]:
                title  = clean(entry.findtext(f"{{{ns}}}title", ""))
                link_el = entry.find(f"{{{ns}}}link")
                link   = link_el.get("href", "") if link_el is not None else ""
                if title:
                    items.append({"title": title, "link": link})
        return items
    except Exception as e:
        print(f"  ❌ {url.split('/')[2]}: {e}")
        return []


def build_digest() -> tuple[str, int]:
    now    = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    lines  = [f"# 📰 每日资讯  {now}\n"]
    total  = 0
    failed = []

    for key, label, url, max_items in FEEDS:
        items = fetch_feed(url, max_items)
        if not items:
            failed.append(label)
            continue
        lines.append(f"\n### {label}\n")
        for item in items:
            t = item["title"]
            l = item["link"]
            if CJK_RE.search(t):
                # 本身是中文，直接输出
                t_short = t[:58] + "…" if len(t) > 60 else t
                lines.append(f"- [{t_short}]({l})" if l else f"- {t_short}")
            else:
                # 英文标题：翻译成中文，双语显示
                zh = translate_to_zh(t)
                en_short = t[:48] + "…" if len(t) > 50 else t
                if zh:
                    zh_short = zh[:42] + "…" if len(zh) > 44 else zh
                    lines.append(f"- [{zh_short}]({l})" if l else f"- {zh_short}")
                    lines.append(f"  *{en_short}*")
                else:
                    lines.append(f"- [{en_short}]({l})" if l else f"- {en_short}")
                time.sleep(0.2)  # 翻译接口限速保护
        total += len(items)

    if failed:
        lines.append(f"\n> ⚠️ 获取失败: {', '.join(failed)}")

    lines.append(f"\n\n---\n共 **{total}** 条  |  {now}")
    return "\n".join(lines), total


def push_serverchan(title: str, content: str):
    key = os.environ.get("SERVERCHAN_KEY", "").strip()
    if not key:
        print("⚠️ 未设置 SERVERCHAN_KEY，跳过推送")
        return

    # Server酱 免费版单条限 5000 字，超出截断
    MAX_LEN = 4800
    if len(content) > MAX_LEN:
        content = content[:MAX_LEN] + "\n\n…(内容已截断)"

    try:
        r = requests.post(
            f"https://sctapi.ftqq.com/{key}.send",
            data={"title": title, "desp": content},
            timeout=10,
        )
        result = r.json()
        code   = result.get("code", result.get("errno", 0))
        msg    = result.get("message", result.get("errmsg", ""))
        if code == 0:
            print(f"✅ 推送成功")
        else:
            print(f"❌ 推送失败: {msg}")
    except Exception as e:
        print(f"❌ 推送异常: {e}")


def main():
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"==== RSS 摘要 {now} ====")

    digest, total = build_digest()
    print(f"共获取 {total} 条")
    print(digest)


if __name__ == "__main__":
    main()
