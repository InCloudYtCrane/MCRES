# utils/data/repositories/messages.py
"""站内信 / 未读计数 / 通知设置的查询。

这批查询原先内联在 `utils/msg.py` 里，其中两条是**全站最贵的查询**：
`get_unread_counts`（4 个关联子查询）与 `get_tea_unread_count`（最多 6 个），
都由模板上下文处理器在**每次页面渲染**时调用。

SQL 文本逐字照搬，未改变语义。后续若要缓存或改写为计数表，只需改本模块。
"""
from utils.data import execute_update, fetch_one


# ============================================================
# 读
# ============================================================
def get_unread_counts(user_id, board_path, last_read_str):
    """主站三类未读的原始计数（未做通知设置过滤）。

    对应原 `utils/msg.py:71-99` 的单条多子查询 SQL。
    返回 {'reply_unread', 'reaction_unread', 'board_unread', 'system_unread'}；
    查询失败返回 None，由调用方决定兜底值。
    """
    sql = """
        SELECT
            (SELECT COUNT(*) FROM comments c
             INNER JOIN comments p ON c.parent_id = p.id
             WHERE p.user_id = %s AND c.user_id != %s
               AND c.is_deleted = 0 AND p.is_deleted = 0
               AND c.created_at > %s) AS reply_unread,

            (SELECT COUNT(*) FROM comment_reactions r
             INNER JOIN comments c ON r.comment_id = c.id
             WHERE c.user_id = %s AND r.user_id != %s
               AND c.is_deleted = 0
               AND r.created_at > %s) AS reaction_unread,

            (SELECT COUNT(*) FROM comments c
             WHERE c.path = %s AND c.parent_id = 0
               AND c.user_id != %s AND c.is_deleted = 0
               AND c.created_at > %s) AS board_unread,

            (SELECT COUNT(*) FROM user_system_message
             WHERE user_id = %s AND created_at > %s) AS system_unread
    """
    params = [
        user_id, user_id, last_read_str,
        user_id, user_id, last_read_str,
        board_path, user_id, last_read_str,
        user_id, last_read_str,
    ]
    try:
        return fetch_one(sql, params)
    except Exception:
        return None


def get_tea_unread_total(subqueries, params):
    """茶室未读总数。

    子查询片段与参数由 `utils/msg.py` 按通知设置**动态拼装**（只含 `%s` 占位与
    固定列名，不含用户输入），因此这里接收拼好的片段。
    返回整数；查询失败返回 0。
    """
    if not subqueries:
        return 0
    try:
        sql = 'SELECT (' + ' + '.join(subqueries) + ') AS total'
        row = fetch_one(sql, params)
        return int((row['total'] if row else 0) or 0)
    except Exception:
        return 0


def get_notification_settings_raw(user_id):
    """取通知设置 JSON 原文（未解析、未合并默认值）。

    对应原 `utils/msg.py:203`。合并默认值与类型校验属于业务规则，
    留在 `msg.py`。
    """
    return fetch_one(
        'SELECT notification_settings FROM user_info WHERE id = %s',
        [user_id],
    )


def get_message_last_read(user_id):
    """取 message_last_read（未读数计算的时间基线）。"""
    return fetch_one(
        'SELECT message_last_read FROM user_info WHERE id = %s',
        [user_id],
    )


# ============================================================
# 写
# ============================================================
def clear_unread(user_id, now_str):
    """把 message_last_read 置为当前时刻（只影响红点，不删消息）。"""
    return execute_update(
        'UPDATE user_info SET message_last_read = %s WHERE id = %s',
        [now_str, user_id],
    )


def add_system_message(user_id, from_user_id, content, now_str):
    """写入一条系统消息（只写 user_system_message 表）。"""
    return execute_update(
        'INSERT INTO user_system_message '
        '(user_id, from_user_id, content, created_at) '
        'VALUES (%s, %s, %s, %s)',
        [user_id, from_user_id, content, now_str],
    )
