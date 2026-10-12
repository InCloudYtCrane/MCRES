# utils/data/repositories/profiles.py
"""个人主页与收藏夹的查询。

原先散落在 `mcres/views/profile/profile.py` 的 32 处调用里，覆盖：
· 作品 / 点赞 / 收藏的资源列表（三张资源表各查一遍）
· 收藏夹（favorite_folders / resource_favorites）
· 在线状态（action_log）
· 每日编辑与审核历史（user_edit_daily / user_edit_history）
· 绑定的茶室话题（tea_topic）

关于资源列表：`get_user_works` / `get_user_likes` / `get_user_favorites`
原先都会**逐条**查资源行（N+1）。B 批已把点赞与收藏改成
`get_resource_cards` 批量 IN 查询；`get_user_works` 仍是整表拉取后按作者
在 Python 里筛（下推到 SQL 需要先抽样确认 `content['authors']` 的格式统一性，
未做）。
"""
from utils.constants import RESOURCE_TABLE, resource_table
from utils.data import execute_query, execute_update, fetch_one


# ============================================================
# 资源行（作品 / 点赞 / 收藏 共用）
# ============================================================
def list_resource_cards(resource_type):
    """取某类型全部资源的卡片字段（作品页按作者在 Python 里筛）。"""
    table = resource_table(resource_type)
    if not table:
        return []
    return execute_query(f'SELECT id, content, view_count FROM {table}') or []


def get_resource_card(resource_type, resource_id):
    """取单条资源的卡片字段。

    点赞/收藏列表原先用它逐条查（N+1），B 批已改用
    `get_resource_cards()` 批量取；本函数保留给单条场景。
    """
    table = resource_table(resource_type)
    if not table:
        return None
    return fetch_one(
        f'SELECT content, view_count FROM {table} WHERE id = %s',
        [resource_id],
    )


def get_resource_cards(resource_type, resource_ids):
    """按 id 集合批量取卡片字段，返回 `{id: row}`。

    `get_resource_card` 的批量版（B 批 N+1 修复）：点赞/收藏列表原先在循环里
    逐条查，收藏多的时候就是 N 次往返。行不存在的 id 不会出现在结果里，
    调用方按原逻辑 `if row:` 判断即可。
    """
    table = resource_table(resource_type)
    ids = [i for i in set(resource_ids) if i is not None]
    if not table or not ids:
        return {}
    placeholders = ','.join(['%s'] * len(ids))
    rows = execute_query(
        f'SELECT id, content, view_count FROM {table} WHERE id IN ({placeholders})',
        ids,
    )
    return {r['id']: r for r in (rows or [])}


def list_likes(user_id):
    """用户点赞过的资源（类型 + id）。"""
    return execute_query(
        'SELECT resource_type, resource_id FROM resource_likes WHERE user_id = %s',
        [user_id],
    ) or []


def increment_favorites_count(resource_type, resource_id, delta):
    """资源收藏数增减。"""
    table = resource_table(resource_type)
    if not table:
        return 0
    return execute_update(
        f'UPDATE {table} SET favorites_count = favorites_count + %s WHERE id = %s',
        [delta, resource_id],
    )


# ============================================================
# 收藏夹
# ============================================================
def list_resource_names(table):
    """取某张资源表的全部 (id, content)，用于拼装"资源名映射"。

    注意：这里接收的是**表名**（`resourcepacks` 等）而不是类型键 ——
    调用方原本就是按表名调用的；曾误按类型处理导致查询被跳过（回归）。

    个人主页已改用只取三个 JSON 子路径的 `list_resource_name_fields`
    （省掉整份 content 的传输），本函数目前**没有调用方**，保留作参考。
    """
    if table not in RESOURCE_TABLE.values():
        return []
    return execute_query(f'SELECT id, content FROM {table}') or []


def list_resource_name_fields(table):
    """取某张资源表全部 (id, abbr, main_name, sub_name) —— 只搬三个 JSON 子路径。

    个人主页原先用 `list_resource_names` 把**每一行**的整份 content JSON
    拉回 Python 再解析，只为了拼 `[abbr] main (sub)` 一个字符串（B 批 2.4）。
    这里把取值下推到 SQL 的 JSON 抽取（`resources.suggest_names` 已有先例）。

    三个字段一律 `COALESCE(..., '')`，与调用方 `content.get(k, '')` 的
    默认值一致；`ok` 列复刻原实现的 `json.loads` 失败分支
    （`JSON_TYPE` 不是 OBJECT 时，原来是 AttributeError → "未命名 #id"）。
    """
    if table not in RESOURCE_TABLE.values():
        return []
    return execute_query(
        f"SELECT id, "
        f"  CASE WHEN JSON_VALID(content) AND JSON_TYPE(content) = 'OBJECT' "
        f"       THEN 1 ELSE 0 END AS ok, "
        f"  COALESCE(JSON_UNQUOTE(JSON_EXTRACT(content, '$.abbr')), '')      AS abbr, "
        f"  COALESCE(JSON_UNQUOTE(JSON_EXTRACT(content, '$.main_name')), '') AS main_name, "
        f"  COALESCE(JSON_UNQUOTE(JSON_EXTRACT(content, '$.sub_name')), '')  AS sub_name "
        f'FROM {table}'
    ) or []


def find_folder_id_by_name(user_id, name, exclude_id=None):
    """按名称查收藏夹（重命名时排除自身）。"""
    if exclude_id is not None:
        return fetch_one(
            'SELECT id FROM favorite_folders '
            'WHERE user_id = %s AND name = %s AND id != %s',
            [user_id, name, exclude_id],
        )
    return fetch_one(
        'SELECT id FROM favorite_folders WHERE user_id = %s AND name = %s',
        [user_id, name],
    )


def get_first_folder(user_id):
    """取该用户的第一个收藏夹（用于"未指定收藏夹"时的兜底）。"""
    return fetch_one(
        'SELECT id FROM favorite_folders WHERE user_id = %s ORDER BY id LIMIT 1',
        [user_id],
    )


def get_owned_folder(folder_id, user_id):
    """取归属该用户的收藏夹（权限判断）。"""
    return fetch_one(
        'SELECT id FROM favorite_folders WHERE id = %s AND user_id = %s',
        [folder_id, user_id],
    )


def list_folders(user_id):
    """用户全部收藏夹。"""
    return execute_query(
        'SELECT id, name FROM favorite_folders WHERE user_id = %s ORDER BY id',
        [user_id],
    ) or []


def create_default_folder(user_id, name='默认收藏夹'):
    """新建收藏夹。"""
    return execute_update(
        'INSERT INTO favorite_folders (user_id, name) VALUES (%s, %s)',
        [user_id, name],
    )


def get_folder(folder_id, columns='id, user_id'):
    """取收藏夹。"""
    return fetch_one(
        f'SELECT {columns} FROM favorite_folders WHERE id = %s', [folder_id])


def rename_folder(folder_id, name):
    return execute_update(
        'UPDATE favorite_folders SET name = %s WHERE id = %s',
        [name, folder_id],
    )


def delete_folder(folder_id):
    return execute_update(
        'DELETE FROM favorite_folders WHERE id = %s', [folder_id])


def list_folder_items(folder_id):
    """收藏夹内的条目（类型 + id）。"""
    return execute_query(
        'SELECT resource_type, resource_id FROM resource_favorites '
        'WHERE folder_id = %s',
        [folder_id],
    ) or []


def get_favorite(user_id, resource_type, resource_id, folder_id):
    """查某资源是否已在（指定/任一）收藏夹内。"""
    if folder_id:
        return fetch_one(
            'SELECT id FROM resource_favorites '
            'WHERE user_id = %s AND resource_type = %s AND resource_id = %s '
            'AND folder_id = %s',
            [user_id, resource_type, resource_id, folder_id],
        )
    return fetch_one(
        'SELECT id FROM resource_favorites '
        'WHERE user_id = %s AND resource_type = %s AND resource_id = %s',
        [user_id, resource_type, resource_id],
    )


def add_favorite(user_id, resource_type, resource_id, folder_id):
    return execute_update(
        'INSERT INTO resource_favorites (user_id, resource_type, resource_id, folder_id) '
        'VALUES (%s, %s, %s, %s)',
        [user_id, resource_type, resource_id, folder_id],
    )


def remove_favorite(user_id, resource_type, resource_id, folder_id=None):
    """移除收藏。`folder_id` 为空时按 (user, type, id) 删除。"""
    if folder_id:
        return execute_update(
            'DELETE FROM resource_favorites '
            'WHERE user_id = %s AND resource_type = %s AND resource_id = %s '
            'AND folder_id = %s',
            [user_id, resource_type, resource_id, folder_id],
        )
    return execute_update(
        'DELETE FROM resource_favorites '
        'WHERE user_id = %s AND resource_type = %s AND resource_id = %s',
        [user_id, resource_type, resource_id],
    )


def delete_folder_items(folder_id):
    """删除收藏夹时清空其条目。"""
    return execute_update(
        'DELETE FROM resource_favorites WHERE folder_id = %s', [folder_id])


# ============================================================
# 在线状态（action_log）
# ============================================================
def get_last_active_since(user_id, since):
    """取窗口内最近一次活动时间。"""
    return fetch_one(
        'SELECT created_at FROM action_log '
        'WHERE user_id = %s AND created_at >= %s '
        'ORDER BY created_at DESC LIMIT 1',
        [user_id, since],
    )


def get_last_active(user_id):
    """取不限时间的最近一次活动时间。"""
    return fetch_one(
        'SELECT created_at FROM action_log '
        'WHERE user_id = %s ORDER BY created_at DESC LIMIT 1',
        [user_id],
    )


# ============================================================
# 编辑统计 / 历史（个人主页的"足迹"区块）
# ============================================================
def list_edit_daily(user_id):
    return execute_query(
        'SELECT date, edit_count, review_count FROM user_edit_daily '
        'WHERE user_id = %s',
        [user_id],
    ) or []


def bump_edit_daily(user_id, today):
    """当日编辑次数 +1。"""
    return execute_update(
        'INSERT INTO user_edit_daily (user_id, date, edit_count, review_count) '
        'VALUES (%s, %s, 1, 0) '
        'ON DUPLICATE KEY UPDATE edit_count = edit_count + 1',
        [user_id, today],
    )


def bump_review_daily(user_id, today):
    """当日提交审核次数 +1。"""
    return execute_update(
        'INSERT INTO user_edit_daily (user_id, date, edit_count, review_count) '
        'VALUES (%s, %s, 0, 1) '
        'ON DUPLICATE KEY UPDATE review_count = review_count + 1',
        [user_id, today],
    )


def insert_edit_history(user_id, operation, target_type, target_id,
                        resource_name, change_summary, created_at):
    """写一条用户编辑动态。"""
    return execute_update(
        'INSERT INTO user_edit_history '
        '(user_id, operation, target_type, target_id, resource_name, change_summary, created_at) '
        'VALUES (%s, %s, %s, %s, %s, %s, %s)',
        [user_id, operation, target_type, target_id, resource_name,
         change_summary, created_at],
    )


def insert_resource_version(resource_type, resource_id, content_json,
                            change_summary, created_at, created_by):
    """保存一条资源版本快照。"""
    return execute_update(
        """INSERT INTO resource_versions
           (resource_type, resource_id, content, change_summary, created_at, created_by)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        [resource_type, resource_id, content_json, change_summary,
         created_at, created_by],
    )


def sum_edit_counts(user_id):
    """汇总编辑数与审核数。"""
    return fetch_one(
        'SELECT COALESCE(SUM(edit_count), 0) AS total_edit, '
        'COALESCE(SUM(review_count), 0) AS total_review '
        'FROM user_edit_daily WHERE user_id = %s',
        [user_id],
    )


def list_edit_history(user_id, limit, offset):
    return execute_query(
        'SELECT operation, target_type, target_id, resource_name, created_at '
        'FROM user_edit_history WHERE user_id = %s '
        'ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s',
        [user_id, limit, offset],
    ) or []


def count_edit_history(user_id):
    """编辑历史条数。"""
    row = fetch_one(
        'SELECT COUNT(*) AS c FROM user_edit_history WHERE user_id = %s',
        [user_id],
    )
    return (row['c'] if row else 0) or 0


def get_preset_shaderpack_id(preset_id):
    """编辑历史里若是预设，反查它所属的光影包 id。"""
    return fetch_one(
        'SELECT shaderpack_id FROM shaderpack_presets WHERE id = %s',
        [preset_id],
    )


# ============================================================
# 茶室绑定话题
# ============================================================
def list_creator_topics():
    """全部 level != 4 的 creator 绑定话题（在 Python 里按 user_id 筛）。"""
    return execute_query(
        '''SELECT id, slug, name, description, level, is_official,
                  post_count, follower_count, last_post_at, link_target
           FROM tea_topic
           WHERE link_type = 'creator' AND level != 4'''
    ) or []


def list_resource_topics():
    """全部 level != 4 的 resource 绑定话题（在 Python 里按 link_target 筛）。

    与 `list_creator_topics` 的差别只有 link_type，原实现就是这么写的。
    """
    return execute_query(
        '''SELECT id, slug, name, description, level, is_official,
                  post_count, follower_count, last_post_at, link_target
           FROM tea_topic
           WHERE link_type = 'resource'
             AND level != 4'''
    ) or []


# ============================================================
# 用户行
# ============================================================
def get_user(user_id):
    """取用户整行（个人主页需要大量字段）。"""
    return fetch_one('SELECT * FROM user_info WHERE id = %s', [user_id])


# ============================================================
# 设置页（mcres/views/profile/settings.py）
# ============================================================
def get_pwd_row(user_id):
    """只取密码哈希（验证当前密码用）。"""
    return fetch_one('SELECT pwd FROM user_info WHERE id = %s', [user_id])


def get_signature(user_id):
    """只取个性签名（更新签名前取旧值用）。"""
    return fetch_one('SELECT signature FROM user_info WHERE id = %s', [user_id])


def get_titles(user_id):
    """取头衔列原文。"""
    return fetch_one('SELECT titles FROM user_info WHERE id = %s', [user_id])


def set_notification_settings(user_id, settings_json):
    return execute_update(
        'UPDATE user_info SET notification_settings = %s WHERE id = %s',
        [settings_json, user_id],
    )


def set_privacy_settings(user_id, settings_json):
    return execute_update(
        'UPDATE user_info SET privacy_settings = %s WHERE id = %s',
        [settings_json, user_id],
    )


def set_titles(user_id, titles_json):
    return execute_update(
        'UPDATE user_info SET titles = %s WHERE id = %s',
        [titles_json, user_id],
    )


def set_signature(user_id, signature):
    return execute_update(
        'UPDATE user_info SET signature = %s WHERE id = %s',
        [signature, user_id],
    )


def set_pwd(user_id, pwd_hash):
    return execute_update(
        'UPDATE user_info SET pwd = %s WHERE id = %s',
        [pwd_hash, user_id],
    )


def clear_titles(user_id):
    return execute_update(
        'UPDATE user_info SET titles = NULL WHERE id = %s',
        [user_id],
    )
