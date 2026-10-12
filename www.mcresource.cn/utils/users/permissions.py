# utils/op.py
from flask import session, abort, redirect
from utils.data.repositories import profiles as profiles_repo
from utils.data.repositories import users as users_repo
from utils.time import datetime_fmt
from functools import wraps
from datetime import datetime


def login_required():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                id = session.get('user_info')['id']
                role = users_repo.get_full_row(id)['role']
                if role == 0:
                    session.pop('user_info', None)
                    abort(403, '当前账户已被封禁，请联系管理员了解详细情况')
            except TypeError:
                return redirect('/login')
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def role_required(lvl):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                id = session.get('user_info')['id']
            except TypeError:
                return redirect('/login')
            role = users_repo.get_role(id)
            if role < lvl:
                abort(403, '权限不足')
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def update_edit_daily(user_id, op_type):
    """
    更新用户每日编辑/提交审核次数

    :param user_id: 用户ID
    :param op_type: 'edit' 或 'submit_review'

    【Phase 1 · Step 1.4a】
    只写 user_edit_daily 表。
    user_info.edit_daily JSON 字段已停写（保留历史值，不再更新）。
    """
    if not user_id:
        return

    if op_type not in ('edit', 'submit_review'):
        return

    today = datetime_fmt.today()

    if op_type == 'edit':
        profiles_repo.bump_edit_daily(user_id, today)
    else:  # submit_review
        profiles_repo.bump_review_daily(user_id, today)


def add_edit_history(user_id, operation, target_type, target_id, resource_name, change_summary=None):
    """
    记录一条用户编辑动态

    【Phase 1 · Step 1.4a】
    只写 user_edit_history 表。
    user_info.edit_history JSON 字段已停写（保留历史值，不再更新）。
    """
    if not user_id:
        return

    profiles_repo.insert_edit_history(
        user_id,
        operation,
        target_type,
        target_id,
        resource_name or '',
        change_summary or '',
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    )


def save_resource_version(resource_type, resource_id, content, change_summary=None, created_by=None):
    """
    保存资源版本到 resource_versions 表
    :param resource_type: 'resourcepack' / 'shaderpack' / 'map' / 'shaderpack_preset'
    :param resource_id: 资源ID
    :param content: 完整的 content 字典
    :param change_summary: 改动说明
    :param created_by: 操作者用户ID（若为None则从session获取）
    """
    import json
    if created_by is None:
        from flask import session
        created_by = session.get('user_info', {}).get('id')
    if not created_by:
        return

    content_json = json.dumps(content, ensure_ascii=False)
    profiles_repo.insert_resource_version(
        resource_type, resource_id, content_json, change_summary or '',
        datetime_fmt.now(), created_by,
    )