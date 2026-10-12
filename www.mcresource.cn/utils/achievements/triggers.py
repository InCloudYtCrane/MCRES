# utils/achievements/triggers.py
"""触发器语法糖"""
from .registry import RouteTrigger, EventTrigger


def on_route(method=None, path=None):
    """
    匹配 HTTP 请求。

    on_route(method='POST', path=r'^/resourcepack/new$')
    on_route(path=r'^/interaction$')          # 不限 method
    """
    return RouteTrigger(method=method, path=path)


def on_event(event_type):
    """
    匹配业务代码显式抛出的事件。

    业务侧：trigger('user.login', uid, {'consecutive_days': 7})
    规则侧：on_event('user.login')
    """
    return EventTrigger(event_type)