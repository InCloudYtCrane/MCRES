# utils/time_utils.py
from datetime import datetime

def timesince(dt, default="刚刚"):
    """
    将 datetime 对象或标准格式字符串转为相对时间（中文）。
    例如：2秒前，5分钟前，2小时前，3天前，1个月前，1年前。
    """
    if not dt:
        return default

    # 如果传入的是字符串，尝试转为 datetime
    if isinstance(dt, str):
        try:
            # 标准格式 'YYYY-MM-DD HH:MM:SS'
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # 若无法解析，返回原字符串
            return dt

    # 如果 dt 不是 datetime 对象，直接返回
    if not isinstance(dt, datetime):
        return str(dt)

    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 0:
        # 未来时间，返回绝对时间字符串
        return dt.strftime('%Y-%m-%d %H:%M')

    if seconds < 60:
        return f"{int(seconds)}秒前"
    minutes = seconds / 60
    if minutes < 60:
        return f"{int(minutes)}分钟前"
    hours = minutes / 60
    if hours < 24:
        return f"{int(hours)}小时前"
    days = hours / 24
    if days < 30:
        return f"{int(days)}天前"
    months = days / 30
    if months < 12:
        return f"{int(months)}个月前"
    years = months / 12
    return f"{int(years)}年前"