# utils/data/pool.py
"""连接池 —— 全站唯一的 MySQL 连接来源。

为什么单独成模块
----------------
原先连接池直接建在 `utils/db.py` 的模块顶层，带来两个问题：

1. **import 期副作用**：`PooledDB(mincached=2)` 会在 import 时立刻建立 2 条真实
   连接。本地/CI 没有数据库时，`from mcres import ...` 直接抛
   `OperationalError (2003)`，导致整个应用无法导入、无法测试。
2. **连接泄漏**：`fetch_one` 是唯一没有 `try/finally` 的封装，`cursor.execute`
   抛错时连接不会归还池子。而 `ping=0` 让 MySQL `wait_timeout` 之后的死连接
   正好走到这条路径，差错会持续累积。

这里用 `mincached=0`（懒建连，池子照样复用，生产行为不变）+ `ping=1`
（取用前探活），并统一用 `cursor()` 上下文管理器保证归还。
"""
import os

import pymysql
from dbutils.pooled_db import PooledDB
from dotenv import load_dotenv
from pymysql.cursors import DictCursor
from pymysql.err import Error as PyMySQLError

load_dotenv()

# 连接参数集中一处，便于测试替换与后续接入配置对象
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'mcres',
    'password': os.getenv('DB_PWD'),
    'db': 'mcres',
    'charset': 'utf8mb4',
}

POOL = PooledDB(
    creator=pymysql,
    maxconnections=0,
    mincached=0,          # 懒建连：避免 import 期就要求数据库可用
    maxcached=10,
    blocking=True,
    setsession=[],
    ping=1,               # 取用前探活，避免 wait_timeout 后的死连接
    **DB_CONFIG,
)


def connection():
    """从池子取一条连接。调用方负责 close；推荐直接用 cursor()。"""
    return POOL.connection()


class cursor:
    """游标上下文管理器，保证游标与连接都被归还且不残留未读结果。

    用法::

        from utils.data import cursor

        with cursor() as cur:
            cur.execute('SELECT id FROM maps WHERE id = %s', [1])
            row = cur.fetchone()

    为什么必须显式排空
    ------------------
    取一行（`fetchone`）就把连接还回池子，会让**未读的结果集留在连接上**。
    PyMySQL 的 `Connection.close()` 是"发 QUIT 并关 socket"，而 DBUtils 的
    `SteadyDBConnection._reset()` 只在连接处于事务中时才 rollback —— 也就是说
    一条刚刚 `fetchone` 过的连接可能带着未读行回到池子里，被下一个请求取到后
    读到脏数据。这里在退出时无条件把游标读干净，消除这个跨请求污染。

    同时保证异常路径也归还连接 —— 这正是原先 `fetch_one` 缺失的 try/finally。
    """

    def __init__(self, dict_cursor=True):
        self._dict_cursor = dict_cursor
        self._conn = None
        self._cur = None

    def __enter__(self):
        self._conn = POOL.connection()
        self._cur = self._conn.cursor(
            cursor=DictCursor if self._dict_cursor else None
        )
        return self._cur

    # 显式提交：上下文管理器本身不自动提交，避免把"隐式事务"的语义
    # 悄悄改成"写操作自动提交"
    def commit(self):
        if self._conn is not None:
            self._conn.commit()

    def rollback(self):
        if self._conn is not None:
            self._conn.rollback()

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._cur is not None:
                # 排空未读结果集（已读完时是廉价空操作）
                try:
                    self._cur.fetchall()
                except PyMySQLError:
                    pass
                self._cur.close()
        finally:
            if self._conn is not None:
                self._conn.close()
        return False
