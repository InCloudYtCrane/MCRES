# utils/data/repositories/comments.py
"""评论（comments / comment_reactions）的查询。

原先散落在 `mcres/views/comment.py` 的 38 处调用里。抽取时顺带定位到一个
**重复查询**：`comments` 的顶层分页、置顶分页、child 查询、总数统计
各自独立，但"取某 path 下顶层评论"被分页与置顶两处重复实现。

返回的仍是 DictCursor 行（dict），字段加工留在视图层。
"""
from utils.data import execute_query, execute_update, fetch_one

#: 列表接口返回给前端的评论列
LIST_COLUMNS = ('id, path, user_id, parent_id, reply_to, reply_to_id, '
                'ip_region, content, is_pinned, created_at')


# ============================================================
# 读
# ============================================================
def list_by_path(path):
    """某 path 下全部评论（顶层+子），按 created_at 升序（旧兼容接口）。"""
    return execute_query(
        f'''SELECT {LIST_COLUMNS}
            FROM comments
            WHERE path = %s AND is_deleted = 0
            ORDER BY created_at ASC''',
        [path],
    ) or []


def get(comment_id, columns='*'):
    """按 id 取评论。"""
    return fetch_one(
        f'SELECT {columns} FROM comments WHERE id = %s', [comment_id])


def list_pinned_top(path):
    """某 path 下已置顶的顶层评论。"""
    return execute_query(
        '''SELECT * FROM comments
           WHERE path = %s AND parent_id = 0 AND is_pinned = 1 AND is_deleted = 0
           ORDER BY created_at DESC''',
        [path],
    ) or []


def count_top_not_pinned(path):
    """某 path 下未置顶顶层评论总数。"""
    row = fetch_one(
        '''SELECT COUNT(*) AS c FROM comments
           WHERE path = %s AND parent_id = 0 AND is_pinned = 0 AND is_deleted = 0''',
        [path],
    )
    return (row['c'] if row else 0) or 0


def count_all_by_path(path):
    """某 path 下全部未删除评论数（含子评论）。"""
    row = fetch_one(
        'SELECT COUNT(*) AS c FROM comments WHERE path = %s AND is_deleted = 0',
        [path],
    )
    return (row['c'] if row else 0) or 0


def list_top_not_pinned_page(path, limit, offset):
    """未置顶顶层评论分页（按 created_at 倒序）。"""
    return execute_query(
        '''SELECT * FROM comments
           WHERE path = %s AND parent_id = 0 AND is_pinned = 0 AND is_deleted = 0
           ORDER BY created_at DESC
           LIMIT %s OFFSET %s''',
        [path, limit, offset],
    ) or []


def list_children(parent_ids):
    """按父评论 id 集合取子评论（按 created_at 升序）。"""
    if not parent_ids:
        return []
    placeholders = ','.join(['%s'] * len(parent_ids))
    return execute_query(
        f'''SELECT * FROM comments
            WHERE parent_id IN ({placeholders}) AND is_deleted = 0
            ORDER BY created_at ASC''',
        list(parent_ids),
    ) or []


def list_ids_by_user(ids):
    """按 id 集合取 (id, user_id)，用于回复对象解析。"""
    if not ids:
        return []
    placeholders = ','.join(['%s'] * len(ids))
    return execute_query(
        f'SELECT id, user_id FROM comments WHERE id IN ({placeholders})',
        list(ids),
    ) or []


def list_children_ids(parent_ids):
    """按父 id 集合取子评论 id（删除时递归收集用）。"""
    if not parent_ids:
        return []
    placeholders = ','.join(['%s'] * len(parent_ids))
    return execute_query(
        f'SELECT id FROM comments WHERE parent_id IN ({placeholders})',
        list(parent_ids),
    ) or []


def count_newer_top(path, created_at):
    """统计某 path 下比给定时间更新的未置顶顶层评论数（用于定位评论在第几页）。"""
    row = fetch_one(
        '''SELECT COUNT(*) AS c FROM comments
           WHERE path = %s
             AND parent_id = 0
             AND is_pinned = 0
             AND is_deleted = 0
             AND created_at > %s''',
        [path, created_at],
    )
    return (row['c'] if row else 0) or 0


def find_by_id_and_path(comment_id, path, columns='id, parent_id, is_pinned, created_at'):
    """定位评论：按 id 在该 path 下查找未删除评论。"""
    return fetch_one(
        f'SELECT {columns} FROM comments '
        f'WHERE id = %s AND path = %s AND is_deleted = 0',
        [comment_id, path],
    )


def find_by_old_uuid_and_path(old_uuid, path, columns='id, parent_id, is_pinned, created_at'):
    """定位评论：按旧 uuid 在该 path 下查找未删除评论。"""
    return fetch_one(
        f'SELECT {columns} FROM comments '
        f'WHERE old_uuid = %s AND path = %s AND is_deleted = 0',
        [old_uuid, path],
    )


def insert_report(target_user_id, reporter_id, reason, content, now):
    """写入一条评论举报（user_reports 表）。"""
    return execute_update(
        'INSERT INTO user_reports '
        '(target_user_id, reporter_id, reason, content, is_handled, created_at) '
        'VALUES (%s, %s, %s, %s, 0, %s)',
        [target_user_id, reporter_id, reason, content, now],
    )


def list_authors(user_ids):
    """批量取评论作者信息（id, nickname, avatar, titles）。

    只服务于评论富化，故留在本模块而不是 users.py。
    """
    if not user_ids:
        return []
    placeholders = ','.join(['%s'] * len(user_ids))
    return execute_query(
        f'SELECT id, nickname, avatar, titles FROM user_info '
        f'WHERE id IN ({placeholders})',
        list(user_ids),
    ) or []


def list_reactions_for_comments(comment_ids):
    """批量取评论的表态（comment_id, reaction_type, user_id）。"""
    if not comment_ids:
        return []
    placeholders = ','.join(['%s'] * len(comment_ids))
    return execute_query(
        f'SELECT comment_id, reaction_type, user_id '
        f'FROM comment_reactions WHERE comment_id IN ({placeholders})',
        list(comment_ids),
    ) or []


def count_reactions_grouped(comment_id):
    """单条评论的表态计数，按类型分组。"""
    return execute_query(
        'SELECT reaction_type, COUNT(*) AS cnt FROM comment_reactions '
        'WHERE comment_id = %s GROUP BY reaction_type',
        [comment_id],
    ) or []


def get_reaction(comment_id, user_id):
    """取某用户对某评论的现有表态类型。"""
    return fetch_one(
        'SELECT reaction_type FROM comment_reactions '
        'WHERE comment_id = %s AND user_id = %s',
        [comment_id, user_id],
    )


# ============================================================
# 写
# ============================================================
def insert(path, user_id, parent_id, reply_to, reply_to_id, ip_region,
           content, now):
    """新增一条评论。"""
    return execute_update(
        '''INSERT INTO comments
           (path, user_id, parent_id, reply_to, reply_to_id, ip_region,
            content, is_pinned, is_deleted, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0, %s)''',
        [path, user_id, parent_id or 0, reply_to, reply_to_id, ip_region,
         content, now],
    )


def find_last_id(path, user_id):
    """取该用户在该 path 下最近插入的评论 id。

    注意：调用方原先用"按 id 倒序取第一条"来猜刚插入的行，
    并发插入时可能取错行。此处**保持原语义**。
    """
    return fetch_one(
        'SELECT id FROM comments WHERE path = %s AND user_id = %s '
        'ORDER BY id DESC LIMIT 1',
        [path, user_id],
    )


def soft_delete_many(comment_ids):
    """批量软删除评论（含回复）。"""
    if not comment_ids:
        return 0
    placeholders = ','.join(['%s'] * len(comment_ids))
    return execute_update(
        f'UPDATE comments SET is_deleted = 1 WHERE id IN ({placeholders})',
        list(comment_ids),
    )


def set_pinned(comment_id, pinned):
    """把单条评论设为/取消置顶。"""
    return execute_update(
        'UPDATE comments SET is_pinned = %s WHERE id = %s',
        [1 if pinned else 0, comment_id],
    )


def clear_pinned_in_path(path):
    """清除该 path 下全部顶层置顶（置顶前先清空）。"""
    return execute_update(
        'UPDATE comments SET is_pinned = 0 '
        'WHERE path = %s AND parent_id = 0 AND is_pinned = 1',
        [path],
    )


def upsert_reaction(comment_id, user_id, reaction_type, now):
    """写入/替换表态。

    原实现用的是 `REPLACE INTO`（不是 INSERT + UPDATE 两步），
    因此这里也保留 REPLACE：它在 (comment_id, user_id) 唯一键上做
    先删后插，语义与"覆盖该用户的表态"一致。
    """
    return execute_update(
        '''REPLACE INTO comment_reactions
           (comment_id, user_id, reaction_type, created_at)
           VALUES (%s, %s, %s, %s)''',
        [comment_id, user_id, reaction_type, now],
    )


def delete_reaction(comment_id, user_id):
    """删除某用户对某评论的表态（取消表态）。"""
    return execute_update(
        'DELETE FROM comment_reactions WHERE comment_id = %s AND user_id = %s',
        [comment_id, user_id],
    )
