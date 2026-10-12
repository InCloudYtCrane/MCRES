# utils/resource_forms/flows.py
"""资源表单的两套流程实现（新建 / 编辑）。

对应原先 `mcres/views/new.py` 与 `mcres/views/edit.py` 里各写三遍的处理器。
差异全部来自 `common.SPECS`，本模块只保留一份流程逻辑。

路由与权限装饰器**仍留在视图模块**，这样 `flask routes`、`url_map` 以及
"打开某个文件就能看到它有哪些路由"的阅读习惯都不受影响。
"""
import json

from flask import abort, jsonify, request

from utils.data.repositories import presets as presets_repo
from utils.data.repositories import resource_forms as forms_repo
from utils.data.repositories import users as users_repo
from utils.time import datetime_fmt
from . import common
from .common import (
    add_edit_history, save_resource_version,
    update_edit_daily, assert_review_editable,
    insert_review, refresh_review,
)


# ============================================================
# 流程一：新建（对应原 new.py）
# ============================================================
def handle_new(spec, current_user_id, role):
    """POST 处理：直接落库（高权限）或提交审核（普通用户）。"""
    data = request.get_json()
    review_id = data.get('id')

    banned = common.check_edit_ban(spec, current_user_id, None,
                                   action=f'create_{spec.action_suffix}')
    if banned:
        return banned

    change_summary = data.get('change_summary', '').strip()
    messenger = data.get('messenger', '').strip()

    content = common.build_content(spec, data, new_flow=True)
    content_json = json.dumps(content, ensure_ascii=False)

    if role >= common.SKIP_REVIEW_ROLE:
        if review_id:
            # 直接更新已有资源（视为编辑）
            common.update_directly(spec, content, content_json, review_id)
            update_edit_daily(current_user_id, 'edit')
            common.add_feed_added(spec, current_user_id, content)
            add_edit_history(current_user_id, 'edit', spec.type_key, review_id,
                             content['main_name'], change_summary)
            save_resource_version(spec.type_key, review_id, content,
                                  change_summary, current_user_id)
            common.log_resource_action(
                spec, action=f'update_{spec.action_suffix}',
                current_user_id=current_user_id, target_id=review_id,
                content=content, mode='direct_update', role=role,
                change_summary=change_summary, messenger=messenger)
            return jsonify({'message': 'updated', 'id': review_id})

        new_id = common.create_directly(spec, content, content_json)
        common.bump_edit_count(current_user_id)
        update_edit_daily(current_user_id, 'edit')
        common.add_feed_added(spec, current_user_id, content)
        add_edit_history(current_user_id, 'add', spec.type_key, new_id,
                         content['main_name'], change_summary)
        save_resource_version(spec.type_key, new_id, content,
                              change_summary, current_user_id)
        common.log_resource_action(
            spec, action=f'create_{spec.action_suffix}',
            current_user_id=current_user_id, target_id=new_id,
            content=content, mode='direct_create', role=role,
            change_summary=change_summary, messenger=messenger)
        return jsonify({'message': 'ok', 'id': new_id})

    # 普通用户：走审核流程
    if review_id:
        assert_review_editable(spec, review_id, current_user_id)
        refresh_review(spec, review_id, content, content_json,
                       change_summary, messenger, current_user_id)
        common.log_review_action(
            spec, action=f'update_{spec.action_suffix}_review',
            current_user_id=current_user_id, target_id=review_id,
            content=content, mode='update_review',
            change_summary=change_summary, messenger=messenger)
        return jsonify({'message': 'updated'})

    insert_review(spec, content, content_json, change_summary, messenger,
                  current_user_id)
    update_edit_daily(current_user_id, 'submit_review')
    common.log_review_action(
        spec, action=spec.submit_action,
        current_user_id=current_user_id, target_id=None,
        content=content, mode='submit_review',
        change_summary=change_summary, messenger=messenger)
    return jsonify({'message': 'ok'})


# ============================================================
# 流程二：编辑已发布资源（对应原 edit.py）
# ============================================================
def _load_edit_lock(spec, resource_id):
    """查询该资源是否有 pending 的编辑，返回 (locked, submitter, time)。"""
    review = forms_repo.get_pending_edit(
        spec.review_table, spec.review_fk, resource_id)
    if not review:
        return False, '', ''
    submitter_id = review[0]['submitter']
    nick_row = users_repo.get_nickname_row(submitter_id)
    return True, nick_row['nickname'], review[0]['submit_time']


def _is_in_edit_area(user_id, resource_id, category):
    """用户是否在编辑管辖区内（role 2 免审核的依据）。"""
    user = presets_repo.get_edit_area(user_id)
    if not user or not user.get('edit_area'):
        return False
    try:
        edit_area = json.loads(user['edit_area'])
    except Exception:
        return False
    if category not in edit_area:
        return False
    cat_data = edit_area[category]
    if cat_data.get('all') is True:
        return True
    return resource_id in cat_data.get('detail', [])


def load_edit_page(spec, resource_id, current_user_id, role):
    """GET：读取资源 + 锁定状态，判断能否免审核。"""
    row = forms_repo.get_content(spec.table, resource_id)
    if not row:
        abort(404)
    resource = json.loads(row['content'])
    resource['id'] = resource_id

    lock, lock_submitter, lock_time = _load_edit_lock(spec, resource_id)

    can_skip_review = False
    if role >= common.SKIP_REVIEW_ROLE:
        can_skip_review = True
    elif role == 2 and _is_in_edit_area(current_user_id, resource_id,
                                        spec.type_key):
        can_skip_review = True

    return resource, lock, lock_submitter, lock_time, can_skip_review


def handle_edit(spec, resource_id, current_user_id, role):
    """POST：更新已发布资源，或提交一条 edit 审核。"""
    from mcres import log_action

    data = request.get_json()
    if not data:
        log_action(
            user_id=current_user_id,
            action=f'edit_{spec.action_suffix}',
            level='WARNING',
            target_type=spec.type_key,
            target_id=resource_id,
            request_data={'error': 'invalid_json'},
        )
        abort(400, description="无效的JSON数据")

    banned = common.check_edit_ban(spec, current_user_id, resource_id,
                                   action=f'edit_{spec.action_suffix}')
    if banned:
        return banned

    # 锁定检查：同资源已有 pending 编辑时禁止再编辑
    lock_check = forms_repo.find_pending_edit_id(
        spec.review_table, spec.review_fk, resource_id)
    if lock_check:
        log_action(
            user_id=current_user_id,
            action=f'edit_{spec.action_suffix}',
            level='WARNING',
            target_type=spec.type_key,
            target_id=resource_id,
            request_data={'reason': 'locked'},
        )
        return jsonify({'message': f'该{spec.label}正在审核中，暂时无法编辑'}), 403
    content = common.build_content(spec, data, new_flow=False)
    content_json = json.dumps(content, ensure_ascii=False)
    change_summary = data.get('change_summary', '').strip()
    messenger = data.get('messenger', '').strip()

    if role >= common.SKIP_REVIEW_ROLE:
        # 高权限：直接更新 + 计数 + 动态 + 历史 + 版本
        forms_repo.update_content(spec.table, content_json, resource_id)
        common.bump_edit_count(current_user_id)
        update_edit_daily(current_user_id, 'edit')
        save_resource_version(spec.type_key, resource_id, content,
                              change_summary, current_user_id)
        common.log_resource_action(
            spec, action=f'edit_{spec.action_suffix}',
            current_user_id=current_user_id, target_id=resource_id,
            content=content, mode='direct_update', role=role,
            change_summary=change_summary, messenger=messenger)
        return jsonify({'message': 'updated', 'id': resource_id})

    # 普通用户：写一条 edit 审核
    review_json = common.append_pending_history(spec, resource_id,
                                                current_user_id, content)
    forms_repo.insert_edit_review(
        spec.review_table, spec.review_fk, current_user_id, datetime_fmt.now(),
        content_json, change_summary, messenger, review_json, resource_id,
    )
    update_edit_daily(current_user_id, 'submit_review')
    log_action(
        user_id=current_user_id,
        action=f'edit_{spec.action_suffix}',
        level='INFO',
        target_type=spec.type_key,
        target_id=resource_id,
        request_data={
            'main_name': content['main_name'],
            'mode': 'submit_review',
            'change_summary': change_summary,
            'messenger': messenger,
        },
    )
    return jsonify({'message': 'ok'})
