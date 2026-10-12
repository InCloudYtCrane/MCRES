# utils/data/repositories/reviews.py
"""资源审核队列的查询（review 表家族）。

涉及四张结构相似的表：
    resourcepack_review / shaderpack_review / map_review / shaderpack_preset_review
前三张以 `id` 为主键、以 `{type}_id` 指向已发布资源；预设审核表则以
`shaderpack_id` + `preset_id` 定位，形态不同。

原先散落在 `mcres/views/index.py` 的审核列表里（含一处在循环内逐条查头像的
N+1）。这里只收拢查询，**未把 N+1 改成批量** —— 那是性能修复，属行为改动。
"""
from utils.data import (
    execute_query,
    execute_update,
    fetch_one,
    fetch_previous_records,
)

#: 待审计数涉及的 (表, 类型)
PENDING_COUNT_TABLES = (
    ('resourcepack_review', 'resourcepack'),
    ('shaderpack_review', 'shaderpack'),
    ('map_review', 'map'),
)


def count_pending(table):
    """某张审核表的 pending 条数。"""
    row = fetch_one(
        f'SELECT COUNT(*) AS cnt FROM {table} WHERE status = %s', ['pending'])
    return (row['cnt'] if row else 0) or 0


def count_pending_map():
    """各类型的待审数（光影包合并主表 + 预设表）。

    对应原实现的 `pending_count` 字典构造。
    """
    return {
        'resourcepack': count_pending('resourcepack_review'),
        'shaderpack': (count_pending('shaderpack_review')
                       + count_pending('shaderpack_preset_review')),
        'map': count_pending('map_review'),
    }


def get_by_id(table, review_id):
    """按 id 取审核记录（整行）。"""
    return fetch_one(f'SELECT * FROM {table} WHERE id = %s', [review_id])


def update_status(table, review_id, status, review):
    """更新审核状态与审核历史。"""
    return execute_update(
        f'UPDATE {table} SET status = %s, review = %s WHERE id = %s',
        [status, review, review_id],
    )


def list_ids(table, where_sql, params, limit):
    """审核列表的 count 模式第一步：取 id 列表。"""
    return execute_query(
        f'SELECT id FROM {table} WHERE {where_sql} '
        f'ORDER BY submit_time DESC LIMIT %s',
        list(params) + [limit],
    )


def list_rows(table, where_sql, params):
    """审核列表：按条件取整行（按 submit_time 倒序）。"""
    return execute_query(
        f'SELECT * FROM {table} WHERE {where_sql} ORDER BY submit_time DESC',
        list(params),
    )


def list_rows_by_ids(table, ids):
    """审核列表的 count 模式第二步：按 id 集合取整行。"""
    if not ids:
        return []
    placeholders = ','.join(['%s'] * len(ids))
    return execute_query(
        f'SELECT * FROM {table} WHERE id IN ({placeholders}) '
        f'ORDER BY submit_time DESC',
        list(ids),
    )


def get_resource_pending_order(table, resource_id):
    """统计该资源在 pending 队列中的位次（用于显示排队序号）。"""
    row = fetch_one(
        f'SELECT COUNT(*) AS cnt FROM {table} '
        f'WHERE status = %s AND id <= %s',
        ['pending', resource_id],
    )
    return (row['cnt'] if row else 0) or 0


def get_shaderpack_content(shaderpack_id):
    """审核项关联的光影包内容（预设审核需要显示宿主名称）。"""
    return fetch_one(
        'SELECT content FROM shaderpacks WHERE id = %s', [shaderpack_id])


def insert_new_review(table, submitter, now, content_json, change_summary):
    """机器人导入：往审核表插一条 `operation='add'`、`status='pending'`。

    对应 api.py 两处 INSERT。SQL 文本逐字照搬（两条语句除表名外完全相同）。
    """
    return execute_update(
        f'''INSERT INTO {table}
           (operation, submitter, submit_time, content, status, change_summary)
           VALUES (%s, %s, %s, %s, %s, %s)''',
        ['add', submitter, now, content_json, 'pending', change_summary],
    )


def last_inserted_id(table):
    """取该表最后插入记录的 id（`fetch_previous_records` 的 LIFO 语义）。

    原实现是 `fetch_previous_records(table, 1, columns='id',
    reverse_result=False)` 再取 `[0]['id']`（空结果给 None），这里保持完全
    相同的取法，返回值也统一成 int / None。
    """
    rows = fetch_previous_records(
        table, 1, columns='id', reverse_result=False)
    return rows[0]['id'] if rows else None
