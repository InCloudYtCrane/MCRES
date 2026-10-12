# utils/resource_forms/preset_flows.py
"""光影包预设表单（新建 / 编辑）的公共实现。

原先 `mcres/views/preset.py` 的 `shaderpack_preset_new`(210 行) 与
`shaderpack_preset_edit`(175 行) 是**同一逻辑的两份副本**，差异只有：

| | new | edit |
|---|---|---|
| 进入时是否加载预设 | 否 | 是（`get_preset`） |
| 锁定提示 | 不显示 | 显示（`get_pending_edit`） |
| 提交审核的表单字段 | `review_id` 取自**查询串** | 取自**请求体** |
| POST 的锁定拦截 | **无** | 有（`get_pending_edit_id`） |
| 直接落库动作 | `insert_preset` | `update_preset_content` |
| 新增审核 | `insert_review_new`（operation='add'） | `insert_review_edit`（operation='edit'） |
| 日志 action 名 | `update_preset_review` / `create_preset_direct` / `submit_preset_review` | `update_preset_review` / `edit_preset_direct` / `edit_preset_submit_review` |
| 重定向 | 新增后回预设详情页 | 回预设详情页 |

保留的既有差异（**不合并**，否则改变行为）：
· `new` 流程**不做锁定拦截**，`edit` 流程做 —— 已如实保留；
· `new` 流程的字段获取用的是 `data.get`，与 `edit` 相同（此处无差异）。

模板与表单字段完全一致，两者共用 `shaderpack_preset_new.html`。
"""
import json

from flask import abort, jsonify, request

from utils.messaging import feed
from utils.text.sanitize import sanitize_html
from utils.time import datetime_fmt
from utils.users.bans import is_ban_active
from utils.data.repositories import presets as presets_repo
from utils.data.repositories import users as users_repo
from utils.users.permissions import (
    update_edit_daily, save_resource_version, add_edit_history,
)
from utils.reviews.review import append_review_history
from .common import (
    SKIP_REVIEW_ROLE, save_image_if_data_uri, extract_reject_reason,
)

PRESET_TEMPLATE = 'resource/edit/children/shaderpack_preset_new.html'

# 审核状态中"允许再编辑"的集合
_EDITABLE_REVIEW_STATUS = ['pending', 'rejected', 'withdrawn']


# ============================================================
# 公共辅助
# ============================================================
def load_shaderpack(shaderpack_id):
    """加载宿主光影包，返回 (shader_row, shader_name)。不存在则 404。"""
    shader_row = presets_repo.get_shaderpack_content(shaderpack_id)
    if not shader_row:
        abort(404)
    try:
        shader_content = json.loads(shader_row['content'])
    except Exception:
        shader_content = {}
    return shader_row, shader_content.get('main_name', f'未命名#{shaderpack_id}')


def compute_can_skip_review(role, current_user_id, shaderpack_id):
    """是否可跳过审核：role>=3，或 role==2 且在该光影包的编辑管辖区内。"""
    if role >= SKIP_REVIEW_ROLE:
        return True
    if role == 2:
        return is_in_edit_area(current_user_id, shaderpack_id)
    return False


def is_in_edit_area(user_id, shaderpack_id):
    """role 2 的编辑管辖区判断（按 shaderpack_id）。"""
    user = presets_repo.get_edit_area(user_id)
    if not user or not user.get('edit_area'):
        return False
    try:
        edit_area = json.loads(user['edit_area'])
    except Exception:
        return False
    key = 'shaderpack'
    if key not in edit_area:
        return False
    cat_data = edit_area[key]
    if cat_data.get('all') is True:
        return True
    return shaderpack_id in cat_data.get('detail', [])


def check_ban(current_user_id):
    """编辑封禁检查。被封禁时返回响应，否则 None。

    注意：预设的提示文案与资源表单**不同**（不含"原因"），
    因此不复用 `common.check_edit_ban`。

    【bug 修复】原实现写的是 `ban_edit['deadline'] > datetime.now().isoformat()`，
    但本模块**从来没有 import datetime** —— 只要用户带着 edit 封禁提交，
    这里就抛 `NameError`（表现为 500，而不是正确的 403）。
    现在统一走 `is_ban_active()`，顺带把两个问题一起修掉。
    """
    ban_raw = users_repo.get_ban(current_user_id)
    if not ban_raw:
        return None
    try:
        ban_data = json.loads(ban_raw)
    except Exception:
        return None
    ban_edit = ban_data.get('edit')
    if is_ban_active(ban_edit):
        return jsonify(
            {'message': f'您已被禁止编辑，截止至 {ban_edit["deadline"]}'}), 403
    return None


def load_review_form(review_id, shaderpack_id, current_user_id,
                     can_skip_review):
    """按 review_id 预填表单（仅 new 流程使用）。

    管理员直接取已发布预设的内容；普通用户从审核记录取。
    返回 (resource, review_id, change_summary, messenger, reject_reason)。
    """
    if can_skip_review:
        row = presets_repo.get_preset_content(shaderpack_id, review_id)
        if not row:
            abort(404, description="预设不存在")
        resource = json.loads(row['content'])
        return resource, review_id, '', '', None

    review_row = presets_repo.get_review(
        review_id, shaderpack_id,
        'content, submitter, status, change_summary, messenger, review')
    if not review_row:
        abort(404, description="审核记录不存在")
    if review_row['submitter'] != current_user_id:
        abort(403, description="您无权操作他人的审核项")
    if review_row['status'] not in _EDITABLE_REVIEW_STATUS:
        abort(403, description="已通过的审核不可再编辑")

    resource = json.loads(review_row['content'])
    change_summary = review_row.get('change_summary', '') or ''
    messenger = review_row.get('messenger', '') or ''
    reject_reason = None
    if review_row['status'] == 'rejected':
        reject_reason = extract_reject_reason(review_row.get('review'))
    return resource, review_id, change_summary, messenger, reject_reason


def parse_and_validate(data):
    """解析表单字段并校验。返回 (preset_data, change_summary, messenger,
    error_response)。

    校验规则在两个流程里逐字相同：名称、≥1 张截图、光影包版本、
    游戏版本、配置内容均为必填。
    """
    name = data.get('name', '').strip()
    shader_version = data.get('shader_version', '').strip()
    mc_version = data.get('mc_version', '').strip()
    description = sanitize_html(data.get('description', ''))
    config_code = data.get('config_code', '').strip()
    config_notes = data.get('config_notes', '').strip()
    change_summary = data.get('change_summary', '').strip()
    messenger = data.get('messenger', '').strip()

    screenshots_raw = data.get('screenshots', [])
    if not isinstance(screenshots_raw, list):
        screenshots_raw = []
    screenshots = [save_image_if_data_uri(img) for img in screenshots_raw]

    errors = []
    if not name:
        errors.append('预设名称不能为空')
    if len(screenshots) < 1:
        errors.append('至少上传一张截图')
    if not shader_version:
        errors.append('光影包版本不能为空')
    if not mc_version:
        errors.append('游戏版本不能为空')
    if not config_code:
        errors.append('配置文件内容不能为空')
    if errors:
        return None, None, None, jsonify(
            {'message': '请完善以下必填项：' + '；'.join(errors)}), 400

    preset_data = {
        'name': name,
        'shader_version': shader_version,
        'mc_version': mc_version,
        'description': description,
        'config_code': config_code,
        'config_notes': config_notes,
        'screenshots': screenshots,
        'submitter': None,          # 由调用方填入（需 current_user_id）
        'submit_time': datetime_fmt.now(),
        'change_summary': change_summary,
    }
    return preset_data, change_summary, messenger, None


# ============================================================
# 两条流程
# ============================================================
def render_preset_form(shaderpack_id, shader_name, *, resource,
                       can_skip_review, review_id=None, preset_id=None,
                       change_summary='', messenger='', reject_reason=None,
                       lock=False, lock_submitter='', lock_time=''):
    """渲染预设表单（新建/编辑共用同一模板）。"""
    from flask import render_template
    return render_template(
        PRESET_TEMPLATE,
        shaderpack={'id': shaderpack_id, 'main_name': shader_name},
        can_skip_review=can_skip_review,
        resource=resource,
        review_id=review_id,
        preset_id=preset_id,
        lock=lock,
        lock_submitter=lock_submitter,
        lock_time=lock_time,
        change_summary=change_summary,
        messenger=messenger,
        reject_reason=reject_reason,
    )


def handle_new_post(shaderpack_id, current_user_id, shader_name):
    """新增预设的 POST 流程（含"再编辑审核项"与直接落库/提交审核）。"""
    from mcres import log_action

    data = request.get_json()
    if not data:
        abort(400, description="无效的JSON数据")

    banned = check_ban(current_user_id)
    if banned:
        return banned

    preset_data, change_summary, messenger, err = parse_and_validate(data)
    if err:
        return err
    preset_data['submitter'] = current_user_id
    name = preset_data['name']
    preset_json = json.dumps(preset_data, ensure_ascii=False)

    # ---------- 处理审核中的"再编辑"（review_id 存在）----------
    review_id = data.get('review_id')
    if review_id:
        check = presets_repo.get_review(
            review_id, shaderpack_id, 'submitter, status')
        if not check:
            abort(404, description="审核记录不存在")
        if check['submitter'] != current_user_id:
            abort(403, description="您无权操作他人的审核项")
        if check['status'] not in _EDITABLE_REVIEW_STATUS:
            abort(403, description="已通过的审核不可再修改")

        row = presets_repo.get_review(review_id, shaderpack_id, 'review')
        review_json = append_review_history(
            review_data=row.get('review') if row else None,
            action='pending', user=current_user_id, note=None,
            content=preset_data,
        )
        presets_repo.update_review(
            review_id, preset_json, datetime_fmt.now(),
            change_summary, messenger, 'pending', review_json)
        log_action(
            user_id=current_user_id, action='update_preset_review',
            level='INFO', target_type='shaderpack', target_id=shaderpack_id,
            request_data={'preset_name': name, 'review_id': review_id,
                          'messenger': messenger})
        return jsonify(
            {'message': 'ok', 'redirect_url': '/review?type=shaderpack'})

    # ---------- 新增投稿 ----------
    role = presets_repo.get_user_role(current_user_id)
    if compute_can_skip_review(role, current_user_id, shaderpack_id):
        presets_repo.insert_preset(
            shaderpack_id, preset_json, datetime_fmt.now())
        new_id = presets_repo.last_inserted_preset_id()
        users_repo.bump_edit_count(current_user_id)
        feed.add_feed(current_user_id, "发布了预设",
                      f"为光影包「{shader_name}」添加预设「{name}」")
        add_edit_history(current_user_id, 'add', 'shaderpack_preset',
                         new_id, name, change_summary)
        save_resource_version('shaderpack_preset', new_id, preset_data,
                              change_summary, current_user_id)
        update_edit_daily(current_user_id, 'edit')
        log_action(
            user_id=current_user_id, action='create_preset_direct',
            level='INFO', target_type='shaderpack', target_id=shaderpack_id,
            request_data={'preset_name': name, 'preset_id': new_id})
        return jsonify(
            {'message': 'ok', 'id': new_id,
             'redirect_url': f'/shaderpack/{shaderpack_id}/preset/{new_id}'})

    review_json = append_review_history(
        review_data=None, action='pending', user=current_user_id,
        note=None, content=preset_data,
    )
    presets_repo.insert_review_new(
        shaderpack_id, preset_json, current_user_id, datetime_fmt.now(),
        change_summary, messenger, review_json)
    update_edit_daily(current_user_id, 'submit_review')
    log_action(
        user_id=current_user_id, action='submit_preset_review',
        level='INFO', target_type='shaderpack', target_id=shaderpack_id,
        request_data={'preset_name': name, 'messenger': messenger})
    return jsonify(
        {'message': 'submitted_to_review',
         'redirect_url': '/review?type=shaderpack'})


def handle_edit_post(shaderpack_id, preset_id, current_user_id, shader_name,
                     can_skip_review):
    """编辑已发布预设的 POST 流程。"""
    from mcres import log_action

    data = request.get_json()
    if not data:
        abort(400, description="无效的JSON数据")

    banned = check_ban(current_user_id)
    if banned:
        return banned

    # 锁定拦截（仅 edit 流程有）
    if presets_repo.get_pending_edit_id(shaderpack_id):
        return jsonify({'message': '该预设正在审核中，暂时无法编辑'}), 403

    preset_data, change_summary, messenger, err = parse_and_validate(data)
    if err:
        return err
    preset_data['submitter'] = current_user_id
    name = preset_data['name']
    preset_json = json.dumps(preset_data, ensure_ascii=False)

    if can_skip_review:
        presets_repo.update_preset_content(preset_id, preset_json)
        users_repo.bump_edit_count(current_user_id)
        feed.add_feed(current_user_id, "编辑了预设",
                      f"为光影包「{shader_name}」编辑预设「{name}」")
        add_edit_history(current_user_id, 'edit', 'shaderpack_preset',
                         preset_id, name, change_summary)
        save_resource_version('shaderpack_preset', preset_id, preset_data,
                              change_summary, current_user_id)
        update_edit_daily(current_user_id, 'edit')
        log_action(
            user_id=current_user_id, action='edit_preset_direct',
            level='INFO', target_type='shaderpack', target_id=shaderpack_id,
            request_data={'preset_name': name, 'preset_id': preset_id,
                          'mode': 'direct_edit', 'messenger': messenger})
        return jsonify(
            {'message': 'ok', 'id': preset_id,
             'redirect_url': f'/shaderpack/{shaderpack_id}/preset/{preset_id}'})

    row = presets_repo.get_pending_edit_for(shaderpack_id)
    review_json = append_review_history(
        review_data=row.get('review') if row else None,
        action='pending', user=current_user_id, note=None,
        content=preset_data,
    )
    presets_repo.insert_review_edit(
        shaderpack_id, preset_id, preset_json, current_user_id,
        datetime_fmt.now(), change_summary, messenger, review_json)
    update_edit_daily(current_user_id, 'submit_review')
    log_action(
        user_id=current_user_id, action='edit_preset_submit_review',
        level='INFO', target_type='shaderpack', target_id=shaderpack_id,
        request_data={'preset_name': name, 'preset_id': preset_id,
                      'messenger': messenger})
    return jsonify(
        {'message': 'submitted_to_review',
         'redirect_url': '/review?type=shaderpack'})
