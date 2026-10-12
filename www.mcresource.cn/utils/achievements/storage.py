# utils/achievements/storage.py
"""user_achievements 表读写封装。

SQL 已迁到 `utils/data/repositories/achievements.py`，本模块只保留原有的
函数名与签名，供既有调用点继续使用。
"""
from utils.data.repositories import achievements as achievements_repo
from utils.time import datetime_fmt


def get(user_id, achievement_key, period_key):
    """返回单条进度记录，不存在返回 None"""
    return achievements_repo.get_progress(user_id, achievement_key, period_key)


def upsert(user_id, achievement_key, period_key, progress, target, completed_at=None):
    """插入或更新进度。completed_at 一旦写入不会被覆盖"""
    achievements_repo.upsert_progress(
        user_id, achievement_key, period_key, progress, target,
        completed_at, datetime_fmt.now(),
    )


def mark_reward_granted(user_id, achievement_key, period_key):
    achievements_repo.mark_reward_granted(user_id, achievement_key, period_key)


def list_all_for_user(user_id):
    """列出某用户的所有成就记录"""
    return achievements_repo.list_all_for_user(user_id)


def list_completed(user_id):
    """列出某用户已完成的成就（含完成时间）"""
    return achievements_repo.list_completed(user_id)
