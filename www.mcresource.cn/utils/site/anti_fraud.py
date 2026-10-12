# utils/site/anti_fraud.py
"""防刷配置读取（默认值兜底 + 进程内 TTL 缓存）。

为什么加缓存
------------
`mcres/middleware.py` 的 `after_request` 里**每个 GET 都会调一次**
`get_anti_fraud_config()`，三条详情路由还会再调一次
（`detail.py` 的 `should_increment_view`）—— 154 条"路由×模式"记录里有 150 条
的 SQL 指纹都含这条查询，未命中的 4 条正好是 `middleware` 里 `/static`、
`/suggest` 那些提前 return 的白名单。

表本身只有 4 行键值，成本不在扫描量而在**每请求一次数据库往返**。

缓存策略
--------
* TTL 60 秒。写入方只有后台站点（`admin.mcresource.cn` 的 `POST /4_ts/config`），
  是管理员手改的分钟级节流参数，60 秒生效延迟可接受。
* 多 worker 各持一份缓存，最长一个 TTL 后一致。
* **失败结果不写入缓存** —— 否则一次瞬时故障会被放大成整个 TTL 都用默认值。
* 返回浅拷贝，调用方拿到的 dict 随便改也不会污染缓存。

需要"改完立刻生效"时调 `invalidate_cache()`（或重启进程）。
"""
import time

from utils.data.repositories import site as site_repo

#: 缓存有效期（秒）
CACHE_TTL_SECONDS = 60

#: 表里缺键时的兜底值（原实现把这份字典在 try/except 两支里各写了一遍）
DEFAULT_CONFIG = {
    'global_session_minutes': 1,
    'global_window_minutes': 10,
    'detail_session_minutes': 5,
    'detail_window_minutes': 60,
}

#: 进程内缓存：{'data': dict | None, 'expires_at': float}
_cache = {'data': None, 'expires_at': 0.0}


def _load_from_db():
    """真的读一次库并把缺失的键补齐。

    失败时**抛出异常**，由 `get_anti_fraud_config` 决定回退默认值
    （这样失败不会被缓存）。
    """
    rows = site_repo.list_anti_fraud_config()
    config = {}
    for row in rows:
        config[row['config_key']] = int(row['config_value'])
    for key, val in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = val
    return config


def get_anti_fraud_config():
    """从数据库读取防刷配置，表不存在或查询失败时返回默认值。"""
    now = time.time()
    cached = _cache['data']
    if cached is not None and now < _cache['expires_at']:
        return dict(cached)

    try:
        config = _load_from_db()
    except Exception:
        # 表不存在或查询失败，返回默认值（且不缓存这个失败结果）
        return dict(DEFAULT_CONFIG)

    _cache['data'] = config
    _cache['expires_at'] = now + CACHE_TTL_SECONDS
    return dict(config)


def invalidate_cache():
    """作废缓存，让下一次调用重新读库。"""
    _cache['data'] = None
    _cache['expires_at'] = 0.0
