# utils/db.py
"""向后兼容转出口 —— 实现已迁到 `utils.data`。

保留此文件的原因：全站有 700+ 处调用点写着 `from utils import db` /
`from utils.db import fetch_one`。转出口让这些写法**无需一次性改动**即可继续
工作，从而可以按模块逐步迁移到 `utils/data/repositories/`。

新代码请直接使用：

    from utils.data import cursor, execute_query, fetch_one, execute_update
    from utils.data.repositories.<领域> import <查询函数>

不要在本文件新增任何逻辑。

注意：`POOL` 通过 `from ... import` 绑定到本模块命名空间。既有代码里
`db.POOL` 的引用方式不受影响；`utils.data.pool.POOL` 才是权威位置。
"""
from utils.data import (          # noqa: F401
    POOL,
    DB_CONFIG,
    connection,
    cursor,
    create_db,
    fetch_one,
    execute_update,
    execute_query,
    fetch_previous_records,
    count_where,
    count_all,
    update_where,
)

__all__ = [
    'POOL', 'DB_CONFIG', 'connection', 'cursor',
    'create_db',
    'fetch_one', 'execute_update', 'execute_query',
    'fetch_previous_records', 'count_where', 'count_all', 'update_where',
]
