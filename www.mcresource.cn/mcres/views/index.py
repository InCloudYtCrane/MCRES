# views/index.py
import os
import re
import time
import json
import base64
import random
import hashlib
import logging
import threading
from datetime import datetime
from collections import OrderedDict

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from flask import Blueprint, render_template, request, redirect, session, jsonify

from utils import db
from utils.messaging import feed
from utils.site import site_data
from utils.users import permissions
from utils.site import announce as announce_core
from utils.constants import (
    RESOURCE_LABEL, RESOURCE_TABLE,
    TYPE_MAP, TYPE_RESOURCEPACK, TYPE_SHADERPACK,
)
from utils.data.repositories import resources
from utils.data.repositories import reviews as reviews_repo
from utils.data.repositories import site as site_repo
from utils.data.repositories import users as users_repo
from utils.imaging.image_store import get_thumbnail_url
from utils.reviews.review import append_review_history
from .. import log_action, get_real_ip, get_ip_region_city
from .resource_lists import render_resource_list

ix = Blueprint('index', __name__)
logger = logging.getLogger(__name__)

# 站点早期用中文类型名作为持久化标识（push_settings / site_promotions 里
# 存的 `type` 字段就是"资源包""光影包""地图"）。这是历史数据契约，
# 因此必须保留这套映射；但只需一份，用它反查 constants 里的类型键。
_LEGACY_TYPE_NAME_TO_KEY = {
    RESOURCE_LABEL[TYPE_RESOURCEPACK]: TYPE_RESOURCEPACK,
    RESOURCE_LABEL[TYPE_SHADERPACK]: TYPE_SHADERPACK,
    RESOURCE_LABEL[TYPE_MAP]: TYPE_MAP,
}


# ============================================================
# 爱发电配置
# ============================================================
AFDIAN_USER_ID = os.getenv('AFDIAN_USER_ID', '')
AFDIAN_API_TOKEN = os.getenv('AFDIAN_API_TOKEN', '')
AFDIAN_API_BASE = 'https://ifdian.net/api/open'

AFDIAN_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwwdaCg1Bt+UKZKs0R54y
lYnuANma49IpgoOwNmk3a0rhg/PQuhUJ0EOZSowIC44l0K3+fqGns3Ygi4AfmEfS
4EKbdk1ahSxu7Zkp2rHMt+R9GarQFQkwSS/5x1dYiHNVMiR8oIXDgjmvxuNes2Cr
8fw9dEF0xNBKdkKgG2qAawcN1nZrdyaKWtPVT9m2Hl0ddOO9thZmVLFOb9NVzgYf
jEgI+KWX6aY19Ka/ghv/L4t1IXmz9pctablN5S0CRWpJW3Cn0k6zSXgjVdKm4uN7
jRlgSRaf/Ind46vMCm3N2sgwxu/g3bnooW+db0iLo13zzuvyn727Q3UDQ0MmZcEW
MQIDAQAB
-----END PUBLIC KEY-----"""

_RE_AF_ID = re.compile(r'#([A-Za-z0-9_\u4e00-\u9fa5-]{1,30})')
_RE_AF_MSG = re.compile(r'\*([^\n]*)')

EXPENSE_LABELS = {
    'server':  ('🖥️', '服务器租赁'),
    'cdn':     ('🚀', 'CDN 流量'),
    'defense': ('🛡️', '安全防护'),
    'domain':  ('🌐', '域名续费'),
    'ssl':     ('🔒', 'SSL 证书'),
    'other':   ('📦', '其他'),
}


def format_view_count(count):
    """将浏览量格式化为可读形式"""
    if count is None:
        return '0'
    if count < 1000:
        return str(count)
    elif count < 10000:
        return f"{count / 1000:.1f}k"
    elif count < 1000000:
        return f"{count // 1000}k"
    else:
        return f"{count // 1000000}M"


def format_resource_item(row, type_name):
    """将数据库行转换为模板需要的字典，且封面使用缩略图"""
    content = json.loads(row['content'])
    raw_cover = content.get('cover', '')
    cover_thumb = get_thumbnail_url(raw_cover) if raw_cover else ''
    views = row.get('view_count', 0)

    return {
        'name': content.get('main_name', '未命名'),
        'summary': content.get('summary', ''),
        'tag': content.get('category') or content.get('style') or content.get('map_type') or type_name,
        'views': views,
        'views_display': format_view_count(views),
        'cover_url': cover_thumb,
        'detail_url': f"/{type_name}/{row['id']}"
    }


def get_resource_by_type_and_id(resource_type, resource_id):
    """
    根据资源类型和 ID 查询对应的资源表，返回包含名称、封面等信息的字典。
    若不存在，返回 None。

    类型映射改由 constants 的单一来源解析，去掉了原先"三条 if/elif 查表"
    与"第二条 if/elif 映射路由前缀"两段重复。
    """
    if not resource_type or not resource_id:
        return None

    type_key = _LEGACY_TYPE_NAME_TO_KEY.get(resource_type)
    if not type_key:
        return None

    try:
        row = resources.get_for_card(type_key, resource_id)
        if not row:
            return None

        content = json.loads(row['content'])
        raw_cover = content.get('cover', '')
        cover_thumb = get_thumbnail_url(raw_cover) if raw_cover else ''

        return {
            'name': content.get('main_name', '未命名'),
            'summary': content.get('summary', ''),
            'cover_url': cover_thumb,
            'views': row.get('view_count', 0),
            'yesterday_views': row.get('yesterday_view_count', 0),
            'detail_url': f"/{type_key}/{row['id']}"
        }
    except Exception:
        return None


# ============================================================
# 【Phase R】site_promotions 读取辅助
# ============================================================
def _load_promotions(promo_type):
    """从 site_promotions 读一个类型的完整列表（按 sort_order 排序）"""
    try:
        rows = site_repo.list_promotions(promo_type)
    except Exception:
        return []

    result = []
    for r in rows:
        raw = r.get('item_json')
        if isinstance(raw, str):
            try:
                result.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                continue
        elif isinstance(raw, dict):
            result.append(raw)

    return result


def get_push_config():
    """
    从 push_settings 表读取配置。

    【Phase R】carousel / hot / latest 改从 site_promotions 表读。
    【Phase P】announce 从 site_announcements 表读。
    hotAutoUpdate / latestAutoUpdate 仍从 push_settings 读（布尔开关）。
    """
    # ---------- 开关读 push_settings ----------
    row = site_repo.get_push_flags()
    if not row:
        site_repo.ensure_push_settings_row()
        row = site_repo.get_push_flags()

    # ---------- carousel / hot / latest 读 site_promotions ----------
    carousel_list = _load_promotions('carousel')
    hot_list      = _load_promotions('hot')
    latest_list   = _load_promotions('latest')

    config = {
        'carousel': carousel_list,
        'hot': hot_list,
        'latest': latest_list,
        'announce': announce_core.get_active_announcements(),
        'hotAutoUpdate': bool(row['hotAutoUpdate']) if row else False,
        'latestAutoUpdate': bool(row['latestAutoUpdate']) if row else False
    }
    return config


def get_resource_groups(resource_type, group_key, limit_per_group=10):
    """
    通用函数：按分组键分组并随机抽样

    resource_type: 'resourcepack' / 'shaderpack' / 'map'（表名由 constants 解析）
    group_key:     'category' / 'style' / 'map_type'
    """
    rows = resources.list_for_cards(resource_type)
    groups = {}
    for row in rows:
        try:
            content = json.loads(row['content'])
        except:
            continue
        key = content.get(group_key, '未分类')
        if key not in groups:
            groups[key] = []
        groups[key].append(row)

    result = {}
    for key, items in groups.items():
        if len(items) > limit_per_group:
            items = random.sample(items, limit_per_group)
        result[key] = [format_resource_item(item, resource_type) for item in items]
    return result


def get_algorithm_hot(limit=6):
    """
    算法推荐热门：
    1. 从三张表分别查询昨日浏览量 > 0 的记录，按昨日浏览量降序，各取前 n 条
    2. 合并后取总前 n 条
    3. 从中随机抽取 limit 条返回
    """
    all_rows = []
    for type_key, table in RESOURCE_TABLE.items():
        type_label = RESOURCE_LABEL[type_key]
        rows = resources.list_hot_candidates(type_key)
        for row in rows:
            try:
                content = json.loads(row['content'])
                raw_cover = content.get('cover', '')
                cover_thumb = get_thumbnail_url(raw_cover) if raw_cover else ''
                all_rows.append({
                    'name': content.get('main_name', '未命名'),
                    'summary': content.get('summary', ''),
                    'cover_url': cover_thumb,
                    'views': row.get('view_count', 0),
                    'yesterday_views': row.get('yesterday_view_count', 0),
                    'tag': type_label,
                    'detail_url': f"/{type_key}/{row['id']}"
                })
            except:
                continue

    all_rows.sort(key=lambda x: x['yesterday_views'], reverse=True)
    top_100 = all_rows[:100]

    if len(top_100) <= limit:
        sampled = top_100
    else:
        sampled = random.sample(top_100, limit)

    return [{
        'name': item['name'],
        'summary': item['summary'],
        'cover_url': item['cover_url'],
        'views': item['views'],
        'views_display': format_view_count(item['views']),
        'tag': item['tag'],
        'detail_url': item['detail_url']
    } for item in sampled]


def get_algorithm_latest(limit=6):
    """
    算法推荐最新：
    1. 从三张表分别查询 date_added 不为空的记录，按 date_added 降序，各取前 100 条
    2. 合并后取总前 100 条
    3. 从中随机抽取 limit 条返回
    """
    all_rows = []
    for type_key, table in RESOURCE_TABLE.items():
        type_label = RESOURCE_LABEL[type_key]
        rows = resources.list_latest_candidates(type_key)
        for row in rows:
            try:
                content = json.loads(row['content'])
                raw_cover = content.get('cover', '')
                cover_thumb = get_thumbnail_url(raw_cover) if raw_cover else ''
                all_rows.append({
                    'name': content.get('main_name', '未命名'),
                    'summary': content.get('summary', ''),
                    'cover_url': cover_thumb,
                    'views': row.get('view_count', 0),
                    'date_added': row.get('date_added', ''),
                    'tag': type_label,
                    'detail_url': f"/{type_key}/{row['id']}"
                })
            except:
                continue

    all_rows.sort(key=lambda x: x['date_added'], reverse=True)
    top_100 = all_rows[:100]

    if len(top_100) <= limit:
        sampled = top_100
    else:
        sampled = random.sample(top_100, limit)

    return [{
        'name': item['name'],
        'summary': item['summary'],
        'cover_url': item['cover_url'],
        'views': item['views'],
        'views_display': format_view_count(item['views']),
        'tag': item['tag'],
        'detail_url': item['detail_url']
    } for item in sampled]


# 首页
@ix.route('/')
def index():
    config = get_push_config()
    posters = config['carousel']

    hot_resources = []
    if config.get('hotAutoUpdate', False):
        hot_resources = get_algorithm_hot(6)
    else:
        hot_items = config.get('hot', [])
        for item in hot_items:
            resource = get_resource_by_type_and_id(item.get('type'), item.get('resourceId'))
            if resource:
                hot_resources.append({
                    'name': resource['name'],
                    'summary': resource.get('summary', ''),
                    'cover_url': resource['cover_url'],
                    'views': resource.get('views', 0),
                    'views_display': format_view_count(resource.get('views', 0)),
                    'tag': item.get('type', '其他'),
                    'detail_url': resource.get('detail_url', '#')
                })
        hot_resources.sort(key=lambda x: x.get('views', 0), reverse=True)

    latest_resources = []
    if config.get('latestAutoUpdate', False):
        latest_resources = get_algorithm_latest(6)
    else:
        latest_items = config.get('latest', [])
        for item in latest_items:
            resource = get_resource_by_type_and_id(item.get('type'), item.get('resourceId'))
            if resource:
                latest_resources.append({
                    'name': resource['name'],
                    'summary': resource.get('summary', ''),
                    'cover_url': resource['cover_url'],
                    'views': resource.get('views', 0),
                    'views_display': format_view_count(resource.get('views', 0)),
                    'tag': item.get('type', '其他'),
                    'detail_url': resource.get('detail_url', '#')
                })

    rp_groups = get_resource_groups(TYPE_RESOURCEPACK, 'category')
    sp_groups = get_resource_groups(TYPE_SHADERPACK, 'style')
    map_groups = get_resource_groups(TYPE_MAP, 'map_type')

    # 随机打乱大类顺序（仅移动端使用，但桌面端也生效无影响）
    def shuffle_dict_items(d):
        items = list(d.items())
        random.shuffle(items)
        return OrderedDict(items)

    rp_groups = shuffle_dict_items(rp_groups)
    sp_groups = shuffle_dict_items(sp_groups)
    map_groups = shuffle_dict_items(map_groups)

    resource_packs_total = sum(len(v) for v in rp_groups.values())
    shader_packs_total = sum(len(v) for v in sp_groups.values())
    maps_total = sum(len(v) for v in map_groups.values())

    announcements = config['announce']

    activities_raw = feed.get_feed(100)
    activities = []
    if activities_raw:
        user_ids = [item['user_id'] for item in activities_raw if 'user_id' in item]
        user_map = {}
        if user_ids:
            user_map = users_repo.get_nicknames(user_ids)
        for item in activities_raw:
            uid = item.get('user_id')
            nickname = user_map.get(uid, '未知用户')
            activities.append({
                'user_id': uid,
                'user': nickname,
                'action': item.get('action', ''),
                'target': item.get('target', ''),
                'time': item.get('time', '')
            })

    # ===== 获取用户 IP 属地（省 市）=====
    user_city = '未知'
    try:
        real_ip = get_real_ip()
        if real_ip and real_ip not in ('127.0.0.1', '::1'):
            user_city = get_ip_region_city(real_ip)
    except Exception:
        pass

    data = {
        'posters': posters,
        'hot_resources': hot_resources,
        'latest_resources': latest_resources,
        'resource_packs': rp_groups,
        'shader_packs': sp_groups,
        'maps': map_groups,
        'random_saying': site_data.random_quote(),
        'resource_packs_total': resource_packs_total,
        'shader_packs_total': shader_packs_total,
        'maps_total': maps_total,
        'activities': activities,
        'announcements': announcements,
        'user_city': user_city,
    }

    # ---------- 设备检测 ----------
    ua = request.headers.get('User-Agent', '').lower()
    mobile_keywords = ['android', 'iphone', 'ipad', 'ipod', 'mobile', 'windows phone']
    is_mobile = any(keyword in ua for keyword in mobile_keywords)
    if 'ipad' in ua:
        is_mobile = False

    if is_mobile:
        return render_template('index/index_mobile.html', **data)

    return render_template('index/index.html', **data)


@ix.route('/about')
def about():
    return redirect('https://help.mcresource.cn/100-%E5%85%B3%E4%BA%8E')


@ix.route('/development')
def changelog():
    return render_template('index/changelog.html', data=site_data.changelog())


@ix.route('/resourcepacks')
def resourcepacks_list():
    """资源包列表。实现见 mcres/views/resource_lists.py（三条列表路由共用）。"""
    return render_resource_list('resourcepack')


@ix.route('/shaderpacks')
def shaderpacks_list():
    """光影包列表。实现见 mcres/views/resource_lists.py。"""
    return render_resource_list('shaderpack')


@ix.route('/maps')
def maps_list():
    """地图列表。实现见 mcres/views/resource_lists.py。"""
    return render_resource_list('map')


@ix.route('/review')
def review():
    type_ = request.args.get('type')
    if not type_:
        return redirect('/review?type=resourcepack')

    resource_name = request.args.get('resource_name', '').strip()
    resource_id = request.args.get('resource_id', type=int)
    operation_type = request.args.get('operation_type', 'all')
    sort = request.args.get('sort', 'time_desc')

    initial_uid = request.args.get('uid', type=int)
    status_str = request.args.get('status', 'pending')
    mode = request.args.get('mode', 'count')
    if mode not in ['count', 'date']:
        mode = 'count'

    limit = request.args.get('limit', default=50, type=int)
    if limit not in [50, 100, 200, 500, 1000]:
        limit = 50

    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1

    if not status_str:
        status_str = 'pending'
    status_list = [s.strip() for s in status_str.split(',') if s.strip()]

    if type_ == 'resourcepack':
        tables = ['resourcepack_review']
        id_field = 'resourcepack_id'
    elif type_ == 'shaderpack':
        tables = ['shaderpack_review', 'shaderpack_preset_review']
        id_field = 'shaderpack_id'
    elif type_ == 'map':
        tables = ['map_review']
        id_field = 'map_id'
    else:
        return redirect('/review?type=resourcepack')

    where_clauses = []
    params = []

    if status_list:
        placeholders = ','.join(['%s'] * len(status_list))
        where_clauses.append(f"status IN ({placeholders})")
        params.extend(status_list)

    if initial_uid:
        where_clauses.append("submitter = %s")
        params.append(initial_uid)

    if operation_type != 'all':
        where_clauses.append("operation = %s")
        params.append(operation_type)

    if mode == 'date':
        if start_date:
            where_clauses.append("submit_time >= %s")
            params.append(start_date + ' 00:00:00')
        if end_date:
            where_clauses.append("submit_time <= %s")
            params.append(end_date + ' 23:59:59')

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    all_raw = []
    for table in tables:
        if mode == 'count':
            id_rows = reviews_repo.list_ids(table, where_sql, params, limit)
            ids = [r['id'] for r in id_rows]
            if ids:
                rows = reviews_repo.list_rows_by_ids(table, ids)
            else:
                rows = []
        else:
            rows = reviews_repo.list_rows(table, where_sql, params)
        for item in rows:
            item['_table'] = table
            all_raw.append(item)

    filtered_all = []
    for item in all_raw:
        if item['_table'] == 'shaderpack_preset_review':
            res_id = item.get('shaderpack_id')
        else:
            res_id = item.get(id_field)

        if resource_id and res_id != resource_id:
            continue

        if resource_name:
            content = json.loads(item['content'])
            if item['_table'] == 'shaderpack_preset_review':
                name = content.get('name', '')
                shader_id = item.get('shaderpack_id')
                # 兜底文案与渲染处不同（这里是 ''），用 or 一次覆盖三种状态
                shader_name = (shader_main_map.get(shader_id) or '') if shader_id else ''
                full_name = f"{name} {shader_name}".strip()
            else:
                main_name = content.get('main_name', '')
                sub_name = content.get('sub_name', '')
                full_name = f"{main_name} {sub_name}".strip()
            if resource_name.lower() not in full_name.lower():
                continue
        filtered_all.append(item)

    if sort == 'time_asc':
        filtered_all.sort(key=lambda x: str(x['submit_time']))
    elif sort == 'status':
        status_order = {'pending': 0, 'passed': 1, 'rejected': 2, 'withdrawn': 3}
        filtered_all.sort(key=lambda x: status_order.get(x['status'], 99))
    else:
        filtered_all.sort(key=lambda x: str(x['submit_time']), reverse=True)

    per_page = limit if mode == 'count' else 50
    total_filtered = len(filtered_all)
    total_pages = (total_filtered + per_page - 1) // per_page if total_filtered > 0 else 1
    if page > total_pages:
        page = total_pages
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_filtered)
    page_items = filtered_all[start_idx:end_idx]

    pending_records = [r for r in filtered_all if r['status'] == 'pending']
    pending_records.sort(key=lambda x: str(x['submit_time']))
    pending_order_map = {}
    for idx, r in enumerate(pending_records, start=1):
        pending_order_map[r['id']] = idx

    all_user_ids = set()
    for item in page_items:
        all_user_ids.add(item['submitter'])
        if item.get('review'):
            try:
                raw_review = item['review']
                if isinstance(raw_review, str):
                    history_data = json.loads(raw_review)
                else:
                    history_data = raw_review
                if isinstance(history_data, list):
                    for entry in history_data:
                        if entry.get('user'):
                            all_user_ids.add(entry['user'])
                elif isinstance(history_data, dict):
                    if history_data.get('reviewer'):
                        all_user_ids.add(history_data['reviewer'])
            except:
                pass

    user_nick_map = {}
    user_avatar_map = {}
    if all_user_ids:
        user_nick_map = users_repo.get_nicknames(list(all_user_ids))
        # 头像也一次取回：原实现是在下面每行一次 get_avatar_row，
        # 每页 50 行就是 50 次数据库往返（B 批 N+1）
        user_avatar_map = users_repo.get_avatars(list(all_user_ids))

    # 预设审核要显示宿主光影包名。原实现在筛选循环和渲染循环里各查一次
    # （同一个 id 最多查两轮），这里一次性建映射。
    #
    # 值的三种状态必须区分，才能逐字保留两个调用点不同的兜底文案：
    #   键不存在        → 光影包行不存在      → 两处都取 ''
    #   值为 None       → 行在、但取不到名字  → 渲染处取 '光影包#<id>'
    #   值为字符串(可空) → 正常名字            → 渲染处原样使用（可能是 ''）
    shader_main_map = {}
    preset_ids = {
        it.get('shaderpack_id') for it in all_raw
        if it['_table'] == 'shaderpack_preset_review' and it.get('shaderpack_id')
    }
    if preset_ids:
        for _row in resources.list_rows_by_ids(
                'shaderpack', list(preset_ids), order_by='id'):
            try:
                _parsed = json.loads(_row['content'])
            except Exception:
                _parsed = None
            shader_main_map[_row['id']] = (
                _parsed.get('main_name') if isinstance(_parsed, dict) else None)

    review_list = []
    for item in page_items:
        content = json.loads(item['content'])
        review_history = []
        reviewer_id = None
        note = None
        latest_review_time = None

        if item.get('review'):
            try:
                raw_review = item['review']
                if isinstance(raw_review, str):
                    history_data = json.loads(raw_review)
                else:
                    history_data = raw_review

                if isinstance(history_data, list):
                    review_history = history_data
                    if review_history:
                        latest = review_history[-1]
                        reviewer_id = latest.get('user')
                        note = latest.get('note')
                        latest_review_time = latest.get('time')
                elif isinstance(history_data, dict):
                    reviewer_id = history_data.get('reviewer')
                    note = history_data.get('note')
                    latest_review_time = history_data.get('latest_review')
                    review_history = [{
                        'action': item.get('status', 'pending'),
                        'user': reviewer_id,
                        'time': latest_review_time,
                        'note': note
                    }]
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                print(f"解析 review 字段失败 (id={item.get('id')}): {e}")

        safe_history = []
        for entry in review_history:
            if not isinstance(entry, dict):
                continue
            user_id = entry.get('user')
            safe_history.append({
                'action': entry.get('action'),
                'user': user_id,
                'user_nick': user_nick_map.get(user_id, f'用户#{user_id}') if user_id else '未知用户',
                'time': entry.get('time'),
                'note': entry.get('note')
            })

        reviewer_nick = user_nick_map.get(reviewer_id) if reviewer_id else None

        is_preset = (item['_table'] == 'shaderpack_preset_review')

        if is_preset:
            preset_name = content.get('name', '未命名预设')
            shaderpack_id = item.get('shaderpack_id')
            # 与筛选处共用同一张映射；三种状态的处理见上面建映射时的注释
            if shaderpack_id in shader_main_map:
                shader_name = shader_main_map[shaderpack_id]
                if shader_name is None:
                    shader_name = f'光影包#{shaderpack_id}'
            else:
                shader_name = ''
            resource_name_display = f'预设「{preset_name}」（{shader_name}）'
            operation_display = '添加' if item.get('operation') == 'add' else '编辑'
        else:
            abbr = content.get('abbr', '')
            main_name = content.get('main_name', '')
            sub_name = content.get('sub_name', '')
            resource_name_display = ''
            if abbr:
                resource_name_display = f'[{abbr}]'
            resource_name_display = resource_name_display + main_name
            if sub_name:
                resource_name_display = resource_name_display + f'({sub_name})'
            operation_display = {
                'add': '添加',
                'edit': '编辑'
            }.get(item.get('operation'), item.get('operation', '操作了'))

        if '添加' in operation_display:
            operation_type_label = 'add'
        else:
            operation_type_label = 'edit'

        submitter_nick = user_nick_map.get(item['submitter'], '未知用户')
        submitter_avatar = (user_avatar_map.get(item['submitter'])
                            if item['submitter'] else None)

        queue_order = pending_order_map.get(item['id']) if item['status'] == 'pending' else None

        review_list.append({
            'id': item['id'],
            'submitter_id': item['submitter'],
            'submitter': submitter_nick,
            'submitter_avatar': submitter_avatar,
            'reviewer_id': reviewer_id,
            'reviewer': reviewer_nick,
            'operation': operation_display,
            'operation_type': operation_type_label,
            'resource_name': resource_name_display,
            'submit_time': item['submit_time'],
            'status': item['status'],
            'note': note,
            'latest_review': latest_review_time,
            'is_preset': is_preset,
            'shaderpack_id': item.get('shaderpack_id') if is_preset else None,
            'queue_order': queue_order,
            'review_history': safe_history,
        })

    stats = {'pending': 0, 'passed': 0, 'rejected': 0, 'withdrawn': 0}
    for item in filtered_all:
        stats[item['status']] = stats.get(item['status'], 0) + 1

    pending_count = reviews_repo.count_pending_map()

    type_label_map = {
        'resourcepack': '资源包',
        'shaderpack': '光影包',
        'map': '地图'
    }
    type_label = type_label_map.get(type_, '资源包')

    pagination = {
        'page': page,
        'total_pages': total_pages,
        'total_items': total_filtered,
        'limit': per_page
    }

    filter_params = {
        'mode': mode,
        'limit': limit,
        'status': status_str,
        'uid': initial_uid,
        'resource_name': resource_name,
        'resource_id': resource_id,
        'operation_type': operation_type,
        'sort': sort,
        'start_date': start_date,
        'end_date': end_date,
        'page': page
    }

    return render_template(
        'index/review_list.html',
        audit_list=review_list,
        type=type_,
        type_label=type_label,
        pending_count=pending_count,
        stats=stats,
        filter=filter_params,
        pagination=pagination,
        initial_uid=initial_uid
    )


@ix.route('/review/recall', methods=['POST'])
def recall_review():
    """撤回待审核条目：状态改为 withdrawn，同时追加 withdraw 记录到 review 历史"""
    if 'user_info' not in session:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    user_id = session['user_info']['id']

    table = request.form.get('table')
    review_id = request.form.get('id', type=int)

    if not table or not review_id:
        return jsonify({'success': False, 'message': '参数缺失'}), 400

    allowed_tables = {
        'resourcepack_review': 'resourcepack',
        'shaderpack_review': 'shaderpack',
        'shaderpack_preset_review': 'shaderpack',
        'map_review': 'map'
    }
    if table not in allowed_tables:
        return jsonify({'success': False, 'message': '无效的审核表'}), 400

    row = reviews_repo.get_by_id(table, review_id)
    if not row:
        return jsonify({'success': False, 'message': '审核记录不存在'}), 404

    if row['submitter'] != user_id:
        return jsonify({'success': False, 'message': '您只能撤回自己提交的条目'}), 403

    if row['status'] != 'pending':
        return jsonify({'success': False, 'message': '当前状态不可撤回'}), 400

    content = row.get('content')
    try:
        content_dict = json.loads(content) if content else {}
    except:
        content_dict = {}

    review_json = append_review_history(
        review_data=row.get('review'),
        action='withdrawn',
        user=user_id,
        note=None,
        content=content_dict
    )

    reviews_repo.update_status(table, review_id, 'withdrawn', review_json)

    log_action(
        user_id=user_id,
        action='recall_review',
        level='INFO',
        target_type=allowed_tables[table],
        target_id=row.get('shaderpack_id') or row.get('resourcepack_id') or row.get('map_id') or 0,
        request_data={'review_id': review_id, 'table': table}
    )

    return jsonify({'success': True, 'message': '已撤回'})


# ============================================================
# 爱发电工具函数
# ============================================================
def _af_verify_sign(order, sign_b64):
    """验证爱发电 Webhook 签名"""
    if not sign_b64:
        return False
    sign_str = (
        str(order.get('out_trade_no', '')) +
        str(order.get('user_id', '')) +
        str(order.get('plan_id', '')) +
        str(order.get('total_amount', ''))
    )
    try:
        pk = serialization.load_pem_public_key(AFDIAN_PUBLIC_KEY.encode())
        pk.verify(
            base64.b64decode(sign_b64),
            sign_str.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception as e:
        logger.warning(f'[afdian] 验签失败: {e}')
        return False


def _af_api_sign(params_json, ts):
    """生成爱发电 API 调用签名：sign = md5(token + params + ts + user_id)"""
    raw = f'{AFDIAN_API_TOKEN}params{params_json}ts{ts}user_id{AFDIAN_USER_ID}'
    return hashlib.md5(raw.encode()).hexdigest()


def _af_call_api(endpoint, params_dict):
    """通用爱发电 API 调用"""
    if not AFDIAN_USER_ID or not AFDIAN_API_TOKEN:
        raise RuntimeError('爱发电 API 未配置')
    params_json = json.dumps(params_dict, ensure_ascii=False, separators=(',', ':'))
    ts = int(time.time())
    sign = _af_api_sign(params_json, ts)
    payload = {
        'user_id': AFDIAN_USER_ID,
        'params': params_json,
        'ts': ts,
        'sign': sign,
    }
    r = requests.post(f'{AFDIAN_API_BASE}/{endpoint}', json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def _af_query_order(out_trade_no):
    """按订单号查询（用于 Webhook 二次验证）"""
    data = _af_call_api('query-order', {'out_trade_no': out_trade_no})
    if data.get('ec') != 200:
        return None
    orders = data.get('data', {}).get('list', [])
    return orders[0] if orders else None


def _af_parse_remark(remark):
    """解析留言：#站内ID 换行 *捎话"""
    if not remark:
        return None, None
    m_id = _RE_AF_ID.search(remark)
    m_msg = _RE_AF_MSG.search(remark)
    return (
        m_id.group(1) if m_id else None,
        m_msg.group(1).strip() if m_msg else None
    )


def _af_clean_remark(remark):
    """
    清洗留言，去掉 #ID 和 * 标记，返回纯正文。
    例：
        '#1 *希望工坊越来越好~'  → '希望工坊越来越好~'
        '#Steve 加油'            → '加油'
        '随便写写 *测试'          → '随便写写 测试'
        '方块工坊越办越好！'      → '方块工坊越办越好！'
    """
    if not remark:
        return ''
    cleaned = _RE_AF_ID.sub('', remark)         # 删掉 #ID
    cleaned = _RE_AF_MSG.sub(r'\1', cleaned)     # 删掉 * 但保留后面的内容
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _af_resolve_nickname(site_id):
    """根据站内 ID 查昵称和头像，查不到返回 ('爱心人士', None)"""
    if not site_id:
        return '爱心人士', None
    row = None
    if site_id.isdigit():
        row = site_repo.find_user_by_site_id(site_id)
    if not row:
        row = site_repo.find_user_by_nickname(site_id)
    if row:
        return row['nickname'], row.get('avatar')
    return '爱心人士', None


def _af_month_income(month_str):
    """月收入（month_str 格式 '2026-10'）"""
    row = site_repo.month_income(month_str)
    return float(row['total']) if row else 0.0


def _af_month_expense(month_str):
    """月支出"""
    row = site_repo.month_expense(month_str)
    return float(row['total']) if row else 0.0


def _af_expense_by_category(month_str):
    """按月按类别汇总支出"""
    return site_repo.expense_by_category(month_str)


def _af_list_income(page=1, per_page=20, month=None):
    """收入列表（分页，可按月筛选）"""
    offset = (page - 1) * per_page

    where = 'WHERE status=2'
    args = []
    if month:
        where += " AND DATE_FORMAT(paid_at, '%%Y-%%m') = %s"
        args.append(month)

    rows = site_repo.income_rows(where, args, per_page, offset)

    for r in rows:
        r['display_remark'] = r.get('parsed_message') or _af_clean_remark(r.get('remark'))

    count_where = 'WHERE status=2'
    count_args = []
    if month:
        count_where += " AND DATE_FORMAT(paid_at, '%%Y-%%m') = %s"
        count_args.append(month)

    tr = site_repo.income_count(count_where, count_args)
    total = int(tr['cnt']) if tr else 0
    pages = max(1, (total + per_page - 1) // per_page)
    return rows, total, pages


def _af_list_expense(page=1, per_page=20, month=None):
    """支出列表（分页，可按月筛选）"""
    offset = (page - 1) * per_page
    where = 'WHERE 1=1'
    args = []
    if month:
        where += ' AND expense_month = %s'
        args.append(month)
    rows = site_repo.expense_rows(where, args, per_page, offset)
    count_args = []
    count_where = 'WHERE 1=1'
    if month:
        count_where += ' AND expense_month = %s'
        count_args.append(month)
    tr = site_repo.expense_count(count_where, count_args)
    total = int(tr['cnt']) if tr else 0
    pages = max(1, (total + per_page - 1) // per_page)
    return rows, total, pages


# ============================================================
# 勉励工坊
# ============================================================
@ix.route('/support')
def support_page():
    now = datetime.now()
    now_month = now.strftime('%Y-%m')

    # ---------- 解析 ?month=YYYY-MM ----------
    month_param = (request.args.get('month') or '').strip()
    if re.match(r'^\d{4}-\d{2}$', month_param):
        try:
            datetime.strptime(month_param, '%Y-%m')
            current_month = month_param
        except ValueError:
            current_month = now_month
    else:
        current_month = now_month

    # ---------- 收支快照 ----------
    income = _af_month_income(current_month)
    expense = _af_month_expense(current_month)
    balance = income - expense

    # ---------- 收款去向 ----------
    raw = _af_expense_by_category(current_month)
    total_expense = sum(float(r['amount']) for r in raw) or 1
    allocations = []
    for r in raw:
        cat = r['category']
        icon, label = EXPENSE_LABELS.get(cat, ('📦', r['item_name']))
        amount = float(r['amount'])
        allocations.append({
            'icon': icon,
            'label': r['item_name'] or label,
            'amount': amount,
            'percent': round(amount / total_expense * 100, 1),
        })

    # ---------- 收入列表（按所选月份筛选） ----------
    income_page = max(1, int(request.args.get('income_page', 1)))
    income_rows, income_total, income_pages = _af_list_income(
        income_page, 20, month=current_month
    )

    # ---------- 支出列表（按所选月份筛选） ----------
    expense_page = max(1, int(request.args.get('expense_page', 1)))
    expense_rows, expense_total, expense_pages = _af_list_expense(
        expense_page, 20, month=current_month
    )

    # ---------- 可选月份列表（从项目起点到现在） ----------
    START_YEAR = 2026
    START_MONTH = 7

    available_months = []
    y, m = now.year, now.month
    while (y, m) >= (START_YEAR, START_MONTH):
        available_months.append(f'{y:04d}-{m:02d}')
        m -= 1
        if m <= 0:
            m = 12
            y -= 1

    return render_template(
        'index/support.html',
        current_month=current_month,
        now_month=now_month,
        available_months=available_months,
        update_date=now.strftime('%Y-%m-%d'),
        income=income,
        expense=expense,
        balance=balance,
        allocations=allocations,
        income_rows=income_rows,
        income_page=income_page,
        income_total_pages=income_pages,
        income_total=income_total,
        expense_rows=expense_rows,
        expense_page=expense_page,
        expense_total_pages=expense_pages,
        expense_total=expense_total,
    )


# ============================================================
# 爱发电 Webhook
# ============================================================
@ix.route('/webhook/afdian', methods=['POST'])
def afdian_webhook():
    data = request.get_json(silent=True) or {}
    order = (data.get('data') or {}).get('order') or {}
    sign = (data.get('data') or {}).get('sign') or ''

    if not order or not order.get('out_trade_no'):
        return jsonify({'ec': 400, 'em': 'missing order'}), 400

    # ---------- 1. 验签 ----------
    if not _af_verify_sign(order, sign):
        logger.warning(f'[webhook] 验签失败: {order.get("out_trade_no")}')
        return jsonify({'ec': 400, 'em': 'sign invalid'}), 400

    out_trade_no = order['out_trade_no']

    # ---------- 2. 幂等检查 ----------
    if site_repo.order_exists(out_trade_no):
        return jsonify({'ec': 200, 'em': ''})

    # ---------- 3. 调 API 二次验证 ----------
    api_order = None
    try:
        api_order = _af_query_order(out_trade_no)
    except Exception as e:
        logger.error(f'[webhook] API 查询失败: {out_trade_no} - {e}')

    final = api_order or order
    status = int(final.get('status', 0))
    total_amount = float(final.get('total_amount', 0))

    if status != 2:
        return jsonify({'ec': 200, 'em': ''})

    # ---------- 4. 解析留言 ----------
    remark = final.get('remark') or ''
    site_id, message = _af_parse_remark(remark)
    nickname, avatar = _af_resolve_nickname(site_id)
    paid_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # ---------- 5. 入库 ----------
    site_repo.insert_order(
        out_trade_no,
        final.get('user_id', ''),
        final.get('plan_id', ''),
        int(final.get('month', 1) or 1),
        total_amount,
        float(final.get('show_amount', 0) or 0),
        status,
        remark,
        None,
        site_id,
        message,
        nickname,
        avatar,
        1,
        1 if api_order else 0,
        paid_at,
    )

    logger.info(f'[webhook] 入库成功: {out_trade_no} / ¥{total_amount} / {nickname}')

    # ---------- 6. 授予隐藏成就「为爱发电」 ----------
    if site_id and nickname != '爱心人士':
        try:
            from utils.achievements import grant_achievement_manually

            user_row = None
            if site_id.isdigit():
                user_row = users_repo.find_id_by_id(int(site_id))
            if not user_row:
                user_row = site_repo.find_user_id_by_nickname(site_id)

            if user_row:
                ok, msg = grant_achievement_manually(user_row['id'], 'supporter')
                if ok:
                    logger.info(f'[webhook] 授予隐藏成就 supporter: user={user_row["id"]}')
                else:
                    logger.info(f'[webhook] 成就已存在，跳过: {msg}')
        except Exception as e:
            logger.exception(f'[webhook] 授予隐藏成就失败: {e}')

    # ---------- 7. 异步生成 AI 回复（不阻塞 webhook） ----------
    if remark and remark.strip():
        _clean_remark_for_ai = _af_clean_remark(remark)

        def _async_reply(_out_trade_no, _remark_text, _nickname, _amount):
            try:
                from utils.finance.afdian_reply import generate_reply
                reply_text = generate_reply(_remark_text, _nickname, _amount)
                if reply_text:
                    site_repo.set_order_reply(_out_trade_no, reply_text)
                    logger.info(f'[webhook] AI 回复已写入: {_out_trade_no} → {reply_text}')
                else:
                    logger.info(f'[webhook] AI 回复为空，跳过: {_out_trade_no}')
            except Exception as e:
                logger.exception(f'[webhook] AI 回复失败: {_out_trade_no} - {e}')

        threading.Thread(
            target=_async_reply,
            args=(out_trade_no, _clean_remark_for_ai, nickname, total_amount),
            daemon=True,
        ).start()

    return jsonify({'ec': 200, 'em': ''})