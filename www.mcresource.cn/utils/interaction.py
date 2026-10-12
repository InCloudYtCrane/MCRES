# utils/interaction.py
from datetime import date
from utils.constants import resource_table
from utils.data.repositories.interaction import (
    add_brick,
    count_user_coins,
    find_daily_coins,
    get_brick,
    get_counts,
    has_coin,
    has_favorite,
    has_like,
    insert_coin,
    insert_daily_coins,
    increment_daily_coins,
    sum_daily_coins,
    update_count,
)


# ===== 常量配置 =====
COIN_DAILY_LIMIT = 10      # 每日投币上限
COIN_MAX_PER_RESOURCE = 2  # 单资源最多投币次数


# ===== 资源表映射 =====
def _get_resource_table(resource_type):
    """类型 -> 表名。定义已收敛到 utils/constants.py。"""
    return resource_table(resource_type)


# ===== 获取资源计数缓存 =====
def _get_resource_counts(resource_type, resource_id):
    row = get_counts(resource_type, resource_id)
    if not row:
        return None
    return {
        'likes': row['likes_count'] or 0,
        'coins': row['coins_count'] or 0,
        'favorites': row['favorites_count'] or 0
    }


# ===== 更新资源计数 =====
def _update_resource_count(resource_type, resource_id, field, delta):
    if not _get_resource_table(resource_type):
        return False
    update_count(resource_type, resource_id, field, delta)
    return True


# ===== 获取用户互动状态（点赞/投币/收藏） =====
def _get_user_interaction_status(user_id, resource_type, resource_id):
    likes_on = has_like(user_id, resource_type, resource_id)
    coins_on = has_coin(user_id, resource_type, resource_id)
    favorites_on = has_favorite(user_id, resource_type, resource_id)
    return bool(likes_on), bool(coins_on), bool(favorites_on)


# ===== 获取用户今日剩余投币次数 =====
def _get_coins_remaining(user_id):
    today = date.today()
    used = sum_daily_coins(user_id, today)
    return max(0, COIN_DAILY_LIMIT - used)


# ===== 获取用户砖块余额 =====
def _get_user_brick(user_id):
    row = get_brick(user_id)
    return row if row else 0.0


# ===== 更新用户砖块余额 =====
def _update_user_brick(user_id, delta):
    add_brick(user_id, delta)


# ===== 获取用户对某资源的投币次数 =====
def _get_user_coin_count(user_id, resource_type, resource_id):
    """获取用户对某资源的投币次数"""
    return count_user_coins(user_id, resource_type, resource_id)


# ===== 别名（保持命名一致） =====
def _get_user_resource_coin_count(user_id, resource_type, resource_id):
    """与 _get_user_coin_count 功能相同，保留两个名字以防兼容问题"""
    return _get_user_coin_count(user_id, resource_type, resource_id)