# utils/achievements/checkers.py
"""
成就进度计算器（Checker）

每个 checker 都是：接收 (user_id, params) → 返回 int（进度值）。
"""
import json
import logging

from utils.data.repositories import achievements as achievements_repo
from utils.time import datetime_fmt
from utils.constants import RESOURCE_TABLE

logger = logging.getLogger(__name__)

# 别名：表名白名单与 SQL 一起迁到 achievements 仓储
_INTERACTION_TABLES = achievements_repo.INTERACTION_TABLES

# 别名：原模块内私有副本，已收敛到 utils/constants.py
_RESOURCE_TABLES = RESOURCE_TABLE


# ============================================================
# 路由访问
# ============================================================
def count_action_log(user_id, p):
    p = p or {}
    try:
        return achievements_repo.count_action_log(
            user_id, path=p.get('path'), prefix=p.get('prefix'),
            method=p.get('method'), status=p.get('status', '2xx3xx'),
            today_only=False,
        )
    except Exception as e:
        logger.error(f'[checker] action_log.count 失败 user={user_id}: {e}')
        return 0


def count_action_log_today(user_id, p):
    p = p or {}
    try:
        return achievements_repo.count_action_log(
            user_id, path=p.get('path'), prefix=p.get('prefix'),
            method=p.get('method'), status=p.get('status', '2xx3xx'),
            today_only=True,
        )
    except Exception as e:
        logger.error(f'[checker] action_log.count_today 失败 user={user_id}: {e}')
        return 0


# ============================================================
# 编辑次数
# ============================================================
def count_rv_total(user_id, p):
    try:
        return achievements_repo.count_versions_total(user_id)
    except Exception as e:
        logger.error(f'[checker] rv.count_total 失败 user={user_id}: {e}')
        return 0


def count_rv_today(user_id, p):
    try:
        return achievements_repo.count_versions_today(user_id)
    except Exception as e:
        logger.error(f'[checker] rv.count_today 失败 user={user_id}: {e}')
        return 0


def count_rv_range(user_id, p):
    p = p or {}
    start = p.get('start')
    end = p.get('end')
    if not start or not end:
        return 0
    try:
        return achievements_repo.count_versions_between(user_id, start, end)
    except Exception as e:
        logger.error(f'[checker] rv.count_range 失败 user={user_id}: {e}')
        return 0


# ============================================================
# 互动
# ============================================================
def count_interaction_given(user_id, p):
    p = p or {}
    table = p.get('table')
    if table not in _INTERACTION_TABLES:
        logger.warning(f'[checker] interaction.given 无效 table: {table}')
        return 0

    try:
        return achievements_repo.count_interaction_given(
            table, user_id, today=p.get('today'))
    except Exception as e:
        logger.error(f'[checker] interaction.given 失败 user={user_id}: {e}')
        return 0


def count_interaction_received(user_id, p):
    p = p or {}
    table = p.get('table')
    if table not in _INTERACTION_TABLES:
        return 0

    res_type = p.get('type')
    if res_type:
        if res_type not in _RESOURCE_TABLES:
            return 0
        targets = [res_type]
    else:
        targets = list(_RESOURCE_TABLES)

    token = f'#id={user_id}'
    total = 0

    for rt in targets:
        try:
            rows = achievements_repo.list_interaction_contents(
                table, rt, user_id) or []

            for row in rows:
                raw = row.get('content')
                if not raw:
                    continue
                try:
                    content = json.loads(raw) if isinstance(raw, str) else raw
                except (json.JSONDecodeError, TypeError):
                    continue
                authors = content.get('authors') or []
                if isinstance(authors, list) and token in authors:
                    total += 1
        except Exception as e:
            logger.error(f'[checker] interaction.received 失败 user={user_id}: {e}')
            continue

    return total


# ============================================================
# 元成就：完成所有每日成就
# ============================================================
def all_daily_done(user_id, p):
    p = p or {}
    exclude = p.get('exclude', 'daily_perfect')
    if isinstance(exclude, str):
        exclude_keys = {exclude}
    elif isinstance(exclude, (list, tuple)):
        exclude_keys = set(exclude)
    else:
        exclude_keys = {'daily_perfect'}

    try:
        rows = achievements_repo.list_daily_achievement_keys() or []
        keys = [r['key'] for r in rows if r['key'] not in exclude_keys]

        if not keys:
            return 0

        period = 'daily:' + datetime_fmt.today()
        row = achievements_repo.count_completed_in(user_id, period, keys)
        done = int(row['cnt'] or 0) if row else 0
        return 1 if done >= len(keys) else 0
    except Exception as e:
        logger.error(f'[checker] all_daily_done 失败 user={user_id}: {e}')
        return 0


# ============================================================
# 用户 ID 阈值（前 N 名）
# ============================================================
def user_id_le(user_id, p):
    """
    判定：用户 ID ≤ 阈值。

    params:
        max_id : int  阈值（含）

    返回 1（达标）或 0（不达标）。
    """
    p = p or {}
    try:
        max_id = int(p.get('max_id', 0))
    except (TypeError, ValueError):
        return 0
    if max_id <= 0:
        return 0
    return 1 if user_id <= max_id else 0


# ============================================================
# 人工授予型（永远返回 0）
# ============================================================
def manual_only(user_id, p):
    """
    人工授予型成就。永远返回 0，需要管理员通过后台接口手动授予。
    """
    return 0


# ============================================================
# 注册表
# ============================================================
_CHECKERS = {
    'action_log.count':               count_action_log,
    'action_log.count_today':         count_action_log_today,
    'resource_versions.count_total':  count_rv_total,
    'resource_versions.count_today':  count_rv_today,
    'resource_versions.count_range':  count_rv_range,
    'interaction.given':              count_interaction_given,
    'interaction.received':           count_interaction_received,
    'achievements.all_daily_done':    all_daily_done,
    'user.id_le':                     user_id_le,
    'manual.only':                    manual_only,
}


def get(name):
    return _CHECKERS.get(name)


def all_names():
    return sorted(_CHECKERS.keys())