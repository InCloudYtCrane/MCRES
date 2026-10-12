import os
import json
import random


def edit():
    """从当前目录的 edit.json 读取数据"""
    path = os.path.join(os.getcwd(), 'edit.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def random_quote():
    """从当前目录的 random_quote.txt 随机选取一条非注释（不含 //）的引用"""
    path = os.path.join(os.getcwd(), 'random_quote.txt')
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()
    quotes = [line for line in lines if not line.startswith('//') and line]
    if not quotes:
        return ''
    return random.choice(quotes)


def changelog():
    """
    从当前目录的 development.json 读取更新日志

    数据格式：
        {
            "config": [
                {"key": "main", "name": "主站", "color": "#55d88b"},
                ...
            ],
            "milestone": [
                {
                    "date": "2026年09月13日",
                    "title": "选料模块上线",
                    "desc": "工坊选料模块正式上线……",
                    "color": "#a855f7",
                    "icon": "fa-rocket"
                },
                ...
            ],
            "content": [
                {
                    "date": "2026年09月12日",
                    "detail": {
                        "main": ["修复了xxx", "修复了yyy"],
                        "admin": ["修复了zzz"]
                    }
                },
                ...
            ]
        }

    返回结构：
        {
            "config":    [{"key", "name", "color"}, ...],
            "milestone": [{"date", "title", "desc", "color", "icon"}, ...],
            "content":   [{"date", "detail": {"cat_key": [str, ...], ...}}, ...]
        }

    兼容旧格式：顶层为数组 [{date, detail: [str, ...]}, ...]，
    全部归到默认分类 "综合"。
    """
    path = os.path.join(os.getcwd(), 'development.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # ---------- 情况 1：旧格式（顶层数组，detail 是字符串数组） ----------
    if isinstance(data, list):
        default_cat = {'key': 'general', 'name': '综合', 'color': '#8b949e'}
        content = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            date = entry.get('date') or ''
            raw_detail = entry.get('detail') or []
            detail = []
            if isinstance(raw_detail, list):
                for d in raw_detail:
                    if isinstance(d, str):
                        detail.append(d)
                    elif isinstance(d, dict) and d.get('text'):
                        detail.append(str(d['text']))
            if date and detail:
                content.append({
                    'date': date,
                    'detail': {'general': detail},
                })

        return {
            'config': [default_cat],
            'milestone': [],
            'content': content,
        }

    # ---------- 情况 2：新格式（dict） ----------
    if isinstance(data, dict):
        raw_config = data.get('config') or []
        raw_content = data.get('content') or []
        raw_milestone = data.get('milestone') or []

        # ---- 归一化 config ----
        norm_config = []
        seen_keys = set()
        for cat in raw_config:
            if not isinstance(cat, dict):
                continue
            key = str(cat.get('key') or '').strip()
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            norm_config.append({
                'key': key,
                'name': str(cat.get('name') or key),
                'color': str(cat.get('color') or '#8b949e'),
            })

        if not norm_config:
            norm_config = [{'key': 'general', 'name': '综合', 'color': '#8b949e'}]

        # ---- 归一化 milestone ----
        norm_milestone = []
        if isinstance(raw_milestone, list):
            for m in raw_milestone:
                if not isinstance(m, dict):
                    continue
                date = str(m.get('date') or '').strip()
                title = str(m.get('title') or '').strip()
                if not date or not title:
                    continue
                norm_milestone.append({
                    'date': date,
                    'title': title,
                    'desc': str(m.get('desc') or ''),
                    'color': str(m.get('color') or '#8b949e'),
                    'icon': str(m.get('icon') or 'fa-flag'),
                })

        # ---- 归一化 content ----
        if not isinstance(raw_content, list):
            raw_content = []

        norm_content = []
        for entry in raw_content:
            if not isinstance(entry, dict):
                continue
            date = entry.get('date') or ''
            raw_detail = entry.get('detail')
            if not date or not raw_detail:
                continue

            detail = {}

            if isinstance(raw_detail, dict):
                for cat_key, items in raw_detail.items():
                    if not isinstance(items, list):
                        if isinstance(items, str):
                            items = [items]
                        else:
                            continue
                    cleaned = [t for t in items if isinstance(t, str) and t]
                    if cleaned:
                        detail[cat_key] = cleaned

            elif isinstance(raw_detail, list):
                cleaned = [t for t in raw_detail if isinstance(t, str) and t]
                if cleaned:
                    detail[norm_config[0]['key']] = cleaned

            if detail:
                norm_content.append({
                    'date': date,
                    'detail': detail,
                })

        return {
            'config': norm_config,
            'milestone': norm_milestone,
            'content': norm_content,
        }

    # ---------- 情况 3：未知格式 ----------
    return {'config': [], 'milestone': [], 'content': []}


def about():
    """从当前目录的 developers.json 读取开发人员信息"""
    path = os.path.join(os.getcwd(), 'developers.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)