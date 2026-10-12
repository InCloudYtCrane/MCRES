# 【主站】utils/msg.py
# 位置：mcres/utils/msg.py
"""
消息工具（Phase 4 后版本）

数据来源变更：
  · 未读     —— 实时 SQL 计算（created_at > message_last_read）
  · 系统消息 —— user_system_message 表
  · 评论回复 / 表态 / 留言 —— 从 comments / comment_reactions 实时查询
  · 茶室     —— 独立（get_tea_unread_count 不变）

已废弃：
  · user_info.message JSON 的 unread / detail 字段不再读写
  · 该字段保留做备份，仅 tea_last_read 还在用
"""
import json
from datetime import datetime, timedelta

from utils.time import datetime_fmt
from utils.data.repositories import messages as messages_repo


# ============================================================
# 主站消息未读数（Phase 4）
# ============================================================

def get_unread_counts(user_id, last_read=None):
    """
    计算某用户的三类未读数。

    参数：
        user_id    用户 ID
        last_read  上次读取时间。不传则从 user_info.message_last_read 读取。

    返回：
        {'reply': int, 'system': int, 'board': int}

    说明：
        · reply  = 别人回复我的评论 + 别人对我评论的表态
        · system = 系统消息（user_system_message 表）
        · board  = 别人在我主页留言（顶层评论）

    通知设置过滤：
        · reply 类：reply 与 reaction 开关**都**开启时才算未读
        · board 类：board 开关开启时才算未读
        · system 类：强制通知，不过滤
    """
    if not user_id:
        return {'reply': 0, 'system': 0, 'board': 0}

    # 读取 last_read
    if last_read is None:
        try:
            row = messages_repo.get_message_last_read(user_id)
            last_read = row.get('message_last_read') if row else None
        except Exception:
            last_read = None

    # 归一化为字符串（MySQL 需要）
    if not last_read:
        last_read_str = '1970-01-01 00:00:00'
    elif hasattr(last_read, 'strftime'):
        last_read_str = last_read.strftime('%Y-%m-%d %H:%M:%S')
    else:
        last_read_str = str(last_read)

    board_path = f'/profile/{user_id}'

    row = messages_repo.get_unread_counts(user_id, board_path, last_read_str)

    if not row:
        return {'reply': 0, 'system': 0, 'board': 0}

    reply_raw  = (row.get('reply_unread') or 0) + (row.get('reaction_unread') or 0)
    system_raw = row.get('system_unread') or 0
    board_raw  = row.get('board_unread') or 0

    # ---------- 通知设置过滤 ----------
    settings = get_notification_settings(user_id)

    # reply tab = 回复 + 表态：两者开关都开才算未读
    reply_on = settings.get('reply', True) and settings.get('reaction', True)
    board_on = settings.get('board', True)
    # system 强制通知，不过滤

    reply  = reply_raw if reply_on else 0
    system = system_raw                      # system 始终保留
    board  = board_raw if board_on else 0

    return {'reply': reply, 'system': system, 'board': board}


def clear_unread(user_id, category=None):
    """
    打开消息页 → 更新 message_last_read = 当前时刻。

    参数：
        user_id   用户 ID
        category  保留但忽略（兼容旧调用）

    说明：
        只影响"未读红点"，不影响消息列表 —— 消息本身一条不删。
    """
    if not user_id:
        return
    messages_repo.clear_unread(user_id, datetime_fmt.now())


def add_system_message(user_id, from_user_id, content):
    """
    给用户添加一条系统消息。

    Phase 4：只写 user_system_message 表。
    （不再写 user_info.message JSON —— 该字段保留做历史备份）
    """
    if not user_id:
        return
    messages_repo.add_system_message(user_id, from_user_id, content,
                                    datetime_fmt.now())


# ============================================================
# 兼容保留：空操作（防止漏看的调用点报错）
# ============================================================

def apply_notification_filter(user_id, msg_data):
    """
    Phase 4：未读改由 get_unread_counts 实时算，
    本函数保留为空操作，仅用于兼容可能遗留的调用。
    """
    return msg_data


# ============================================================
# 通知设置相关工具函数（完全保留）
# ============================================================

# 通知类别 → 中文 label
NOTIFICATION_LABELS = {
    'reply':     '回复与@',
    'reaction':  '表态',
    'board':     '留言板',
    'tea_reply': '茶室回复',
    'tea_like':  '茶室点赞',
    'tea_topic': '关注话题新帖',
}


def get_notification_settings(user_id):
    """
    获取用户的通知设置，返回字典。
    系统消息(system)强制通知，不包含在设置中。
    """
    default = {
        'reply': True,
        'reaction': True,
        'board': True,
        'tea_reply': True,
        'tea_like': True,
        'tea_topic': True,
    }
    row = messages_repo.get_notification_settings_raw(user_id)
    if row and row.get('notification_settings'):
        try:
            settings = json.loads(row['notification_settings'])
            if isinstance(settings, dict):
                default.update(settings)
                return default
        except:
            pass
    return default


def should_notify(user_id, category):
    """
    检查用户是否开启某类通知
    category: 'reply', 'reaction', 'board', 'tea_reply', 'tea_like', 'tea_topic'
    系统消息 'system' 不受设置控制，始终返回 True
    """
    if category == 'system':
        return True
    settings = get_notification_settings(user_id)
    return settings.get(category, True)


def get_disabled_notifications(user_id):
    """
    返回被用户关闭的通知类别列表，用于消息页顶部提示条。
    """
    settings = get_notification_settings(user_id)
    disabled = []
    for key, label in NOTIFICATION_LABELS.items():
        if not settings.get(key, True):
            disabled.append({'key': key, 'label': label})
    return disabled


# ============================================================
# 茶室未读数（用于 navbar 红点）—— 完全不动
# ------------------------------------------------------------
# 说明：
#   · 与 views/message.py 里 _load_tea_messages 的统计口径一致
#   · 用单条 SQL（UNION 子查询相加）完成 6 类统计
#   · tea_last_read 为空时，按「最近 7 天」做兜底
#   · 受通知设置控制
# ============================================================
def get_tea_unread_count(user_id, tea_last_read=None, notif_settings=None):
    """计算某用户的茶室未读数，用于 navbar 红点。"""
    if not user_id:
        return 0

    if notif_settings is None:
        notif_settings = get_notification_settings(user_id)

    tea_reply_on = notif_settings.get('tea_reply', True)
    tea_like_on  = notif_settings.get('tea_like', True)
    tea_topic_on = notif_settings.get('tea_topic', True)

    if tea_last_read:
        threshold = tea_last_read
    else:
        threshold = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

    subqueries = []
    params = []

    if tea_reply_on:
        subqueries.append(
            "(SELECT COUNT(*) FROM tea_reply r "
            " INNER JOIN tea_post p ON r.post_id = p.id "
            " WHERE p.author_id = %s AND r.author_id != %s "
            "   AND r.status = 'published' AND p.status = 'published' "
            "   AND r.created_at > %s)"
        )
        params += [user_id, user_id, threshold]

    if tea_like_on:
        subqueries.append(
            "(SELECT COUNT(*) FROM tea_like l "
            " INNER JOIN tea_post p ON l.target_id = p.id "
            " WHERE l.target_type = 'post' "
            "   AND p.author_id = %s AND l.user_id != %s "
            "   AND p.status = 'published' "
            "   AND l.created_at > %s)"
        )
        params += [user_id, user_id, threshold]

        subqueries.append(
            "(SELECT COUNT(*) FROM tea_like l "
            " INNER JOIN tea_reply r ON l.target_id = r.id "
            " WHERE l.target_type = 'reply' "
            "   AND r.author_id = %s AND l.user_id != %s "
            "   AND r.status = 'published' "
            "   AND l.created_at > %s)"
        )
        params += [user_id, user_id, threshold]

    if tea_topic_on:
        subqueries.append(
            "(SELECT COUNT(*) FROM tea_topic_follow f "
            " INNER JOIN tea_post  p ON p.topic_id = f.topic_id "
            " INNER JOIN tea_topic t ON f.topic_id = t.id "
            " WHERE f.user_id = %s AND p.author_id != %s "
            "   AND p.status = 'published' AND t.level != 4 "
            "   AND p.created_at > %s)"
        )
        params += [user_id, user_id, threshold]

    subqueries.append(
        "(SELECT COUNT(*) FROM tea_topic_punish "
        " WHERE user_id = %s AND created_at > %s)"
    )
    params += [user_id, threshold]

    subqueries.append(
        "(SELECT COUNT(*) FROM tea_topic_manager "
        " WHERE user_id = %s AND created_at > %s)"
    )
    params += [user_id, threshold]

    if not subqueries:
        return 0

    return messages_repo.get_tea_unread_total(subqueries, params)
