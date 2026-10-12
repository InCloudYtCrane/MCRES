# utils/data/repositories/logging.py
"""访问与操作日志（access_log / action_log）的查询。

原先内联在 `mcres/middleware.py` 与 `mcres/audit.py`。这两张表都在**每个请求**
的写入路径上，因此 SQL 文本逐字照搬，未做任何改写。
"""
from utils.data import execute_update, fetch_one


# ============================================================
# access_log（访问日志，middleware 记录）
# ============================================================
def insert_access_log(path, ip_hash, region, user_id, visitor_key,
                      status_code, duration_ms):
    """插入一条访问记录（visit_date/visit_time 由 SQL 侧 NOW()/CURDATE() 生成）。"""
    return execute_update(
        '''
        INSERT INTO access_log
        (path, ip_hash, region, user_id, visit_date, visit_time,
         visitor_key, status_code, duration_ms)
        VALUES (%s, %s, %s, %s, CURDATE(), NOW(), %s, %s, %s)
        ''',
        [path, ip_hash, region, user_id, visitor_key,
         status_code, duration_ms],
    )


def find_recent_visit(visitor_key, window_ago):
    """窗口期内该访客是否已有访问记录（全站防刷，LIMIT 1）。"""
    return fetch_one(
        'SELECT id FROM access_log '
        'WHERE visitor_key = %s AND visit_time > %s LIMIT 1',
        [visitor_key, window_ago],
    )


# ============================================================
# action_log（操作日志，audit 记录）
# ============================================================
def insert_action_log(user_id, action, level, target_type, target_id, method,
                      path, status_code, duration_ms, ip, user_agent,
                      request_data, created_at):
    return execute_update(
        """INSERT INTO action_log
           (user_id, action, level, target_type, target_id, method, path,
            status_code, duration_ms, ip, user_agent, request_data, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        [user_id, action, level, target_type, target_id, method, path,
         status_code, duration_ms, ip, user_agent, request_data, created_at],
    )
