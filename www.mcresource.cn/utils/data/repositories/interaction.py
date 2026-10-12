# utils/data/repositories/interaction.py
"""资源互动（点赞 / 投币 / 收藏）的查询。

覆盖两处调用方：
· `mcres/views/interaction.py` —— `/interaction` 接口的动作实现
· `utils/interaction.py` —— 计数读取 / 写回与用户状态（该模块自身不再写 SQL）

SQL 文本逐字照搬，未改变语义。表名一律经 `resource_table(类型键)` 解析，
**不接受外部传入的表名**。
"""
from utils.constants import resource_table
from utils.data import execute_query, execute_update, fetch_one


def _table(resource_type):
    """把类型键解析成表名；非法类型返回 None。"""
    return resource_table(resource_type)


# ============================================================
# 是否存在 / 计数
# ============================================================
def resource_exists(resource_type, resource_id):
    """资源是否存在（互动前的 404 判定）。"""
    table = _table(resource_type)
    if not table:
        return False
    return fetch_one(
        f'SELECT id FROM {table} WHERE id = %s',
        [resource_id],
    ) is not None


def find_resource_id(resource_type, resource_id):
    """只取 id（存在性判断）。与 `utils/data/repositories/users.find_id_by_id`
    同名不同域：这里的目标表由资源类型决定。"""
    table = _table(resource_type)
    if not table:
        return None
    return fetch_one(f'SELECT id FROM {table} WHERE id = %s', [resource_id])


def get_counts(resource_type, resource_id):
    """资源行上的三个互动计数。返回 dict 或 None。"""
    table = _table(resource_type)
    if not table:
        return None
    return fetch_one(
        f'SELECT likes_count, coins_count, favorites_count '
        f'FROM {table} WHERE id = %s',
        [resource_id],
    )


def get_content(resource_type, resource_id):
    """只取 content 列（投币后给作者发砖块奖励时解析 authors）。"""
    table = _table(resource_type)
    if not table:
        return None
    return fetch_one(
        f'SELECT content FROM {table} WHERE id = %s',
        [resource_id],
    )


#: `update_count` 允许的计数列白名单（列名来自调用方的常量字符串）。
COUNT_COLUMNS = frozenset({'likes_count', 'coins_count', 'favorites_count'})


def update_count(resource_type, resource_id, field, delta):
    """把某个计数列按 delta 增减。"""
    if field not in COUNT_COLUMNS:
        raise ValueError(f'不允许更新的计数列: {field!r}')
    table = _table(resource_type)
    if not table:
        return None
    return execute_update(
        f'UPDATE {table} SET {field} = {field} + %s WHERE id = %s',
        [delta, resource_id],
    )


# ============================================================
# 点赞（resource_likes）
# ============================================================
def find_like(user_id, resource_type, resource_id):
    return fetch_one(
        'SELECT id FROM resource_likes '
        'WHERE user_id = %s AND resource_type = %s AND resource_id = %s',
        [user_id, resource_type, resource_id],
    )


def has_like(user_id, resource_type, resource_id):
    return fetch_one(
        'SELECT 1 FROM resource_likes '
        'WHERE user_id = %s AND resource_type = %s AND resource_id = %s',
        [user_id, resource_type, resource_id],
    ) is not None


def delete_like(like_id):
    return execute_update('DELETE FROM resource_likes WHERE id = %s', [like_id])


def insert_like(user_id, resource_type, resource_id):
    return execute_update(
        'INSERT INTO resource_likes (user_id, resource_type, resource_id) '
        'VALUES (%s, %s, %s)',
        [user_id, resource_type, resource_id],
    )


# ============================================================
# 收藏（resource_favorites）
# ============================================================
def find_favorite(user_id, resource_type, resource_id):
    return fetch_one(
        'SELECT id FROM resource_favorites '
        'WHERE user_id = %s AND resource_type = %s AND resource_id = %s',
        [user_id, resource_type, resource_id],
    )


def has_favorite(user_id, resource_type, resource_id):
    return fetch_one(
        'SELECT 1 FROM resource_favorites '
        'WHERE user_id = %s AND resource_type = %s AND resource_id = %s',
        [user_id, resource_type, resource_id],
    ) is not None


def delete_favorite(favorite_id):
    return execute_update(
        'DELETE FROM resource_favorites WHERE id = %s', [favorite_id])


def insert_favorite(user_id, resource_type, resource_id):
    return execute_update(
        'INSERT INTO resource_favorites (user_id, resource_type, resource_id) '
        'VALUES (%s, %s, %s)',
        [user_id, resource_type, resource_id],
    )


# ============================================================
# 投币（resource_coins / user_daily_coins）
# ============================================================
def has_coin(user_id, resource_type, resource_id):
    return fetch_one(
        'SELECT 1 FROM resource_coins '
        'WHERE user_id = %s AND resource_type = %s AND resource_id = %s',
        [user_id, resource_type, resource_id],
    ) is not None


def insert_coin(user_id, resource_type, resource_id):
    return execute_update(
        'INSERT INTO resource_coins (user_id, resource_type, resource_id) '
        'VALUES (%s, %s, %s)',
        [user_id, resource_type, resource_id],
    )


def count_user_coins(user_id, resource_type, resource_id):
    """该用户对某资源的投币次数。"""
    row = fetch_one(
        'SELECT COUNT(*) as cnt FROM resource_coins '
        'WHERE user_id = %s AND resource_type = %s AND resource_id = %s',
        [user_id, resource_type, resource_id],
    )
    return (row['cnt'] if row else 0) or 0


def find_daily_coins(user_id, today):
    """取当天已用投币数那一行。"""
    return fetch_one(
        'SELECT id, coins_used FROM user_daily_coins '
        'WHERE user_id = %s AND date = %s',
        [user_id, today],
    )


def sum_daily_coins(user_id, today):
    """当天已用投币数（无记录为 0）。"""
    row = fetch_one(
        'SELECT coins_used FROM user_daily_coins '
        'WHERE user_id = %s AND date = %s',
        [user_id, today],
    )
    return (row['coins_used'] if row else 0) or 0


def increment_daily_coins(daily_id):
    return execute_update(
        'UPDATE user_daily_coins SET coins_used = coins_used + 1 WHERE id = %s',
        [daily_id],
    )


def insert_daily_coins(user_id, today):
    return execute_update(
        'INSERT INTO user_daily_coins (user_id, date, coins_used) '
        'VALUES (%s, %s, 1)',
        [user_id, today],
    )


# ============================================================
# 用户侧：砖块（user_info.brick）
# ============================================================
def get_brick(user_id):
    row = fetch_one('SELECT brick FROM user_info WHERE id = %s', [user_id])
    return row['brick'] if row else 0


def add_brick(user_id, delta):
    return execute_update(
        'UPDATE user_info SET brick = brick + %s WHERE id = %s',
        [delta, user_id],
    )
