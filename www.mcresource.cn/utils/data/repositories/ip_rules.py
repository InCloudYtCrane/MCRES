# utils/data/repositories/ip_rules.py
"""IP 风控（白名单 / 黑名单 / 违规记录）的查询。

原先内联在 `mcres/ip_service.py`。该模块是一个跨请求缓存层：每次访问都可能
命中 `get_blacklist()` / `get_whitelist()`，缓存策略留在视图层，SQL 收在这里。

SQL 文本逐字照搬；`report_violation` 里两条语句原本各自包在 try/except 里，
这里的两个函数也把同样的失败降级语义放在**仓储层**，视图只负责组装参数。
"""
from utils.data import execute_query, execute_update, fetch_one

#: 黑名单整行里，缓存需要的那几列。
_BLACKLIST_COLUMNS = 'ip, reason, expires_at, created_at'


# ============================================================
# 白名单（ip_whitelist）
# ============================================================
def list_whitelist_ips():
    """全部白名单 IP。查询失败返回空列表（由调用方决定兜底）。"""
    return execute_query('SELECT ip FROM ip_whitelist') or []


# ============================================================
# 跨域版本号（ip_ban_state）
# ============================================================
def bump_ban_version():
    """写入黑名单后调用：让所有子域感知变化。"""
    return execute_update(
        'UPDATE ip_ban_state SET version = version + 1, updated_at = NOW() '
        'WHERE id = 1'
    )


def get_remote_ban_version():
    """读远端版本号；无记录返回 0，查询异常返回 -1。"""
    try:
        row = fetch_one('SELECT version FROM ip_ban_state WHERE id = 1')
        return int(row['version']) if row else 0
    except Exception:
        return -1


# ============================================================
# 黑名单（ip_blacklist）
# ============================================================
def deactivate_expired_bans(now):
    """把已过期的自动封禁下线（返回受影响行数）。"""
    return execute_update(
        "UPDATE ip_blacklist SET is_active = 0 "
        "WHERE is_active = 1 AND expires_at IS NOT NULL AND expires_at <= %s",
        [now]
    )


def list_active_bans():
    """生效中的黑名单整行（含触发时间）。"""
    return execute_query(
        f'SELECT {_BLACKLIST_COLUMNS} '
        f'FROM ip_blacklist WHERE is_active = 1'
    ) or []


def increment_hit_count(ip):
    return execute_update(
        'UPDATE ip_blacklist SET hit_count = hit_count + 1 WHERE ip = %s',
        [ip]
    )


def deactivate_ban(ip):
    """解封单个 IP，返回受影响行数（0 表示本来就没生效）。"""
    return execute_update(
        'UPDATE ip_blacklist SET is_active = 0 WHERE ip = %s AND is_active = 1',
        [ip]
    )


def upsert_auto_ban(ip, reason, created_at, expires_at):
    """自动封禁：不存在则插入，存在则刷新原因与到期时间。"""
    return execute_update(
        """
        INSERT INTO ip_blacklist
            (ip, reason, source, hit_count, is_active, created_at, expires_at)
        VALUES (%s, %s, 'auto', 0, 1, %s, %s)
        ON DUPLICATE KEY UPDATE
            reason     = VALUES(reason),
            source     = 'auto',
            is_active  = 1,
            expires_at = VALUES(expires_at)
        """,
        [ip, reason, created_at, expires_at]
    )


# ============================================================
# 违规记录（ip_violation）
# ============================================================
def insert_violation(ip, rule, score, detail, method, path, ua, created_at):
    return execute_update(
        """INSERT INTO ip_violation
           (ip, rule, score, detail, method, path, user_agent, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        [ip, rule, score, detail, method, path, ua, created_at]
    )


def sum_violation_score(ip, window_start):
    """窗口期内该 IP 的违规总分。返回 dict（含 `total` 列）或 None。"""
    return fetch_one(
        'SELECT COALESCE(SUM(score), 0) AS total FROM ip_violation '
        'WHERE ip = %s AND created_at >= %s',
        [ip, window_start]
    )


def delete_old_violations(days):
    return execute_update(
        'DELETE FROM ip_violation WHERE created_at < '
        'DATE_SUB(NOW(), INTERVAL %s DAY)',
        [days]
    )
