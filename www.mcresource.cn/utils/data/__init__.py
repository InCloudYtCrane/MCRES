# utils/data/__init__.py
"""数据访问层 —— 全站唯一的数据库入口。

分层
----
    utils/data/pool.py            连接池 + cursor() 上下文管理器
    utils/data/repositories/      按领域拆分的查询模块（每个函数 = 一次明确意图的查询）
    utils/data/__init__.py        本文件：对外 API（原 utils/db.py 的公开函数）

向后兼容
--------
原 `utils/db.py` 已改为转出口本包，因此 `from utils import db` 以及
`from utils.db import fetch_one` 这类既有写法全部继续可用，700 多个调用点
无需一次性改动，可以按模块逐步迁移到 repositories。

新增查询请放进 `repositories/`，不要再在视图里写裸 SQL。
"""
from .pool import POOL, DB_CONFIG, connection, cursor
from .queries import (
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
