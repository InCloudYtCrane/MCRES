# utils/data/repositories/message_center.py
"""消息中心（主站三类 + 茶室）的查询。

这批查询原先内联在 `mcres/views/message.py` 里。SQL 文本逐字照搬，
只做了两件与语义无关的整理：

1. 分页参数的计算留在视图（`offset = (page - 1) * per_page`），
   仓储只接收最终的 `limit / offset`；
2. 视图里原先的 `db.execute_query(...) or []` 全部合并进仓储的
   `or []`，调用方不再重复兜底。
"""
from utils.data import execute_query, execute_update, fetch_one


# ============================================================
# 主站：回复 + 表态
# ============================================================
def count_replies_and_reactions(user_id):
    """reply 类别总数（回复 + 表态）。

    返回 dict（含 `total` 列），与调用方 `row.get('total')` 的形状一致。
    """
    sql = """
        SELECT
            (SELECT COUNT(*) FROM comments c
             INNER JOIN comments p ON c.parent_id = p.id
             WHERE p.user_id = %s AND c.user_id != %s
               AND c.is_deleted = 0 AND p.is_deleted = 0)
          + (SELECT COUNT(*) FROM comment_reactions r
             INNER JOIN comments c ON r.comment_id = c.id
             WHERE c.user_id = %s AND r.user_id != %s
               AND c.is_deleted = 0) AS total
    """
    return fetch_one(sql, [user_id, user_id, user_id, user_id])


def fetch_replies_and_reactions(user_id, limit, offset):
    """reply 类别分页（回复 + 表态 UNION）。"""
    sql = """
        SELECT * FROM (
            -- 别人回复我
            SELECT
                'reply' AS _subtype,
                c.id AS comment_id,
                c.user_id AS from_user_id,
                c.content AS content,
                c.created_at AS created_at,
                c.path AS path,
                c.reply_to_id AS reply_to_id,
                p.content AS parent_content,
                p.user_id AS parent_user_id,
                NULL AS reaction_type,
                NULL AS target_content,
                u.nickname AS from_nickname,
                u.avatar AS from_avatar,
                pu.nickname AS parent_nickname
            FROM comments c
            INNER JOIN comments p ON c.parent_id = p.id
            LEFT JOIN user_info u ON c.user_id = u.id
            LEFT JOIN user_info pu ON p.user_id = pu.id
            WHERE p.user_id = %s AND c.user_id != %s
              AND c.is_deleted = 0 AND p.is_deleted = 0

            UNION ALL

            -- 别人对我的评论表态
            SELECT
                'reaction' AS _subtype,
                c.id AS comment_id,
                r.user_id AS from_user_id,
                NULL AS content,
                r.created_at AS created_at,
                c.path AS path,
                NULL AS reply_to_id,
                NULL AS parent_content,
                c.user_id AS parent_user_id,
                r.reaction_type AS reaction_type,
                c.content AS target_content,
                u.nickname AS from_nickname,
                u.avatar AS from_avatar,
                NULL AS parent_nickname
            FROM comment_reactions r
            INNER JOIN comments c ON r.comment_id = c.id
            LEFT JOIN user_info u ON r.user_id = u.id
            WHERE c.user_id = %s AND r.user_id != %s
              AND c.is_deleted = 0
        ) t
        ORDER BY t.created_at DESC, t.comment_id DESC
        LIMIT %s OFFSET %s
    """
    return execute_query(
        sql,
        [user_id, user_id, user_id, user_id, limit, offset]
    ) or []


# ============================================================
# 主站：系统消息
# ============================================================
def count_system_messages(user_id):
    """system 类别总数。返回 dict（含 `total` 列）。"""
    return fetch_one(
        'SELECT COUNT(*) AS total FROM user_system_message WHERE user_id = %s',
        [user_id]
    )


def fetch_system_messages(user_id, limit, offset):
    """system 类别分页。"""
    return execute_query(
        '''SELECT id, from_user_id, content, created_at
           FROM user_system_message
           WHERE user_id = %s
           ORDER BY created_at DESC, id DESC
           LIMIT %s OFFSET %s''',
        [user_id, limit, offset]
    ) or []


# ============================================================
# 主站：留言板
# ============================================================
def count_board_messages(board_path, user_id):
    """board 类别总数。返回 dict（含 `total` 列）。"""
    return fetch_one(
        '''SELECT COUNT(*) AS total FROM comments
           WHERE path = %s AND parent_id = 0
             AND user_id != %s AND is_deleted = 0''',
        [board_path, user_id]
    )


def fetch_board_messages(board_path, user_id, limit, offset):
    """board 类别分页。"""
    return execute_query(
        '''SELECT c.id AS comment_id,
                  c.user_id AS from_user_id,
                  c.content,
                  c.created_at,
                  c.path,
                  u.nickname AS from_nickname,
                  u.avatar AS from_avatar
           FROM comments c
           LEFT JOIN user_info u ON c.user_id = u.id
           WHERE c.path = %s AND c.parent_id = 0
             AND c.user_id != %s AND c.is_deleted = 0
           ORDER BY c.created_at DESC, c.id DESC
           LIMIT %s OFFSET %s''',
        [board_path, user_id, limit, offset]
    ) or []


# ============================================================
# 通用：批量取用户显示信息
# ============================================================
def list_users_brief(user_ids):
    """按 id 批量取 (id, nickname, avatar)。user_ids 必须是已去重的序列。"""
    user_ids = list(user_ids)
    if not user_ids:
        return []
    ph = ','.join(['%s'] * len(user_ids))
    return execute_query(
        f'SELECT id, nickname, avatar FROM user_info WHERE id IN ({ph})',
        user_ids
    ) or []


# ============================================================
# 茶室：六类消息
# ============================================================
def fetch_tea_replies(user_id, limit):
    """别人回复我的帖子。"""
    return execute_query(
        '''SELECT r.id, r.post_id, r.floor, r.content_html, r.created_at,
                  r.author_id,
                  p.title AS post_title,
                  t.name  AS topic_name
           FROM tea_reply r
           INNER JOIN tea_post  p ON r.post_id = p.id
           LEFT JOIN  tea_topic t ON p.topic_id = t.id
           WHERE p.author_id = %s
             AND r.author_id != %s
             AND r.status = 'published'
             AND p.status = 'published'
           ORDER BY r.created_at DESC
           LIMIT %s''',
        [user_id, user_id, limit]
    ) or []


def fetch_tea_post_likes(user_id, limit):
    """别人点赞我的帖子。"""
    return execute_query(
        '''SELECT l.id, l.created_at, l.user_id,
                  p.id AS post_id, p.title AS post_title,
                  t.name AS topic_name
           FROM tea_like l
           INNER JOIN tea_post  p ON l.target_id = p.id
           LEFT JOIN  tea_topic t ON p.topic_id = t.id
           WHERE l.target_type = 'post'
             AND p.author_id = %s
             AND l.user_id != %s
             AND p.status = 'published'
           ORDER BY l.created_at DESC
           LIMIT %s''',
        [user_id, user_id, limit]
    ) or []


def fetch_tea_reply_likes(user_id, limit):
    """别人点赞我的回复。"""
    return execute_query(
        '''SELECT l.id, l.created_at, l.user_id,
                  r.id AS reply_id, r.post_id, r.content_html,
                  p.title AS post_title,
                  t.name  AS topic_name
           FROM tea_like l
           INNER JOIN tea_reply r ON l.target_id = r.id
           INNER JOIN tea_post  p ON r.post_id = p.id
           LEFT JOIN  tea_topic t ON p.topic_id = t.id
           WHERE l.target_type = 'reply'
             AND r.author_id = %s
             AND l.user_id != %s
             AND r.status = 'published'
           ORDER BY l.created_at DESC
           LIMIT %s''',
        [user_id, user_id, limit]
    ) or []


def fetch_tea_punishments(user_id, limit):
    """被话题处罚。"""
    return execute_query(
        '''SELECT tp.id, tp.created_at, tp.punish_type, tp.reason,
                  tp.granted_by,
                  t.slug AS topic_slug, t.name AS topic_name
           FROM tea_topic_punish tp
           LEFT JOIN tea_topic t ON tp.topic_id = t.id
           WHERE tp.user_id = %s
           ORDER BY tp.created_at DESC
           LIMIT %s''',
        [user_id, limit]
    ) or []


def fetch_tea_managements(user_id, limit):
    """被任命为护法 / 堂主。"""
    return execute_query(
        '''SELECT tm.id, tm.created_at, tm.role,
                  t.slug AS topic_slug, t.name AS topic_name
           FROM tea_topic_manager tm
           INNER JOIN tea_topic t ON tm.topic_id = t.id
           WHERE tm.user_id = %s
           ORDER BY tm.created_at DESC
           LIMIT %s''',
        [user_id, limit]
    ) or []


def fetch_tea_topic_posts(user_id, limit):
    """关注话题有新帖。"""
    return execute_query(
        '''SELECT p.id AS post_id, p.title AS post_title, p.created_at,
                  p.author_id,
                  t.slug AS topic_slug, t.name AS topic_name
           FROM tea_topic_follow f
           INNER JOIN tea_post  p ON p.topic_id = f.topic_id
           INNER JOIN tea_topic t ON f.topic_id = t.id
           WHERE f.user_id = %s
             AND p.author_id != %s
             AND p.status = 'published'
             AND t.level != 4
           ORDER BY p.created_at DESC
           LIMIT %s''',
        [user_id, user_id, limit]
    ) or []


# ============================================================
# user_info 上的两个消息相关列
# ============================================================
def get_last_read(user_id):
    """取 message_last_read（主站三类未读的时间基线）。返回 dict 或 None。"""
    return fetch_one(
        'SELECT message_last_read FROM user_info WHERE id = %s',
        [user_id]
    )


def get_tea_message_blob(user_id):
    """取 message 列 JSON 原文（内含 tea_last_read）。返回 dict 或 None。"""
    return fetch_one('SELECT message FROM user_info WHERE id = %s', [user_id])


def set_tea_message_blob(user_id, blob):
    """写回 message 列 JSON 原文。"""
    return execute_update(
        'UPDATE user_info SET message = %s WHERE id = %s',
        [blob, user_id]
    )
