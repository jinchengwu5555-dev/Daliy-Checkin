#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NBA 每日赛程 - GitHub Actions 版
数据源：data.nba.com 整季赛程静态文件（不拦机房 IP），从整季数据筛当天比赛
备用：cdn.nba.com 今日赛程（若可用）
"""

import requests
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/126.0.0.0 Safari/537.36'),
    'Referer': 'https://www.nba.com/',
    'Accept': 'application/json',
}


SCRIPT_VERSION = 'nba-v3-20260828'


def season_year():
    """NBA 赛季以开赛年为准：8 月及以后属当年新赛季，之前属上一年"""
    now = datetime.now(CST)
    return now.year if now.month >= 8 else now.year - 1


# 整季赛程静态文件（{year} 为赛季起始年，如 2026-27 赛季填 2026）
FULL_SCHEDULE = 'https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/{year}/league/00_full_schedule.json'


def utc_to_cst_parts(utc_str: str):
    """把 UTC 时间字符串转成 (北京日期 YYYY-MM-DD, 北京时刻 HH:MM)"""
    try:
        dt = datetime.strptime(utc_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
    except Exception:
        try:
            dt = datetime.strptime(utc_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        except Exception:
            return '', ''
    cst = dt.astimezone(CST)
    return cst.strftime('%Y-%m-%d'), cst.strftime('%H:%M')


def fetch_full_schedule():
    """拉取整季赛程；成功返回 JSON，失败返回 None"""
    url = FULL_SCHEDULE.format(year=season_year())
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200 and '<html' not in r.text[:100].lower():
            return r.json()
        print(f"[诊断] data.nba.com HTTP {r.status_code}, 前80字: {r.text[:80]}")
    except Exception as e:
        print(f"[诊断] data.nba.com 请求失败: {e}")
    return None


def extract_today_games(data, target_date):
    """从整季赛程里筛出北京时间 target_date 当天的比赛"""
    games = []
    # 结构: data['lscd'] = [{'mscd': {'g': [场次...]}}, ...]（按月分组）
    for month in data.get('lscd', []):
        for g in month.get('mscd', {}).get('g', []):
            utc = g.get('gdtutc', '')
            tm = g.get('utctm', '')  # 形如 "23:00"
            if not utc:
                continue
            # gdtutc 是 UTC 日期（YYYY-MM-DD），utctm 是 UTC 时刻
            utc_full = f"{utc}T{tm}:00Z" if tm else f"{utc}T00:00:00Z"
            game_date_cst, start_cst = utc_to_cst_parts(utc_full)
            if game_date_cst != target_date:
                continue

            v = g.get('v', {})  # visitor 客队
            h = g.get('h', {})  # home 主队
            away_name = f"{v.get('tc','')} {v.get('tn','')}".strip()
            home_name = f"{h.get('tc','')} {h.get('tn','')}".strip()
            # stt: 状态文本；比分在 v['s'] / h['s']（未开赛为空字符串）
            stt = g.get('stt', '')
            v_score = v.get('s', '').strip()
            h_score = h.get('s', '').strip()

            # 判断状态
            if 'Final' in stt:
                state = 'post'
            elif v_score and h_score and any(ch.isdigit() for ch in stt):
                state = 'in'
            else:
                state = 'pre'

            games.append({
                'home': home_name, 'away': away_name,
                'home_score': int(h_score) if h_score.isdigit() else 0,
                'away_score': int(v_score) if v_score.isdigit() else 0,
                'state': state, 'status_txt': stt, 'start_cst': start_cst,
            })
    return games


def main():
    print(f'🔖 脚本版本: {SCRIPT_VERSION}')
    cst_date = datetime.now(CST).strftime('%Y-%m-%d')

    data = fetch_full_schedule()
    if data is None:
        print(f"### 🏀 NBA 赛程\n\n⚠️ 数据源暂时不可用，稍后再试。")
        return

    games = extract_today_games(data, cst_date)
    if not games:
        print(f"### 🏀 NBA 赛程\n\n**{cst_date}** 今日暂无比赛（可能处于休赛期）。")
        return

    finished, ongoing, upcoming = [], [], []
    for g in games:
        if g['state'] == 'post':
            finished.append(g)
        elif g['state'] == 'in':
            ongoing.append(g)
        else:
            upcoming.append(g)

    sections = [f"### 🏀 NBA 赛程\n\n**北京时间:** {cst_date}"]

    if ongoing:
        block = ['\n#### 🔴 进行中\n',
                 '| 主场 | 客场 | 比分 | 状态 |',
                 '|:---|:---|:---:|:---:|']
        for g in ongoing:
            block.append(f"| **{g['home']}** | {g['away']} "
                         f"| {g['home_score']}-{g['away_score']} | {g['status_txt']} |")
        sections.append('\n'.join(block))

    if upcoming:
        block = ['\n#### 🕐 今日待开赛\n',
                 '| 主场 | 客场 | 开赛(北京时间) |',
                 '|:---|:---|:---:|']
        for g in upcoming:
            block.append(f"| **{g['home']}** | {g['away']} | {g['start_cst'] or '-'} |")
        sections.append('\n'.join(block))

    if finished:
        block = ['\n#### ✅ 已结束\n',
                 '| 主场 | 客场 | 比分 | 胜者 |',
                 '|:---|:---|:---:|:---|']
        for g in finished:
            h_win = g['home_score'] > g['away_score']
            home_f = f"**{g['home']}**" if h_win else g['home']
            away_f = f"**{g['away']}**" if not h_win else g['away']
            winner = g['home'] if h_win else g['away']
            block.append(f"| {home_f} | {away_f} "
                         f"| {g['home_score']}-{g['away_score']} | 🏆 **{winner}** |")
        sections.append('\n'.join(block))

    sections.append('\n> 数据源: NBA官方赛程')
    print('\n'.join(sections))


if __name__ == '__main__':
    main()
