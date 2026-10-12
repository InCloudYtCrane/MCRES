# -*- coding: utf-8 -*-
from flask import Blueprint, request, render_template, jsonify, session

from utils.data.repositories.resources import (
    SEARCH_TABLES,
    list_all_for_search,
    suggest_names,
)
from utils.data.repositories.users import (
    search_by_nickname,
    search_full_by_nickname,
)

import math
import json
import re
from difflib import SequenceMatcher

sch = Blueprint('sch', __name__)

TABLE_TO_TYPE = {
    'resourcepacks': 'resourcepack',
    'shaderpacks': 'shaderpack',
    'maps': 'map'
}

DEFAULT_SIMILARITY_THRESHOLD = 0.8
DEFAULT_FUZZY_WEIGHT_FACTOR = 0.5


def parse_resource(row, table):
    try:
        data = json.loads(row['content'])
    except json.JSONDecodeError:
        return None

    name = data.get('main_name') or data.get('name') or '未命名'
    abbr = data.get('abbr', '')
    sub_name = data.get('sub_name', '')
    summary = data.get('summary', '')
    description = data.get('description', '')
    plain_desc = re.sub(r'<[^>]+>', '', description).strip()
    desc_preview = plain_desc[:200] + ('...' if len(plain_desc) > 200 else '')
    keywords = data.get('keywords', '')
    cover = data.get('cover', '')
    screenshots = data.get('screenshots', [])

    if table == 'resourcepacks':
        category = data.get('category', '未分类')
    elif table == 'shaderpacks':
        category = data.get('style', '未分类')
    else:
        category = data.get('map_type', '未分类')

    type_prefix = TABLE_TO_TYPE.get(table, table.rstrip('s'))
    detail_url = f"/{type_prefix}/{row['id']}"

    return {
        'id': row['id'],
        'type': type_prefix,
        'name': name,
        'abbr': abbr,
        'sub_name': sub_name,
        'summary': summary,
        'description_preview': desc_preview,
        'keywords': keywords,
        'cover': cover,
        'screenshots': screenshots,
        'category': category,
        'detail_url': detail_url
    }


def parse_user(row):
    return {
        'id': row['id'],
        'nickname': row['nickname'],
        'avatar': row.get('avatar', ''),
        'signature': row.get('signature', ''),
        'role': row.get('role', 1),
        'profile_url': f"/profile/{row['id']}"
    }


def get_searchable_fields(item):
    fields = []
    if 'name' in item:
        fields.append((item['name'], 5))
    if 'nickname' in item:
        fields.append((item['nickname'], 5))
    if 'abbr' in item:
        fields.append((item['abbr'], 3))
    if 'sub_name' in item:
        fields.append((item['sub_name'], 3))
    if 'summary' in item:
        fields.append((item['summary'], 2))
    if 'signature' in item:
        fields.append((item['signature'], 2))
    if 'keywords' in item:
        fields.append((item['keywords'], 2))
    if 'description_preview' in item:
        fields.append((item['description_preview'], 1))
    return fields


def get_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def calculate_relevance(item, q, threshold, fuzzy_weight):
    q_lower = q.lower()
    q_words = [w for w in q_lower.split() if w]
    if not q_words:
        return 0

    total_score = 0

    for text, weight in get_searchable_fields(item):
        text_lower = text.lower()

        if q_lower in text_lower:
            total_score += weight * len(q_words)
            continue

        word_match = False
        for word in q_words:
            if word in text_lower:
                total_score += weight
                word_match = True
        if word_match:
            continue

        best_ratio = 0
        for word in q_words:
            ratio = get_similarity(text, word)
            if ratio > best_ratio:
                best_ratio = ratio
        if best_ratio >= threshold:
            total_score += weight * fuzzy_weight

    return total_score


# ============================================================
# 搜索补全 API
# ============================================================
@sch.route('/suggest')
def suggest():
    q = request.args.get('q', '').strip()

    # ----- 空查询：返回搜索历史（从 session 读取） -----
    if not q:
        history = session.get('search_history', [])
        seen = set()
        unique_history = []
        for item in history:
            if item not in seen:
                seen.add(item)
                unique_history.append(item)
        unique_history = unique_history[:10]
        # 返回对象数组
        return jsonify([{'label': item} for item in unique_history])

    limit = 8

    rp_rows = suggest_names('resourcepacks', f'{q}%', limit)
    sp_rows = suggest_names('shaderpacks', f'{q}%', limit)
    map_rows = suggest_names('maps', f'{q}%', limit)
    user_rows = search_by_nickname(f'{q}%', limit)

    suggestions = []

    for row in rp_rows:
        try:
            content = json.loads(row['content'])
            name = content.get('main_name', '')
            if name:
                suggestions.append({'label': name})
        except:
            pass

    for row in sp_rows:
        try:
            content = json.loads(row['content'])
            name = content.get('main_name', '')
            if name:
                suggestions.append({'label': name})
        except:
            pass

    for row in map_rows:
        try:
            content = json.loads(row['content'])
            name = content.get('main_name', '')
            if name:
                suggestions.append({'label': name})
        except:
            pass

    for row in user_rows:
        suggestions.append({'label': row['nickname']})

    seen = set()
    unique = []
    for s in suggestions:
        if s['label'] not in seen:
            seen.add(s['label'])
            unique.append(s)

    unique = unique[:10]
    return jsonify(unique)


# ============================================================
# 清空搜索历史
# ============================================================
@sch.route('/clear_search_history', methods=['POST'])
def clear_search_history():
    session['search_history'] = []
    return jsonify({'success': True})


# ============================================================
# 搜索页面
# ============================================================
@sch.route('/search')
def search():
    q = request.args.get('q', '').strip()
    resource_type = request.args.get('type', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # ----- 存储搜索历史 -----
    if q:
        history = session.get('search_history', [])
        history = [item for item in history if item != q]
        history.insert(0, q)
        if len(history) > 20:
            history = history[:20]
        session['search_history'] = history

    threshold = request.args.get('threshold', DEFAULT_SIMILARITY_THRESHOLD, type=float)
    fuzzy_weight = request.args.get('fuzzy_weight', DEFAULT_FUZZY_WEIGHT_FACTOR, type=float)
    threshold = max(0.0, min(1.0, threshold))
    fuzzy_weight = max(0.0, min(1.0, fuzzy_weight))

    if not q:
        return render_template(
            'search.html',
            q='',
            results=[],
            total=0,
            type=resource_type,
            page=1,
            total_pages=1,
            threshold=threshold,
            fuzzy_weight=fuzzy_weight
        )

    user_results = []
    resource_results = []

    if resource_type == 'all' or resource_type == 'user':
        like_pattern = f'%{q}%'
        user_rows = search_full_by_nickname(like_pattern)
        for row in user_rows:
            parsed = parse_user(row)
            if parsed:
                user_results.append(parsed)

    tables = []
    for table, type_name in SEARCH_TABLES:
        if resource_type == 'all' or resource_type == type_name:
            tables.append(table)

    for table in tables:
        rows = list_all_for_search(table)
        for row in rows:
            parsed = parse_resource(row, table)
            if parsed:
                resource_results.append(parsed)

    all_results = resource_results + user_results

    scored_items = []
    for item in all_results:
        score = calculate_relevance(item, q, threshold, fuzzy_weight)
        if score > 0:
            item['_score'] = score
            scored_items.append(item)

    scored_items.sort(
        key=lambda x: (-x['_score'], x.get('name', x.get('nickname', '')))
    )

    total = len(scored_items)
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    end = start + per_page
    page_results = scored_items[start:end]

    for item in page_results:
        item.pop('_score', None)

    return render_template(
        'search.html',
        q=q,
        results=page_results,
        total=total,
        type=resource_type,
        page=page,
        total_pages=total_pages,
        threshold=threshold,
        fuzzy_weight=fuzzy_weight
    )