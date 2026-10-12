# mcres/views/comment.py
import json
import os
import re
import hashlib
import threading
from collections import defaultdict
from datetime import datetime

from flask import Blueprint, request, jsonify, session, current_app, render_template

from utils.data.repositories import comments as comments_repo
from utils.data.repositories import users as users_repo
from utils.time import datetime_fmt
from utils.users import permissions
from utils.users.bans import is_ban_active
from utils.text.titles import get_selected_title
from .. import log_action, get_real_ip, get_ip_region

from utils.text.forbidden_words import detector
from utils.users.punishment import apply_punishment
from utils.text.emo import render_content as render_emo_content, get_emoji_list

cmt = Blueprint('cmt', __name__)


# ============================================================
# ★ 表态类型配置：从 reactions.json 读取，支持热加载
# ============================================================
_REACTION_CONFIG_PATH = os.path.join(os.getcwd(), 'reactions.json')

_DEFAULT_REACTIONS = [
    {"key": "love",     "emoji": "❤️", "label": "爱了"},
    {"key": "laugh",    "emoji": "😂", "label": "笑不活了"},
    {"key": "learn",    "emoji": "📖", "label": "学到了"},
    {"key": "taste",    "emoji": "✨", "label": "有品位"},
    {"key": "melon",    "emoji": "🍉", "label": "吃瓜"},
    {"key": "confused", "emoji": "🤔", "label": "我不理解"},
]

_REACTION_CACHE = {'mtime': 0.0, 'types': None}
_REACTION_LOCK = threading.Lock()


def _normalize_reactions(raw):
    if not isinstance(raw, list):
        return None

    result = []
    seen_keys = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get('enabled') is False:
            continue
        key = str(item.get('key', '')).strip()
        emoji = str(item.get('emoji', '')).strip()
        label = str(item.get('label', '')).strip()
        if not key or not emoji or not label:
            continue
        if not re.match(r'^[a-z0-9_\-]{1,32}$', key):
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        result.append({'key': key, 'emoji': emoji, 'label': label})

    return result or None


def _load_reactions():
    if not os.path.exists(_REACTION_CONFIG_PATH):
        return _REACTION_CACHE['types'] or _DEFAULT_REACTIONS

    try:
        mtime = os.path.getmtime(_REACTION_CONFIG_PATH)
    except OSError:
        return _REACTION_CACHE['types'] or _DEFAULT_REACTIONS

    with _REACTION_LOCK:
        if _REACTION_CACHE['mtime'] == mtime and _REACTION_CACHE['types'] is not None:
            return _REACTION_CACHE['types']

        try:
            with open(_REACTION_CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ 读取 reactions.json 失败，沿用旧配置: {e}")
            return _REACTION_CACHE['types'] or _DEFAULT_REACTIONS

        types = _normalize_reactions(data)
        if not types:
            print("⚠️ reactions.json 无有效表态，沿用旧配置")
            return _REACTION_CACHE['types'] or _DEFAULT_REACTIONS

        _REACTION_CACHE['mtime'] = mtime
        _REACTION_CACHE['types'] = types
        print(f"✅ 表态配置已加载，共 {len(types)} 种")
        return types


def get_reaction_types():
    return _load_reactions()


def get_reaction_list():
    return [t['key'] for t in _load_reactions()]


def get_reaction_map():
    return {t['key']: t for t in _load_reactions()}


# ============================================================
#  评论数据操作
# ============================================================
def get_comments_by_url(url):
    """兼容旧接口：拿某 url 下所有评论（顶层+子评论），按 created_at 升序。"""
    rows = comments_repo.list_by_path(url)
    return [_row_to_comment(r) for r in rows]


def _row_to_comment(r):
    """
    DB row → 前端兼容的评论 dict

    ★ 新增 content_html 字段：
        在服务端把 [xxx] 表情标识符渲染为 <img>。
        渲染函数内部先做 HTML 转义再做白名单替换，天然防 XSS。
        · content       —— 原始纯文本（前端插入、编辑、复制等场景使用）
        · content_html  —— 已渲染的安全 HTML（前端展示使用）
    """
    created = r.get('created_at')
    if isinstance(created, datetime):
        created_str = created.strftime('%Y-%m-%d %H:%M:%S')
    else:
        created_str = str(created) if created else ''

    raw_content = r.get('content') or ''

    return {
        'id': r['id'],
        'user_id': r['user_id'],
        'parent_id': r['parent_id'] if r.get('parent_id') else None,
        'reply_to': r.get('reply_to') or '',
        'reply_to_id': r.get('reply_to_id'),
        'ip_region': r.get('ip_region') or '',
        'content': raw_content,
        'content_html': render_emo_content(raw_content),   # ★ 服务端渲染表情
        'is_pinned': bool(r.get('is_pinned')),
        'created_at': created_str,
    }


def get_profile_owner_id(path):
    match = re.match(r'^/profile/(\d+)$', path)
    if match:
        return int(match.group(1))
    return None


# ============================================================
#  评论上下文丰富
# ============================================================
def enrich_comments_with_context(comments, current_user_id, current_path):
    if not comments:
        return comments

    # ---------- 1. 收集所有 user_id ----------
    user_ids = set()
    for c in comments:
        if c.get('user_id'):
            user_ids.add(c['user_id'])

    # ---------- 2. 批量查 reply_to_id → user_id ----------
    reply_to_ids = set()
    for c in comments:
        if c.get('reply_to_id'):
            reply_to_ids.add(c['reply_to_id'])

    reply_to_user_map = {}
    if reply_to_ids:
        rows = comments_repo.list_ids_by_user(list(reply_to_ids))
        for r in rows:
            reply_to_user_map[r['id']] = r['user_id']
            if r['user_id']:
                user_ids.add(r['user_id'])

    # ---------- 3. 批量查用户信息 ----------
    user_map = {}
    if user_ids:
        rows = comments_repo.list_authors(list(user_ids))
        for row in rows:
            user_map[row['id']] = {
                'nickname': row['nickname'],
                'avatar': row.get('avatar', 'https://img.mcresource.cn/user/avatar/default.jpg'),
                'title': get_selected_title(row.get('titles'))
            }

    # ---------- 4. 权限预计算 ----------
    is_admin = False
    if current_user_id:
        is_admin = (users_repo.get_role(current_user_id) or 0) >= 3

    profile_owner_id = get_profile_owner_id(current_path)

    can_pin_path = False
    if current_user_id:
        user_role = users_repo.get_role_and_area(current_user_id)
        if user_role:
            role = user_role['role']
            if role >= 3:
                can_pin_path = True
            elif profile_owner_id and profile_owner_id == current_user_id:
                can_pin_path = True
            elif user_role.get('review_area'):
                try:
                    review_area = json.loads(user_role['review_area'])
                    match = re.match(r'^/(resourcepack|shaderpack|map)/(\d+)$', current_path)
                    if match:
                        res_type = match.group(1)
                        res_id = int(match.group(2))
                        if res_type in review_area:
                            area = review_area[res_type]
                            if area.get('all') == True:
                                can_pin_path = True
                            elif res_id in area.get('detail', []):
                                can_pin_path = True
                except Exception:
                    pass

    # ---------- 5. parent_id → 顶层评论作者 ----------
    parent_ids = set()
    for c in comments:
        if c.get('parent_id'):
            parent_ids.add(c['parent_id'])

    parent_map = {}
    if parent_ids:
        rows = comments_repo.list_ids_by_user(list(parent_ids))
        for r in rows:
            parent_map[r['id']] = r['user_id']

    # ---------- 6. 逐条填充 ----------
    for c in comments:
        uid = c.get('user_id')
        if uid and uid in user_map:
            c['nickname'] = user_map[uid]['nickname']
            c['avatar'] = user_map[uid]['avatar']
            c['title'] = user_map[uid]['title']
        else:
            c['nickname'] = '已注销用户'
            c['avatar'] = 'https://img.mcresource.cn/user/avatar/default.jpg'
            c['title'] = None

        can_delete = False
        if current_user_id:
            if c.get('user_id') == current_user_id:
                can_delete = True
            elif is_admin:
                can_delete = True
            elif profile_owner_id and profile_owner_id == current_user_id:
                can_delete = True
        c['can_delete'] = can_delete

        # ★ reply_to_nickname 优先级：
        #   1. reply_to_id 动态查（新数据，改名能同步）
        #   2. reply_to 快照（老数据）
        #   3. parent_id 作者（回复顶层评论）
        if c.get('reply_to_id'):
            r_uid = reply_to_user_map.get(c['reply_to_id'])
            if r_uid and r_uid in user_map:
                c['reply_to_nickname'] = user_map[r_uid]['nickname']
            else:
                c['reply_to_nickname'] = c.get('reply_to') or ''
        elif c.get('reply_to'):
            c['reply_to_nickname'] = c['reply_to']
        elif c.get('parent_id'):
            parent_uid = parent_map.get(c['parent_id'])
            if parent_uid and parent_uid in user_map:
                c['reply_to_nickname'] = user_map[parent_uid]['nickname']
            else:
                c['reply_to_nickname'] = ''
        else:
            c['reply_to_nickname'] = ''

        c['can_pin'] = can_pin_path and not c.get('parent_id')

    return comments


# ============================================================
#  表态数据丰富
# ============================================================
def enrich_comments_with_reactions(comments, current_user_id):
    if not comments:
        return comments

    comment_ids = [c['id'] for c in comments if c.get('id')]
    if not comment_ids:
        return comments

    reaction_keys = get_reaction_list()

    rows = comments_repo.list_reactions_for_comments(comment_ids)

    reaction_counts = {}
    user_reactions = {}
    for row in rows:
        cid = row['comment_id']
        if cid not in reaction_counts:
            reaction_counts[cid] = {t: 0 for t in reaction_keys}
        if row['reaction_type'] in reaction_counts[cid]:
            reaction_counts[cid][row['reaction_type']] += 1
        if current_user_id and row['user_id'] == current_user_id:
            user_reactions[cid] = row['reaction_type']

    for c in comments:
        cid = c['id']
        c['reactions'] = reaction_counts.get(cid, {t: 0 for t in reaction_keys})
        c['user_reaction'] = user_reactions.get(cid)

    return comments


def get_reaction_counts(comment_id):
    reaction_keys = get_reaction_list()
    rows = comments_repo.count_reactions_grouped(comment_id)
    counts = {t: 0 for t in reaction_keys}
    for row in rows:
        if row['reaction_type'] in counts:
            counts[row['reaction_type']] = row['cnt']
    return counts


# ============================================================
#  GET /comments  —— 读评论
# ============================================================
@cmt.route('/comments', methods=['GET'])
def get_comments():
    path = request.args.get('path')
    if not path:
        return jsonify({'success': False, 'message': '缺少 path 参数'}), 400

    cpage = request.args.get('cpage', 1, type=int)
    if cpage < 1:
        cpage = 1
    csize = request.args.get('csize', 20, type=int)
    if csize < 1 or csize > 50:
        csize = 20

    current_user_id = session.get('user_info', {}).get('id')

    pinned_rows = comments_repo.list_pinned_top(path)

    total_normal = comments_repo.count_top_not_pinned(path)

    total_pages = max(1, (total_normal + csize - 1) // csize) if total_normal else 1
    if cpage > total_pages:
        cpage = total_pages
    offset = (cpage - 1) * csize

    normal_rows = comments_repo.list_top_not_pinned_page(path, csize, offset)

    total_all = comments_repo.count_all_by_path(path)

    page_top_ids = [r['id'] for r in pinned_rows] + [r['id'] for r in normal_rows]
    all_rows = list(pinned_rows) + list(normal_rows)

    if page_top_ids:
        child_rows = comments_repo.list_children(page_top_ids)
        all_rows.extend(child_rows)

    comments = [_row_to_comment(r) for r in all_rows]

    pinned_comments = [c for c in comments if c.get('is_pinned') and not c.get('parent_id')]
    normal_comments = [c for c in comments if not c.get('is_pinned') and not c.get('parent_id')]
    normal_comments.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    children_by_parent = {}
    for c in comments:
        if c.get('parent_id'):
            children_by_parent.setdefault(c['parent_id'], []).append(c)

    page_comments = []
    for c in pinned_comments:
        page_comments.append(c)
        page_comments.extend(children_by_parent.get(c['id'], []))
    for c in normal_comments:
        page_comments.append(c)
        page_comments.extend(children_by_parent.get(c['id'], []))

    page_comments = enrich_comments_with_context(page_comments, current_user_id, path)
    page_comments = enrich_comments_with_reactions(page_comments, current_user_id)

    return jsonify({
        'success': True,
        'data': page_comments,
        'total_count': total_all,
        'pagination': {
            'page': cpage,
            'size': csize,
            'total': total_normal,
            'total_pages': total_pages,
        }
    })


# ============================================================
#  POST /comments  —— 发评论
# ============================================================
@cmt.route('/comments', methods=['POST'])
@permissions.login_required()
def post_comment():
    data = request.get_json()
    if not data:
        log_action(
            user_id=session.get('user_info', {}).get('id'),
            action='post_comment', level='WARNING',
            request_data={'error': 'invalid_json'}
        )
        return jsonify({'success': False, 'message': '无效的 JSON 数据'}), 400

    path = data.get('path')
    content = data.get('content', '').strip()
    parent_id = data.get('parent_id')
    reply_to = data.get('reply_to', '').strip()
    reply_to_id = data.get('reply_to_id')

    if not path:
        return jsonify({'success': False, 'message': '缺少 path 参数'}), 400
    if not content:
        return jsonify({'success': False, 'message': '评论内容不能为空'}), 400

    user_id = session.get('user_info', {}).get('id')
    if not user_id:
        return jsonify({'success': False, 'message': '未登录'}), 401

    if parent_id in ('', 'null', 'None', None):
        parent_id = None
    else:
        try:
            parent_id = int(parent_id)
        except (ValueError, TypeError):
            parent_id = None

    if reply_to_id in ('', 'null', 'None', None):
        reply_to_id = None
    else:
        try:
            reply_to_id = int(reply_to_id)
        except (ValueError, TypeError):
            reply_to_id = None

    content_hash = hashlib.md5(content.encode()).hexdigest()
    submit_cache_key = f'comment_submit_{user_id}_{content_hash}'
    if session.get(submit_cache_key):
        return jsonify({
            'success': False,
            'message': '您刚才已提交过相同内容，请稍后再试'
        }), 429
    session[submit_cache_key] = True

    _ban_raw = users_repo.get_ban(user_id)
    if _ban_raw:
        try:
            ban_data = json.loads(_ban_raw)
            ban_comment = ban_data.get('comment')
            if is_ban_active(ban_comment):
                log_action(
                    user_id=user_id, action='post_comment', level='WARNING',
                    request_data={'path': path, 'reason': 'comment_banned'}
                )
                return jsonify({
                    'success': False,
                    'message': f'您已被禁止发表评论，截止至 {ban_comment["deadline"]}，'
                               f'原因：{ban_comment.get("reason", "无")}'
                }), 403
        except Exception:
            pass

    user_role = users_repo.get_role(user_id)
    if user_role is None:
        user_role = 1
    exempt_roles = detector.get_exempt_roles()

    if user_role not in exempt_roles:
        level, matched_keywords, level_config = detector.check(content)
        if level and level_config:
            apply_punishment(user_id, level, matched_keywords, level_config)
            log_action(
                user_id=user_id, action='post_comment_blocked',
                level='WARNING' if level != 'WARN' else 'INFO',
                request_data={
                    'path': path, 'level': level,
                    'matched_keywords': matched_keywords,
                    'content_preview': content[:50]
                }
            )
            session.pop(submit_cache_key, None)
            return render_template(
                'errors/error_forbidden_comment.html',
                message=f'评论包含违禁词，已触发 {level_config["punishment"]} 处罚',
                redirect_url=path,
                level=level,
                punishment=level_config['punishment'],
                matched_keywords=', '.join(matched_keywords)
            ), 403

    now = datetime_fmt.now()

    # 获取发评论时的 IP 属地（省级）
    try:
        client_ip = get_real_ip()
        ip_region = get_ip_region(client_ip) if client_ip else '未知'
    except Exception:
        ip_region = '未知'

    comments_repo.insert(path, user_id, parent_id, reply_to, reply_to_id,
                         ip_region, content, now)
    new_row = comments_repo.find_last_id(path, user_id)
    comment_id = new_row['id'] if new_row else 0

    users_repo.increment_comment_count(user_id)

    session.pop(submit_cache_key, None)

    # ============================================================
    # 【Phase 4】移除通知写入
    # 未读改由 SQL 实时算（基于 created_at > message_last_read）
    # ============================================================

    log_action(
        user_id=user_id, action='post_comment', level='INFO',
        target_type='path', target_id=hash(path),
        request_data={
            'path': path, 'parent_id': parent_id,
            'reply_to_id': reply_to_id,
            'content_preview': content[:50],
            'comment_id': comment_id,
            'ip_region': ip_region,
        }
    )

    new_comment_row = comments_repo.get(comment_id)
    comment = _row_to_comment(new_comment_row)
    enriched = enrich_comments_with_context([comment], user_id, path)
    return jsonify({
        'success': True,
        'message': '评论发表成功',
        'data': enriched[0] if enriched else comment
    })


# ============================================================
#  DELETE /comments/<comment_id>
# ============================================================
@cmt.route('/comments/<int:comment_id>', methods=['DELETE'])
@permissions.login_required()
def delete_comment(comment_id):
    current_user_id = session.get('user_info', {}).get('id')
    if not current_user_id:
        return jsonify({'success': False, 'message': '未登录'}), 401

    path = request.args.get('path')
    if not path:
        return jsonify({'success': False, 'message': '缺少 path 参数'}), 400

    is_admin = (users_repo.get_role(current_user_id) or 0) >= 3
    profile_owner_id = get_profile_owner_id(path)

    target = comments_repo.get(comment_id)
    if not target:
        log_action(
            user_id=current_user_id, action='delete_comment', level='WARNING',
            request_data={'path': path, 'comment_id': comment_id, 'reason': 'not_found'}
        )
        return jsonify({'success': False, 'message': '评论不存在'}), 404

    can_delete = False
    if target['user_id'] == current_user_id:
        can_delete = True
    elif is_admin:
        can_delete = True
    elif profile_owner_id == current_user_id:
        can_delete = True

    if not can_delete:
        log_action(
            user_id=current_user_id, action='delete_comment', level='WARNING',
            request_data={'path': path, 'comment_id': comment_id,
                          'reason': 'permission_denied'}
        )
        return jsonify({'success': False, 'message': '无权删除此评论'}), 403

    ids_to_delete = [comment_id]
    frontier = [comment_id]
    while frontier:
        children = comments_repo.list_children_ids(frontier)
        child_ids = [c['id'] for c in children]
        if not child_ids:
            break
        ids_to_delete.extend(child_ids)
        frontier = child_ids

    comments_repo.soft_delete_many(ids_to_delete)

    if target['user_id']:
        users_repo.decrement_comment_count(target['user_id'])

    log_action(
        user_id=current_user_id, action='delete_comment', level='INFO',
        target_type='path', target_id=hash(path),
        request_data={
            'path': path,
            'deleted_count': len(ids_to_delete),
            'comment_id': comment_id,
            'author_id': target['user_id'],
            'is_admin': is_admin
        }
    )

    return jsonify({
        'success': True,
        'message': f'已删除 {len(ids_to_delete)} 条评论（含回复）',
        'deleted_count': len(ids_to_delete)
    })


# ============================================================
#  POST /comments/report
# ------------------------------------------------------------
# 【Phase Q】举报写入 user_reports 表，不再写 user_info.report JSON
# ============================================================
@cmt.route('/comments/report', methods=['POST'])
@permissions.login_required()
def report_comment():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '无效的JSON数据'}), 400

    author_id = data.get('author_id')
    reason = data.get('reason', '').strip()
    content = data.get('content', '').strip()

    if not author_id or not reason or not content:
        return jsonify({'success': False, 'message': '参数不完整'}), 400

    reporter_id = session.get('user_info', {}).get('id')
    if not reporter_id:
        return jsonify({'success': False, 'message': '未登录'}), 401

    if int(reporter_id) == int(author_id):
        log_action(
            user_id=reporter_id, action='report_comment', level='WARNING',
            target_type='user', target_id=author_id,
            request_data={'reason': 'self_report'}
        )
        return jsonify({'success': False, 'message': '不能举报自己的评论'}), 403

    # ============================================================
    # 【Phase Q】写入 user_reports 表
    # ============================================================
    comments_repo.insert_report(
        author_id, reporter_id, reason, content, datetime_fmt.now())

    log_action(
        user_id=reporter_id, action='report_comment', level='INFO',
        target_type='user', target_id=author_id,
        request_data={
            'reason': reason,
            'content_preview': content[:50],
            'report_time': datetime_fmt.now()
        }
    )

    return jsonify({'success': True, 'message': '举报已提交'})


# ============================================================
# ★ 表态类型 API
# ============================================================
@cmt.route('/comments/reactions', methods=['GET'])
def get_reaction_types_api():
    data = get_reaction_types()
    resp = jsonify({'success': True, 'data': data})
    resp.headers['Cache-Control'] = 'public, max-age=60'
    return resp


# ============================================================
# ★ 站内表情列表 API
# ------------------------------------------------------------
# 返回 emo.json 里配置的所有表情：
#     [{"key": "smile", "url": "https://..."}, ...]
# 前端用来渲染表情面板，点击时插入 [smile] 到输入框光标位置。
# 实际渲染 [smile] → <img> 由 _row_to_comment 里的 render_emo_content 完成。
# ============================================================
@cmt.route('/comments/emojis', methods=['GET'])
def get_emoji_list_api():
    data = get_emoji_list()
    resp = jsonify({'success': True, 'data': data})
    resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp


# ============================================================
#  POST /comments/reaction
# ============================================================
@cmt.route('/comments/reaction', methods=['POST'])
@permissions.login_required()
def set_reaction():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '无效的JSON数据'}), 400

    comment_id = data.get('comment_id')
    reaction = data.get('reaction')

    if not comment_id:
        return jsonify({'success': False, 'message': '缺少 comment_id'}), 400

    try:
        comment_id = int(comment_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'comment_id 格式错误'}), 400

    current_user_id = session.get('user_info', {}).get('id')
    if not current_user_id:
        return jsonify({'success': False, 'message': '未登录'}), 401

    comment_row = comments_repo.get(
        comment_id, 'id, user_id, content, path')
    if not comment_row:
        return jsonify({'success': False, 'message': '评论不存在'}), 404

    if reaction is None:
        comments_repo.delete_reaction(comment_id, current_user_id)
        counts = get_reaction_counts(comment_id)
        return jsonify({
            'success': True,
            'user_reaction': None,
            'reactions': counts
        })

    if reaction not in get_reaction_list():
        return jsonify({'success': False, 'message': '无效的表态类型'}), 400

    existing = comments_repo.get_reaction(comment_id, current_user_id)

    comments_repo.upsert_reaction(
        comment_id, current_user_id, reaction, datetime_fmt.now())

    # ============================================================
    # 【Phase 4】移除通知写入
    # ============================================================

    counts = get_reaction_counts(comment_id)
    return jsonify({
        'success': True,
        'user_reaction': reaction,
        'reactions': counts
    })


# ============================================================
#  POST /comments/pin
# ============================================================
@cmt.route('/comments/pin', methods=['POST'])
@permissions.login_required()
def pin_comment():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '无效的JSON数据'}), 400

    comment_id = data.get('comment_id')
    path = data.get('path')
    if not comment_id or not path:
        return jsonify({'success': False, 'message': '缺少参数'}), 400

    try:
        comment_id = int(comment_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'comment_id 格式错误'}), 400

    current_user_id = session.get('user_info', {}).get('id')
    if not current_user_id:
        return jsonify({'success': False, 'message': '未登录'}), 401

    target = comments_repo.find_by_id_and_path(
        comment_id, path, 'id, parent_id, is_pinned')
    if not target:
        return jsonify({'success': False, 'message': '评论不存在'}), 404

    if target['parent_id']:
        return jsonify({'success': False, 'message': '回复不能置顶'}), 400

    has_permission = False
    user_role = users_repo.get_role_and_area(current_user_id)
    if user_role:
        if user_role['role'] >= 3:
            has_permission = True

    if not has_permission:
        profile_owner_id = get_profile_owner_id(path)
        if profile_owner_id == current_user_id:
            has_permission = True

    if not has_permission and user_role and user_role.get('review_area'):
        try:
            review_area = json.loads(user_role['review_area'])
            match = re.match(r'^/(resourcepack|shaderpack|map)/(\d+)$', path)
            if match:
                res_type = match.group(1)
                res_id = int(match.group(2))
                if res_type in review_area:
                    area = review_area[res_type]
                    if area.get('all') == True:
                        has_permission = True
                    elif res_id in area.get('detail', []):
                        has_permission = True
        except Exception:
            pass

    if not has_permission:
        log_action(
            user_id=current_user_id, action='pin_comment', level='WARNING',
            request_data={'path': path, 'comment_id': comment_id,
                          'reason': 'permission_denied'}
        )
        return jsonify({'success': False, 'message': '您没有置顶权限'}), 403

    if target['is_pinned']:
        comments_repo.set_pinned(comment_id, False)
        log_action(
            user_id=current_user_id, action='pin_comment', level='INFO',
            target_type='path', target_id=hash(path),
            request_data={'path': path, 'comment_id': comment_id, 'pinned': False}
        )
        return jsonify({'success': True, 'message': '已取消置顶', 'pinned': False})

    comments_repo.clear_pinned_in_path(path)
    comments_repo.set_pinned(comment_id, True)

    log_action(
        user_id=current_user_id, action='pin_comment', level='INFO',
        target_type='path', target_id=hash(path),
        request_data={'path': path, 'comment_id': comment_id, 'pinned': True}
    )
    return jsonify({'success': True, 'message': '已置顶成功', 'pinned': True})


# ============================================================
#  GET /comments/locate  —— 定位评论在第几页
# ============================================================
@cmt.route('/comments/locate', methods=['GET'])
def locate_comment():
    path = request.args.get('path')
    raw_id = (request.args.get('comment_id') or '').strip()

    if not path or not raw_id:
        return jsonify({'success': False, 'message': '缺少参数'}), 400

    try:
        csize = int(request.args.get('csize', 20))
    except (ValueError, TypeError):
        csize = 20
    if csize < 1 or csize > 50:
        csize = 20

    if raw_id.isdigit():
        row = comments_repo.find_by_id_and_path(
            int(raw_id), path, 'id, parent_id, is_pinned, created_at')
    else:
        row = comments_repo.find_by_old_uuid_and_path(
            raw_id, path, 'id, parent_id, is_pinned, created_at')

    if not row:
        return jsonify({'success': False, 'message': '评论不存在'})

    target_id = row['id']

    if row['parent_id']:
        top = comments_repo.get(
            row['parent_id'], 'id, is_pinned, created_at')
        if not top:
            return jsonify({
                'success': True,
                'page': 1,
                'target_id': target_id,
                'is_child': True,
            })
        top_id = top['id']
        top_pinned = top['is_pinned']
        top_created = top['created_at']
        is_child = True
    else:
        top_id = row['id']
        top_pinned = row['is_pinned']
        top_created = row['created_at']
        is_child = False

    if top_pinned:
        return jsonify({
            'success': True,
            'page': 1,
            'target_id': target_id,
            'is_child': is_child,
        })

    rank = comments_repo.count_newer_top(path, top_created)

    page = rank // csize + 1

    return jsonify({
        'success': True,
        'page': page,
        'target_id': target_id,
        'is_child': is_child,
    })