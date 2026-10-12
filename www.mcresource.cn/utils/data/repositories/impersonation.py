# utils/data/repositories/impersonation.py
"""模拟登录记录（impersonation_log / imitation_log）的查询。

原先内联在 `mcres/middleware.py`：模拟登录超时后把最后一条 active 记录
收尾。SQL 文本逐字照搬（含 `ORDER BY ... LIMIT 1`）。
"""
from utils.data import execute_update


def close_expired_impersonation(admin_id, target_user_id):
    """把该 (管理员, 目标用户) 最后一条 active 记录标记为过期。"""
    return execute_update(
        """UPDATE impersonation_log
           SET end_time = NOW(), status = 'expired'
           WHERE admin_id = %s AND target_user_id = %s AND status = 'active'
           ORDER BY start_time DESC LIMIT 1""",
        [admin_id, target_user_id],
    )
