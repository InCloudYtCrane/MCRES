# utils/achievements/registry.py
import re
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 触发器：决定一条成就"在什么条件下被激活"
# ============================================================
class Trigger:
    def match(self, ctx):
        raise NotImplementedError


class RouteTrigger(Trigger):
    """匹配 HTTP 请求：method + path 正则"""

    def __init__(self, method=None, path=None):
        if not path:
            raise ValueError("RouteTrigger 需要 path 参数")
        self.method = method.upper() if method else None
        self.path_re = re.compile(path)

    def match(self, ctx):
        req = ctx.get('request')
        if not req:
            return False
        if self.method and req.method != self.method:
            return False
        return bool(self.path_re.search(req.path))

    def __repr__(self):
        return f"RouteTrigger({self.method}, {self.path_re.pattern})"


class EventTrigger(Trigger):
    """匹配业务代码显式抛出的事件"""

    def __init__(self, event_type):
        self.event_type = event_type

    def match(self, ctx):
        return ctx.get('event_type') == self.event_type

    def __repr__(self):
        return f"EventTrigger({self.event_type})"


# ============================================================
# 规则对象
# ============================================================
class Rule:
    __slots__ = (
        'key', 'name', 'desc', 'icon', 'rarity', 'category',
        'trigger', 'agg', 'reward', 'value_fn', 'filter_fn', 'is_hidden',
    )

    def __init__(self, key, name, desc, icon, rarity, category,
                 trigger, agg, reward, value_fn=None, filter_fn=None, is_hidden=False):
        self.key = key
        self.name = name
        self.desc = desc
        self.icon = icon
        self.rarity = rarity
        self.category = category
        self.trigger = trigger
        self.agg = agg
        self.reward = reward
        self.value_fn = value_fn
        self.filter_fn = filter_fn
        self.is_hidden = is_hidden


# ============================================================
# 注册中心（模块级单例）
# ============================================================
_route_rules = []
_event_rules = {}   # {event_type: [Rule]}
_all_rules = {}     # {key: Rule}


def register_rule(rule):
    if rule.key in _all_rules:
        raise ValueError(f"[achievements] 重复的成就 key: {rule.key}")
    _all_rules[rule.key] = rule

    if isinstance(rule.trigger, RouteTrigger):
        _route_rules.append(rule)
    elif isinstance(rule.trigger, EventTrigger):
        _event_rules.setdefault(rule.trigger.event_type, []).append(rule)
    else:
        raise TypeError(f"[achievements] 未知触发器类型: {type(rule.trigger)}")


def get_route_rules():
    return _route_rules


def get_event_rules(event_type):
    return _event_rules.get(event_type, [])


def get_all_rules():
    return list(_all_rules.values())


def get_rule(key):
    return _all_rules.get(key)


# ============================================================
# 用户接口：achievement(...)
# ============================================================
def achievement(*, key, name=None, desc='', icon='fa-trophy',
                rarity='common', category='permanent',
                trigger, agg=None, reward=None,
                value=None, filter=None, is_hidden=False):
    """
    注册一条成就。

    参数：
        key        唯一标识
        name       展示名
        desc       描述
        icon       FontAwesome 图标
        rarity     common / rare / epic / legendary
        category   permanent / daily / weekly / limited
        trigger    on_route(...) 或 on_event(...)
        agg        {'type': 'count'|'sum'|'max'|'exists', 'target': N}
        reward     [{'type': 'brick'|'reputation'|'title', ...}, ...]
        value      callable(ctx) -> int，自定义本次事件的 delta（默认 1）
        filter     callable(ctx) -> bool，额外过滤条件
        is_hidden  隐藏成就（前端未完成时显示 ???）
    """
    if not key:
        raise ValueError("achievement 需要 key")
    if trigger is None:
        raise ValueError(f"achievement {key} 需要 trigger")

    rule = Rule(
        key=key,
        name=name or key,
        desc=desc,
        icon=icon,
        rarity=rarity,
        category=category,
        trigger=trigger,
        agg=agg or {'type': 'count', 'target': 1},
        reward=reward or [],
        value_fn=value,
        filter_fn=filter,
        is_hidden=is_hidden,
    )
    register_rule(rule)
    return rule