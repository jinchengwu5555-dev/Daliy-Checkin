#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Name: NBA每日赛程 (让分盘热门)
Cron: 0 8 * * *
"""

import requests
import os
import json
import urllib3
from datetime import datetime, timezone, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from notify import send
    NOTIFY_AVAILABLE = True
except ImportError:
    NOTIFY_AVAILABLE = False

CST = timezone(timedelta(hours=8))
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def utc_to_cst(utc_str: str) -> str:
    try:
        dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        return dt.astimezone(CST).strftime('%H:%M')
    except Exception:
        return ''


def normalize(name: str) -> str:
    return name.strip().lower().split()[-1]


def fetch_spread_odds() -> dict:
    """
    从 ESPN odds 接口逐场获取让分数据
    返回 {(away_normalized, home_normalized): abs_spread}
    """
    scoreboard_url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
    try:
        r = requests.get(scoreboard_url, headers=HEADERS, timeout=10, verify=False)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f'[警告] 获取ESPN赛程失败: {e}')
        return {}

    spread_map = {}

    for event in data.get('events', []):
        event_id = event.get('id', '')
        comp = event.get('competitions', [{}])[0]
        competitors = comp.get('competitors', [])
        if len(competitors) < 2:
            continue

        home = next((c for c in competitors if c.get('homeAway') == 'home'), None)
        away = next((c for c in competitors if c.get('homeAway') == 'away'), None)
        if not home or not away:
            continue

        home_name = home.get('team', {}).get('displayName', '')
        away_name = away.get('team', {}).get('displayName', '')

        odds_url = (
            f'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba'
            f'/events/{event_id}/competitions/{event_id}/odds'
        )
        try:
            ro = requests.get(odds_url, headers=HEADERS, timeout=10, verify=False)
            ro.raise_for_status()
            items = ro.json().get('items', [])
            if items:
                spread = items[0].get('spread')
                if spread is not None:
                    key = (normalize(away_name), normalize(home_name))
                    spread_map[key] = abs(float(spread))
        except Exception:
            continue

    print(f'[信息] ESPN让分数据获取成功，共 {len(spread_map)} 场')
    return spread_map


def match_spread(spread_map: dict, away_full: str, home_full: str):
    key = (normalize(away_full), normalize(home_full))
    if key in spread_map:
        return spread_map[key]
    key_rev = (normalize(home_full), normalize(away_full))
    if key_rev in spread_map:
        return spread_map[key_rev]
    return None


def main():
    cst_date = datetime.now(CST).strftime('%Y-%m-%d')

    # 获取NBA今日赛程
    try:
        r = requests.get(
            'https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json',
            headers=HEADERS, timeout=10, verify=False
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        msg = f'[错误] 获取NBA赛程失败: {e}'
        print(msg)
        if NOTIFY_AVAILABLE:
            send('NBA赛程', msg)
        return

    games = data.get('scoreboard', {}).get('games', [])
    game_date = data.get('scoreboard', {}).get('gameDate', '')

    if not games:
        msg = f'### 🏀 NBA 赛程\n\n**{cst_date}** 今日暂无比赛。'
        print(msg)
        if NOTIFY_AVAILABLE:
            send('NBA赛程', msg)
        return

    # 获取让分盘
    spread_map = fetch_spread_odds()

    # 计算热门：让分绝对值最小的2场
    game_spreads = []
    for g in games:
        away_full = f"{g['awayTeam']['teamCity']} {g['awayTeam']['teamName']}"
        home_full = f"{g['homeTeam']['teamCity']} {g['homeTeam']['teamName']}"
        sp = match_spread(spread_map, away_full, home_full)
        game_spreads.append((str(g['gameId']), sp))

    spread_info = {gid: sp for gid, sp in game_spreads if sp is not None}

    if any(sp is not None for _, sp in game_spreads):
        with_data = [(gid, sp) for gid, sp in game_spreads if sp is not None]
        with_data.sort(key=lambda x: x[1])
        hot_ids = {gid for gid, _ in with_data[:2]}
        hot_method = '让分盘'
    else:
        # 回退：胜场排名
        team_wins = {}
        for g in games:
            for side in ('awayTeam', 'homeTeam'):
                t = g[side]
                tid = str(t.get('teamId', ''))
                w = t.get('wins')
                if tid and w is not None:
                    team_wins[tid] = int(w)
        sorted_teams = sorted(team_wins.items(), key=lambda x: x[1], reverse=True)
        ranking = {tid: rank for rank, (tid, _) in enumerate(sorted_teams, 1)}
        scored = []
        for g in games:
            away_id = str(g['awayTeam'].get('teamId', ''))
            home_id = str(g['homeTeam'].get('teamId', ''))
            r_away = ranking.get(away_id, 99)
            r_home = ranking.get(home_id, 99)
            score = (99 - r_away) + (99 - r_home)
            if r_away <= 8 and r_home <= 8:
                score += 5
            scored.append((score, str(g['gameId'])))
        scored.sort(key=lambda x: x[0], reverse=True)
        hot_ids = {gid for _, gid in scored[:2]}
        hot_method = '胜场排名(回退)'

    # 分类
    finished, ongoing, upcoming = [], [], []

    for g in games:
        away = g['awayTeam']
        home = g['homeTeam']
        status = g.get('gameStatus', 1)
        status_txt = g.get('gameStatusText', '').strip()
        game_id = str(g['gameId'])
        is_hot = game_id in hot_ids
        start_cst = utc_to_cst(g.get('gameTimeUTC', ''))
        away_full = f"{away['teamCity']} {away['teamName']}"
        home_full = f"{home['teamCity']} {home['teamName']}"
        sp = spread_info.get(game_id)
        spread_str = f"{sp:.1f}" if sp is not None else '-'

        info = {
            'home': home_full,
            'away': away_full,
            'home_score': home.get('score', 0),
            'away_score': away.get('score', 0),
            'status_txt': status_txt,
            'start_cst': start_cst,
            'is_hot': is_hot,
            'spread': spread_str,
        }
        if status == 3:
            finished.append(info)
        elif status == 2:
            ongoing.append(info)
        else:
            upcoming.append(info)

    # Markdown 排版
    sections = [
        f"### 🏀 NBA 赛程\n\n"
        f"**赛事日期(美东):** {game_date}　　**北京时间:** {cst_date}"
    ]

    if ongoing:
        block = ['\n#### 🔴 进行中\n']
        block.append('| 主场 | 客场 | 比分 | 节次 | 让分 |')
        block.append('|:---|:---|:---:|:---:|:---:|')
        for g in ongoing:
            hot = '🔥 ' if g['is_hot'] else ''
            block.append(
                f"| {hot}**{g['home']}** "
                f"| {g['away']} "
                f"| {g['home_score']}-{g['away_score']} "
                f"| {g['status_txt']} "
                f"| {g['spread']} |"
            )
        sections.append('\n'.join(block))

    if upcoming:
        block = ['\n#### 🕐 今日待开赛\n']
        block.append('| 主场 | 客场 | 开赛(北京时间) | 让分 |')
        block.append('|:---|:---|:---:|:---:|')
        for g in upcoming:
            hot = '🔥 ' if g['is_hot'] else ''
            time = g['start_cst'] if g['start_cst'] else '-'
            block.append(
                f"| {hot}**{g['home']}** "
                f"| {g['away']} "
                f"| {time} "
                f"| {g['spread']} |"
            )
        sections.append('\n'.join(block))

    if finished:
        block = ['\n#### ✅ 已结束\n']
        block.append('| 主场 | 客场 | 比分 | 胜者 | 让分 |')
        block.append('|:---|:---|:---:|:---|:---:|')
        for g in finished:
            hot = '🔥 ' if g['is_hot'] else ''
            h_win = g['home_score'] > g['away_score']
            home_f = f"**{g['home']}**" if h_win else g['home']
            away_f = f"**{g['away']}**" if not h_win else g['away']
            winner = g['home'] if h_win else g['away']
            block.append(
                f"| {hot}{home_f} "
                f"| {away_f} "
                f"| {g['home_score']}-{g['away_score']} "
                f"| 🏆 **{winner}** "
                f"| {g['spread']} |"
            )
        sections.append('\n'.join(block))

    sections.append(
        f'\n> 🔥 热门标准: **{hot_method}** — 让分绝对值最小的2场(盘口越平 = 最受关注)'
    )

    result = '\n'.join(sections)
    print(result)

    if NOTIFY_AVAILABLE:
        send('NBA每日赛程', result)


if __name__ == '__main__':
    main()
