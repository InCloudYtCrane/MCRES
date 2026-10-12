# utils/data/repositories/presets.py
"""光影包预设（shaderpack_presets / shaderpack_preset_review）的查询。

原先散落在 `mcres/views/preset.py` 的 7 个路由函数里，同一形态反复出现：
· `SELECT content FROM shaderpacks WHERE id = %s` 被 4 处各写一遍；
· `SELECT id, content, date_added FROM shaderpack_presets ...` 被 3 处各写一遍。

注意：预设的审核表**同时**用 `shaderpack_id` 和 `preset_id` 定位，
与资源主表"仅靠 id"的形态不同，故单独成模块而不是并入 resources.py。
"""
from utils.data import (
    execute_query,
    execute_update,
    fetch_one,
    fetch_previous_records,
)


# ============================================================
# 光影包（预设的宿主）
# ============================================================
def get_shaderpack_content(shaderpack_id):
    """取宿主光影包的 content（用于显示名称、校验存在性）。"""
    return fetch_one(
        'SELECT content FROM shaderpacks WHERE id = %s', [shaderpack_id])


def get_edit_area(user_id):
    """取用户的编辑管辖区字段。"""
    return fetch_one(
        'SELECT edit_area FROM user_info WHERE id = %s', [user_id])


# ============================================================
# 预设主表
# ============================================================
def get_preset(shaderpack_id, preset_id, columns='id, content, date_added'):
    """取某个预设（限定在指定光影包下）。"""
    return fetch_one(
        f'SELECT {columns} FROM shaderpack_presets '
        f'WHERE id = %s AND shaderpack_id = %s',
        [preset_id, shaderpack_id],
    )


def get_preset_content(shaderpack_id, preset_id):
    """只取预设的 content（diff 用）。"""
    return fetch_one(
        'SELECT content FROM shaderpack_presets '
        'WHERE id = %s AND shaderpack_id = %s',
        [preset_id, shaderpack_id],
    )


def get_versions_by_ids(version_ids, resource_type, resource_id):
    """按 id 集合取版本行（diff 对比页）。"""
    a, b = version_ids
    return execute_query(
        'SELECT id, content, created_at, change_summary, created_by '
        'FROM resource_versions '
        'WHERE id IN (%s, %s) AND resource_type = %s AND resource_id = %s',
        [a, b, resource_type, resource_id],
    )


def list_presets(shaderpack_id):
    """列出某光影包的全部预设，按 date_added 倒序。"""
    return execute_query(
        'SELECT id, content, date_added FROM shaderpack_presets '
        'WHERE shaderpack_id = %s ORDER BY date_added DESC',
        [shaderpack_id],
    )


def insert_preset(shaderpack_id, preset_json, now):
    """新增预设。"""
    return execute_update(
        'INSERT INTO shaderpack_presets (shaderpack_id, content, date_added) '
        'VALUES (%s, %s, %s)',
        [shaderpack_id, preset_json, now],
    )


def update_preset_content(preset_id, preset_json):
    """更新预设内容。"""
    return execute_update(
        'UPDATE shaderpack_presets SET content = %s WHERE id = %s',
        [preset_json, preset_id],
    )


def last_inserted_preset_id():
    """取最近插入的预设 id。

    注意：调用方原先用 `fetch_previous_records(limit=1)` 猜新行 id，
    并发插入时有取错行的风险。此处**保持原语义**，未改用 lastrowid。
    """
    return fetch_previous_records(
        'shaderpack_presets', limit=1, columns='id', reverse_result=False
    )[0]['id']


# ============================================================
# 预设审核表
# ============================================================
def get_review(review_id, shaderpack_id, columns='*'):
    """取审核记录（限定在指定光影包下）。"""
    return fetch_one(
        f'SELECT {columns} FROM shaderpack_preset_review '
        f'WHERE id = %s AND shaderpack_id = %s',
        [review_id, shaderpack_id],
    )


def get_pending_edit_for(shaderpack_id):
    """取该光影包下 pending 的 edit 审核（用于锁定判断）。

    注意：原实现按 `shaderpack_id` 而非 `preset_id` 判断锁定，
    即"同一光影包下任一预设正在审核"就会锁住其它预设的编辑。
    此处**保持原语义**。
    """
    return fetch_one(
        'SELECT id, content, date_added FROM shaderpack_preset_review '
        'WHERE shaderpack_id = %s AND operation = "edit" AND status = "pending"',
        [shaderpack_id],
    )


def get_pending_edit(shaderpack_id):
    """取 pending edit 审核的 submitter / submit_time（编辑页锁定提示用）。"""
    return fetch_one(
        'SELECT submitter, submit_time FROM shaderpack_preset_review '
        'WHERE shaderpack_id = %s AND operation = "edit" AND status = "pending"',
        [shaderpack_id],
    )


def get_pending_edit_id(shaderpack_id):
    """取 pending edit 审核的 id（POST 时的锁定判断，只要存在性）。"""
    return fetch_one(
        'SELECT id FROM shaderpack_preset_review '
        'WHERE shaderpack_id = %s AND operation = "edit" AND status = "pending"',
        [shaderpack_id],
    )


def get_pending_edit_review_row(shaderpack_id):
    """取 pending edit 审核的 review 字段（用于追加时间线）。"""
    return fetch_one(
        'SELECT review FROM shaderpack_preset_review '
        'WHERE shaderpack_id = %s AND operation = "edit" AND status = "pending"',
        [shaderpack_id],
    )


def update_review(review_id, preset_json, now, change_summary, messenger,
                  status, review_json):
    """更新已有审核记录。"""
    return execute_update(
        'UPDATE shaderpack_preset_review SET content = %s, submit_time = %s, '
        'change_summary = %s, messenger = %s, status = %s, review = %s '
        'WHERE id = %s',
        [preset_json, now, change_summary, messenger, status,
         review_json, review_id],
    )


def insert_review_new(shaderpack_id, preset_json, submitter, now,
                      change_summary, messenger, review_json):
    """新增审核记录（operation='add'，无 preset_id）。"""
    return execute_update(
        'INSERT INTO shaderpack_preset_review (shaderpack_id, content, '
        'submitter, submit_time, status, operation, change_summary, '
        'messenger, review) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
        [shaderpack_id, preset_json, submitter, now, 'pending', 'add',
         change_summary, messenger, review_json],
    )


def insert_review_edit(shaderpack_id, preset_id, preset_json, submitter, now,
                       change_summary, messenger, review_json):
    """新增审核记录（operation='edit'，带 preset_id）。"""
    return execute_update(
        'INSERT INTO shaderpack_preset_review (shaderpack_id, preset_id, '
        'content, submitter, submit_time, status, operation, change_summary, '
        'messenger, review) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
        [shaderpack_id, preset_id, preset_json, submitter, now, 'pending',
         'edit', change_summary, messenger, review_json],
    )


# ============================================================
# 版本历史（diff 用）
# ============================================================
def list_versions(resource_type, resource_id, columns,
                  order_by='created_at DESC'):
    """取某个资源的版本历史。

    `order_by` 由调用方指定：diff 列表页用 `created_at DESC`，
    对比页用 `id DESC`（原实现两种排序并存）。
    """
    return execute_query(
        f'SELECT {columns} FROM resource_versions '
        f'WHERE resource_type = %s AND resource_id = %s '
        f'ORDER BY {order_by}',
        [resource_type, resource_id],
    )


# ============================================================
# 用户昵称批量查询（多处各写一遍的 IN 查询）
# ============================================================
def get_nicknames(user_ids):
    """按 id 集合取昵称，返回 {id: nickname}。"""
    user_ids = [u for u in set(user_ids) if u]
    if not user_ids:
        return {}
    placeholders = ','.join(['%s'] * len(user_ids))
    rows = execute_query(
        f'SELECT id, nickname FROM user_info WHERE id IN ({placeholders})',
        user_ids,
    )
    return {r['id']: r['nickname'] for r in (rows or [])}
