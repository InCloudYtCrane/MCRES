# utils/announce.py
"""
公告读取（Phase P 后版本）

数据来源：site_announcements 表。
admin 侧已经直接写表，主站直接读表，不再需要懒同步。
"""
import json

from utils.data.repositories import site as site_repo
from utils.time import datetime_fmt


# ============================================================
# 对外：读公告
# ============================================================
def get_active_announcements():
    """
    返回当前生效的公告列表。

    生效判定：
        · is_active = 1
        · start_at 为空 或 <= 当前时间
        · end_at   为空 或 >= 当前时间

    返回结构：
        [{'title': ..., 'content': ..., **extra}, ...]
        —— 与原 JSON 中每条的 dict 完全一致。
    """
    now = datetime_fmt.now()

    try:
        rows = site_repo.list_active_announcements(now)
    except Exception:
        return []

    if not rows:
        return []

    result = []
    for r in rows:
        item = {
            'title':   r.get('title') or '',
            'content': r.get('content') or '',
        }

        extra_raw = r.get('extra_json')
        if extra_raw:
            try:
                extra = (
                    json.loads(extra_raw)
                    if isinstance(extra_raw, str)
                    else extra_raw
                )
                if isinstance(extra, dict):
                    for k, v in extra.items():
                        if k not in ('title', 'content'):
                            item[k] = v
            except Exception:
                pass

        result.append(item)

    return result