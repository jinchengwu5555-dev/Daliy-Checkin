#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
名称：行情播报
定时：30 9,15 * * 1-5
"""

import requests
from datetime import datetime, timezone, timedelta

try:
    import yfinance as yf
except ImportError:
    import subprocess
    subprocess.run(['pip', 'install', 'yfinance', '-q'])
    import yfinance as yf

# ── 资产配置表 ──────────────────────────────────────────────
# (显示名, 数据来源, 代码/ticker, 备注)
# 来源: 'sina_sh' | 'sina_sz' | 'sina_hk' | 'yahoo'
ASSETS = [
    ('🥇 黄金',        'yahoo',    'GC=F',       'gold'),
    ('中证A500',       'sina_sh',  '588200',     'etf'),   # 中证A500ETF (588200.SH)
    ('标普500',         'yahoo',    '^GSPC',      'stock'),
    ('英伟达',         'yahoo',    'NVDA',       'stock'),
    ('Oklo',           'yahoo',    'OKLO',       'stock'),
    ('NuScale',        'yahoo',    'SMR',        'stock'),
    ('Bloom Energy',   'yahoo',    'BE',         'stock'),
    ('比亚迪A',        'sina_sz',  '002594',     'stock'),
    ('比亚迪H',        'sina_hk',  '01211',      'stock'),
    ('宁德时代',       'sina_sz',  '300750',     'stock'),
    ('步科股份',       'sina_sh',  '603272',     'stock'),
    ('大族激光',       'sina_sz',  '002008',     'stock'),
    ('TCL电子',        'sina_hk',  '01070',      'stock'),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://finance.sina.com.cn'
}


# ── 行情获取 ────────────────────────────────────────────────

def get_sina(prefix, code):
    """通用新浪行情：sh/sz/hk"""
    try:
        symbol = f"{prefix}{code}"
        r = requests.get(f"https://hq.sinajs.cn/list={symbol}",
                         headers=HEADERS, timeout=10)
        r.encoding = 'gbk'
        data_str = r.text.split('"')[1]
        if not data_str:
            return None
        f = data_str.split(',')

        if prefix == 'hk':
            # 港股字段：f[2]=昨收, f[6]=当前价
            prev_close = float(f[2])
            current    = float(f[6])
        else:
            # A股 sh/sz: f[2]=昨收, f[3]=当前价
            prev_close = float(f[2])
            current    = float(f[3])
            if current == 0:
                bid = float(f[6]) if len(f) > 6 else 0
                current = bid if bid > 0 else prev_close

        if prev_close == 0 or current == 0:
            return None

        return {
            'current':    current,
            'change_pct': (current - prev_close) / prev_close * 100,
        }
    except:
        return None


def get_yahoo_quote(ticker_symbol):
    """Yahoo Finance 实时报价（含历史最高）"""
    try:
        t    = yf.Ticker(ticker_symbol)
        hist = t.history(period='2d')
        if hist.empty:
            return None
        current = hist['Close'].iloc[-1]
        prev    = hist['Close'].iloc[-2] if len(hist) >= 2 else current
        chg_pct = (current - prev) / prev * 100 if prev else 0
        return {'current': current, 'change_pct': chg_pct}
    except:
        return None


def get_history_high_yahoo(ticker_symbol):
    try:
        hist = yf.Ticker(ticker_symbol).history(period='max')
        return hist['High'].max() if not hist.empty else None
    except:
        return None


def get_sina_history_high(prefix, code):
    """用 Yahoo 对应代码取历史最高（A股/港股映射）"""
    # 映射表：新浪代码 → Yahoo ticker
    MAP = {
        'sh588200': '588200.SS',
        'sh513500': '513500.SS',
        'sz002594': '002594.SZ',
        'hk01211':  '1211.HK',
        'sz300750': '300750.SZ',
        'sh603272': '603272.SS',
        'sz002008': '002008.SZ',
        'hk01070':  '1070.HK',
    }
    key = f"{prefix}{code}"
    yahoo_sym = MAP.get(key)
    if not yahoo_sym:
        return None
    return get_history_high_yahoo(yahoo_sym)


def get_gold_data():
    """黄金：人民币/克，当日涨跌，年内高低"""
    try:
        gc   = yf.Ticker('GC=F')
        hist = gc.history(period='2d')
        if hist.empty:
            return None, None, None, None

        usd_oz  = hist['Close'].iloc[-1]
        prev_oz = hist['Close'].iloc[-2] if len(hist) >= 2 else usd_oz

        fx   = yf.Ticker('CNY=X').history(period='2d')
        rate = fx['Close'].iloc[-1] if not fx.empty else 7.1

        cny_gram = usd_oz * rate / 31.1035
        chg_pct  = (usd_oz - prev_oz) / prev_oz * 100 if prev_oz else 0

        ytd = gc.history(period='ytd')
        if not ytd.empty:
            ytd_high = ytd['High'].max() * rate / 31.1035
            ytd_low  = ytd['Low'].min()  * rate / 31.1035
        else:
            ytd_high = ytd_low = None

        return round(cny_gram, 2), chg_pct, ytd_high, ytd_low
    except:
        return None, None, None, None


# ── 格式化辅助 ──────────────────────────────────────────────

def fmt_pct(pct):
    if pct is None:
        return 'N/A'
    arrow = '↑' if pct >= 0 else '↓'
    sign  = '+' if pct >= 0 else ''
    return f"{arrow}{sign}{pct:.2f}%"


def fmt_ratio(current, high):
    if high and high > 0:
        return f"{current / high * 100:.1f}%"
    return 'N/A'


# ── 主逻辑 ──────────────────────────────────────────────────

def main():
    now   = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')
    lines = [f'### 📊 行情播报  {now}\n']
    lines.append('| 资产 | 现价 | 较前日 | 历史最高 | 现价/最高 |')
    lines.append('|:---|:---:|:---:|:---:|:---:|')

    for label, source, code, kind in ASSETS:

        # ── 黄金单独处理 ──
        if kind == 'gold':
            cny, chg, ytd_high, ytd_low = get_gold_data()
            if cny:
                h_str = f"¥{ytd_high:.2f}(年内)" if ytd_high else 'N/A'
                ratio = fmt_ratio(cny, ytd_high)
                lines.append(
                    f"| {label} | ¥{cny}/克 | {fmt_pct(chg)} | ↑{h_str} | {ratio} |"
                )
            else:
                lines.append(f"| {label} | N/A | N/A | N/A | - |")
            continue

        # ── Yahoo 股票 ──
        if source == 'yahoo':
            d    = get_yahoo_quote(code)
            high = get_history_high_yahoo(code)
            if d:
                cur   = d['current']
                # 美股用美元符号
                cur_str = f"${cur:.2f}"
                h_str   = f"${high:.2f}" if high else 'N/A'
                ratio   = fmt_ratio(cur, high)
                lines.append(
                    f"| {label} ({code}) | {cur_str} | {fmt_pct(d['change_pct'])} | {h_str} | {ratio} |"
                )
            else:
                lines.append(f"| {label} ({code}) | N/A | N/A | N/A | N/A |")
            continue

        # ── 新浪 A股 / 港股 ──
        prefix_map = {'sina_sh': 'sh', 'sina_sz': 'sz', 'sina_hk': 'hk'}
        prefix = prefix_map[source]
        d    = get_sina(prefix, code)
        high = get_sina_history_high(prefix, code)

        if d:
            cur = d['current']
            # 港股用港元，A股用人民币
            currency = 'HK$' if source == 'sina_hk' else '¥'
            decimals  = 3 if source != 'sina_hk' else 2
            cur_str   = f"{currency}{cur:.{decimals}f}"
            h_str     = f"{currency}{high:.{decimals}f}" if high else 'N/A'
            ratio     = fmt_ratio(cur, high)
            lines.append(
                f"| {label} | {cur_str} | {fmt_pct(d['change_pct'])} | {h_str} | {ratio} |"
            )
        else:
            lines.append(f"| {label} | N/A | N/A | N/A | N/A |")

    print('\n'.join(lines))


if __name__ == '__main__':
    main()