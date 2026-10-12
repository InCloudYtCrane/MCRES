# utils/data/repositories/resource_forms.py
"""资源表单（新建 / 编辑）流程的数据访问。

`utils/resource_forms/common.py` 把三种资源类型的处理器收敛成一张 `SPECS` 表，
表名 / 审核表名都来自 `TypeSpec`（模块内常量，不接受用户输入），
因此这里的 `table` / `review_table` 参数只会拿到常量。

SQL 文本逐字照搬，未做任何改写（这些路由不在渲染回归的认证范围内，
回归抓不到这里的改动，必须靠人工比对）。
"""
from utils.data import (
    execute_query,
    execute_update,
    fetch_one,
    fetch_previous_records,
)


# ============================================================
# 读：主表
# ============================================================
def get_content(table, resource_id):
    """主表某行的 content（管理员直接编辑时的预填）。"""
    return fetch_one(f'select content from {table} where id = %s', [resource_id])


# ============================================================
# 读：审核表
# ============================================================
def get_review_for_edit(review_table, review_id):
    """审核项的编辑预填字段（content 及审核元信息）。"""
    return execute_query(
        f'select content, submitter, status, change_summary, messenger, review '
        f'from {review_table} where id = %s',
        [review_id],
    )


def get_review_submitter_status(review_table, review_id):
    """审核项的提交者与状态（编辑许可校验）。"""
    return execute_query(
        f'select submitter, status from {review_table} where id = %s',
        [review_id],
    )


def get_review_field(review_table, review_id):
    """审核项的 review 时间线原文。"""
    return fetch_one(
        f'SELECT review FROM {review_table} WHERE id = %s', [review_id])


def get_latest_review_field(review_table, review_fk, resource_id):
    """某资源最近一条审核记录的 review 时间线（不限 operation）。"""
    return fetch_one(
        f'SELECT review FROM {review_table} '
        f'WHERE {review_fk} = %s ORDER BY id DESC LIMIT 1',
        [resource_id],
    )


def get_pending_edit(review_table, review_fk, resource_id):
    """该资源是否已有 pending 的 edit 审核（编辑锁定，取提交者信息）。"""
    return execute_query(
        f'select submitter, submit_time, review from {review_table} '
        f'where {review_fk} = %s and operation = "edit" and status = "pending"',
        [resource_id],
    )


def find_pending_edit_id(review_table, review_fk, resource_id):
    """同上的轻量版：只探测是否存在（POST 前的锁定检查）。"""
    return execute_query(
        f'select id from {review_table} '
        f'where {review_fk} = %s and operation = "edit" and status = "pending"',
        [resource_id],
    )


# ============================================================
# 写：主表
# ============================================================
def update_content(table, content_json, target_id):
    """直接更新已发布资源的内容。"""
    return execute_update(
        f'update {table} set content = %s where id = %s',
        [content_json, target_id],
    )


def insert_resource(table, content_json, date_added):
    """直接插入新资源。"""
    return execute_update(
        f'insert into {table}(content, date_added) values(%s, %s)',
        [content_json, date_added],
    )


def last_inserted_resource_id(table):
    """取刚插入行的 id。

    `common.create_directly` 的原实现就是 `fetch_previous_records(...)[0]['id']`，
    空结果会抛 IndexError。这里**刻意保留**该行为（改用 lastrowid 是行为改动，
    属并发正确性修复，另批处理）。
    """
    return fetch_previous_records(
        table=table, limit=1, columns='id', reverse_result=False
    )[0]['id']


# ============================================================
# 写：审核表
# ============================================================
def update_pending_review(review_table, content_json, submit_time,
                          change_summary, messenger, review_json, review_id):
    """已有审核项改回 pending 并覆盖内容。"""
    return execute_update(
        f'update {review_table} set content = %s, submit_time = %s, '
        f'status = %s, change_summary = %s, messenger = %s, review = %s '
        f'where id = %s',
        [content_json, submit_time, 'pending', change_summary,
         messenger, review_json, review_id],
    )


def insert_pending_review(review_table, submitter, submit_time, content_json,
                          change_summary, messenger, review_json):
    """首次提交：新增一条 operation='add'、status='pending' 的审核记录。"""
    return execute_update(
        f'insert into {review_table}(operation, submitter, submit_time, '
        f'content, status, change_summary, messenger, review) '
        f'values(%s, %s, %s, %s, %s, %s, %s, %s)',
        ['add', submitter, submit_time, content_json,
         'pending', change_summary, messenger, review_json],
    )


def insert_edit_review(review_table, review_fk, submitter, submit_time,
                       content_json, change_summary, messenger, review_json,
                       resource_id):
    """普通用户编辑已发布资源：新增一条 operation='edit' 的审核记录。"""
    return execute_update(
        f'insert into {review_table}(operation, submitter, submit_time, '
        f'content, status, change_summary, messenger, review, {review_fk}) '
        f'values(%s, %s, %s, %s, %s, %s, %s, %s, %s)',
        ['edit', submitter, submit_time, content_json,
         'pending', change_summary, messenger, review_json, resource_id],
    )
