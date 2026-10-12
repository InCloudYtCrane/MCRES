# mcres/views/resource_create.py
"""资源新建 / 提交审核的路由（原名 new.py）。

原 `new.py` 把**同一种处理器按资源类型写了三遍**
（`resourcepack_new` / `shaderpack_new` / `map_new`，共 742 行），
三份逐行相同、差异只有约 10 处配置点。

现流程逻辑收敛到 `utils/resource_forms/flows.py`，差异由
`utils/resource_forms/common.py` 的 `SPECS` 描述；本模块只保留
**路由定义与权限装饰器**，因此打开这个文件就能看到它有哪几个路由。
"""
from flask import Blueprint, request, session

from utils.messaging import feed  # noqa: F401  (历史依赖保留)
from utils.users import permissions
from utils.resource_forms import common, flows

nw = Blueprint('new', __name__)


def _handle(spec):
    """GET 渲染表单 / POST 执行提交。"""
    settings, current_user_id, role, can_skip_review = common.page_context(spec)

    if request.method != 'GET':
        return flows.handle_new(spec, current_user_id, role)

    resource, change_summary, messenger, reject_reason = common.load_for_new(
        spec, request.args.get('id', type=int), current_user_id, can_skip_review)
    return common.render_form(
        spec, settings, resource,
        can_skip_review=can_skip_review,
        mode='new',
        change_summary=change_summary,
        messenger=messenger,
        reject_reason=reject_reason,
    )


# ---------- 资源包 ----------
@nw.route('/resourcepack/new', methods=['GET', 'POST'])
@permissions.login_required()
def resourcepack_new():
    return _handle(common.SPECS['resourcepack'])


# ---------- 光影包 ----------
@nw.route('/shaderpack/new', methods=['GET', 'POST'])
@permissions.login_required()
def shaderpack_new():
    return _handle(common.SPECS['shaderpack'])


# ---------- 地图 ----------
@nw.route('/map/new', methods=['GET', 'POST'])
@permissions.login_required()
def map_new():
    return _handle(common.SPECS['map'])
