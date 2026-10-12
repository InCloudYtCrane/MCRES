# utils/data/repositories/system.py
"""系统级单例状态 —— 目前是每日归档状态。

这些查询原先内联在 `utils/hot.py` 里（`archive_all_if_needed`），
与纯计算逻辑混在一起。抽出来之后 `hot.py` 只剩评分计算。
"""
from utils.constants import RESOURCE_TABLE
from utils.data import execute_update, fetch_one

# 归档状态是单行表：固定 id=1
_STATUS_ROW_ID = 1


def get_archive_status():
    """读取归档状态行；不存在返回 None。

    一次查询同时满足"是否存在"和"上次归档日期"两个需求 ——
    刻意不做单独的 EXISTS 探测，避免多一次数据库往返。
    """
    return fetch_one(
        'SELECT last_archive_date FROM system_archive_status WHERE id = %s',
        [_STATUS_ROW_ID],
    )


def insert_archive_status(today):
    """初始化归档状态行。"""
    return execute_update(
        'INSERT INTO system_archive_status (id, last_archive_date) VALUES (%s, %s)',
        [_STATUS_ROW_ID, today],
    )


def set_last_archive_date(today):
    """更新上次归档日期。"""
    return execute_update(
        'UPDATE system_archive_status SET last_archive_date = %s WHERE id = %s',
        [today, _STATUS_ROW_ID],
    )


def upsert_archive_status(today):
    """一步写入归档日期与更新时间（行不存在则插入 id=1）。

    原先内联在 `utils/scheduling/scheduler.py`，与 `set_last_archive_date`
    是同一行表的两种写法：这条晚于前者出现，保留了 `updated_at`。
    """
    return execute_update('''
        INSERT INTO system_archive_status (id, last_archive_date, updated_at)
        VALUES (1, %s, NOW())
        ON DUPLICATE KEY UPDATE
            last_archive_date = VALUES(last_archive_date),
            updated_at = NOW()
    ''', [today])


def roll_over_daily_view_counts(today):
    """把三张资源表的"今日浏览"滚成"昨日浏览"，并重置今日计数。

    返回每张表受影响的行数 {'resourcepacks': n, ...}。

    原实现是三条仅表名不同的 UPDATE 复制粘贴；这里按 RESOURCE_TABLE 遍历，
    新增资源类型时自动覆盖，不会再出现"漏掉一张表"的问题。
    """
    affected = {}
    for resource_type, table in RESOURCE_TABLE.items():
        affected[table] = execute_update(
            f'''
            UPDATE {table}
            SET yesterday_view_count = today_view_count,
                today_view_count     = 0,
                today_date           = %s
            WHERE today_date != %s
               OR today_date IS NULL
            ''',
            [today, today],
        )
    return affected


def get_average_yesterday_views(table):
    """某张资源表的昨日浏览量均值（用于热度评分基准）。

    `table` 必须来自 `RESOURCE_TABLE`，不接受外部输入。
    """
    row = fetch_one(f'SELECT AVG(yesterday_view_count) AS avg_count FROM {table}')
    return row['avg_count'] if row else None
