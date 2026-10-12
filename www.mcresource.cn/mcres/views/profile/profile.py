# 【主站】mcres/views/profile/profile.py
# 位置：mcres/views/profile/profile.py
import json
from datetime import datetime, timedelta

from flask import render_template, abort, request, session, jsonify, redirect
from utils import db
from utils.messaging import feed
from utils.time import datetime_fmt
from utils.users import permissions
from utils.constants import resource_table
from utils.data.repositories import profiles as profiles_repo
from ... import log_action
from utils.users.permissions import login_required
from .blueprint import profile_bp
from utils.text.titles import parse_titles, get_selected_title


# ========== 选料用户组映射 ==========
SEL_ROLE_MAP = {
    0: {'name': '未分配', 'color': '#6b7480'},
    1: {'name': '试料员', 'color': '#55d88b'},
    2: {'name': '甄料师', 'color': '#5dade2'},
    3: {'name': '掌料人', 'color': '#b06ad0'},
    4: {'name': '料总管', 'color': '#e67e22'},
}


# ========== 在线状态配置 ==========
ONLINE_THRESHOLD_MIN = 5
RECENT_THRESHOLD_DAYS = 30
ACTION_LOG_RECENT_WINDOW_MIN = 5


# ========== 隐私设置默认值 ==========
_PRIVACY_DEFAULT = {
    'board': True,
    'show_favorites': True,
    'show_achievements': True,
    'search_visible': True,
    'hide_login': False,
    'hide_online_status': False,
}


# ========== 辅助函数 ==========
def get_user_works(user_id):
    tables = [
        ('resourcepacks', 'resourcepack'),
        ('shaderpacks', 'shaderpack'),
        ('maps', 'map')
    ]
    works = {'resourcepack': [], 'shaderpack': [], 'map': []}
    for table, type_name in tables:
        rows = profiles_repo.list_resource_cards(type_name)
        for row in rows:
            try:
                content = json.loads(row['content'])
                authors = content.get('authors', [])
                if any(a == f'#id={user_id}' for a in authors):
                    works[type_name].append({
                        'id': row['id'],
                        'type': type_name,
                        'title': content.get('main_name', '未命名'),
                        'cover': content.get('cover', '/images/cover/default.jpg'),
                        'views': row.get('view_count', 0)
                    })
            except:
                continue
    return works


def get_user_likes(user_id):
    likes = profiles_repo.list_likes(user_id)
    if not likes:
        return {'resourcepack': [], 'shaderpack': [], 'map': []}
    grouped = {'resourcepack': [], 'shaderpack': [], 'map': []}

    # 按类型分组后一次性批量取回（原实现在循环里逐条 get_resource_card）
    ids_by_type = {}
    for like in likes:
        if resource_table(like['resource_type']):
            ids_by_type.setdefault(like['resource_type'], []).append(like['resource_id'])
    cards_by_type = {
        res_type: profiles_repo.get_resource_cards(res_type, ids)
        for res_type, ids in ids_by_type.items()
    }

    for like in likes:
        res_type = like['resource_type']
        res_id = like['resource_id']
        if not resource_table(res_type):
            continue
        row = cards_by_type.get(res_type, {}).get(res_id)
        if row:
            try:
                content = json.loads(row['content'])
                grouped[res_type].append({
                    'id': res_id,
                    'type': res_type,
                    'title': content.get('main_name', '未命名'),
                    'cover': content.get('cover', '/images/cover/default.jpg'),
                    'views': row.get('view_count', 0)
                })
            except:
                continue
    return grouped


def get_user_favorites(user_id):
    """获取用户所有收藏夹及其资源"""
    folders = profiles_repo.list_folders(user_id)
    if not folders:
        profiles_repo.create_default_folder(user_id)
        folders = profiles_repo.list_folders(user_id)

    # 先把各收藏夹的条目取出来，同时收集要查的资源 id。
    # 原实现是「每个条目一次 get_resource_card」（收藏越多查询越多），
    # 现在按资源类型各批量查一次。
    #
    # 注意：**不**把 list_folder_items 合并成一条 IN 查询 —— 那条 SQL 没有
    # ORDER BY，合并后每个收藏夹内的条目顺序不再保证与逐夹查询一致，
    # 而收藏夹页面的展示顺序是用户可见的。收藏夹数量通常是个位数，
    # 这里保留逐夹查询是有意为之。
    items_by_folder = []
    ids_by_type = {}
    for folder in folders:
        fav_items = profiles_repo.list_folder_items(folder['id'])
        items_by_folder.append((folder, fav_items))
        for item in fav_items:
            if resource_table(item['resource_type']):
                ids_by_type.setdefault(item['resource_type'], []).append(
                    item['resource_id'])

    cards_by_type = {
        res_type: profiles_repo.get_resource_cards(res_type, ids)
        for res_type, ids in ids_by_type.items()
    }

    result = []
    for folder, fav_items in items_by_folder:
        folder_resources = []
        for item in fav_items:
            res_type = item['resource_type']
            res_id = item['resource_id']
            if not resource_table(res_type):
                continue
            row = cards_by_type.get(res_type, {}).get(res_id)
            if row:
                try:
                    content = json.loads(row['content'])
                    folder_resources.append({
                        'id': res_id,
                        'type': res_type,
                        'title': content.get('main_name', '未命名'),
                        'cover': content.get('cover', '/images/cover/default.jpg'),
                        'views': row.get('view_count', 0)
                    })
                except:
                    continue
        result.append({
            'id': folder['id'],
            'name': folder['name'],
            'resources': folder_resources
        })
    return result


# ============================================================
# 在线状态
# ============================================================
def _to_dt(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.strptime(v[:19], '%Y-%m-%d %H:%M:%S')
        except Exception:
            return None
    return None


def _fmt_delta(delta):
    secs = int(delta.total_seconds())
    if secs < 0:
        secs = 0
    if secs < 60:
        return '刚刚'
    if secs < 3600:
        return f'{secs // 60} 分钟前'
    if secs < 86400:
        return f'{secs // 3600} 小时前'
    if secs < 86400 * 30:
        return f'{secs // 86400} 天前'
    if secs < 86400 * 365:
        return f'{secs // (86400 * 30)} 个月前'
    return f'{secs // (86400 * 365)} 年前'


def _get_main_last_active(user_id, is_self=False):
    if not user_id:
        return None

    if is_self:
        return datetime.now()

    try:
        window_ago = (
            datetime.now() - timedelta(minutes=ACTION_LOG_RECENT_WINDOW_MIN)
        ).strftime('%Y-%m-%d %H:%M:%S')

        row = profiles_repo.get_last_active_since(user_id, window_ago)
        if row:
            return _to_dt(row.get('created_at'))
    except Exception:
        pass

    try:
        row = profiles_repo.get_last_active(user_id)
        if row:
            return _to_dt(row.get('created_at'))
    except Exception:
        pass

    return None


def get_user_online_status(user_id, tea_last_active=None, is_self=False, hide=False):
    if hide and not is_self:
        return None

    now = datetime.now()
    main_last = _get_main_last_active(user_id, is_self=is_self)
    tea_last = _to_dt(tea_last_active)

    if main_last and tea_last:
        if main_last >= tea_last:
            last_active = main_last
            source = 'main'
        else:
            last_active = tea_last
            source = 'tea'
    elif main_last:
        last_active = main_last
        source = 'main'
    elif tea_last:
        last_active = tea_last
        source = 'tea'
    else:
        return {
            'status': 'offline',
            'label': '离线',
            'color': '#4d4d60',
            'last_active': None,
            'source': None,
        }

    delta = now - last_active
    online_cutoff = timedelta(minutes=ONLINE_THRESHOLD_MIN)
    recent_cutoff = timedelta(days=RECENT_THRESHOLD_DAYS)

    if delta < online_cutoff:
        if source == 'main':
            return {
                'status': 'online',
                'label': '在线',
                'color': '#55d88b',
                'last_active': last_active,
                'source': 'main',
            }
        else:
            return {
                'status': 'tea_online',
                'label': '在茶室',
                'color': '#e8a437',
                'last_active': last_active,
                'source': 'tea',
            }

    if delta < recent_cutoff:
        return {
            'status': 'recent',
            'label': _fmt_delta(delta) + '活跃',
            'color': '#8a929a',
            'last_active': last_active,
            'source': source,
        }

    return {
        'status': 'offline',
        'label': '离线',
        'color': '#4d4d60',
        'last_active': last_active,
        'source': source,
    }


# ============================================================
# 茶室：用户被绑定的话题
# ============================================================
_LEVEL_VISUAL = {
    1: {'label': '雅间', 'type': 'yajian'},
    2: {'label': '茶桌', 'type': 'chatai'},
    3: {'label': '散座', 'type': 'sanzuo'},
    4: {'label': '封座', 'type': 'sealed'},
}


def get_user_bound_tea_topics(user_id):
    rows = profiles_repo.list_creator_topics()

    bound = []
    for r in rows:
        raw = r.get('link_target')
        try:
            target = json.loads(raw) if isinstance(raw, str) else (raw or {})
            if not isinstance(target, dict):
                continue
            if int(target.get('user_id') or 0) != int(user_id):
                continue
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        bound.append(r)

    bound.sort(key=lambda x: (x.get('post_count') or 0), reverse=True)

    result = []
    for r in bound:
        level = r.get('level') or 3
        is_official = bool(r.get('is_official'))

        visual = _LEVEL_VISUAL.get(level, _LEVEL_VISUAL[3])
        if is_official:
            visual = {'label': '柜台', 'type': 'counter'}

        result.append({
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
        })

    return result


def _update_resource_favorites_count(resource_type, resource_id, delta):
    table = resource_table(resource_type)
    if not table:
        return
    profiles_repo.increment_favorites_count(resource_type, resource_id, delta)


# ============================================================
# 个人主页
# ============================================================
@profile_bp.route('/<int:id>')
def profile(id):
    user_row = profiles_repo.get_user(id)
    if not user_row:
        abort(404)

    user = {
        'id': user_row['id'],
        'nickname': user_row['nickname'],
        'email': user_row['email'],
        'avatar': user_row.get('avatar', '/images/avatar/default.jpg'),
        'signature': user_row.get('signature', ''),
        'registration_time': user_row.get('registration_time', ''),
        'edit_count': user_row.get('edit_count', 0),
        'view_count': user_row.get('view_count', 0),
        'reputation': user_row.get('reputation', 100),
        'role': user_row['role'],
        'sel_role': user_row.get('sel_role') or 0,
        'tea_role': user_row.get('tea_role') or 0,
        'brick': user_row.get('brick', 0.0)
    }

    # ===== 是否为本人 =====
    is_me = False
    if session.get('user_info'):
        is_me = (session['user_info']['id'] == id)

    # ===== 成就评定（仅本人访问时触发，engine 内部有 5 分钟防抖） =====
    if is_me:
        try:
            from utils.achievements import evaluate_user
            evaluate_user(id)
        except Exception:
            pass

    # ============================================================
    # 隐私设置（需要在在线状态之前解析）
    # ============================================================
    privacy_settings = dict(_PRIVACY_DEFAULT)
    raw_privacy = user_row.get('privacy_settings')
    if raw_privacy:
        try:
            saved = json.loads(raw_privacy)
            if isinstance(saved, dict):
                privacy_settings.update(saved)
        except:
            pass

    # ===== 成就数据（供 base.html 里的成就 tab 使用） =====
    achievements_grouped = {'daily': [], 'limited': [], 'permanent': []}
    achievements_total = 0
    achievements_completed = 0

    if is_me or privacy_settings.get('show_achievements', True):
        try:
            from utils.achievements import get_user_achievements
            achievements_data = get_user_achievements(id)
            for a in achievements_data:
                achievements_grouped.setdefault(a['category'], []).append(a)
            achievements_total = len(achievements_data)
            achievements_completed = sum(1 for a in achievements_data if a['completed'])
        except Exception:
            pass

    # ===== 在线状态 =====
    hide_online = (not is_me) and privacy_settings.get('hide_online_status', False)

    online_status = get_user_online_status(
        id,
        tea_last_active=user_row.get('tea_last_active'),
        is_self=is_me,
        hide=hide_online,
    )

    # ===== 解析头衔 =====
    selected_title = get_selected_title(user_row.get('titles'))
    all_titles = parse_titles(user_row.get('titles')).get('list', [])

    # ============================================================
    # 【Phase 1】每日编辑统计 —— 从 user_edit_daily 表读取
    # ============================================================
    edit_daily_dict = {}
    try:
        daily_rows = profiles_repo.list_edit_daily(id)
        for row in daily_rows:
            date_val = row.get('date')
            if hasattr(date_val, 'isoformat'):
                date_str = date_val.isoformat()
            else:
                date_str = str(date_val) if date_val else ''
            if not date_str:
                continue
            edit_daily_dict[date_str] = {
                'edit': row.get('edit_count') or 0,
                'submit_review': row.get('review_count') or 0
            }
    except Exception:
        pass

    # ============================================================
    # 【Phase 1】编辑历史列表 —— 从 user_edit_history 表读取
    # ============================================================
    total_edit_history = 0
    try:
        total_edit_history = profiles_repo.count_edit_history(id)
    except Exception:
        total_edit_history = 0

    page = request.args.get('page', 1, type=int)
    per_page = 20
    total_pages = (total_edit_history + per_page - 1) // per_page if total_edit_history > 0 else 1
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    type_map = {
        'resourcepack': '资源包',
        'shaderpack': '光影包',
        'map': '地图',
        'shaderpack_preset': '光影包预设'
    }
    op_map = {'add': '添加了', 'edit': '编辑了'}

    edit_history_paginated = []
    try:
        history_rows = profiles_repo.list_edit_history(id, per_page, offset)
        for item in history_rows:
            target_type = item.get('target_type') or ''
            target_id = item.get('target_id')

            if target_type == 'shaderpack_preset':
                preset_row = profiles_repo.get_preset_shaderpack_id(target_id)
                if preset_row:
                    url = f'/shaderpack/{preset_row["shaderpack_id"]}/preset/{target_id}'
                else:
                    url = '#'
            elif target_type == 'resourcepack':
                url = f'/resourcepack/{target_id}'
            elif target_type == 'shaderpack':
                url = f'/shaderpack/{target_id}'
            elif target_type == 'map':
                url = f'/map/{target_id}'
            else:
                url = '#'

            op_display = op_map.get(item.get('operation'), '操作了')
            type_display = type_map.get(target_type, target_type)

            created_at = item.get('created_at')
            if hasattr(created_at, 'strftime'):
                timestamp_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
            else:
                timestamp_str = str(created_at) if created_at else ''

            edit_history_paginated.append({
                'operation_display': op_display,
                'type_display': type_display,
                'resource_name': item.get('resource_name') or '',
                'url': url,
                'timestamp': timestamp_str
            })
    except Exception:
        pass

    def parse_area(raw_json):
        if not raw_json:
            return {}
        try:
            return json.loads(raw_json)
        except:
            return {}

    edit_area = parse_area(user_row.get('edit_area'))
    review_area = parse_area(user_row.get('review_area'))
    file_area = parse_area(user_row.get('file_area'))

    categories = ['resourcepack', 'shaderpack', 'map']
    for area in [edit_area, review_area, file_area]:
        for cat in categories:
            if cat not in area:
                area[cat] = {'all': False, 'detail': []}

    def get_resource_names(table_name):
        # 只取 abbr / main_name / sub_name 三个 JSON 子路径，
        # 不再把每一行的整份 content 拉回来解析（B 批 2.4）
        rows = profiles_repo.list_resource_name_fields(table_name)
        mapping = {}
        for row in rows:
            if not row.get('ok'):
                # 复刻原实现的 json.loads 失败 / content 不是对象时的分支
                mapping[row['id']] = f'未命名 #{row["id"]}'
                continue
            abbr = row.get('abbr') or ''
            main = row.get('main_name') or ''
            sub = row.get('sub_name') or ''
            if abbr:
                name = f'[{abbr}] {main}'
            else:
                name = main
            if sub and sub != main:
                name += f' ({sub})'
            mapping[row['id']] = name
        return mapping

    resource_names = {
        'resourcepack': get_resource_names('resourcepacks'),
        'shaderpack': get_resource_names('shaderpacks'),
        'map': get_resource_names('maps'),
    }

    role_map = {
        0: {'name': '已封禁用户', 'color': '#777777'},
        1: {'name': '工坊成员', 'color': '#55d88b'},
        2: {'name': '工坊工匠', 'color': '#3498db'},
        3: {'name': '精英工匠', 'color': '#9b59b6'},
        4: {'name': '工坊主管', 'color': '#e67e22'}
    }
    role_info = role_map.get(user['role'], role_map[1])

    sel_role_val = user.get('sel_role') or 0
    sel_role_info = SEL_ROLE_MAP.get(sel_role_val, SEL_ROLE_MAP[0])

    works_data = get_user_works(id)
    likes_data = get_user_likes(id)
    favorites_data = get_user_favorites(id)
    bound_tea_topics = get_user_bound_tea_topics(id)

    # ===== 移动端检测 =====
    ua = request.headers.get('User-Agent', '').lower()
    mobile_keywords = ['android', 'iphone', 'ipad', 'ipod', 'mobile', 'windows phone']
    is_mobile = any(keyword in ua for keyword in mobile_keywords)
    if 'ipad' in ua:
        is_mobile = False

    if request.args.get('desktop') == '1':
        is_mobile = False

    if is_mobile:
        return render_template(
            'profile/mobile.html',
            user=user,
            role_name=role_info['name'],
            role_color=role_info['color'],
            sel_role_name=sel_role_info['name'],
            sel_role_color=sel_role_info['color'],
            is_me=is_me,
            privacy_settings=privacy_settings,
            selected_title=selected_title,
            online_status=online_status,
        )

    # ===== 桌面端 =====
    return render_template(
        'profile/base.html',
        user=user,
        role_name=role_info['name'],
        role_color=role_info['color'],
        sel_role_name=sel_role_info['name'],
        sel_role_color=sel_role_info['color'],
        is_me=is_me,
        edit_area=edit_area,
        review_area=review_area,
        file_area=file_area,
        resource_names=resource_names,
        edit_daily=edit_daily_dict,
        edit_history=edit_history_paginated,
        total_edit_history=total_edit_history,
        current_page=page,
        total_pages=total_pages,
        per_page=per_page,
        works_data=works_data,
        likes_data=likes_data,
        favorites_data=favorites_data,
        bound_tea_topics=bound_tea_topics,
        privacy_settings=privacy_settings,
        selected_title=selected_title,
        all_titles=all_titles,
        online_status=online_status,
        # ★ 成就 tab 数据
        achievements_grouped=achievements_grouped,
        achievements_total=achievements_total,
        achievements_completed=achievements_completed,
    )


# ============================================================
# 成就页（独立 URL → 重定向到主页的成就 tab）
# ============================================================
@profile_bp.route('/<int:id>/achievements')
def achievements_page(id):
    """独立路由 → 跳到主页并自动切到成就 tab"""
    return redirect(f'/profile/{id}?tab=achievements')


# ============================================================
# 收藏夹管理 API（需登录）
# ============================================================
@profile_bp.route('/favorites/data', methods=['GET'])
@login_required()
def get_favorites_data():
    user_id = session['user_info']['id']
    data = get_user_favorites(user_id)
    return jsonify({'success': True, 'data': data})


@profile_bp.route('/favorites/folder', methods=['POST'])
@login_required()
def create_folder():
    user_id = session['user_info']['id']
    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '收藏夹名称不能为空'}), 400
    existing = profiles_repo.find_folder_id_by_name(user_id, name)
    if existing:
        return jsonify({'success': False, 'message': '收藏夹名称已存在'}), 400
    profiles_repo.create_default_folder(user_id, name)
    log_action(
        user_id=user_id,
        action='create_folder',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data={'folder_name': name}
    )
    return jsonify({'success': True, 'message': '收藏夹创建成功'})


@profile_bp.route('/favorites/folder/<int:folder_id>', methods=['PUT'])
@login_required()
def rename_folder(folder_id):
    user_id = session['user_info']['id']
    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '名称不能为空'}), 400
    folder = profiles_repo.get_owned_folder(folder_id, user_id)
    if not folder:
        return jsonify({'success': False, 'message': '收藏夹不存在或无权限'}), 404
    existing = profiles_repo.find_folder_id_by_name(user_id, name, folder_id)
    if existing:
        return jsonify({'success': False, 'message': '名称已存在'}), 400
    profiles_repo.rename_folder(folder_id, name)
    log_action(
        user_id=user_id,
        action='rename_folder',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data={'folder_id': folder_id, 'new_name': name}
    )
    return jsonify({'success': True, 'message': '重命名成功'})


@profile_bp.route('/favorites/folder/<int:folder_id>', methods=['DELETE'])
@login_required()
def delete_folder(folder_id):
    user_id = session['user_info']['id']
    folder = profiles_repo.get_owned_folder(folder_id, user_id)
    if not folder:
        return jsonify({'success': False, 'message': '收藏夹不存在或无权限'}), 404
    profiles_repo.delete_folder_items(folder_id)
    profiles_repo.delete_folder(folder_id)
    log_action(
        user_id=user_id,
        action='delete_folder',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data={'folder_id': folder_id}
    )
    return jsonify({'success': True, 'message': '删除成功'})


@profile_bp.route('/favorites/add', methods=['POST'])
@login_required()
def add_to_favorites():
    user_id = session['user_info']['id']
    data = request.json
    resource_type = data.get('resource_type')
    resource_id = data.get('resource_id')
    folder_id = data.get('folder_id')

    if not resource_type or not resource_id:
        return jsonify({'success': False, 'message': '缺少资源参数'}), 400

    if not folder_id:
        first = profiles_repo.get_first_folder(user_id)
        if not first:
            profiles_repo.create_default_folder(user_id)
            first = profiles_repo.get_first_folder(user_id)
        folder_id = first['id']

    existing = profiles_repo.get_favorite(
        user_id, resource_type, resource_id, folder_id)
    if existing:
        return jsonify({'success': False, 'message': '资源已在该收藏夹中'}), 400

    profiles_repo.add_favorite(
        user_id, resource_type, resource_id, folder_id)
    _update_resource_favorites_count(resource_type, resource_id, 1)

    log_action(
        user_id=user_id,
        action='add_to_favorites',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data={'resource_type': resource_type, 'resource_id': resource_id, 'folder_id': folder_id}
    )
    return jsonify({'success': True, 'message': '已添加到收藏夹'})


@profile_bp.route('/favorites/remove', methods=['POST'])
@login_required()
def remove_from_favorites():
    user_id = session['user_info']['id']
    data = request.json
    resource_type = data.get('resource_type')
    resource_id = data.get('resource_id')
    folder_id = data.get('folder_id')

    if not resource_type or not resource_id:
        return jsonify({'success': False, 'message': '缺少资源参数'}), 400

    profiles_repo.remove_favorite(
        user_id, resource_type, resource_id, folder_id)
    _update_resource_favorites_count(resource_type, resource_id, -1)

    log_action(
        user_id=user_id,
        action='remove_from_favorites',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data={'resource_type': resource_type, 'resource_id': resource_id}
    )
    return jsonify({'success': True, 'message': '已从收藏夹移除'})