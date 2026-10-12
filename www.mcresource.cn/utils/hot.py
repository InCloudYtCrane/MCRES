# utils/hot.py
"""资源热度评分。

本模块只做**纯计算**：把昨日浏览量换算成星级与评分等级。
数据访问已移到 `utils/data/repositories/system.py`。
"""
from datetime import datetime

from utils.constants import resource_table
from utils.data.repositories import system as system_repo


def archive_all_if_needed():
    """检测是否需要全量归档：今天还没归档过就执行一次全量归档。

    归档语义（与重构前完全一致）：
    · 状态行不存在 -> 建行并返回，本轮不归档；
    · 状态行日期 == 今天 -> 已归档，直接返回；
    · 否则把三张资源表的"今日浏览"滚成"昨日浏览"、清零今日计数，
      并更新状态行的日期。
    """
    today = datetime.now().date().isoformat()

    row = system_repo.get_archive_status()
    if not row:
        system_repo.insert_archive_status(today)
        return

    last_archive = row['last_archive_date']
    last_archive_str = last_archive.isoformat() if last_archive else None
    if last_archive_str == today:
        return

    system_repo.roll_over_daily_view_counts(today)
    system_repo.set_last_archive_date(today)


def get_yesterday_avg_by_type(resource_type):
    """
    获取指定类型所有资源昨日浏览量的平均值（用于评分基准）
    """
    archive_all_if_needed()

    table = resource_table(resource_type)
    if not table:
        return 0

    avg_count = system_repo.get_average_yesterday_views(table)
    if avg_count:
        return round(float(avg_count), 2)
    return 0


def render_stars(star_count):
    full = int(star_count)
    half = star_count - full >= 0.5
    empty = 5 - full - (1 if half else 0)
    stars = '★' * full
    if half:
        stars += '⯨'
    stars += '☆' * empty
    return stars


def calculate_hot_score(yesterday_view_count, avg_count):
    if avg_count <= 0:
        if yesterday_view_count > 0:
            return {
                'level': 'hot',
                'label': '独树一帜',
                'icon': 'fire',
                'color': '#f5a623',
                'star_count': 4.0,
                'star_display': '★★★★☆',
                'score': 2.0,
                'avg': 0,
                'yesterday_count': yesterday_view_count
            }
        else:
            return {
                'level': 'cold',
                'label': '门可罗雀',
                'icon': 'snowflake',
                'color': '#6b7480',
                'star_count': 0.0,
                'star_display': '☆☆☆☆☆',
                'score': 0,
                'avg': 0,
                'yesterday_count': yesterday_view_count
            }

    ratio = yesterday_view_count / avg_count

    if ratio >= 15.0:
        level = 'legend'
        emoji = '👑'
        label = '万众瞩目'
        color = '#ff2d55'
        star_count = 5.0
        icon = 'crown'
    elif ratio >= 8.0:
        level = 'blockbuster'
        emoji = '💎'
        label = '如日中天'
        color = '#ff6b6b'
        star_count = 4.5
        icon = 'gem'
    elif ratio >= 4.0:
        level = 'top'
        emoji = '⭐'
        label = '炙手可热'
        color = '#f5a623'
        star_count = 4.0
        icon = 'star'
    elif ratio >= 2.5:
        level = 'hot'
        emoji = '🔥'
        label = '门庭若市'
        color = '#55d88b'
        star_count = 3.5
        icon = 'fire'
    elif ratio >= 1.2:
        level = 'warm'
        emoji = '🌱'
        label = '崭露头角'
        color = '#4A90D9'
        star_count = 3.0
        icon = 'seedling'
    elif ratio >= 0.8:
        level = 'normal'
        emoji = '📈'
        label = '稳中有进'
        color = '#7ab7f0'
        star_count = 2.5
        icon = 'chart-line'
    elif ratio >= 0.4:
        level = 'quiet'
        emoji = '🌙'
        label = '养精蓄锐'
        color = '#8b949e'
        star_count = 2.0
        icon = 'moon'
    elif ratio >= 0.2:
        level = 'quiet'
        emoji = '🌙'
        label = '韬光养晦'
        color = '#8b949e'
        star_count = 1.5
        icon = 'moon'
    elif ratio >= 0.05:
        level = 'cold'
        emoji = '❄️'
        label = '门可罗雀'
        color = '#6b7480'
        star_count = 1.0
        icon = 'snowflake'
    else:
        level = 'cold'
        emoji = '❄️'
        label = '无人问津'
        color = '#6b7480'
        star_count = 0.5
        icon = 'snowflake'

    star_display = render_stars(star_count)

    return {
        'level': level,
        'label': label,
        'icon': icon,
        'color': color,
        'star_count': star_count,
        'star_display': star_display,
        'score': round(ratio, 2),
        'avg': round(avg_count, 1),
        'yesterday_count': yesterday_view_count
    }


def get_hot_score(resource_type, yesterday_view_count):
    avg_count = get_yesterday_avg_by_type(resource_type)
    return calculate_hot_score(yesterday_view_count, avg_count)