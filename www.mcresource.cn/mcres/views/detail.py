# 【主站】mcres/views/detail.py
# 位置：mcres/views/detail.py
import hashlib
from flask import Blueprint, render_template, abort, request, jsonify, session

from utils.constants import is_valid_resource_type
from utils.data.repositories import resources
from utils.data.repositories import users as users_repo
from utils.data.repositories.profiles import list_resource_topics

from utils.hot import get_hot_score
from utils.site.anti_fraud import get_anti_fraud_config
from utils.site.security import process_external_links
from utils.users.permissions import login_required
from utils.interaction import (
    _get_resource_counts, _get_user_interaction_status, _get_coins_remaining,
    _get_user_brick, _get_user_coin_count, COIN_DAILY_LIMIT
)
from json import loads
from datetime import datetime, timedelta
import os, json

from ..config import SECRET_KEY

dl = Blueprint('detail', __name__)

# 【Phase 6 · 6.1】与 mcres/audit.py 保持一致：统一用 SECRET_KEY 兜底
SALT = SECRET_KEY or 'mcres-fixed-salt'


# ============================================================
# 茶室话题档位视觉
# ============================================================
_LEVEL_VISUAL = {
    1: {'label': '雅间', 'type': 'yajian'},
    2: {'label': '茶桌', 'type': 'chatai'},
    3: {'label': '散座', 'type': 'sanzuo'},
    4: {'label': '封座', 'type': 'sealed'},
}


# ============================================================
# 原有工具函数（保持不变）
# ============================================================

def get_real_ip():
    real_ip = request.headers.get('CF-Connecting-IP') or request.headers.get('X-Real-IP')
    if not real_ip:
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            real_ip = forwarded.split(',')[-1].strip()
    if not real_ip:
        real_ip = request.remote_addr
    return real_ip

def get_visitor_key():
    user_info = session.get('user_info')
    if user_info and user_info.get('id'):
        return f"user_{user_info['id']}"

    real_ip = get_real_ip()
    user_agent = request.headers.get('User-Agent', '')
    # 【Phase 6 · 6.1】统一 salt 来源，与 audit.py 对齐
    salt = SECRET_KEY or 'mcres-fixed-salt'
    raw_string = f"{real_ip}|{user_agent}|{salt}"
    hashed_key = hashlib.sha256(raw_string.encode()).hexdigest()[:16]
    return f"hash_{hashed_key}"

def should_increment_view(resource_type, resource_id, visitor_key):
    config = get_anti_fraud_config()
    session_minutes = config.get('detail_session_minutes', 5)
    window_minutes = config.get('detail_window_minutes', 60)

    session_key = f'last_view_{resource_type}_{resource_id}'
    last_view_str = session.get(session_key)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if last_view_str:
        try:
            last_time = datetime.strptime(last_view_str, '%Y-%m-%d %H:%M:%S')
            if (datetime.now() - last_time) < timedelta(minutes=session_minutes):
                session[session_key] = now_str
                return False
        except:
            pass

    window_ago = (datetime.now() - timedelta(minutes=window_minutes)).strftime('%Y-%m-%d %H:%M:%S')
    row = resources.find_recent_view(
        resource_type, resource_id, visitor_key, window_ago)

    session[session_key] = now_str
    return row is None

def log_view(resource_type, resource_id, visitor_key):
    resources.insert_view_log(
        resource_type, resource_id, visitor_key,
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

def ensure_today_date(resource_type, resource_id):
    """确保"今日浏览"是今天的；跨天则先归档昨日数据并返回昨日浏览量。

    参数由原先的表名改为资源类型（表名由 constants 解析），
    与 _resolve_view_counts / resources.* 的调用风格一致。
    """
    today = datetime.now().date().isoformat()
    row = resources.get_today_view_state(resource_type, resource_id)
    if not row:
        return 0

    stored_date = row.get('today_date')
    stored_date_str = stored_date.isoformat() if stored_date else None

    if stored_date_str != today:
        resources.roll_over_today_if_stale(resource_type, resource_id, today)
        updated_row = resources.get_yesterday_view_count(resource_type, resource_id)
        return updated_row['yesterday_view_count']

    return row.get('yesterday_view_count', 0)

def enrich_authors(authors):
    if not authors:
        return []

    id_list = []
    for author in authors:
        if isinstance(author, str) and author.startswith('#id='):
            try:
                uid = int(author[4:].strip())
                id_list.append(uid)
            except ValueError:
                pass

    user_map = users_repo.get_nicknames(id_list) if id_list else {}

    enriched = []
    for author in authors:
        if isinstance(author, str) and author.startswith('#id='):
            try:
                uid = int(author[4:].strip())
                nickname = user_map.get(uid)
                if nickname:
                    enriched.append({'display': nickname, 'url': f'/profile/{uid}'})
                else:
                    enriched.append({'display': f'#id={uid}', 'url': None})
            except ValueError:
                enriched.append({'display': author, 'url': None})
        else:
            enriched.append({'display': author, 'url': None})
    return enriched


# ============================================================
# 绑定茶室话题
# ============================================================
def get_bound_tea_topic(resource_type, resource_id):
    """
    查询绑定到该资源的茶室话题，返回话题 dict 或 None。
    """
    if not resource_type or resource_id is None:
        return None

    rows = list_resource_topics()

    try:
        rid_int = int(resource_id)
    except (ValueError, TypeError):
        return None

    for r in rows:
        raw = r.get('link_target')
        try:
            target = json.loads(raw) if isinstance(raw, str) else (raw or {})
            if not isinstance(target, dict):
                continue
            if (target.get('resource_type') == resource_type
                    and int(target.get('resource_id') or 0) == rid_int):

                level = r.get('level') or 3
                is_official = bool(r.get('is_official'))

                visual = _LEVEL_VISUAL.get(level, _LEVEL_VISUAL[3])
                if is_official:
                    visual = {'label': '柜台', 'type': 'counter'}

                return {
                    'id': r['id'],
                    'slug': r['slug'],
                    'name': r['name'],
                    'description': r.get('description') or '',
                    'level': level,
                    'is_official': is_official,
                    'post_count': r.get('post_count') or 0,
                    'follower_count': r.get('follower_count') or 0,
                    'last_post_at': r.get('last_post_at'),
                    'level_visual': visual,
                }
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    return None


# ============================================================
# 路由：资源详情页
# ============================================================

def _resolve_view_counts(resource_type, resource_id, row):
    """详情页的浏览量处理：必要时自增，并返回当前计数。

    原先 `resourcepacks` / `shaderpacks` / `maps` 三个视图各写了一遍逐字相同的
    这段逻辑，只有类型名不同。抽成一处后，任何改动只需改一次。

    返回 (view_count, today_view_count)。
    """
    visitor_key = get_visitor_key()
    if not should_increment_view(resource_type, resource_id, visitor_key):
        return row.get('view_count', 0), row.get('today_view_count', 0)

    resources.increment_view_count(resource_type, resource_id)
    log_view(resource_type, resource_id, visitor_key)
    count_row = resources.get_view_counts(resource_type, resource_id)
    return count_row['view_count'], count_row['today_view_count']


@dl.route('/resourcepack/<int:id>')
def resourcepacks(id):
    row = resources.get_for_detail('resourcepack', id)
    if not row:
        abort(404)

    yesterday_view_count = ensure_today_date('resourcepack', id)
    view_count, today_view_count = _resolve_view_counts('resourcepack', id, row)

    hot_score = get_hot_score('resourcepack', yesterday_view_count)
    data = loads(row['content'])
    data['id'] = id
    data['view_count'] = view_count
    data['today_view_count'] = today_view_count
    data['yesterday_view_count'] = yesterday_view_count
    data['date_added'] = row.get('date_added')
    data['hot_score'] = hot_score

    if 'description' in data and data['description']:
        data['description'] = process_external_links(data['description'])

    texture_data = {}
    if row.get('texture'):
        try:
            texture_data = loads(row['texture'])
        except:
            pass
    data['preview_items'] = texture_data
    data['preview_count'] = len(texture_data)

    file_data = {}
    if row.get('file'):
        try:
            file_data = loads(row['file'])
        except:
            pass
    data['auth_image'] = file_data.get('auth_image')
    data['files'] = file_data.get('files', [])
    data['authors_display'] = enrich_authors(data.get('authors', []))

    data['bound_tea_topic'] = get_bound_tea_topic('resourcepack', id)

    user_id = session.get('user_info', {}).get('id')
    if user_id:
        liked, coined, favorited = _get_user_interaction_status(user_id, 'resourcepack', id)
        coins_remaining = _get_coins_remaining(user_id)
        counts = _get_resource_counts('resourcepack', id)
        brick = _get_user_brick(user_id)
        user_coin_count = _get_user_coin_count(user_id, 'resourcepack', id)
        interaction_data = {
            'likes_count': counts['likes'],
            'coins_count': counts['coins'],
            'favorites_count': counts['favorites'],
            'user_liked': liked,
            'user_coined': coined,
            'user_favorited': favorited,
            'coins_remaining': coins_remaining,
            'brick': brick,
            'user_coin_count': user_coin_count
        }
    else:
        interaction_data = {
            'likes_count': 0,
            'coins_count': 0,
            'favorites_count': 0,
            'user_liked': False,
            'user_coined': False,
            'user_favorited': False,
            'coins_remaining': COIN_DAILY_LIMIT,
            'brick': 0,
            'user_coin_count': 0
        }
    data['interaction'] = interaction_data
    data['type'] = 'resourcepack'

    return render_template('resource/detail/detail_resourcepack.html', resource=data)


@dl.route('/shaderpack/<int:id>')
def shaderpacks(id):
    row = resources.get_for_detail('shaderpack', id)
    if not row:
        abort(404)

    yesterday_view_count = ensure_today_date('shaderpack', id)
    view_count, today_view_count = _resolve_view_counts('shaderpack', id, row)

    hot_score = get_hot_score('shaderpack', yesterday_view_count)
    data = loads(row['content'])
    data['id'] = id
    data['view_count'] = view_count
    data['today_view_count'] = today_view_count
    data['yesterday_view_count'] = yesterday_view_count
    data['date_added'] = row.get('date_added')
    data['hot_score'] = hot_score

    if 'description' in data and data['description']:
        data['description'] = process_external_links(data['description'])

    file_data = {}
    if row.get('file'):
        try:
            file_data = loads(row['file'])
        except:
            file_data = {}
    data['auth_image'] = file_data.get('auth_image')
    data['files'] = file_data.get('files', [])
    data['authors_display'] = enrich_authors(data.get('authors', []))

    data['bound_tea_topic'] = get_bound_tea_topic('shaderpack', id)

    user_id = session.get('user_info', {}).get('id')
    if user_id:
        liked, coined, favorited = _get_user_interaction_status(user_id, 'shaderpack', id)
        coins_remaining = _get_coins_remaining(user_id)
        counts = _get_resource_counts('shaderpack', id)
        brick = _get_user_brick(user_id)
        user_coin_count = _get_user_coin_count(user_id, 'shaderpack', id)
        interaction_data = {
            'likes_count': counts['likes'],
            'coins_count': counts['coins'],
            'favorites_count': counts['favorites'],
            'user_liked': liked,
            'user_coined': coined,
            'user_favorited': favorited,
            'coins_remaining': coins_remaining,
            'brick': brick,
            'user_coin_count': user_coin_count
        }
    else:
        interaction_data = {
            'likes_count': 0,
            'coins_count': 0,
            'favorites_count': 0,
            'user_liked': False,
            'user_coined': False,
            'user_favorited': False,
            'coins_remaining': COIN_DAILY_LIMIT,
            'brick': 0,
            'user_coin_count': 0
        }
    data['interaction'] = interaction_data
    data['type'] = 'shaderpack'

    return render_template('resource/detail/detail_shaderpack.html', shader=data)


@dl.route('/map/<int:id>')
def maps(id):
    row = resources.get_for_detail('map', id)
    if not row:
        abort(404)

    yesterday_view_count = ensure_today_date('map', id)
    view_count, today_view_count = _resolve_view_counts('map', id, row)

    hot_score = get_hot_score('map', yesterday_view_count)
    data = loads(row['content'])
    data['id'] = id
    data['view_count'] = view_count
    data['today_view_count'] = today_view_count
    data['yesterday_view_count'] = yesterday_view_count
    data['date_added'] = row.get('date_added')
    data['hot_score'] = hot_score

    if 'description' in data and data['description']:
        data['description'] = process_external_links(data['description'])

    file_data = {}
    if row.get('file'):
        try:
            file_data = loads(row['file'])
        except:
            file_data = {}
    data['auth_image'] = file_data.get('auth_image')
    data['files'] = file_data.get('files', [])
    data['authors_display'] = enrich_authors(data.get('authors', []))

    data['bound_tea_topic'] = get_bound_tea_topic('map', id)

    user_id = session.get('user_info', {}).get('id')
    if user_id:
        liked, coined, favorited = _get_user_interaction_status(user_id, 'map', id)
        coins_remaining = _get_coins_remaining(user_id)
        counts = _get_resource_counts('map', id)
        brick = _get_user_brick(user_id)
        user_coin_count = _get_user_coin_count(user_id, 'map', id)
        interaction_data = {
            'likes_count': counts['likes'],
            'coins_count': counts['coins'],
            'favorites_count': counts['favorites'],
            'user_liked': liked,
            'user_coined': coined,
            'user_favorited': favorited,
            'coins_remaining': coins_remaining,
            'brick': brick,
            'user_coin_count': user_coin_count
        }
    else:
        interaction_data = {
            'likes_count': 0,
            'coins_count': 0,
            'favorites_count': 0,
            'user_liked': False,
            'user_coined': False,
            'user_favorited': False,
            'coins_remaining': COIN_DAILY_LIMIT,
            'brick': 0,
            'user_coin_count': 0
        }
    data['interaction'] = interaction_data
    data['type'] = 'map'

    return render_template('resource/detail/detail_map.html', map=data)


@dl.route('/pv_trend', methods=['GET'])
def pv_trend():
    """
    获取指定资源的每日 PV 统计 + 全站同类资源每日平均 PV
    参数：type=resourcepack|shaderpack|map, id=资源ID
    返回：{
        "code": 0,
        "data": {
            "resource": [{"date": "2026-09-03", "pv": 12}, ...],
            "site_avg": [{"date": "2026-09-03", "avg": 8.5}, ...]
        }
    }

    【Phase 5】改从 resource_daily_pv 表读取（不再读 daily_pv_stats JSON）。
    """
    res_type = request.args.get('type')
    res_id = request.args.get('id', type=int)

    if not res_type or res_id is None:
        return jsonify({'code': 400, 'message': '缺少参数 type 或 id'}), 400

    if not is_valid_resource_type(res_type):
        return jsonify({'code': 400, 'message': '无效的资源类型'}), 400

    row = resources.find_id(res_type, res_id)
    if not row:
        return jsonify({'code': 404, 'message': '资源不存在'}), 404

    try:
        resource_rows = resources.list_daily_pv(res_type, res_id)
    except Exception:
        resource_rows = []

    resource_data = []
    for r in resource_rows:
        d = r.get('date')
        if hasattr(d, 'isoformat'):
            d_str = d.isoformat()
        else:
            d_str = str(d) if d else ''
        if not d_str:
            continue
        resource_data.append({
            'date': d_str,
            'pv': int(r.get('pv') or 0),
        })

    try:
        avg_rows = resources.list_site_avg_pv(res_type)
    except Exception:
        avg_rows = []

    site_avg_items = []
    for r in avg_rows:
        d = r.get('date')
        if hasattr(d, 'isoformat'):
            d_str = d.isoformat()
        else:
            d_str = str(d) if d else ''
        if not d_str:
            continue
        avg_val = r.get('avg_pv')
        try:
            avg_val = round(float(avg_val), 2) if avg_val is not None else 0
        except (ValueError, TypeError):
            avg_val = 0
        site_avg_items.append({
            'date': d_str,
            'avg': avg_val,
        })

    return jsonify({
        'code': 0,
        'data': {
            'resource': resource_data,
            'site_avg': site_avg_items,
        }
    })