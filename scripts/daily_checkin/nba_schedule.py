#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NBA每日赛程 (让分盘热门) - GitHub Actions 版
数据源：ESPN scoreboard API（cdn.nba.com 封锁 GitHub Actions IP）
"""

import requests
import urllib3
from datetime import datetime, timezone, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CST = timezone(timedelta(hours=8))
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
SCOREBOARD_URL = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'


def utc_to_cst(utc_str: str) -> str:
    try:
        dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        return dt.astimezone(CST).strftime('%H:%M')
    except Exception:
        return ''


def fetch_scoreboard():
    try:
        r = requests.get(SCOREBOARD_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f'[错误] 获取ESPN赛程失败: {e}')
        return None


def fetch_spread(event_id: str):
    url = (
        f'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba'
        f'/events/{event_id}/competitions/{event_id}/odds'
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        items = r.json().get('items', [])
        if items:
            spread = items[0].get('spread')
            if spread is not None:
                return abs(float(spread))
    except Exception:
        pass
    return None


def main():
    cst_date = datetime.now(CST).strftime('%Y-%m-%d')

    data = fetch_scoreboard()
    if not data:
        return

    events = data.get('events', [])
    if not events:
        print(f"### 🏀 NBA 赛程\n\n**{cst_date}** 今日暂无比赛。")
        return

    # 解析赛程
    games = []
    for event in events:
        comp = event.get('competitions', [{}])[0]
        competitors = comp.get('competitors', [])
        if len(competitors) < 2:
            continue

        home = next((c for c in competitors if c.get('homeAway') == 'home'), None)
        away = next((c for c in competitors if c.get('homeAway') == 'away'), None)
        if not home or not away:
            continue

        status_type  = event.get('status', {}).get('type', {})
        status_state = status_type.get('state', 'pre')   # pre / in / post
        status_txt   = status_type.get('shortDetail', '')
        start_cst    = utc_to_cst(event.get('date', ''))
        event_id     = event.get('id', '')

        home_name  = f"{home['team'].get('location', '')} {home['team'].get('name', '')}".strip()
        away_name  = f"{away['team'].get('location', '')} {away['team'].get('name', '')}".strip()
        home_score = int(home.get('score') or 0)
        away_score = int(away.get('score') or 0)

        games.append({
            'event_id':   event_id,
            'home':       home_name,
            'away':       away_name,
            'home_score': home_score,
            'away_score': away_score,
            'state':      status_state,
            'status_txt': status_txt,
            'start_cst':  start_cst,
            'spread':     fetch_spread(event_id),
        })

    if not games:
        print(f"### 🏀 NBA 赛程\n\n**{cst_date}** 今日暂无比赛。")
        return

    # 热门：让分绝对值最小的 2 场
    with_spread = [(g['event_id'], g['spread']) for g in games if g['spread'] is not None]
    if with_spread:
        with_spread.sort(key=lambda x: x[1])
        hot_ids    = {eid for eid, _ in with_spread[:2]}
        hot_method = '让分盘'
    else:
        hot_ids    = set()
        hot_method = '(无让分数据)'

    finished, ongoing, upcoming = [], [], []
    for g in games:
        g['is_hot']     = g['event_id'] in hot_ids
        g['spread_str'] = f"{g['spread']:.1f}" if g['spread'] is not None else '-'
        if g['state'] == 'post':
            finished.append(g)
        elif g['state'] == 'in':
            ongoing.append(g)
        else:
            upcoming.append(g)

    sections = [f"### 🏀 NBA 赛程\n\n**北京时间:** {cst_date}"]

    if ongoing:
        block = ['\n#### 🔴 进行中\n',
                 '| 主场 | 客场 | 比分 | 节次 | 让分 |',
                 '|:---|:---|:---:|:---:|:---:|']
        for g in ongoing:
            hot = '🔥 ' if g['is_hot'] else ''
            block.append(
                f"| {hot}**{g['home']}** | {g['away']} "
                f"| {g['home_score']}-{g['away_score']} "
                f"| {g['status_txt']} | {g['spread_str']} |"
            )
        sections.append('\n'.join(block))

    if upcoming:
        block = ['\n#### 🕐 今日待开赛\n',
                 '| 主场 | 客场 | 开赛(北京时间) | 让分 |',
                 '|:---|:---|:---:|:---:|']
        for g in upcoming:
            hot = '🔥 ' if g['is_hot'] else ''
            block.append(
                f"| {hot}**{g['home']}** | {g['away']} "
                f"| {g['start_cst'] or '-'} | {g['spread_str']} |"
            )
        sections.append('\n'.join(block))

    if finished:
        block = ['\n#### ✅ 已结束\n',
                 '| 主场 | 客场 | 比分 | 胜者 | 让分 |',
                 '|:---|:---|:---:|:---|:---:|']
        for g in finished:
            h_win  = g['home_score'] > g['away_score']
            home_f = f"**{g['home']}**" if h_win else g['home']
            away_f = f"**{g['away']}**" if not h_win else g['away']
            winner = g['home'] if h_win else g['away']
            hot    = '🔥 ' if g['is_hot'] else ''
            block.append(
                f"| {hot}{home_f} | {away_f} "
                f"| {g['home_score']}-{g['away_score']} "
                f"| 🏆 **{winner}** | {g['spread_str']} |"
            )
        sections.append('\n'.join(block))

    sections.append(f'\n> 🔥 热门标准: **{hot_method}** — 让分绝对值最小的2场')
    print('\n'.join(sections))


if __name__ == '__main__':
    main()
