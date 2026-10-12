# utils/data/repositories/resources.py
"""资源三表（resourcepacks / shaderpacks / maps）的共用查询。

为什么单独成模块
----------------
这三张表的查询在多个视图里被**逐字复制**，最典型的是"按类型取一行"：

    index.py:103-112        三条 if/elif 分支，只有表名不同
    new.py / edit.py / preset.py   各自又写一遍

以及"列表页取基础字段"：

    index.py:221        （首页分组）
    resource_lists.py:216（列表页）
    同一条 `SELECT id, content, view_count FROM <表> ORDER BY id DESC`

本模块把这些收敛成一份。表名一律来自 `utils/constants.py` 的
`RESOURCE_TABLE`，**不接受外部传入的表名**。

约定
----
· 函数名描述业务意图，不描述 SQL 形状。
· 参数一律 `%s` 占位；表名只来自常量。
· 返回 DictCursor 形状的 dict / list[dict]，与迁移前一致。
"""
from utils.constants import RESOURCE_TABLE, resource_table
from utils.data import execute_query, execute_update, fetch_one


def _table(resource_type):
    """把类型解析成表名；非法类型返回 None，由调用方决定回 400 还是 404。"""
    return resource_table(resource_type)


# ============================================================
# 取单行
# ============================================================
def get_for_card(resource_type, resource_id):
    """按类型取一行，字段供"资源卡片"使用（列表/推荐位）。

    对应 index.py:103-112 的三条分支。
    """
    table = _table(resource_type)
    if not table:
        return None
    return fetch_one(
        f'SELECT id, content, view_count, yesterday_view_count '
        f'FROM {table} WHERE id = %s',
        [resource_id],
    )


def get_full(resource_type, resource_id):
    """按类型取一行全部列（详情页、审核、回滚等）。

    对应 index.py:869 `SELECT * FROM {table} WHERE id = %s`。
    """
    table = _table(resource_type)
    if not table:
        return None
    return fetch_one(f'SELECT * FROM {table} WHERE id = %s', [resource_id])


def get_content(resource_type, resource_id):
    """只取 content 列（用于读名称/摘要等，避免拉整行）。

    对应 index.py:609,736 `SELECT content FROM {table} WHERE id = %s`。
    """
    table = _table(resource_type)
    if not table:
        return None
    return fetch_one(f'SELECT content FROM {table} WHERE id = %s', [resource_id])


def get_for_detail(resource_type, resource_id):
    """详情页取整行。

    原实现三条分支的列清单并不一致：`resourcepacks` 多取一个 `texture` 列，
    另外两张表没有。这里统一为 `SELECT *`，让三种类型走同一条语句
    （少一条不同的 SQL 语句，MySQL 侧也少一份解析），且调用方本来就用
    `row.get(...)` 取值 —— 多出的列不会被误用。**不要**据此把 body/content
    之外的敏感列写进模板。
    """
    table = _table(resource_type)
    if not table:
        return None
    return fetch_one(f'SELECT * FROM {table} WHERE id = %s', [resource_id])


def get_today_view_state(resource_type, resource_id):
    """取当日浏览状态，对应 detail.py:100 `ensure_today_date`。"""
    table = _table(resource_type)
    if not table:
        return None
    return fetch_one(
        f'SELECT today_date, today_view_count, yesterday_view_count '
        f'FROM {table} WHERE id = %s',
        [resource_id],
    )


def roll_over_today_if_stale(resource_type, resource_id, today):
    """把"今日浏览"滚成"昨日浏览"并重置今日计数。

    对应 detail.py:111-114。`AND today_date != %s` 是原实现的条件守卫，
    保持原样以保证并发下的行为不变。
    """
    table = _table(resource_type)
    if not table:
        return 0
    return execute_update(
        f'UPDATE {table} SET yesterday_view_count = today_view_count, '
        f'today_view_count = 0, today_date = %s '
        f'WHERE id = %s AND today_date != %s',
        [today, resource_id, today],
    )


def get_yesterday_view_count(resource_type, resource_id):
    """只取昨日浏览量，对应 detail.py:115-118。"""
    table = _table(resource_type)
    if not table:
        return None
    return fetch_one(
        f'SELECT yesterday_view_count FROM {table} WHERE id = %s',
        [resource_id],
    )


def get_ids(resource_type):
    """取某类型全部 id（升序），对应 index.py:576 的 count 模式。"""
    table = _table(resource_type)
    if not table:
        return []
    return execute_query(f'SELECT id FROM {table} ORDER BY id')


# ============================================================
# 取多行
# ============================================================
def list_for_cards(resource_type, limit=None):
    """列表页/首页分组用的基础字段列表。

    · `limit=None` -> 全表（列表页现状：SQL 不带 LIMIT，过滤在 Python 里做）
    · 指定 limit -> 加 LIMIT
    """
    table = _table(resource_type)
    if not table:
        return []
    sql = f'SELECT id, content, view_count FROM {table} ORDER BY id DESC'
    return execute_query(sql)


def list_rows_by_id(resource_type, columns, where_sql, params, order_by,
                    limit=None):
    """审核列表用的动态查询。

    对应 index.py:576-587：`where_sql` 由调用方按筛选条件拼装（只拼列名与
    `%s` 占位，不含用户输入）。表名与排序列必须来自常量或调用方的固定字面量。
    """
    table = _table(resource_type)
    if not table:
        return []
    sql = f'SELECT {columns} FROM {table} WHERE {where_sql} ORDER BY {order_by}'
    if limit is not None:
        sql += ' LIMIT %s'
        return execute_query(sql, list(params) + [limit])
    return execute_query(sql, list(params))


def list_rows_by_ids(resource_type, ids, order_by='submit_time DESC'):
    """按 id 集合取整行，对应 index.py:581。"""
    table = _table(resource_type)
    if not table or not ids:
        return []
    placeholders = ','.join(['%s'] * len(ids))
    return execute_query(
        f'SELECT * FROM {table} WHERE id IN ({placeholders}) ORDER BY {order_by}',
        list(ids),
    )


def list_hot_candidates(resource_type, limit=100):
    """昨日浏览量 > 0 的候选集，按昨日浏览量降序。

    对应 index.py:257 `get_algorithm_hot`。
    """
    table = _table(resource_type)
    if not table:
        return []
    return execute_query(
        f'SELECT id, content, view_count, yesterday_view_count FROM {table} '
        f'WHERE yesterday_view_count > 0 '
        f'ORDER BY yesterday_view_count DESC LIMIT %s',
        [limit],
    )


def list_latest_candidates(resource_type, limit=100):
    """date_added 非空的候选集，按 date_added 降序。

    对应 index.py:312 `get_algorithm_latest`。
    """
    table = _table(resource_type)
    if not table:
        return []
    return execute_query(
        f'SELECT id, content, view_count, date_added FROM {table} '
        f'WHERE date_added IS NOT NULL '
        f'ORDER BY date_added DESC LIMIT %s',
        [limit],
    )


# ============================================================
# 写
# ============================================================
def increment_view_count(resource_type, resource_id):
    """浏览量 +1（同时累加今日浏览）。

    对应 detail.py:236 等三处逐字重复的 UPDATE。
    """
    table = _table(resource_type)
    if not table:
        return 0
    return execute_update(
        f'UPDATE {table} SET view_count = view_count + 1, '
        f'today_view_count = today_view_count + 1 WHERE id = %s',
        [resource_id],
    )


def get_for_preview(resource_id):
    """资源包预览页：取 content 与 texture。"""
    return fetch_one(
        'SELECT content, texture FROM resourcepacks WHERE id = %s',
        [resource_id],
    )


def get_view_counts(resource_type, resource_id):
    """重新读取浏览量（加完之后回读，对应 detail.py:241）。"""
    table = _table(resource_type)
    if not table:
        return None
    return fetch_one(
        f'SELECT view_count, today_view_count FROM {table} WHERE id = %s',
        [resource_id],
    )


# ============================================================
# 开放 API（mcres/views/api.py）：三表各查一遍 / 按 content 字段反查
# ============================================================
#: 「开放 API 反向查询」覆盖的三张表及其对外类型名。
API_LOOKUP_TABLES = (
    ('resourcepacks', 'resourcepack'),
    ('shaderpacks', 'shaderpack'),
    ('maps', 'map'),
)

#: check_duplicate 允许的 JSON 字段名（列名白名单，防止拼接外部输入）。
DUPLICATE_FIELDS = ('main_name', 'curseforge_id', 'modrinth_id', 'mcmod_id')


def _api_lookup_table(table):
    """把 API 白名单里的表名解析回类型键，再交给 _table 统一校验。

    调用方传入的是本模块常量里的**表名**，不是类型键 —— 这两个概念
    在旧的 `resource_table()` 语义下极易混淆（传表名会静默返回 None）。
    """
    for t, type_name in API_LOOKUP_TABLES:
        if t == table:
            return _table(type_name)
    return None


def find_ids_by_mcmod_id(table, mcmod_id):
    """按 content.mcmod_id 反查该表的资源 id 列表。"""
    table = _api_lookup_table(table)
    if not table:
        return []
    return execute_query(
        f"SELECT id FROM {table} "
        f"WHERE JSON_UNQUOTE(JSON_EXTRACT(content, '$.mcmod_id')) = %s",
        [mcmod_id],
    ) or []


def find_ids_by_content_field(table, field, value, case_insensitive=False):
    """按 content 里的某个 JSON 字段反查 id。

    `field` 只允许 `DUPLICATE_FIELDS` 里的列名（业务 API 的字段来自请求参数，
    因此这里必须白名单校验，否则就是拼接外部输入）。
    """
    if field not in DUPLICATE_FIELDS:
        raise ValueError(f'不允许的检测字段: {field!r}')
    table = _api_lookup_table(table)
    if not table:
        return []
    expr = f"JSON_UNQUOTE(JSON_EXTRACT(content, '$.{field}'))"
    if case_insensitive:
        sql = f'SELECT id, content FROM {table} WHERE LOWER({expr}) = LOWER(%s)'
    else:
        sql = f'SELECT id, content FROM {table} WHERE {expr} = %s'
    return execute_query(sql, [value]) or []


# ============================================================
# 浏览日志与每日 PV（mcres/views/detail.py）
# ============================================================
def find_id(resource_type, resource_id):
    """只取 id（存在性判断）。"""
    table = _table(resource_type)
    if not table:
        return None
    return fetch_one(f'SELECT id FROM {table} WHERE id = %s', [resource_id])


def find_recent_view(resource_type, resource_id, visitor_key, window_ago):
    """窗口期内是否已有该访客的浏览记录（详情页防刷用，LIMIT 1）。"""
    return fetch_one(
        'SELECT id FROM resource_view_log '
        'WHERE resource_type = %s AND resource_id = %s '
        'AND visitor_key = %s AND visit_time > %s LIMIT 1',
        [resource_type, resource_id, visitor_key, window_ago],
    )


def insert_view_log(resource_type, resource_id, visitor_key, visit_time):
    return execute_update(
        'INSERT INTO resource_view_log'
        '(resource_type, resource_id, visitor_key, visit_time) '
        'VALUES(%s, %s, %s, %s)',
        [resource_type, resource_id, visitor_key, visit_time],
    )


def list_daily_pv(resource_type, resource_id):
    """某资源的每日 PV 序列（按日期升序）。"""
    return execute_query(
        'SELECT date, pv FROM resource_daily_pv '
        'WHERE resource_type = %s AND resource_id = %s '
        'ORDER BY date',
        [resource_type, resource_id],
    ) or []


def list_site_avg_pv(resource_type):
    """该类型全站的每日平均 PV（按日期升序）。"""
    return execute_query(
        'SELECT date, AVG(pv) AS avg_pv '
        'FROM resource_daily_pv '
        'WHERE resource_type = %s '
        'GROUP BY date '
        'ORDER BY date',
        [resource_type],
    ) or []


# ============================================================
# 搜索 / 建议 / sitemap / RSS（mcres/views/search.py、site.py、
# resource_lists.py、difference.py）
# ============================================================
#: 站点搜索覆盖的三张表及其对外类型名。
SEARCH_TABLES = (
    ('resourcepacks', 'resourcepack'),
    ('shaderpacks', 'shaderpack'),
    ('maps', 'map'),
)


def suggest_names(table, like_pattern, limit):
    """搜索建议：按 content.main_name 前缀匹配取 (id, content)。"""
    return execute_query(
        f"SELECT id, content FROM {table} "
        f"WHERE JSON_UNQUOTE(JSON_EXTRACT(content, '$.main_name')) LIKE %s "
        f"LIMIT %s",
        [like_pattern, limit],
    ) or []


def list_all_for_search(table):
    """搜索页：整表拉取后在 Python 端打分过滤（N+1/全表扫描原样保留）。"""
    return execute_query(f'SELECT id, content, file FROM {table}') or []


def list_ids_and_dates(table):
    """sitemap：取 id 与 date_added（按 id 升序）。"""
    return execute_query(
        f'SELECT id, date_added FROM {table} ORDER BY id') or []


def list_recent_for_feed(table, limit=10):
    """RSS：最新 limit 条 (id, content, date_added)。"""
    return execute_query(
        f'SELECT id, content, date_added FROM {table} '
        f'ORDER BY id DESC LIMIT %s',
        [limit],
    ) or []


def list_for_cards_by_table(table):
    """列表页：按 id 倒序取卡片字段（供 Python 端过滤 + 排序）。"""
    return execute_query(
        f'SELECT id, content, view_count, yesterday_view_count '
        f'FROM {table} ORDER BY id DESC'
    ) or []


# ============================================================
# 版本历史（resource_versions，difference.py 用）
# ============================================================
def list_versions_by_ids(version_ids, resource_type, resource_id):
    """取指定两个版本（用于 diff 对比）。"""
    return execute_query(
        'SELECT id, content, created_at, change_summary, created_by '
        'FROM resource_versions '
        'WHERE id IN (%s, %s) AND resource_type = %s AND resource_id = %s',
        [version_ids[0], version_ids[1], resource_type, resource_id],
    ) or []


def list_versions(resource_type, resource_id):
    """某资源的全部版本（created_at 倒序）。"""
    return execute_query(
        'SELECT id, change_summary, created_at, created_by '
        'FROM resource_versions '
        'WHERE resource_type = %s AND resource_id = %s '
        'ORDER BY created_at DESC',
        [resource_type, resource_id],
    ) or []
