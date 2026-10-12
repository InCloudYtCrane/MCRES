# utils/data/repositories/achievements.py
"""成就系统的数据访问。

覆盖三块：

1. 成就定义表 `achievements`（`utils/achievements/engine.py` 的定义加载与指纹）
2. 用户进度表 `user_achievements`（引擎的评定/手动授予/展示，以及
   `utils/achievements/storage.py` 的全部读写）
3. checker 用的统计查询（`action_log` / `resource_versions` / 三张互动表）

原先 SQL 散在 `engine.py`、`storage.py`、`checkers.py` 三个文件里，
其中 `storage.upsert` 与 `engine._evaluate_user` 的 INSERT ... ON DUPLICATE
只差几处换行，已合并成同一个 `upsert_progress`。

**SQL 文本逐字照搬**（比对时只忽略空白与缩进），未改语义。
"""
from utils.constants import RESOURCE_TABLE
from utils.data import execute_query, execute_update, fetch_one

#: 允许参与互动统计的三张表（checker 的 params 可指定，必须白名单校验）
INTERACTION_TABLES = frozenset({
    'resource_likes',
    'resource_coins',
    'resource_favorites',
})


def _checked_table(table, allowed):
    """表名白名单校验 —— 这些名字来自 checker 的 params JSON，不能直接进 SQL。"""
    if table not in allowed:
        raise ValueError(f'非法的表名: {table!r}')
    return table


# ============================================================
# 成就定义（achievements）
# ============================================================
def get_active_definitions_fingerprint():
    """启用的成就定义的 (条数, 最大更新时间戳)，用于判断是否需要重载。"""
    return fetch_one(
        'SELECT COUNT(*) AS n, '
        '       UNIX_TIMESTAMP(MAX(updated_at)) AS t '
        'FROM achievements WHERE is_active = 1'
    )


def list_active_definitions():
    """全部启用的成就定义（按 sort_order / key 排序）。"""
    return execute_query(
        'SELECT * FROM achievements WHERE is_active = 1 '
        'ORDER BY sort_order, `key`'
    )


def list_daily_achievement_keys():
    """所有启用的每日成就 key（元成就 checker 用）。"""
    return execute_query(
        "SELECT `key` FROM achievements "
        "WHERE is_active = 1 AND category = 'daily'"
    )


def list_evaluable_user_ids():
    """参与全量成就评定的用户（role > 0，即非封禁用户）。"""
    return execute_query('SELECT id FROM user_info WHERE role > 0')


# ============================================================
# 用户进度（user_achievements）
# ============================================================
def get_progress_state(user_id, achievement_key, period_key):
    """进度 + 完成时间（引擎评定前的存在性检查）。"""
    return fetch_one(
        'SELECT progress, completed_at FROM user_achievements '
        'WHERE user_id = %s AND achievement_key = %s AND period_key = %s',
        [user_id, achievement_key, period_key],
    )


def get_progress(user_id, achievement_key, period_key):
    """进度 + 目标 + 完成时间 + 是否已发奖（storage 的完整形态）。"""
    return fetch_one(
        '''SELECT progress, target, completed_at, reward_granted
           FROM user_achievements
           WHERE user_id = %s AND achievement_key = %s AND period_key = %s''',
        [user_id, achievement_key, period_key],
    )


def get_completed_at(user_id, achievement_key, period_key):
    """只取完成时间（手动授予前的重复判定）。"""
    return fetch_one(
        'SELECT completed_at FROM user_achievements '
        'WHERE user_id = %s AND achievement_key = %s AND period_key = %s',
        [user_id, achievement_key, period_key],
    )


def upsert_progress(user_id, achievement_key, period_key, progress, target,
                    completed_at, updated_at):
    """写入进度；`completed_at` 一旦写入不会被覆盖。"""
    return execute_update(
        '''INSERT INTO user_achievements
               (user_id, achievement_key, period_key,
                progress, target, completed_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE
               progress     = VALUES(progress),
               target       = VALUES(target),
               completed_at = COALESCE(completed_at, VALUES(completed_at)),
               updated_at   = VALUES(updated_at)''',
        [user_id, achievement_key, period_key, progress, target,
         completed_at, updated_at],
    )


def upsert_manual_completion(user_id, achievement_key, period_key, progress,
                             target, now):
    """人工授予：直接标记为已完成（不保留旧的 completed_at）。"""
    return execute_update(
        '''INSERT INTO user_achievements
               (user_id, achievement_key, period_key,
                progress, target, completed_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE
               progress     = VALUES(progress),
               completed_at = VALUES(completed_at),
               updated_at   = VALUES(updated_at)''',
        [user_id, achievement_key, period_key, progress, target, now, now],
    )


def mark_reward_granted(user_id, achievement_key, period_key):
    """标记奖励已发放。"""
    return execute_update(
        '''UPDATE user_achievements SET reward_granted = 1
           WHERE user_id = %s AND achievement_key = %s AND period_key = %s''',
        [user_id, achievement_key, period_key],
    )


def list_all_for_user(user_id):
    """某用户全部成就进度（引擎展示与 storage 共用同一查询）。"""
    return execute_query(
        'SELECT achievement_key, period_key, progress, target, completed_at '
        'FROM user_achievements WHERE user_id = %s',
        [user_id],
    )


def list_completed(user_id):
    """某用户已完成的成就（含完成时间，倒序）。"""
    return execute_query(
        '''SELECT achievement_key, period_key, completed_at
           FROM user_achievements
           WHERE user_id = %s AND completed_at IS NOT NULL
           ORDER BY completed_at DESC''',
        [user_id],
    )


def count_completed_in(user_id, period_key, achievement_keys):
    """已完成的成就数（限于给定 key 集合）。"""
    placeholders = ','.join(['%s'] * len(achievement_keys))
    return fetch_one(
        f'SELECT COUNT(*) AS cnt FROM user_achievements '
        f'WHERE user_id = %s AND period_key = %s '
        f'  AND completed_at IS NOT NULL '
        f'  AND achievement_key IN ({placeholders})',
        [user_id, period_key] + list(achievement_keys),
    )


def delete_old_periods(cutoff_key):
    """清理周期早于 cutoff_key 的 daily/limited 记录。"""
    return execute_update(
        "DELETE FROM user_achievements "
        "WHERE (period_key LIKE 'daily:%%' OR period_key LIKE 'limited:%%') "
        "  AND period_key < %s",
        [cutoff_key],
    )


# ============================================================
# checker 统计：路由访问（action_log）
# ============================================================
def count_action_log(user_id, path=None, prefix=False, method=None,
                     status='2xx3xx', today_only=False):
    """按可选的 path / method / 状态段过滤，统计用户的 action_log 条数。

    对应原 `checkers._build_action_log_sql` —— 过滤条件按需拼接，
    值一律走 `%s` 参数化。
    """
    sql = ['SELECT COUNT(*) AS cnt FROM action_log WHERE user_id = %s']
    args = [user_id]

    if today_only:
        sql.append('AND DATE(created_at) = CURDATE()')

    if path:
        if prefix:
            sql.append('AND path LIKE %s')
            args.append(path + '%')
        else:
            sql.append('AND path = %s')
            args.append(path)

    if method:
        sql.append('AND method = %s')
        args.append(method.upper())

    if status == '2xx':
        sql.append('AND status_code >= 200 AND status_code < 300')
    elif status == '2xx3xx':
        sql.append('AND status_code >= 200 AND status_code < 400')

    row = fetch_one(' '.join(sql), args)
    return int(row['cnt'] or 0) if row else 0


# ============================================================
# checker 统计：编辑次数（resource_versions）
# ============================================================
def count_versions_total(user_id):
    row = fetch_one(
        'SELECT COUNT(*) AS cnt FROM resource_versions WHERE created_by = %s',
        [user_id],
    )
    return int(row['cnt'] or 0) if row else 0


def count_versions_today(user_id):
    row = fetch_one(
        'SELECT COUNT(*) AS cnt FROM resource_versions '
        'WHERE created_by = %s AND DATE(created_at) = CURDATE()',
        [user_id],
    )
    return int(row['cnt'] or 0) if row else 0


def count_versions_between(user_id, start, end):
    row = fetch_one(
        'SELECT COUNT(*) AS cnt FROM resource_versions '
        'WHERE created_by = %s AND DATE(created_at) BETWEEN %s AND %s',
        [user_id, start, end],
    )
    return int(row['cnt'] or 0) if row else 0


# ============================================================
# checker 统计：互动
# ============================================================
def count_interaction_given(table, user_id, today=False):
    """某用户在三张互动表里给出的互动数。"""
    _checked_table(table, INTERACTION_TABLES)
    sql = [f'SELECT COUNT(*) AS cnt FROM {table} WHERE user_id = %s']
    args = [user_id]
    if today:
        sql.append('AND DATE(created_at) = CURDATE()')
    row = fetch_one(' '.join(sql), args)
    return int(row['cnt'] or 0) if row else 0


def list_interaction_contents(table, resource_type, user_id):
    """某用户在某类资源上"给出"的互动所指向的资源 content（按类型遍历）。"""
    _checked_table(table, INTERACTION_TABLES)
    res_table = _checked_table(
        RESOURCE_TABLE.get(resource_type), set(RESOURCE_TABLE.values()))
    return execute_query(
        f'SELECT r.content FROM {table} i '
        f'INNER JOIN {res_table} r ON i.resource_id = r.id '
        f'WHERE i.resource_type = %s AND i.user_id != %s',
        [resource_type, user_id],
    )
