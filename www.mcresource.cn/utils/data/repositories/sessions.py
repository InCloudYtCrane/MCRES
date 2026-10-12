# utils/data/repositories/sessions.py
"""登录设备会话（user_sessions 表）的查询。

原先内联在 `utils/sessions.py`。该模块的 `is_session_valid` 与 `touch_session`
处在**每个已登录请求**的校验路径上（`mcres/middleware.py` 的 session_token 检查），
所以这里保持每条查询只取必要列。

返回值的加工（时间格式化、`is_current` 判定、默认文案）属于展示逻辑，
留在 `utils/sessions.py`。
"""
from utils.data import execute_query, execute_update, fetch_one


# ============================================================
# 读
# ============================================================
def find_by_user_agent(user_id, user_agent):
    """按 user_agent 找同设备记录（用于复用而不是新增）。"""
    return fetch_one(
        '''SELECT id FROM user_sessions
           WHERE user_id = %s AND user_agent = %s
           LIMIT 1''',
        [user_id, user_agent],
    )


def find_by_device_name(user_id, device_name):
    """按 device_name 找同设备记录（无 UA 时的兜底匹配）。"""
    return fetch_one(
        '''SELECT id FROM user_sessions
           WHERE user_id = %s AND device_name = %s
           LIMIT 1''',
        [user_id, device_name],
    )


def find_session_token(session_id, user_id):
    """按 (会话 id, 用户 id) 取 session_token（退出指定设备前校验归属）。"""
    return fetch_one(
        'SELECT session_token FROM user_sessions WHERE id = %s AND user_id = %s',
        [session_id, user_id],
    )


def is_valid(user_id, token):
    """token 是否仍存在于该用户名下。"""
    return fetch_one(
        'SELECT id FROM user_sessions WHERE user_id = %s AND session_token = %s',
        [user_id, token],
    ) is not None


def list_for_user(user_id):
    """列出该用户全部登录设备（按最后活跃倒序）。"""
    return execute_query(
        '''SELECT id, session_token, device_name, device_type,
                  ip, ip_region, login_time, last_active
           FROM user_sessions
           WHERE user_id = %s
           ORDER BY last_active DESC''',
        [user_id],
    )


# ============================================================
# 写
# ============================================================
def refresh_token(session_id, token, device_type, device_name, ip, ip_region, now):
    """复用已有设备记录：更新 token 与本次登录信息。"""
    return execute_update(
        '''UPDATE user_sessions
           SET session_token = %s,
               device_type   = %s,
               device_name   = %s,
               ip            = %s,
               ip_region     = %s,
               login_time    = %s,
               last_active   = %s
           WHERE id = %s''',
        [token, device_type, device_name, ip or '', ip_region or '',
         now, now, session_id],
    )


def insert(user_id, token, device_name, device_type, user_agent,
           ip, ip_region, now):
    """新增一条登录设备记录。"""
    return execute_update(
        '''INSERT INTO user_sessions
           (user_id, session_token, device_name, device_type, user_agent,
            ip, ip_region, login_time, last_active)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
        [user_id, token, device_name, device_type, user_agent or '',
         ip or '', ip_region or '', now, now],
    )


def touch(token, now):
    """更新最后活跃时间。"""
    return execute_update(
        'UPDATE user_sessions SET last_active = %s WHERE session_token = %s',
        [now, token],
    )


def delete_one(user_id, session_id):
    """删除指定设备（限定只能删自己的）。"""
    return execute_update(
        'DELETE FROM user_sessions WHERE id = %s AND user_id = %s',
        [session_id, user_id],
    )


def delete_others(user_id, current_token):
    """踢掉该用户除当前设备外的所有会话。"""
    return execute_update(
        'DELETE FROM user_sessions WHERE user_id = %s AND session_token != %s',
        [user_id, current_token],
    )


def delete_by_token(token):
    """按 token 删除会话（登出）。"""
    return execute_update(
        'DELETE FROM user_sessions WHERE session_token = %s', [token])


def delete_stale(days):
    """清理 N 天未活跃的会话。"""
    return execute_update(
        'DELETE FROM user_sessions '
        'WHERE last_active < DATE_SUB(NOW(), INTERVAL %s DAY)',
        [days],
    )
