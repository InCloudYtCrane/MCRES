# utils/data/repositories/scheduling.py
"""定时任务（每日归档 / PV 保存 / 历史补全 / 评论清理）的数据访问。

原先内联在 `utils/scheduling/scheduler.py`。这些 SQL 不在请求路径上，
因此渲染回归与 SQL 指纹都覆盖不到 —— SQL 文本逐字照搬，未做任何改写。

两张 PV 聚合查询的列别名刻意保持原样不同（`pv_count` / `cnt`），
因为调用方分别按这两个键取值；统一别名会静默取到 None。
"""
from utils.data import execute_query, execute_update

#: 单次物理删除上限：防止一次锁表太久，超出的留给下次调度
_CLEANUP_BATCH = 2000


# ============================================================
# 清理过期软删评论
# ============================================================
def list_purgeable_comment_ids(cutoff):
    """N 天前软删的评论 id，单次最多 `_CLEANUP_BATCH` 条。"""
    return execute_query(
        'SELECT id FROM comments '
        'WHERE is_deleted = 1 AND created_at < %s '
        f'LIMIT {_CLEANUP_BATCH}',
        [cutoff],
    )


def _placeholders(values):
    """`IN (%s, %s, ...)` 的占位符串；values 不能为空。"""
    return ','.join(['%s'] * len(values))


def delete_comment_reactions(comment_ids):
    """按评论 id 批量删除表态（先删，避免孤儿）。"""
    return execute_update(
        f'DELETE FROM comment_reactions WHERE comment_id IN ({_placeholders(comment_ids)})',
        comment_ids,
    )


def delete_comments(comment_ids):
    """按评论 id 批量物理删除评论。"""
    return execute_update(
        f'DELETE FROM comments WHERE id IN ({_placeholders(comment_ids)})',
        comment_ids,
    )


# ============================================================
# 每日 PV：聚合 / 落表 / 清理
# ============================================================
def aggregate_daily_pv(day):
    """某天各资源的 PV 聚合（列别名 `pv_count`）。"""
    return execute_query("""
        SELECT resource_type, resource_id, COUNT(*) AS pv_count
        FROM resource_view_log
        WHERE DATE(visit_time) = %s
        GROUP BY resource_type, resource_id
    """, [day])


def upsert_daily_pv(resource_type, resource_id, day, pv):
    """写入/覆盖某资源某天的 PV。"""
    return execute_update(
        'INSERT INTO resource_daily_pv (resource_type, resource_id, date, pv) '
        'VALUES (%s, %s, %s, %s) '
        'ON DUPLICATE KEY UPDATE pv = VALUES(pv)',
        [resource_type, resource_id, day, pv],
    )


def delete_daily_pv_older_than_365d():
    """清理 365 天前的 PV 记录。"""
    return execute_update(
        'DELETE FROM resource_daily_pv '
        'WHERE date < DATE_SUB(CURDATE(), INTERVAL 365 DAY)',
        [],
    )


# ============================================================
# 历史 PV 补全
# ============================================================
def list_pv_dates():
    """`resource_view_log` 里所有有 PV 记录的日期（升序）。"""
    return execute_query("""
        SELECT DISTINCT DATE(visit_time) AS date
        FROM resource_view_log
        ORDER BY date
    """)


def aggregate_daily_pv_for_backfill(day):
    """补全用的某天 PV 聚合（列别名 `cnt`，与 `aggregate_daily_pv` 不同）。"""
    return execute_query(
        'SELECT resource_type, resource_id, COUNT(*) AS cnt '
        'FROM resource_view_log '
        'WHERE DATE(visit_time) = %s '
        'GROUP BY resource_type, resource_id',
        [day],
    )


def insert_daily_pv_if_absent(resource_type, resource_id, day, pv):
    """补历史：已存在的日期不覆盖。"""
    return execute_update(
        'INSERT IGNORE INTO resource_daily_pv '
        '(resource_type, resource_id, date, pv) VALUES (%s, %s, %s, %s)',
        [resource_type, resource_id, day, pv],
    )


# ============================================================
# 归档收尾
# ============================================================
def restore_daily_reputation():
    """每日名誉恢复：+3，上限 100，只动 0 < reputation < 100 的行。"""
    return execute_update('''
        UPDATE user_info
        SET reputation = LEAST(reputation + 3, 100)
        WHERE reputation > 0 AND reputation < 100
    ''', [])
