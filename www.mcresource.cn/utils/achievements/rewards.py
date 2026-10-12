# utils/achievements/rewards.py
"""奖励发放器（注册模式，方便扩展）"""
import json
import random
import logging

from utils.data.repositories import interaction as interaction_repo
from utils.data.repositories import profiles as profiles_repo
from utils.data.repositories import users as users_repo

logger = logging.getLogger(__name__)

_granters = {}


def register(reward_type):
    """注册一个奖励类型"""
    def deco(fn):
        _granters[reward_type] = fn
        return fn
    return deco


def grant(user_id, rewards):
    """批量发放奖励，返回发放结果列表"""
    if not rewards:
        return []
    granted = []
    for r in rewards:
        rt = r.get('type')
        granter = _granters.get(rt)
        if not granter:
            logger.warning(f"[rewards] 未注册的奖励类型: {rt}")
            continue
        try:
            result = granter(user_id, r)
            granted.append({'type': rt, 'result': result})
        except Exception as e:
            logger.error(f"[rewards] 发放失败 user={user_id} reward={r}: {e}")
    return granted


# ============================================================
# 内置奖励类型
# ============================================================

@register('brick')
def _grant_brick(user_id, r):
    """砖块：count 可以是数字或 [min, max]"""
    cnt = r.get('count', 0)
    if isinstance(cnt, (list, tuple)) and len(cnt) == 2:
        cnt = random.randint(int(cnt[0]), int(cnt[1]))
    cnt = int(cnt or 0)
    if cnt:
        interaction_repo.add_brick(user_id, cnt)
    return cnt


@register('reputation')
def _grant_reputation(user_id, r):
    cnt = int(r.get('count', 0) or 0)
    if cnt:
        users_repo.add_reputation(user_id, cnt)
    return cnt


@register('title')
def _grant_title(user_id, r):
    """头衔：追加到 user_info.titles.list"""
    from utils.text.titles import parse_titles
    row = profiles_repo.get_titles(user_id)
    data = parse_titles(row.get('titles') if row else None)
    title = {'text': r.get('text', ''), 'color': r.get('color', '#55d88b')}
    data['list'].append(title)
    profiles_repo.set_titles(user_id, json.dumps(data, ensure_ascii=False))
    return title