#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NBA 每日赛程 - GitHub Actions 版
数据源：优先 NBA 官方 cdn.nba.com，失败回退 ESPN
"""

import requests
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
ET = timezone(timedelta(hours=-5))  # NBA 赛程以美东时间为基准
HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/126.0.0.0 Safari/537.36'),
    'Referer': 'https://www.nba.com/',
    'Accept': 'application/json',
}

NBA_TODAY = 'https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json'
ESPN_SB = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'


SCRIPT_VERSION = 'nba-v2-20260828'


def utc_to_cst(utc_str: str) -> str:
    try:
        dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        return dt.astimezone(CST).strftime('%H:%M')
    except Exception:
        return ''


def parse_nba_official(data):
    """解析 NBA 官方 todaysScoreboard，返回统一结构的 games 列表"""
    sb = data.get('scoreboard', {})
    games = []
    for g in sb.get('games', []):
        home = g.get('homeTeam', {})
        away = g.get('awayTeam', {})
        # gameStatus: 1=未开始 2=进行中 3=已结束
        st = g.get('gameStatus', 1)
        state = {1: 'pre', 2: 'in', 3: 'post'}.get(st, 'pre')
        games.append({
            'home': f"{home.get('teamCity','')} {home.get('teamName','')}".strip(),
            'away': f"{away.get('teamCity','')} {away.get('teamName','')}".strip(),
            'home_score': int(home.get('score') or 0),
            'away_score': int(away.get('score') or 0),
            'state': state,
            'status_txt': g.get('gameStatusText', '').strip(),
            'start_cst': utc_to_cst(g.get('gameTimeUTC', '')),
        })
    return games


def parse_espn(data):
    """解析 ESPN scoreboard（备用源）"""
    games = []
    for event in data.get('events', []):
        comp = event.get('competitions', [{}])[0]
        cs = comp.get('competitors', [])
        home = next((c for c in cs if c.get('homeAway') == 'home'), None)
        away = next((c for c in cs if c.get('homeAway') == 'away'), None)
        if not home or not away:
            continue
        stype = event.get('status', {}).get('type', {})
        state = stype.get('state', 'pre')
        games.append({
            'home': f"{home['team'].get('location','')} {home['team'].get('name','')}".strip(),
            'away': f"{away['team'].get('location','')} {away['team'].get('name','')}".strip(),
            'home_score': int(home.get('score') or 0),
            'away_score': int(away.get('score') or 0),
            'state': state,
            'status_txt': stype.get('shortDetail', ''),
            'start_cst': utc_to_cst(event.get('date', '')),
        })
    return games


def fetch_games():
    """按优先级尝试数据源，返回 (games, 源名)；全失败返回 (None, None)"""
    errors = []
    # 1) NBA 官方
    try:
        r = requests.get(NBA_TODAY, headers=HEADERS, timeout=15)
        if r.status_code == 200 and '<html' not in r.text[:100].lower():
            return parse_nba_official(r.json()), 'NBA官方'
        errors.append(f'NBA官方 HTTP {r.status_code}')
    except Exception as e:
        errors.append(f'NBA官方 {e}')
    # 2) ESPN 备用
    try:
        r = requests.get(ESPN_SB, headers=HEADERS, timeout=15)
        if r.status_code == 200 and '<html' not in r.text[:100].lower():
            return parse_espn(r.json()), 'ESPN'
        errors.append(f'ESPN HTTP {r.status_code}')
    except Exception as e:
        errors.append(f'ESPN {e}')

    print(f"[诊断] 所有数据源失败: {'; '.join(errors)}")
    return None, None


def main():
    print(f'🔖 脚本版本: {SCRIPT_VERSION}')
    cst_date = datetime.now(CST).strftime('%Y-%m-%d')
    games, source = fetch_games()

    if games is None:
        print(f"### 🏀 NBA 赛程\n\n⚠️ 数据源暂时不可用，稍后再试。")
        return

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

    sections.append(f'\n> 数据源: {source}')
    print('\n'.join(sections))


if __name__ == '__main__':
    main()
