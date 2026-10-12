# utils/users/bans.py
"""`user_info.ban` 字段的解析与到期判定。

背景（安全批次 A4）
------------------
`ban` 是一个 JSON 字段，形如：

    {"login":  {"deadline": "2026-01-01T12:00:00.123456", "reason": ..., "operator": 3},
     "comment": {"deadline": "2026-01-01 12:00:00",        "reason": ...}}

**deadline 有两种写法**：

1. 本仓 `utils/users/punishment.py` 写的 `datetime.isoformat()`，
   用 `T` 分隔：`'2026-01-01T12:00:00.123456'`
2. 后台/历史数据写的空格分隔格式：`'2026-01-01 12:00:00'`

原先所有判定都是**直接拿字符串比**（`deadline > datetime.now().isoformat()`）。
字符串比较在**同一天**必然出错：比到第 11 个字符时 `' '`(0x20) < `'T'`(0x54)，
于是同一日期下空格格式的 deadline 恒被判定为"已过期"：

    '2026-01-01 23:00:00' <= '2026-01-01T10:00:00'  →  True  ← 错！禁言还剩 13 小时

后果是**当天到期的封禁被静默解除**（`templating.py` / `account.py` 会把它从
`ban` 字段里删掉），登录/评论/编辑的封禁检查随之放行。

修法：统一走 `is_ban_active()`，先把 deadline 解析成 `datetime` 再比。
"""
from datetime import datetime

#: 兜底解析格式（`fromisoformat` 认不出时才用）
_FALLBACK_FORMATS = (
    '%Y-%m-%d %H:%M:%S.%f',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%dT%H:%M:%S.%f',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%d',
    '%Y/%m/%d %H:%M:%S',
    '%Y/%m/%d',
)


def parse_deadline(value):
    """把 deadline 值解析成 `datetime`；不能解析时返回 None。

    兼容 `T` 分隔、空格分隔、带/不带微秒、只有日期这几种写法
    （Python 3.11+ 的 `fromisoformat` 已能吃下前四种，兜底格式是给
    斜杠分隔之类历史脏数据准备的）。
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None

    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass

    for fmt in _FALLBACK_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except (ValueError, TypeError):
            continue
    return None


def is_ban_active(ban_item, now=None):
    """某个 ban 条目是否仍在生效期内。

    参数
    ----
    ban_item : dict | None    ``ban`` 字段里的一个子项（如 ``ban_data['login']``）
    now      : datetime | None 判定基准时刻，默认 ``datetime.now()``

    语义（与原先各调用点的守卫保持一致，只修掉字符串比较）
    ----------------------------------------------------
    * 条目为空 / 没有 ``deadline`` → **False**
      （原先每个调用点都写了 ``and x.get('deadline')``，即无截止时间的条目
      不参与判定，这里保持不变）
    * 有 ``deadline`` 但解析不了 → **True**
      （宁可继续封着，也不因为一条脏数据把封禁静默解除）
    * 否则 → ``解析出的时间 > now``
    """
    if not ban_item:
        return False

    raw_deadline = ban_item.get('deadline')
    if not raw_deadline:
        return False

    deadline = parse_deadline(raw_deadline)
    if deadline is None:
        return True

    return deadline > (now or datetime.now())
