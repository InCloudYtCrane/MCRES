# utils/data/repositories/users.py
"""用户表的共用查询。

`user_info` 是全站查询最频繁的表：role / ban / edit_count / nickname /
notification_settings 等在视图、中间件、工具层里反复出现。这里收敛成单点，
顺带为后续"每请求重复读同一用户行"的优化（在 `g` 上做请求级缓存）留出接缝。
"""
import json

from utils.data import execute_query, execute_update, fetch_one


# ============================================================
# 读
# ============================================================
def get_role(user_id):
    """取用户角色（role）。缺失时返回 None。"""
    row = fetch_one('select role from user_info where id = %s', [user_id])
    return row['role'] if row else None


def get_ban(user_id):
    """取用户的 ban 字段原文。"""
    row = fetch_one('SELECT ban FROM user_info WHERE id = %s', [user_id])
    return row.get('ban') if row else None


def get_ban_parsed(user_id):
    """取 ban 字段并解析为 dict；无效或缺失返回 None。

    原先各视图各自 `json.loads` 并吞掉异常，这里统一。
    """
    raw = get_ban(user_id)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def get_edit_count(user_id):
    """取用户的编辑计数。"""
    row = fetch_one(
        'SELECT edit_count FROM user_info WHERE id = %s', [user_id])
    return row['edit_count'] if row else 0


def add_reputation(user_id, delta):
    """名誉 +delta，上限 100（成就奖励发放用）。"""
    return execute_update(
        'UPDATE user_info SET reputation = LEAST(reputation + %s, 100) WHERE id = %s',
        [delta, user_id],
    )


def deduct_reputation(user_id, amount):
    """名誉 -amount，下限 0（违禁词处罚用）。"""
    return execute_update(
        'UPDATE user_info SET reputation = GREATEST(reputation - %s, 0) WHERE id = %s',
        [amount, user_id],
    )


def get_reputation(user_id):
    """取名誉值；行不存在返回 None（调用方需自行兜底 100）。"""
    row = fetch_one('SELECT reputation FROM user_info WHERE id = %s', [user_id])
    return row['reputation'] if row else None


def set_role(user_id, role):
    """直接设置角色（role=0 即封号）。"""
    return execute_update(
        'UPDATE user_info SET role = %s WHERE id = %s', [role, user_id])


def get_full_row(user_id):
    """取整行。

    登录校验原先写的是 `select * from user_info where id = %s`，
    这里**刻意保留 `select *`** —— 换成只取 role 会改变站点发出的 SQL，
    属单独的性能改动。行不存在返回 None（调用方按原样下标取值，
    由 `except TypeError` 兜住）。
    """
    return fetch_one('select * from user_info where id = %s', [user_id])


def list_users_with_default_avatar():
    """头像为空或仍指向默认图的所有用户（头像批量重置用）。"""
    return execute_query(
        "SELECT id, nickname, avatar FROM user_info "
        "WHERE avatar IS NULL "
        "   OR avatar = 'https://img.mcresource.cn/user/avatar/default.jpg'"
    )


def get_nickname(user_id):
    """取昵称；不存在时返回 '未知用户'（与各视图的兜底一致）。"""
    row = fetch_one(
        'SELECT nickname FROM user_info WHERE id = %s', [user_id])
    return row['nickname'] if row else '未知用户'


def get_nicknames(user_ids):
    """按 id 集合批量取昵称，返回 {id: nickname}。"""
    ids = [u for u in set(user_ids) if u]
    if not ids:
        return {}
    placeholders = ','.join(['%s'] * len(ids))
    rows = execute_query(
        f'SELECT id, nickname FROM user_info WHERE id IN ({placeholders})',
        ids,
    )
    return {r['id']: r['nickname'] for r in (rows or [])}


def get_avatars(user_ids):
    """按 id 集合批量取头像，返回 {id: avatar}。

    与 `get_nicknames` 同形（审核列表原先在 50 行的循环里逐条查头像）。
    用户不存在时不会出现在结果里；avatar 为 NULL 时值就是 None。
    """
    ids = [u for u in set(user_ids) if u]
    if not ids:
        return {}
    placeholders = ','.join(['%s'] * len(ids))
    rows = execute_query(
        f'SELECT id, avatar FROM user_info WHERE id IN ({placeholders})',
        ids,
    )
    return {r['id']: r['avatar'] for r in (rows or [])}


def get_role_and_area(user_id):
    """取 role 与 review_area（评论/审核权限判断用）。"""
    return fetch_one(
        'SELECT role, review_area FROM user_info WHERE id = %s', [user_id])


# ============================================================
# 按邮箱查找 / 注册（account.py 用）
# ============================================================
def find_id_by_email(email):
    """按邮箱取 id（注册/找回密码前的重名检查）。"""
    return fetch_one('select id from user_info where email = %s', [email])


def find_by_email(email):
    """按邮箱取整行（密码登录、第三方登录绑定用）。"""
    return fetch_one('SELECT * FROM user_info WHERE email = %s', [email])


def find_id_and_pwd_by_email(email):
    """按邮箱取 id / pwd（开放 API 的账号密码校验）。"""
    return fetch_one('SELECT id, pwd FROM user_info WHERE email = %s', [email])


def find_id_only(user_id):
    """只取 id（模拟登录时确认管理员仍存在）。"""
    return fetch_one('SELECT id FROM user_info WHERE id = %s', [user_id])


def get_role_ban(id_or_row):
    """取 id / role / ban（登录态校验：封禁与角色）。"""
    return fetch_one(
        'SELECT id, role, ban FROM user_info WHERE id = %s', [id_or_row])


def search_by_nickname(like_pattern, limit):
    """昵称模糊匹配（搜索建议）。"""
    return execute_query(
        'SELECT id, nickname FROM user_info WHERE nickname LIKE %s LIMIT %s',
        [like_pattern, limit],
    ) or []


def search_full_by_nickname(like_pattern):
    """昵称模糊匹配整行（搜索页用户结果）。"""
    return execute_query(
        '''SELECT id, nickname, avatar, signature, role
           FROM user_info
           WHERE nickname LIKE %s''',
        [like_pattern],
    ) or []


def create_user(nickname, email, pwd_hash, registration_time):
    """插入新用户（最小字段集，与原实现一致）。"""
    return execute_update(
        'insert into user_info(nickname, email, pwd, registration_time) '
        'values(%s, %s, %s, %s)',
        [nickname, email, pwd_hash, registration_time],
    )


def get_identity(user_id):
    """取 id / nickname / avatar（少量字段，供登录态展示）。"""
    return fetch_one(
        'SELECT id, nickname, avatar FROM user_info WHERE id = %s', [user_id])


def get_identity_with_role(user_id):
    """取 id / nickname / avatar / role（模拟登录等场景）。"""
    return fetch_one(
        'SELECT id, nickname, avatar, role FROM user_info WHERE id = %s',
        [user_id])


def set_avatar(user_id, avatar_url):
    return execute_update(
        'UPDATE user_info SET avatar = %s WHERE id = %s',
        [avatar_url, user_id],
    )


def set_nickname(user_id, nickname):
    return execute_update(
        'UPDATE user_info SET nickname = %s WHERE id = %s',
        [nickname, user_id],
    )


def set_ban(user_id, ban_json):
    """写回 ban 字段（用于清理过期封禁项）。"""
    return execute_update(
        'UPDATE user_info SET ban = %s WHERE id = %s',
        [ban_json, user_id],
    )


def update_password_by_email(email, pwd_hash):
    return execute_update(
        'update user_info set pwd = %s where email = %s',
        [pwd_hash, email],
    )


#: 允许通过 update_profile_fields 更新的列白名单。
#: 原实现把动态拼出的 `updates` 片段直接插进 SQL，只靠调用方自律；
#: 这里加一层白名单，把"动态 SQL"限制在已知列上（不改行为，只收紧边界）。
_PROFILE_UPDATE_COLUMNS = frozenset({
    'nickname', 'avatar', 'email', 'pwd', 'titles',
    'notification_settings', 'privacy_settings', 'edit_area',
    'review_area', 'file_area', 'ban', 'sel_role', 'message',
})


def update_profile_fields(user_id, set_fragments, params):
    """按动态字段集更新用户资料（第三方资料同步用）。

    `set_fragments` 形如 `['nickname = %s', 'avatar = %s']`，
    由调用方在只含固定列名的分支里拼装；这里额外校验列名白名单。
    """
    columns = []
    for frag in set_fragments:
        col = frag.split('=')[0].strip()
        if col not in _PROFILE_UPDATE_COLUMNS:
            raise ValueError(f'不允许更新的列: {col!r}')
        columns.append(frag)
    return execute_update(
        f"UPDATE user_info SET {', '.join(columns)} WHERE id = %s",
        list(params) + [user_id],
    )


def get_role_row(user_id):
    """取含 role 的一行（登录态校验用）。"""
    return fetch_one('SELECT role FROM user_info WHERE id = %s', [user_id])


def get_avatar_row(user_id):
    """只取头像字段（单条）。

    审核列表原先用它逐条查（50 行 = 50 次往返），B 批已改用
    `get_avatars()` 批量取；本函数保留给确实只需要单条的场景。
    """
    return fetch_one(
        'SELECT avatar FROM user_info WHERE id = %s', [user_id])


def find_id_by_id(user_id):
    """按 id 取 id（存在性判断）。命名沿用调用方语义。"""
    return fetch_one('SELECT id FROM user_info WHERE id = %s', [user_id])


def get_privacy_settings(user_id):
    """取隐私设置 JSON 原文。"""
    return fetch_one(
        'SELECT privacy_settings FROM user_info WHERE id = %s', [user_id])


def get_notification_settings(user_id):
    """取通知设置 JSON 原文。"""
    return fetch_one(
        'SELECT notification_settings FROM user_info WHERE id = %s', [user_id])


def get_nickname_row(user_id):
    """只取昵称字段（改名接口查旧值用）。"""
    return fetch_one('SELECT nickname FROM user_info WHERE id = %s', [user_id])


# ============================================================
# 写
# ============================================================
def increment_comment_count(user_id):
    """发评论时 author 的 view_count +1。"""
    return execute_update(
        'UPDATE user_info SET view_count = view_count + 1 WHERE id = %s',
        [user_id],
    )


def decrement_comment_count(user_id):
    """删除评论时 author 的 view_count -1（原 SQL 用 GREATEST 兜底为 0）。"""
    return execute_update(
        'UPDATE user_info SET view_count = GREATEST(view_count - 1, 0) '
        'WHERE id = %s',
        [user_id],
    )


def bump_edit_count(user_id):
    """edit_count +1。

    注意：原实现是"先读再写"（`count + 1`），并发下会丢更新。
    此处**保持原语义**；要修的话改成单条
    `UPDATE user_info SET edit_count = edit_count + 1 WHERE id = %s`
    即可（属行为改动，另行处理）。
    """
    count = get_edit_count(user_id)
    return execute_update(
        'UPDATE user_info SET edit_count = %s WHERE id = %s',
        [count + 1, user_id],
    )
