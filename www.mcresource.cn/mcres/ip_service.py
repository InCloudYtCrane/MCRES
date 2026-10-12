# mcres/ip_service.py
"""
全自动 IP 封禁系统（跨子域名共享）

组件：
  · ip_whitelist    白名单（DB，缓存 5 min）
  · ip_blacklist    黑名单（DB，跨域版本号同步）
  · ip_violation    违规记录（累进计分，7 天窗口）
  · ip_ban_state    跨域版本号（一行，version 字段）

跨子域名同步机制：
  1. 任一子域写入黑名单 → ip_ban_state.version += 1
  2. 所有子域每 2 秒检查一次 version
  3. version 变化 → 重载本地黑名单缓存
  4. 兜底：每 30 秒强制重载一次（防手动 SQL 改库未 bump）

自动封禁策略：
  · 敏感路径扫描    +3 分
  · 攻击工具 UA     +5 分
  · 请求速率超限    +2 分
  · 4xx 洪水        +3 分

封禁阶梯（7 天累计分）：
  ≥ 10   → 封 1 小时
  ≥ 25   → 封 1 天
  ≥ 50   → 封 7 天
  ≥ 100  → 永久封禁

豁免：
  · ip_whitelist 表中的 IP
  · 私有 / 回环 / 链路本地 IP

IP 属地查询：
  · get_ip_region(ip)      → 省级（用于日志）
  · get_ip_region_city(ip) → 「省 市」格式（用于登录设备管理）
"""
import hashlib
import ipaddress
import json
import os
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

from flask import request

from utils.data.repositories import ip_rules
from utils.time import datetime_fmt


from .config import VISIT_SALT


# ============================================================
# 配置
# ============================================================
BLACKLIST_CACHE_TTL              = 30   # 兜底强制重载间隔（秒）
BLACKLIST_VERSION_CHECK_INTERVAL = 2    # 版本号检查节流（秒）
WHITELIST_CACHE_TTL              = 300  # 白名单缓存（秒）
VIOLATION_WINDOW_DAYS            = 7
RATE_WINDOW_SECONDS              = 60
RATE_MAX_REQUESTS                = 300
FOURXX_WINDOW_SECONDS            = 300
FOURXX_MAX_COUNT                 = 20

# ---------- IP 数据库路径（根目录下的 ip_region 文件夹） ----------
IP_DB_DIR = os.environ.get(
    'IP_DB_DIR',
    os.path.join(os.getcwd(), 'ip_region')
)
IP_V4_DB_PATH = os.path.join(IP_DB_DIR, 'ip2region_v4.xdb')
IP_V6_DB_PATH = os.path.join(IP_DB_DIR, 'ip2region_v6.xdb')
IP_GEO_CN_DB_PATH = os.path.join(IP_DB_DIR, 'GeoCN.mmdb')
IP_DIVISION_JSON_PATH = os.path.join(IP_DB_DIR, 'division_code_to_city.json')

IP_V4_DB_URL = os.environ.get(
    'IP_V4_DB_URL',
    'https://gitee.com/lionsoul/ip2region/raw/master/data/ip2region_v4.xdb'
)
IP_V6_DB_URL = os.environ.get(
    'IP_V6_DB_URL',
    'https://gitee.com/lionsoul/ip2region/raw/master/data/ip2region_v6.xdb'
)
IP_GEO_CN_DB_URL = os.environ.get(
    'IP_GEO_CN_DB_URL',
    'https://github.com/ljxi/GeoCN/releases/latest/download/GeoCN.mmdb'
)
IP_DB_MAX_AGE_DAYS = 30


# ============================================================
# 行政区划代码 → (省, 市) 映射（从 JSON 加载）
# ============================================================
def _load_division_code_map():
    try:
        with open(IP_DIVISION_JSON_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        result = {}
        for k, v in raw.items():
            if isinstance(v, list) and len(v) >= 2:
                result[str(k)] = (str(v[0]), str(v[1]))
            elif isinstance(v, str):
                result[str(k)] = (v, '')
        return result
    except Exception as e:
        print(f"⚠️ 加载 division_code_to_city.json 失败: {e}")
        return {}


_DIVISION_CODE_TO_CITY = _load_division_code_map()


_BAN_TIERS = [
    (10,   60),
    (25,   60 * 24),
    (50,   60 * 24 * 7),
    (100,  None),
]

_SENSITIVE_PATHS = (
    '/.env', '/.git', '/.svn', '/.htaccess', '/.DS_Store',
    '/wp-admin', '/wp-login', '/wp-content', '/wp-includes',
    '/phpmyadmin', '/pma/', '/adminer',
    '/xmlrpc.php', '/phpinfo', '/info.php',
    '/cgi-bin/', '/shell.php', '/cmd.php',
    '/config.php', '/configuration.php',
)

_BAD_UA_KEYWORDS = (
    'sqlmap', 'nikto', 'nmap', 'masscan', 'acunetix',
    'nessus', 'openvas', 'w3af', 'dirbuster', 'gobuster',
    'wfuzz', 'hydra', 'zgrab', 'xray', 'pocscan',
)

_MAX_TRACKED_IPS = 10000


# ============================================================
# 缓存 & 计数器
# ============================================================
_blacklist_cache = {
    'data': {},                # {ip: {'reason', 'created_at', 'expires_at'}}
    'version': -1,
    'loaded_at': 0.0,
    'version_checked_at': 0.0,
}
_whitelist_cache = {'data': set(), 'loaded_at': 0.0}

_rate_counter   = defaultdict(list)
_fourxx_counter = defaultdict(list)


def _invalidate_blacklist_cache():
    _blacklist_cache['version'] = -1
    _blacklist_cache['loaded_at'] = 0.0


def _invalidate_whitelist_cache():
    _whitelist_cache['loaded_at'] = 0.0


# ============================================================
# 真实 IP（适配 Nginx real_ip 模块）
# ============================================================
def get_real_ip():
    """
    获取真实用户 IP。
    Nginx 已通过 real_ip 模块把 $remote_addr 换成 CF-Connecting-IP 值，
    并通过 X-Real-IP 转发给后端，因此优先信任 X-Real-IP。
    """
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip.strip()

    cf_ip = request.headers.get('CF-Connecting-IP')
    if cf_ip:
        return cf_ip.strip()

    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()

    return request.remote_addr or ''


# ============================================================
# 私有 IP 判定
# ============================================================
def _is_private_ip(ip):
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


# ============================================================
# 白名单
# ============================================================
def _load_whitelist_from_db():
    try:
        return {r['ip'] for r in ip_rules.list_whitelist_ips() if r.get('ip')}
    except Exception:
        return set()


def get_whitelist():
    now = time.time()
    if now - _whitelist_cache['loaded_at'] > WHITELIST_CACHE_TTL:
        _whitelist_cache['data'] = _load_whitelist_from_db()
        _whitelist_cache['loaded_at'] = now
    return _whitelist_cache['data']


def is_whitelisted(ip):
    if not ip:
        return True
    if _is_private_ip(ip):
        return True
    return ip in get_whitelist()


# ============================================================
# 跨域版本号
# ============================================================
def _bump_blacklist_version():
    """写入黑名单后调用：让所有子域感知变化。"""
    try:
        ip_rules.bump_ban_version()
        _blacklist_cache['version'] = -1
        _blacklist_cache['version_checked_at'] = 0.0
        _blacklist_cache['loaded_at'] = 0.0
    except Exception:
        pass


def _get_remote_version():
    return ip_rules.get_remote_ban_version()


# ============================================================
# 黑名单
# ============================================================
def _load_blacklist_from_db():
    """
    从数据库拉取所有生效中的黑名单。
    ★ 同时读取 created_at，供封禁页展示"触发时间"。
    """
    now = datetime.now()
    # 先把已过期的自动下线
    ip_rules.deactivate_expired_bans(now)
    rows = ip_rules.list_active_bans()
    data = {}
    for r in rows:
        data[r['ip']] = {
            'reason': r.get('reason') or '',
            'expires_at': r.get('expires_at'),
            'created_at': r.get('created_at'),
        }
    return data


def get_blacklist():
    """
    读黑名单（带跨域版本同步）。
    """
    now = time.time()

    # ---- 版本检查（带节流）----
    if now - _blacklist_cache['version_checked_at'] >= BLACKLIST_VERSION_CHECK_INTERVAL:
        remote_ver = _get_remote_version()
        _blacklist_cache['version_checked_at'] = now
        if remote_ver != _blacklist_cache['version']:
            _blacklist_cache['data'] = _load_blacklist_from_db()
            _blacklist_cache['version'] = remote_ver
            _blacklist_cache['loaded_at'] = now
            return _blacklist_cache['data']

    # ---- 兜底：距上次全量重载 ≥ 30 秒，强制刷新 ----
    if now - _blacklist_cache['loaded_at'] >= BLACKLIST_CACHE_TTL:
        _blacklist_cache['data'] = _load_blacklist_from_db()
        _blacklist_cache['loaded_at'] = now
        _blacklist_cache['version'] = _get_remote_version()

    return _blacklist_cache['data']


def is_blocked(ip):
    if not ip:
        return False
    return ip in get_blacklist()


def record_block_hit(ip):
    if not ip:
        return
    try:
        ip_rules.increment_hit_count(ip)
    except Exception:
        pass


def remove_ip_from_blacklist(ip):
    """应用内解封（自动 bump 版本号，跨域立即生效）。"""
    if not ip:
        return False
    affected = ip_rules.deactivate_ban(ip)
    if affected > 0:
        _bump_blacklist_version()
    return affected > 0


# ============================================================
# 违规上报 & 累进封禁
# ============================================================
def _calc_ban_duration(total_score):
    for threshold, duration in reversed(_BAN_TIERS):
        if total_score >= threshold:
            return duration
    return 0


def _apply_ban(ip, score, rule, detail):
    duration = _calc_ban_duration(score)
    if duration == 0:
        return False

    if duration is None:
        reason = f'[自动/永久] 累计违规 {score} 分（{rule}）：{detail[:120]}'
        expires_at = None
    else:
        if duration >= 60 * 24:
            label = f'{duration // (60 * 24)} 天'
        else:
            label = f'{duration // 60} 小时'
        reason = f'[自动/{label}] 累计违规 {score} 分（{rule}）：{detail[:120]}'
        expires_at = datetime.now() + timedelta(minutes=duration)

    ip_rules.upsert_auto_ban(ip, reason, datetime_fmt.now(), expires_at)

    _bump_blacklist_version()
    return True


def report_violation(ip, rule, score, detail=''):
    if not ip or is_whitelisted(ip):
        return False

    try:
        ua = ''
        method = ''
        path = ''
        try:
            method = request.method or ''
            path = (request.path or '')[:255]
            ua = (request.headers.get('User-Agent', '') or '')[:255]
        except Exception:
            pass

        ip_rules.insert_violation(
            ip, rule, score, (detail or '')[:255],
            method[:16], path, ua, datetime_fmt.now()
        )
    except Exception:
        pass

    try:
        window_start = (
            datetime.now() - timedelta(days=VIOLATION_WINDOW_DAYS)
        ).strftime('%Y-%m-%d %H:%M:%S')
        row = ip_rules.sum_violation_score(ip, window_start)
        total_score = int(row['total']) if row else 0
    except Exception:
        return False

    return _apply_ban(ip, total_score, rule, detail)


# ============================================================
# 检测规则
# ============================================================
def is_sensitive_path(path):
    if not path:
        return False
    low = path.lower()
    return any(low.startswith(p) for p in _SENSITIVE_PATHS)


def is_bad_user_agent(ua):
    if not ua:
        return False
    low = ua.lower()
    return any(kw in low for kw in _BAD_UA_KEYWORDS)


def is_rate_limited(ip):
    if not ip:
        return False
    now = time.time()
    bucket = _rate_counter[ip]
    bucket.append(now)

    cutoff = now - RATE_WINDOW_SECONDS
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)

    if len(_rate_counter) > _MAX_TRACKED_IPS:
        _prune_counter(_rate_counter)

    return len(bucket) > RATE_MAX_REQUESTS


def count_4xx(ip):
    if not ip:
        return False
    now = time.time()
    bucket = _fourxx_counter[ip]
    bucket.append(now)

    cutoff = now - FOURXX_WINDOW_SECONDS
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)

    if len(_fourxx_counter) > _MAX_TRACKED_IPS:
        _prune_counter(_fourxx_counter)

    return len(bucket) >= FOURXX_MAX_COUNT


def consume_4xx_bucket(ip):
    _fourxx_counter.pop(ip, None)


def _prune_counter(counter):
    if len(counter) <= _MAX_TRACKED_IPS:
        return
    sorted_items = sorted(
        counter.items(),
        key=lambda kv: kv[1][-1] if kv[1] else 0
    )
    to_remove = len(counter) - _MAX_TRACKED_IPS
    for k, _ in sorted_items[:to_remove]:
        counter.pop(k, None)


# ============================================================
# 定期清理
# ============================================================
def cleanup_old_violations(days=30):
    try:
        affected = ip_rules.delete_old_violations(days)
        print(f"✅ 已清理 {affected} 条过期违规记录")
        return affected
    except Exception as e:
        print(f"⚠️ 清理违规记录失败: {e}")
        return 0


# ============================================================
# IP 属地数据库（ip2region + GeoCN 双库）
# ============================================================
try:
    import ip2region.searcher as xdb
    import ip2region.util as util
    HAS_IP2REGION = True
except ImportError:
    HAS_IP2REGION = False
    print("⚠️ py-ip2region 未安装，请运行: pip install py-ip2region")

try:
    import maxminddb
    HAS_MAXMINDDB = True
except ImportError:
    HAS_MAXMINDDB = False
    print("⚠️ maxminddb 未安装，请运行: pip install maxminddb")


_searcher_v4 = None
_searcher_v6 = None
_geocn_reader = None


def download_file(url, dest, retries=3, timeout=60):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for attempt in range(retries):
        try:
            print(f"📥 正在下载 {os.path.basename(dest)} (尝试 {attempt+1}/{retries})...")
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                with open(dest, 'wb') as f:
                    f.write(resp.read())
            print(f"✅ 下载成功 -> {dest}")
            return True
        except Exception as e:
            print(f"⚠️ 下载失败: {e}")
            if attempt < retries - 1:
                print("🔄 等待 2 秒后重试...")
                time.sleep(2)
    return False


def ensure_ip_db_downloaded():
    """确保 IPv4 / IPv6 / GeoCN 三个数据库都存在且未过期。"""
    tasks = (
        (IP_V4_DB_URL, IP_V4_DB_PATH, 'ip2region_v4', 1),
        (IP_V6_DB_URL, IP_V6_DB_PATH, 'ip2region_v6', 1),
        (IP_GEO_CN_DB_URL, IP_GEO_CN_DB_PATH, 'GeoCN', 0),
    )
    for url, path, label, auto_download in tasks:
        if not os.path.exists(path):
            if auto_download:
                print(f"📦 {label} 未找到，开始自动下载...")
                download_file(url, path)
            else:
                print(f"⚠️ {label} 未找到，请手动下载: {url}")
        else:
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if (datetime.now() - mtime) > timedelta(days=IP_DB_MAX_AGE_DAYS):
                if auto_download:
                    print(f"🔄 {label} 已超过 {IP_DB_MAX_AGE_DAYS} 天，开始更新...")
                    download_file(url, path)
    return True


def _parse_ip2region_result(result):
    if not result:
        return None
    parts = result.split('|')
    country = parts[0] if len(parts) > 0 else ''
    province = parts[1] if len(parts) > 1 else ''
    city = parts[2] if len(parts) > 2 else ''
    if not country or country == '0':
        return None
    if province == '0':
        province = ''
    if city == '0':
        city = ''
    return (country, province, city)


def _query_ip2region(ip, is_v6):
    searcher = _searcher_v6 if is_v6 else _searcher_v4
    if searcher is None:
        return None
    try:
        return _parse_ip2region_result(searcher.search(ip))
    except Exception:
        return None


def _query_geocn(ip):
    """用 maxminddb 直读 GeoCN。返回 (country, province, city) 或 None"""
    if _geocn_reader is None:
        return None
    try:
        record = _geocn_reader.get(ip)
    except Exception:
        return None
    if not record:
        return None

    division_code = record.get('division_code')
    if not division_code:
        return None

    code_str = str(division_code)
    if len(code_str) < 4:
        return None

    region = _DIVISION_CODE_TO_CITY.get(code_str[:4])
    if not region:
        return None

    province, city = region
    return ('中国', province, city)


def _pick_region(r_ip2region, r_geocn, is_v6):
    """优先 GeoCN，失败回退 ip2region"""
    if r_geocn:
        return r_geocn
    if r_ip2region:
        return r_ip2region
    return None


def get_ip_region(ip):
    """
    查询 IP 属地（**省级**，用于日志）。
    · 中国：返回省级
    · 海外：返回国家
    """
    if not ip:
        return '未知'

    ip = str(ip).strip()
    if not ip:
        return '未知'
    if ip in ('127.0.0.1', '::1', 'localhost'):
        return '本地'

    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return '未知'

    if addr.is_private or addr.is_loopback or addr.is_link_local:
        return '内网'

    is_v6 = isinstance(addr, ipaddress.IPv6Address)

    r_ip2region = _query_ip2region(ip, is_v6)
    r_geocn = _query_geocn(ip)

    picked = _pick_region(r_ip2region, r_geocn, is_v6)
    if not picked:
        return '未知'

    country, province, _city = picked
    if country == '中国' and province:
        return province
    return country or '未知'


def get_ip_region_city(ip):
    """
    查询 IP 属地（**「省 市」格式**，用于登录设备管理）。
    · 国内非直辖市：返回「省 市」，如「浙江省 杭州市」
    · 直辖市：只返回市名，如「北京市」
    · 省直辖县级行政区划：只返回省名
    · 海外：返回国家名
    """
    if not ip:
        return '未知'

    ip = str(ip).strip()
    if not ip:
        return '未知'
    if ip in ('127.0.0.1', '::1', 'localhost'):
        return '本地'

    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return '未知'

    if addr.is_private or addr.is_loopback or addr.is_link_local:
        return '内网'

    is_v6 = isinstance(addr, ipaddress.IPv6Address)

    r_ip2region = _query_ip2region(ip, is_v6)
    r_geocn = _query_geocn(ip)

    picked = _pick_region(r_ip2region, r_geocn, is_v6)
    if not picked:
        return '未知'

    country, province, city = picked

    if country == '中国':
        # 省直辖县级行政区划 → 只返回省名
        if city and city not in ('省直辖县级行政区划',):
            # 直辖市：province == city（如「北京市」「上海市」）
            if province and city == province:
                return province
            # 普通省市：返回「省 市」
            if province and city:
                return f'{province} {city}'
            # 只有市没有省
            if city:
                return city
        # 只有省
        if province:
            return province
        return '未知'

    return country or '未知'


def hash_ip(ip):
    salt = VISIT_SALT or 'mcres-fixed-salt'
    return hashlib.sha256(f"{ip}|{salt}".encode()).hexdigest()


def init_ip_database():
    """初始化 ip2region (v4/v6) + GeoCN 三个数据源。"""
    global _searcher_v4, _searcher_v6, _geocn_reader
    _searcher_v4 = None
    _searcher_v6 = None
    _geocn_reader = None

    ensure_ip_db_downloaded()

    # ---- ip2region IPv4 ----
    if HAS_IP2REGION and os.path.exists(IP_V4_DB_PATH):
        try:
            _searcher_v4 = xdb.new_with_file_only(util.IPv4, IP_V4_DB_PATH)
            print(f"✅ ip2region IPv4 数据库加载成功 -> {IP_V4_DB_PATH}")
        except Exception as e:
            print(f"⚠️ ip2region IPv4 加载失败: {e}")
    elif HAS_IP2REGION:
        print(f"⚠️ ip2region IPv4 数据库不存在: {IP_V4_DB_PATH}")

    # ---- ip2region IPv6 ----
    if HAS_IP2REGION and os.path.exists(IP_V6_DB_PATH):
        try:
            _searcher_v6 = xdb.new_with_file_only(util.IPv6, IP_V6_DB_PATH)
            print(f"✅ ip2region IPv6 数据库加载成功 -> {IP_V6_DB_PATH}")
        except Exception as e:
            print(f"⚠️ ip2region IPv6 加载失败: {e}")
    elif HAS_IP2REGION:
        print(f"⚠️ ip2region IPv6 数据库不存在: {IP_V6_DB_PATH}")

    # ---- GeoCN ----
    if HAS_MAXMINDDB and os.path.exists(IP_GEO_CN_DB_PATH):
        try:
            _geocn_reader = maxminddb.open_database(IP_GEO_CN_DB_PATH)
            print(f"✅ GeoCN 数据库加载成功 -> {IP_GEO_CN_DB_PATH}")
        except Exception as e:
            print(f"⚠️ GeoCN 加载失败: {e}")
    elif HAS_MAXMINDDB:
        print(f"⚠️ GeoCN 数据库不存在，请手动下载: {IP_GEO_CN_DB_URL}")