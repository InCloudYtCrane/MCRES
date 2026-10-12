# utils/data/repositories/site.py
"""站点级配置与推广位（site_promotions / push_settings / site_expenses）。

原先内联在 `mcres/views/index.py` 的首页配置与 `/support` 收支页里。
"""
from utils.data import execute_query, execute_update, fetch_one


# ============================================================
# 推广位（首页轮播 / 热门 / 最新）
# ============================================================
def list_promotions(promo_type):
    """取某类推广位（按 sort_order、id 升序）。"""
    return execute_query(
        'SELECT item_json FROM site_promotions '
        'WHERE promo_type = %s '
        'ORDER BY sort_order ASC, id ASC',
        [promo_type],
    ) or []


# ============================================================
# 推送开关
# ============================================================
def get_push_flags():
    """取 hotAutoUpdate / latestAutoUpdate 两个开关。"""
    return fetch_one(
        'SELECT hotAutoUpdate, latestAutoUpdate FROM push_settings WHERE id = %s',
        [1],
    )


def ensure_push_settings_row():
    """初始化 push_settings 单行（缺失时创建）。"""
    return execute_update(
        "INSERT INTO push_settings "
        "(id, carousel, hot, latest, announce, feed, hotAutoUpdate, latestAutoUpdate) "
        "VALUES (1, '[]', '[]', '[]', '[]', '[]', 0, 0)",
        (),
    )


# ============================================================
# 收支（/support 页）
# ============================================================
def month_income(month_str):
    """按月统计爱发电收入合计。"""
    return fetch_one(
        "SELECT COALESCE(SUM(total_amount), 0) AS total "
        "FROM afdian_orders WHERE status=2 "
        "AND DATE_FORMAT(paid_at, '%%Y-%%m') = %s",
        [month_str],
    )


def month_expense(month_str):
    """按月统计支出合计。"""
    return fetch_one(
        'SELECT COALESCE(SUM(amount), 0) AS total '
        'FROM site_expenses WHERE expense_month = %s',
        [month_str],
    )


def expense_by_category(month_str):
    """按月按类别/项目汇总支出。"""
    return execute_query(
        'SELECT category, item_name, SUM(amount) AS amount '
        'FROM site_expenses WHERE expense_month = %s '
        'GROUP BY category, item_name ORDER BY amount DESC',
        [month_str],
    ) or []


def income_rows(where_sql, params, limit, offset):
    """收入流水（分页）。"""
    return execute_query(
        f'SELECT paid_at, nickname, total_amount, remark, parsed_message, reply '
        f'FROM afdian_orders {where_sql} ORDER BY paid_at DESC '
        f'LIMIT %s OFFSET %s',
        list(params) + [limit, offset],
    ) or []


def income_count(where_sql, params):
    """收入条数查询行（调用方按 `row['cnt']` 取值，故返回整行）。"""
    return fetch_one(
        f'SELECT COUNT(*) AS cnt FROM afdian_orders {where_sql}', list(params))


def expense_rows(where_sql, params, limit, offset):
    """支出流水（分页）。"""
    return execute_query(
        'SELECT created_at, operator, item_name, amount, note, expense_month '
        f'FROM site_expenses {where_sql} ORDER BY created_at DESC '
        'LIMIT %s OFFSET %s',
        list(params) + [limit, offset],
    ) or []


def expense_count(where_sql, params):
    """支出条数查询行（调用方按 `row['cnt']` 取值，故返回整行）。"""
    return fetch_one(
        f'SELECT COUNT(*) AS cnt FROM site_expenses {where_sql}', list(params))


# ============================================================
# 爱发电订单（webhook 与查询）
# ============================================================
def order_exists(out_trade_no):
    return fetch_one(
        'SELECT id FROM afdian_orders WHERE out_trade_no = %s', [out_trade_no])


def insert_order(out_trade_no, afdian_user_id, plan_id, month, total_amount,
                 show_amount, status, remark, reply, parsed_site_id,
                 parsed_message, nickname, avatar, sign_verified,
                 api_verified, paid_at):
    """写入爱发电订单（webhook 用，16 列）。

    注意：这条 SQL 由 `afdian_webhook` 使用，而该路由在回归框架里被跳过
    （会外呼第三方 API），因此改动**未被回归覆盖**，改这里要手动验证。
    """
    return execute_update(
        '''INSERT INTO afdian_orders
           (out_trade_no, afdian_user_id, plan_id, month,
            total_amount, show_amount, status, remark, reply,
            parsed_site_id, parsed_message, nickname, avatar,
            sign_verified, api_verified, paid_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        [out_trade_no, afdian_user_id, plan_id, month, total_amount,
         show_amount, status, remark, reply, parsed_site_id, parsed_message,
         nickname, avatar, sign_verified, api_verified, paid_at],
    )


def set_order_reply(out_trade_no, reply):
    return execute_update(
        'UPDATE afdian_orders SET reply = %s WHERE out_trade_no = %s',
        [reply, out_trade_no],
    )


def find_user_by_site_id(site_id):
    """按数字站内 ID 取昵称与头像。"""
    return fetch_one(
        'SELECT nickname, avatar FROM user_info WHERE id = %s', [int(site_id)])


def find_user_by_nickname(nickname):
    """按昵称取昵称与头像。"""
    return fetch_one(
        'SELECT nickname, avatar FROM user_info WHERE nickname = %s',
        [nickname],
    )


def find_user_id_by_nickname(nickname):
    return fetch_one(
        'SELECT id FROM user_info WHERE nickname = %s', [nickname])


# ============================================================
# 站点规则（site_rules）
# ============================================================
def list_active_rules():
    """所有启用规则的 (rule_key, title) 简要列表（侧边栏加载用）。"""
    return execute_query(
        'SELECT rule_key, title FROM site_rules '
        'WHERE is_active = 1 ORDER BY rule_key'
    ) or []


def list_active_rules_with_dates():
    """所有启用规则（含 updated_at），规则页侧边栏用。"""
    return execute_query(
        'SELECT rule_key, title, updated_at FROM site_rules '
        'WHERE is_active = 1 ORDER BY rule_key'
    ) or []


def get_rule_by_key(rule_key):
    """按 rule_key 取正文与审计字段（启用中的那条）。"""
    return fetch_one(
        'SELECT title, content, updated_at, created_by, updated_by '
        'FROM site_rules WHERE rule_key = %s AND is_active = 1',
        [rule_key],
    )


def list_rule_versions(rule_key):
    """某规则的版本历史（version 倒序）。"""
    return execute_query(
        'SELECT version, title, updated_at, is_active FROM site_rules '
        'WHERE rule_key = %s ORDER BY version DESC',
        [rule_key],
    ) or []


def get_rule_version(rule_key, version):
    """按 rule_key + version 取某一版正文。"""
    return fetch_one(
        'SELECT title, content FROM site_rules '
        'WHERE rule_key = %s AND version = %s',
        [rule_key, version],
    )


# ============================================================
# 外链映射（external_link_mappings）
# ============================================================
def find_external_link(url_hash):
    """按 hash 取原始链接与域名（/target 跳转确认页）。"""
    return fetch_one(
        'SELECT url, domain FROM external_link_mappings WHERE url_hash = %s',
        [url_hash],
    )


def external_link_exists(url_hash):
    """该 hash 是否已登记（`security.py` 的"先查后插"用）。"""
    return fetch_one(
        'SELECT url_hash FROM external_link_mappings WHERE url_hash = %s',
        [url_hash],
    )


def insert_external_link(url_hash, url, domain):
    """登记一条外链映射。"""
    return execute_update(
        'INSERT INTO external_link_mappings (url_hash, url, domain) '
        'VALUES (%s, %s, %s)',
        [url_hash, url, domain],
    )


# ============================================================
# 站点动态（site_feed）
# ============================================================
def insert_feed(user_id, action, target, created_at):
    """写一条站点动态。"""
    return execute_update(
        'INSERT INTO site_feed (user_id, action, target, created_at) '
        'VALUES (%s, %s, %s, %s)',
        [user_id, action or '', target if target else None, created_at],
    )


def list_recent_feed(limit):
    """最近若干条动态（时间倒序）。"""
    return execute_query(
        'SELECT user_id, action, target, created_at '
        'FROM site_feed '
        'ORDER BY created_at DESC, id DESC '
        'LIMIT %s',
        [limit],
    )


# ============================================================
# 防刷配置（anti_fraud_config）
# ============================================================
def list_anti_fraud_config():
    """防刷配置的全部键值行。"""
    return execute_query('SELECT config_key, config_value FROM anti_fraud_config')


# ============================================================
# 公告（site_announcements）
# ============================================================
def list_active_announcements(now):
    """当前生效的公告（未开始/未结束都算生效）。"""
    return execute_query(
        '''SELECT title, content, extra_json
           FROM site_announcements
           WHERE is_active = 1
             AND (start_at IS NULL OR start_at <= %s)
             AND (end_at   IS NULL OR end_at   >= %s)
           ORDER BY id''',
        [now, now],
    )
