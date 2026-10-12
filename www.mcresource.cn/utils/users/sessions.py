# utils/sessions.py
"""
登录设备管理工具
"""
import uuid
from utils.time import datetime_fmt
from utils.data.repositories import sessions as sessions_repo


# ============================================================
# User-Agent 解析
# ============================================================
def parse_user_agent(ua):
    """解析 User-Agent → (device_type, device_name)"""
    ua = (ua or '').lower()

    if 'ipad' in ua or 'tablet' in ua or ('android' in ua and 'mobile' not in ua):
        device_type = 'tablet'
    elif any(k in ua for k in ('mobile', 'iphone', 'ipod', 'android',
                               'windows phone', 'blackberry')):
        device_type = 'mobile'
    else:
        device_type = 'desktop'

    if 'windows' in ua:
        os_name = 'Windows'
    elif 'iphone' in ua or 'ipad' in ua or 'ios' in ua:
        os_name = 'iOS'
    elif 'mac os' in ua or 'macintosh' in ua:
        os_name = 'macOS'
    elif 'android' in ua:
        os_name = 'Android'
    elif 'linux' in ua:
        os_name = 'Linux'
    else:
        os_name = '未知系统'

    if 'edg/' in ua or 'edge/' in ua:
        browser = 'Edge'
    elif 'chrome/' in ua and 'edg' not in ua:
        browser = 'Chrome'
    elif 'firefox/' in ua:
        browser = 'Firefox'
    elif 'safari/' in ua and 'chrome' not in ua:
        browser = 'Safari'
    else:
        browser = '未知浏览器'

    return device_type, f'{os_name} · {browser}'


# ============================================================
# IP 属地兜底（仅当调用方没传 ip_region 时才用）
# ============================================================
def get_ip_region_full(ip):
    """兜底用：返回「省 市」格式。正常情况下调用方会传已算好的 ip_region"""
    if not ip:
        return '未知'
    if ip in ('127.0.0.1', '::1'):
        return '本地'

    try:
        from mcres import get_ip_region_city
        return get_ip_region_city(ip)
    except Exception:
        return '未知'


# ============================================================
# 创建 / 复用登录设备记录
# ============================================================
def create_user_session(user_id, ip, ip_region, user_agent):
    """
    创建（或复用）一条登录设备记录，返回 session_token。
    """
    device_type, device_name = parse_user_agent(user_agent)

    # ★ 优先用调用方传入的 ip_region（account.py 已用 get_ip_region_city 算好市级）
    if not ip_region:
        ip_region = get_ip_region_full(ip)

    now = datetime_fmt.now()
    token = uuid.uuid4().hex + uuid.uuid4().hex[:16]

    if user_agent:
        existing = sessions_repo.find_by_user_agent(user_id, user_agent)
    else:
        existing = sessions_repo.find_by_device_name(user_id, device_name)

    if existing:
        sessions_repo.refresh_token(
            existing['id'], token, device_type, device_name, ip, ip_region, now
        )
        return token

    sessions_repo.insert(user_id, token, device_name, device_type, user_agent,
                         ip, ip_region, now)
    return token


# ============================================================
# 会话校验
# ============================================================
def is_session_valid(user_id, token):
    """判断 session_token 是否仍存在于该用户名下"""
    if not token:
        return False
    return sessions_repo.is_valid(user_id, token)


def touch_session(token):
    """更新最后活跃时间"""
    if not token:
        return
    sessions_repo.touch(token, datetime_fmt.now())


# ============================================================
# 设备列表 / 删除
# ============================================================
def list_user_sessions(user_id, current_token=None):
    """列出该用户的所有登录设备，按 last_active 倒序。"""
    rows = sessions_repo.list_for_user(user_id)
    result = []
    for r in rows:
        result.append({
            'id': r['id'],
            'device_name': r['device_name'] or '未知设备',
            'device_type': r['device_type'] or 'desktop',
            'ip': r['ip'] or '—',
            'ip_region': r['ip_region'] or '未知',
            'login_time': r['login_time'].strftime('%Y-%m-%d %H:%M:%S') if r['login_time'] else '',
            'last_active': r['last_active'].strftime('%Y-%m-%d %H:%M:%S') if r['last_active'] else '',
            'is_current': (r['session_token'] == current_token) if current_token else False,
        })
    return result


def delete_user_session(user_id, session_id):
    """删除指定设备（只能删自己的）"""
    return sessions_repo.delete_one(user_id, session_id)


def delete_other_sessions(user_id, current_token):
    """踢掉该用户的所有其他设备"""
    return sessions_repo.delete_others(user_id, current_token)


# ============================================================
# 清理过期会话（可选，配合定时任务调用）
# ============================================================
def cleanup_expired_sessions(days=30):
    """清理 N 天未活跃的会话"""
    sessions_repo.delete_stale(days)
