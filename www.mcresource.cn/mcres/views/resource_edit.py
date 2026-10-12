# mcres/views/resource_edit.py
"""已发布资源编辑的路由（原名 edit.py）。

原 `edit.py` 把**同一种处理器按资源类型写了三遍**
（`resourcepack_edit` / `shaderpack_edit` / `map_edit`，共 655 行），
差异只有约 10 处配置点。

与新建流程的区别（不是简单复制）：
  · **锁定机制** —— 同一资源已有 `operation="edit"` 的 pending 审核时禁止再编辑；
  · **管辖区放行** —— role 2 且该资源在其编辑管辖区内时，可跳过审核直接落库。

流程逻辑在 `utils/resource_forms/flows.py`，配置在
`utils/resource_forms/common.py` 的 `SPECS`；本模块只保留路由与权限装饰器。
"""
from flask import Blueprint, request

from utils.users import permissions
from utils.resource_forms import common, flows

et = Blueprint('edit', __name__)


def _handle(spec, resource_id):
    """GET 渲染表单 / POST 执行更新或提交审核。"""
    settings, current_user_id, role, _ = common.page_context(spec)

    if request.method != 'GET':
        return flows.handle_edit(spec, resource_id, current_user_id, role)

    (resource, lock, lock_submitter, lock_time,
     can_skip_review) = flows.load_edit_page(
        spec, resource_id, current_user_id, role)
    return common.render_form(
        spec, settings, resource,
        can_skip_review=can_skip_review,
        mode='edit',
        lock=lock,
        lock_submitter=lock_submitter,
        lock_time=lock_time,
        change_summary='',
        messenger='',
        reject_reason=None,
    )


# ---------- 资源包 ----------
@et.route('/resourcepack/edit/<int:id>', methods=['GET', 'POST'])
@permissions.login_required()
def resourcepack_edit(id):
    return _handle(common.SPECS['resourcepack'], id)


# ---------- 光影包 ----------
@et.route('/shaderpack/edit/<int:id>', methods=['GET', 'POST'])
@permissions.login_required()
def shaderpack_edit(id):
    return _handle(common.SPECS['shaderpack'], id)


# ---------- 地图 ----------
@et.route('/map/edit/<int:id>', methods=['GET', 'POST'])
@permissions.login_required()
def map_edit(id):
    return _handle(common.SPECS['map'], id)
