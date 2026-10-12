# 【主站】views/message.py
# 位置：mcres/views/message.py
"""
消息中心（Phase 4 后版本）

数据来源：
  · reply —— comments + comment_reactions 实时查询
  · board —— comments 实时查询（path = /profile/{uid}）
  · system —— user_system_message 表
  · tea    —— 独立查询（茶室域）

未读判定：
  · 只由 created_at > user_info.message_last_read 决定
  · 打开消息页 → 更新 last_read → 红点消失，消息不清空
"""
import re

from flask import Blueprint, render_template, session, request, jsonify


from utils.time import datetime_fmt
from utils.users import permissions
from utils.time.time_utils import timesince
from utils.data.repositories.message_center import (
    count_board_messages,
    count_replies_and_reactions,
    count_system_messages,
    fetch_board_messages,
    fetch_replies_and_reactions,
    fetch_system_messages,
    fetch_tea_post_likes,
    fetch_tea_punishments,
    fetch_tea_replies,
    fetch_tea_reply_likes,
    fetch_tea_topic_posts,
    fetch_tea_managements,
    get_last_read,
    get_tea_message_blob,
    list_users_brief,
    set_tea_message_blob,
)
from utils.messaging.msg import (
    clear_unread,
    get_unread_counts,
    get_disabled_notifications,
    get_notification_settings,
)

msg_bp = Blueprint('message', __name__)


# ============================================================
# 全局配置
# ============================================================
_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')

TEA_DOMAIN = 'https://tea.mcresource.cn'
DEFAULT_AVATAR = 'https://img.mcresource.cn/user/avatar/default.jpg'

PER_PAGE = 20
TEA_MAX_PER_TYPE = 500

# 表态文案兜底（reactions.json 加载失败时用）
_DEFAULT_REACTION_MAP = {
    'love':     {'emoji': '❤️', 'label': '爱了'},
    'laugh':    {'emoji': '😂', 'label': '笑不活了'},
    'learn':    {'emoji': '📖', 'label': '学到了'},
    'taste':    {'emoji': '✨', 'label': '有品位'},
    'melon':    {'emoji': '🍉', 'label': '吃瓜'},
    'confused': {'emoji': '🤔', 'label': '我不理解'},
}


def _get_reaction_map():
    """
    从 comment.py 拿热加载的表态映射。

    【修复】原写法 `from views.comment import ...` 会 ImportError（主站包是 mcres.views），
    被 except 吞掉后走 _DEFAULT_REACTION_MAP（只有 6 个原始 key），
    导致所有新加的表态（good/dog/thanks/...）都显示兜底文案「表态」。
    改用相对导入 .comment。
    """
    try:
        from .comment import get_reaction_map
        return get_reaction_map()
    except Exception:
        return _DEFAULT_REACTION_MAP


# ============================================================
# 通用工具
# ============================================================
def _strip_html(html, limit=100):
    if not html:
        return ''
    text = _TAG_RE.sub('', html)
    text = _WS_RE.sub(' ', text).strip()
    if len(text) > limit:
        text = text[:limit] + '…'
    return text


def _to_time_str(v):
    """datetime / str / None → 'YYYY-MM-DD HH:MM:SS'"""
    if v is None:
        return ''
    if isinstance(v, str):
        if '.' in v and len(v) > 19:
            return v[:19]
        return v
    try:
        return v.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(v)


def _is_unread(created_at, last_read):
    """created_at 是否晚于 last_read"""
    if not last_read:
        return True
    created_str = _to_time_str(created_at)
    last_read_str = _to_time_str(last_read)
    if not created_str:
        return False
    return created_str > last_read_str


# ============================================================
# 主站三类：分页参数计算
# ============================================================
def _station_offset(page, per_page):
    return (page - 1) * per_page





# ============================================================
# 主站三类 enrichment（从 SQL 结果组装）
# ============================================================
def _enrich_replies(rows, user_id, last_read):
    """
    把 SQL 结果组装成模板用的 reply item。
    区分两种子类型：
      · reply    —— 别人回复我的评论
      · reaction —— 别人对我的评论表态
    模板通过 item.action_type 判断渲染。
    """
    reaction_map = _get_reaction_map()
    items = []

    for r in rows:
        subtype = r.get('_subtype')
        from_user_id = r.get('from_user_id')
        from_nickname = r.get('from_nickname') or '已注销用户'
        from_avatar = r.get('from_avatar') or DEFAULT_AVATAR
        created_at = r.get('created_at')
        path = r.get('path') or ''
        comment_id = r.get('comment_id')

        reaction_emoji = ''
        reaction_label = ''

        if subtype == 'reply':
            # ---------- 普通回复 ----------
            content_dict = {
                'id': comment_id,
                'user_id': from_user_id,
                'content': r.get('content') or '',
                'created_at': created_at,
                'reply_to_id': r.get('reply_to_id'),
            }
            parent_content = r.get('parent_content') or ''
            parent_user_id = r.get('parent_user_id')
            parent_nickname = r.get('parent_nickname') or '已注销用户'

            action_type = 'reply'
            action_label = '回复了你'

        else:  # reaction
            # ---------- 表态 ----------
            reaction_type = r.get('reaction_type') or ''
            target_content = r.get('target_content') or ''
            info = reaction_map.get(reaction_type)

            if info:
                reaction_emoji = info.get('emoji') or ''
                reaction_label = info.get('label') or ''
            else:
                # 配置里没有这个表态类型 → 通用兜底
                reaction_emoji = ''
                reaction_label = '表态'

            content_dict = {
                'id': comment_id,
                'user_id': from_user_id,
                'content': '',
                'created_at': created_at,
                'is_reaction': True,
                'reaction_type': reaction_type,
                'reaction_emoji': reaction_emoji,
                'reaction_label': reaction_label,
                'target_content': target_content,
            }
            parent_content = target_content
            parent_user_id = r.get('parent_user_id')
            parent_nickname = ''

            action_type = 'reaction'
            action_label = '对你的评论表态'

        target_url = ''
        if path and comment_id:
            target_url = f"{path}#comment-{comment_id}"

        content_dict['nickname'] = from_nickname
        content_dict['avatar'] = from_avatar
        content_dict['profile_url'] = f"/profile/{from_user_id}" if from_user_id else '#'

        item = {
            'url': path,
            'content': content_dict,
            'parent_content': parent_content,
            'parent_user_id': parent_user_id,
            'parent_nickname': parent_nickname,
            'target_url': target_url,
            'is_unread': _is_unread(created_at, last_read),
            'time': _to_time_str(created_at),
            '_subtype': subtype,
            'action_type': action_type,
            'action_label': action_label,
            'reaction_emoji': reaction_emoji,
            'reaction_label': reaction_label,
        }
        items.append(item)

    return items


def _enrich_system(rows, last_read):
    """把 SQL 结果组装成模板用的 system item"""
    items = []
    user_ids = set()

    for r in rows:
        uid = r.get('from_user_id')
        if uid and uid != 3:
            user_ids.add(uid)

    user_map = {}
    if user_ids:
        users = list_users_brief(user_ids)
        user_map = {u['id']: u for u in users}

    for r in rows:
        uid = r.get('from_user_id')
        if uid == 3:
            sender_nick = '系统'
            sender_avatar = 'https://img.mcresource.cn/user/avatar/mcres.jpg'
            profile_url = '/profile/3'
        elif uid and uid in user_map:
            sender_nick = user_map[uid]['nickname']
            sender_avatar = user_map[uid]['avatar'] or DEFAULT_AVATAR
            profile_url = f"/profile/{uid}"
        else:
            sender_nick = '未知用户'
            sender_avatar = DEFAULT_AVATAR
            profile_url = '#'

        content = r.get('content') or ''
        created_at = r.get('created_at')

        if '#已通过#' in content or '#已退回#' in content:
            m = re.search(r'#(已通过|已退回)#', content)
            if m:
                status = m.group(1)
                status_tag = status
                status_color = 'green' if status == '已通过' else 'red'
                content_parts = re.split(r'(#已通过#|#已退回#)', content)
            else:
                status_tag = None
                status_color = None
                content_parts = [content]
        else:
            status_tag = None
            status_color = None
            content_parts = [content]

        items.append({
            'from_user_id': uid,
            'sender_nick': sender_nick,
            'sender_avatar': sender_avatar,
            'profile_url': profile_url,
            'content': content,
            'content_parts': content_parts,
            'status_tag': status_tag,
            'status_color': status_color,
            'time': _to_time_str(created_at),
            'is_unread': _is_unread(created_at, last_read),
        })

    return items


def _enrich_boards(rows, last_read):
    """把 SQL 结果组装成模板用的 board item"""
    items = []
    for r in rows:
        from_user_id = r.get('from_user_id')
        from_nickname = r.get('from_nickname') or '已注销用户'
        from_avatar = r.get('from_avatar') or DEFAULT_AVATAR
        created_at = r.get('created_at')
        path = r.get('path') or ''
        comment_id = r.get('comment_id')

        content_dict = {
            'id': comment_id,
            'user_id': from_user_id,
            'content': r.get('content') or '',
            'created_at': created_at,
            'nickname': from_nickname,
            'avatar': from_avatar,
            'profile_url': f"/profile/{from_user_id}" if from_user_id else '#',
        }

        target_url = ''
        if path and comment_id:
            target_url = f"{path}#comment-{comment_id}"

        items.append({
            'url': path,
            'content': content_dict,
            'target_url': target_url,
            'is_unread': _is_unread(created_at, last_read),
            'time': _to_time_str(created_at),
        })

    return items


# ============================================================
# 主站三类：分页读取
# ============================================================
def _load_station_page(user_id, category, page=1, per_page=PER_PAGE, last_read=None):
    """
    返回 (items, pagination)
    category: 'reply' / 'system' / 'board'
    """
    if category == 'reply':
        row = count_replies_and_reactions(user_id)
        total = int((row.get('total') if row else 0) or 0)
    elif category == 'system':
        row = count_system_messages(user_id)
        total = int((row.get('total') if row else 0) or 0)
    elif category == 'board':
        row = count_board_messages(f'/profile/{user_id}', user_id)
        total = int((row.get('total') if row else 0) or 0)
    else:
        return [], {
            'page': 1, 'per_page': per_page, 'total': 0,
            'total_pages': 1, 'has_prev': False, 'has_next': False,
        }

    total_pages = max(1, (total + per_page - 1) // per_page)
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1
    page = max(1, min(page, total_pages))

    offset = _station_offset(page, per_page)
    if category == 'reply':
        rows = fetch_replies_and_reactions(user_id, per_page, offset)
        items = _enrich_replies(rows, user_id, last_read)
    elif category == 'system':
        rows = fetch_system_messages(user_id, per_page, offset)
        items = _enrich_system(rows, last_read)
    elif category == 'board':
        board_path = f'/profile/{user_id}'
        rows = fetch_board_messages(board_path, user_id, per_page, offset)
        items = _enrich_boards(rows, last_read)
    else:
        items = []

    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
    }
    return items, pagination


# ============================================================
# 茶室消息
# ============================================================



def _load_tea_messages(user_id, last_read=None, page=1, per_page=PER_PAGE):
    """茶室消息"""
    last_read = _to_time_str(last_read)

    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1
    if page < 1:
        page = 1

    settings = get_notification_settings(user_id)
    tea_reply_on = settings.get('tea_reply', True)
    tea_like_on = settings.get('tea_like', True)
    tea_topic_on = settings.get('tea_topic', True)

    raw_limit = min(per_page * page + 40, TEA_MAX_PER_TYPE)

    items = []
    user_map = {}

    # 1. 别人回复我的帖子
    rows = fetch_tea_replies(user_id, raw_limit)

    if rows:
        user_map.update({
            u['id']: {'nickname': u.get('nickname') or '已注销用户',
                      'avatar': u.get('avatar') or DEFAULT_AVATAR}
            for u in list_users_brief(
                {r['author_id'] for r in rows if r.get('author_id')})
        })

    for r in rows:
        u = user_map.get(r['author_id'], {})
        items.append({
            'type': 'reply',
            'time': _to_time_str(r.get('created_at')),
            'user_id': r['author_id'],
            'nickname': u.get('nickname') or '已注销用户',
            'avatar': u.get('avatar'),
            'content': _strip_html(r.get('content_html') or '', 100),
            'title': r.get('post_title') or '(无标题)',
            'topic': r.get('topic_name') or '',
            'url': f"{TEA_DOMAIN}/post/{r['post_id']}#reply-{r['id']}",
        })

    # 2. 别人点赞我的帖子
    rows = fetch_tea_post_likes(user_id, raw_limit)

    if rows:
        user_map.update({
            u['id']: {'nickname': u.get('nickname') or '已注销用户',
                      'avatar': u.get('avatar') or DEFAULT_AVATAR}
            for u in list_users_brief(
                {r['user_id'] for r in rows if r.get('user_id')} - set(user_map.keys()))
        })

    for r in rows:
        u = user_map.get(r['user_id'], {})
        items.append({
            'type': 'like',
            'time': _to_time_str(r.get('created_at')),
            'user_id': r['user_id'],
            'nickname': u.get('nickname') or '已注销用户',
            'avatar': u.get('avatar'),
            'content': '赞了你的帖子',
            'title': r.get('post_title') or '(无标题)',
            'topic': r.get('topic_name') or '',
            'url': f"{TEA_DOMAIN}/post/{r['post_id']}",
        })

    # 3. 别人点赞我的回复
    rows = fetch_tea_reply_likes(user_id, raw_limit)

    if rows:
        user_map.update({
            u['id']: {'nickname': u.get('nickname') or '已注销用户',
                      'avatar': u.get('avatar') or DEFAULT_AVATAR}
            for u in list_users_brief(
                {r['user_id'] for r in rows if r.get('user_id')} - set(user_map.keys()))
        })

    for r in rows:
        u = user_map.get(r['user_id'], {})
        items.append({
            'type': 'like',
            'time': _to_time_str(r.get('created_at')),
            'user_id': r['user_id'],
            'nickname': u.get('nickname') or '已注销用户',
            'avatar': u.get('avatar'),
            'content': '赞了你的回复：' + _strip_html(r.get('content_html') or '', 60),
            'title': r.get('post_title') or '(无标题)',
            'topic': r.get('topic_name') or '',
            'url': f"{TEA_DOMAIN}/post/{r['post_id']}#reply-{r['reply_id']}",
        })

    # 4. 被话题处罚
    rows = fetch_tea_punishments(user_id, raw_limit)

    if rows:
        user_map.update({
            u['id']: {'nickname': u.get('nickname') or '已注销用户',
                      'avatar': u.get('avatar') or DEFAULT_AVATAR}
            for u in list_users_brief(
                {r['granted_by'] for r in rows if r.get('granted_by')} - set(user_map.keys()))
        })

    _PT_LABEL = {'mute': '禁言', 'ban': '封禁'}
    for r in rows:
        op = user_map.get(r.get('granted_by'), {})
        pt = r.get('punish_type') or 'mute'
        reason = (r.get('reason') or '').strip()
        topic_name = r.get('topic_name') or '未知话题'
        content = f"在 #{topic_name} 内被{_PT_LABEL.get(pt, pt)}"
        if reason:
            content += f"，原因：{reason}"

        items.append({
            'type': 'punish',
            'time': _to_time_str(r.get('created_at')),
            'user_id': r.get('granted_by'),
            'nickname': op.get('nickname') or '茶室系统',
            'avatar': op.get('avatar'),
            'content': content,
            'title': f"#{topic_name}",
            'topic': '',
            'url': (f"{TEA_DOMAIN}/topic/{r['topic_slug']}"
                    if r.get('topic_slug') else '#'),
        })

    # 5. 被任命为护法 / 堂主
    rows = fetch_tea_managements(user_id, raw_limit)

    _ROLE_LABEL = {'owner': '堂主', 'mod': '护法'}
    for r in rows:
        role = r.get('role') or 'mod'
        topic_name = r.get('topic_name') or '未知话题'
        items.append({
            'type': 'manager',
            'time': _to_time_str(r.get('created_at')),
            'user_id': None,
            'nickname': '茶室系统',
            'avatar': None,
            'content': f"你被任命为 #{topic_name} 的{_ROLE_LABEL.get(role, role)}",
            'title': f"#{topic_name}",
            'topic': '',
            'url': (f"{TEA_DOMAIN}/topic/{r['topic_slug']}"
                    if r.get('topic_slug') else '#'),
        })

    # 6. 关注话题有新帖
    rows = fetch_tea_topic_posts(user_id, raw_limit)

    if rows:
        user_map.update({
            u['id']: {'nickname': u.get('nickname') or '已注销用户',
                      'avatar': u.get('avatar') or DEFAULT_AVATAR}
            for u in list_users_brief(
                {r['author_id'] for r in rows if r.get('author_id')} - set(user_map.keys()))
        })

    for r in rows:
        u = user_map.get(r['author_id'], {})
        items.append({
            'type': 'topic',
            'time': _to_time_str(r.get('created_at')),
            'user_id': r['author_id'],
            'nickname': u.get('nickname') or '已注销用户',
            'avatar': u.get('avatar'),
            'content': '在你关注的话题发布了新帖',
            'title': r.get('post_title') or '(无标题)',
            'topic': r.get('topic_name') or '',
            'url': f"{TEA_DOMAIN}/post/{r['post_id']}",
        })

    items.sort(key=lambda x: x.get('time') or '', reverse=True)

    def _is_unread_tea(it):
        t = it.get('time') or ''
        flag = (not last_read) or (t > last_read)
        if it['type'] == 'reply' and not tea_reply_on:
            flag = False
        elif it['type'] == 'like' and not tea_like_on:
            flag = False
        elif it['type'] == 'topic' and not tea_topic_on:
            flag = False
        return flag

    unread_total = sum(1 for it in items if _is_unread_tea(it))

    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page
    page_items = items[offset:offset + per_page]

    for it in page_items:
        it['is_unread'] = _is_unread_tea(it)

    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
    }

    return page_items, unread_total, pagination


def _tea_last_read(user_id):
    """取茶室消息的已读时间基线（user_info.message 列里的小字段）。"""
    import json as _json
    row = get_tea_message_blob(user_id)
    if row and row.get('message'):
        try:
            return _json.loads(row['message']).get('tea_last_read')
        except Exception:
            return None
    return None


# ============================================================
# 【主站】消息中心首页
# ============================================================
@msg_bp.route('/message')
@permissions.login_required()
def messages():
    user_id = session.get('user_info')['id']

    row = get_last_read(user_id)
    last_read = row.get('message_last_read') if row else None

    unread_counts = get_unread_counts(user_id, last_read)

    replies, reply_pagination = _load_station_page(
        user_id, 'reply', page=1, last_read=last_read
    )
    system_msgs, system_pagination = _load_station_page(
        user_id, 'system', page=1, last_read=last_read
    )
    boards, board_pagination = _load_station_page(
        user_id, 'board', page=1, last_read=last_read
    )

    # 茶室消息
    tea_last_read = _tea_last_read(user_id)

    tea_messages, tea_unread, tea_pagination = _load_tea_messages(
        user_id, tea_last_read, page=1, per_page=PER_PAGE
    )
    unread_counts['tea'] = tea_unread

    # 更新 tea_last_read
    if tea_messages:
        try:
            import json as _json
            msg_data = {}
            blob = get_tea_message_blob(user_id)
            if blob and blob.get('message'):
                msg_data = _json.loads(blob['message'])
            msg_data['tea_last_read'] = datetime_fmt.now()
            set_tea_message_blob(
                user_id, _json.dumps(msg_data, ensure_ascii=False)
            )
        except Exception:
            pass

    # 更新主站 last_read
    clear_unread(user_id)

    disabled_notifications = get_disabled_notifications(user_id)

    return render_template(
        'messages.html',
        replies=replies,
        system_messages=system_msgs,
        guestbook_messages=boards,
        tea_messages=tea_messages,
        reply_pagination=reply_pagination,
        system_pagination=system_pagination,
        board_pagination=board_pagination,
        tea_pagination=tea_pagination,
        unread_counts=unread_counts,
        disabled_notifications=disabled_notifications,
    )


# ============================================================
# 【主站】消息翻页 API
# ============================================================
@msg_bp.route('/message/page')
@permissions.login_required()
def message_page():
    user_id = session.get('user_info')['id']

    tab = (request.args.get('tab') or '').strip()
    try:
        page = int(request.args.get('page', 1))
    except (ValueError, TypeError):
        page = 1
    if page < 1:
        page = 1

    row = get_last_read(user_id)
    last_read = row.get('message_last_read') if row else None

    # 茶室
    if tab == 'tea':
        tea_last_read = _tea_last_read(user_id)

        items, _, pagination = _load_tea_messages(
            user_id, tea_last_read, page=page, per_page=PER_PAGE
        )
        for it in items:
            it['time_since'] = timesince(it.get('time') or '')
        return jsonify({'success': True, 'items': items, 'pagination': pagination})

    # 主站三类
    cat_map = {'replies': 'reply', 'system': 'system', 'guestbook': 'board'}
    if tab not in cat_map:
        return jsonify({'success': False, 'message': '无效的 tab'}), 400

    category = cat_map[tab]
    items, pagination = _load_station_page(
        user_id, category, page=page, per_page=PER_PAGE, last_read=last_read
    )

    for item in items:
        if category == 'system':
            item['time_since'] = timesince(item.get('time') or '')
        else:
            created = (item.get('content') or {}).get('created_at') or ''
            item['time_since'] = timesince(created)

    return jsonify({
        'success': True,
        'items': items,
        'pagination': pagination,
    })