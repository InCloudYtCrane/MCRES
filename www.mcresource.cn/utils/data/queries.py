# utils/data/queries.py
"""通用 SQL 封装 —— 原 utils/db.py 的实现，迁到这里并修复两处问题。

与原实现的差异（仅两处，均为修复，不变更任何查询语义）
----------------------------------------------------
1. `fetch_one` 原先**没有 try/finally**：`cursor.execute` 抛错时连接不会归还。
   现统一走 `pool.cursor()` 上下文管理器。其余封装原本就有 finally，语义不变。
2. `execute_update` 原先只 `finally: close()`，异常时不 rollback；现在异常路径
   显式 rollback 后再归还 —— 避免把未提交的隐式事务留在池中连接上。

SQL 文本、参数形式与返回值（DictCursor 行 / rowcount）保持逐字一致，
因此 700 多个既有调用点无需改动即可继续工作。

新增查询请放进 `utils/data/repositories/`，不要继续在这里堆通用方法，
也不要在视图里写裸 SQL。
"""
import os

from .pool import cursor


# ============================================================
# 建表（应用启动时调用）
# ============================================================
def create_db():
    """执行建表脚本。

    注意：原实现直接 `open("db_mysql.sql")`，而该文件在本仓库中**并不存在**，
    异常信息是裸的 FileNotFoundError，很难定位。这里改为显式报错，指出期望路径
    与缺失原因；行为上仍然是"文件缺失即抛异常"，不做静默跳过 —— 静默跳过会让
    部署者以为初始化成功。
    """
    path = os.path.join(os.getcwd(), 'db_mysql.sql')
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"建表脚本不存在: {path}\n"
            "create_db() 只应在持有数据库 schema 的部署环境中调用；"
            "仓库快照里没有 db_mysql.sql，因此本地/CI 不应调用它。"
        )

    with open(path, 'r', encoding='utf-8') as f:
        sql = f.read()

    ctx = cursor(dict_cursor=False)
    with ctx as cur:
        # 按分号拆分多条 SQL 语句并逐条执行（忽略空语句）
        for stmt in (s.strip() for s in sql.split(';')):
            if stmt:
                cur.execute(stmt)
        # DDL 在 MySQL 中隐式提交；这里显式 commit 保持与原实现一致
        ctx.commit()


# ============================================================
# 读
# ============================================================
def fetch_one(sql, params=[]):
    """执行查询并返回首行（dict）；无结果返回 None。"""
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute_query(sql, params=None):
    """执行查询并返回全部行（list[dict]）；无结果返回空列表。"""
    with cursor() as cur:
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return cur.fetchall()


# ============================================================
# 写
# ============================================================
def execute_update(sql, params):
    """执行写操作（INSERT/UPDATE/DELETE）并提交，返回受影响行数。

    与原实现的差异：异常路径显式 rollback。原先只有 `finally: close()`，
    出错时可能把未提交的隐式事务跟着连接一起还回池子。
    """
    ctx = cursor()
    with ctx as cur:
        try:
            cur.execute(sql, params)
        except Exception:
            ctx.rollback()
            raise
        ctx.commit()
        return cur.rowcount


# ============================================================
# 便利方法（表名/列名由调用方保证安全，不接受用户输入）
# ============================================================
def fetch_previous_records(table, start_id=None, limit=10, columns='*',
                           id_column='id', reverse_result=True):
    """获取从最后一项或指定 id 往前（更旧）的 limit 条记录。

    :param table:          表名（不要直接拼接用户输入）
    :param start_id:       起始 id；None 表示从最新记录开始
    :param limit:          条数
    :param columns:        列
    :param id_column:      id 列名
    :param reverse_result: True 则把结果按 id 升序返回（旧→新）
    """
    if start_id is not None:
        sql = (f"SELECT {columns} FROM {table} WHERE {id_column} < %s "
               f"ORDER BY {id_column} DESC LIMIT %s")
        params = (start_id, limit)
    else:
        sql = (f"SELECT {columns} FROM {table} "
               f"ORDER BY {id_column} DESC LIMIT %s")
        params = (limit,)

    rows = execute_query(sql, params)
    if reverse_result:
        rows.reverse()   # 降序变升序（旧→新）
    return rows


def count_where(table, column, value):
    """统计指定表中某列等于某值的记录数。"""
    sql = f"SELECT COUNT(*) AS cnt FROM {table} WHERE {column} = %s"
    row = fetch_one(sql, (value,))
    return row['cnt'] if row else 0


def count_all(table):
    """统计指定表的全部记录数。"""
    sql = f"SELECT COUNT(*) AS cnt FROM {table}"
    row = fetch_one(sql)
    return row['cnt'] if row else 0


def update_where(table, set_column, set_value, where_column, where_value):
    """按条件列更新目标列，返回受影响行数。"""
    sql = f"UPDATE {table} SET {set_column} = %s WHERE {where_column} = %s"
    return execute_update(sql, (set_value, where_value))
