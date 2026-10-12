# utils/feed.py
import json
from utils.data.repositories import site as site_repo
from utils.data.repositories import users as users_repo
from utils.time import datetime_fmt

FEED_LIMIT = 500


def get_privacy_settings(user_id):
    """获取用户的隐私设置"""
    default = {'hide_login': False}
    row = users_repo.get_privacy_settings(user_id)
    if row and row.get('privacy_settings'):
        try:
            settings = json.loads(row['privacy_settings'])
            if isinstance(settings, dict):
                default.update(settings)
                return default
        except:
            pass
    return default


def should_add_feed(user_id, action):
    """
    检查是否应该添加这条动态
    如果 action 是 '登录' 且用户开启了 hide_login，则不添加
    """
    if action == '登录':
        settings = get_privacy_settings(user_id)
        if settings.get('hide_login', False):
            return False
    return True


def add_feed(user_id, action, target=None):
    """
    添加一条动态记录（登录动态受隐私设置控制）

    【Phase 2 · Step 2.3】
    只写 site_feed 表。
    push_settings.feed JSON 字段已停写（保留历史值，不再更新）。
    """
    if not should_add_feed(user_id, action):
        return

    site_repo.insert_feed(user_id, action, target, datetime_fmt.now())


def get_feed(limit=100):
    """
    获取最近 limit 条动态（按时间倒序）

    【Phase 2 · Step 2.3】
    改读 site_feed 表。
    返回的 dict 结构与旧 JSON 版本完全一致（含 'time' 字段），
    调用方（views/index.py）无需改动。
    """
    try:
        rows = site_repo.list_recent_feed(limit)
    except Exception:
        return []

    if not rows:
        return []

    result = []
    for r in rows:
        created_at = r.get('created_at')
        if hasattr(created_at, 'strftime'):
            time_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
        else:
            time_str = str(created_at) if created_at else ''

        item = {
            'user_id': r.get('user_id'),
            'action': r.get('action') or '',
            'time': time_str,
        }
        # 旧 JSON 里"没有 target 就不写这个键"，保持一致
        if r.get('target'):
            item['target'] = r['target']

        result.append(item)

    return result