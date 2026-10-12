# mcres/views/resource_forms/common.py
"""资源表单（新建 / 编辑）的公共实现。

背景
----
`new.py` 与 `edit.py` 各自把**同一种处理器按资源类型写了三遍**：

    new.py : resourcepack_new / shaderpack_new / map_new
    edit.py: resourcepack_edit / shaderpack_edit / map_edit

三个副本逐行相同，差异只有约 10 处**配置点**（表名、审核表名、模板、
下拉选项键名、content 里多出的字段、日志 action 名、中文标签）。
本模块把这些配置收敛成 `SPECS` 表，其余逻辑只写一份。

已修复（安全批次 A4，2026 年 bug 批次）
--------------------------------------------------
3. ~~`ban` 的 deadline 用字符串比较~~ —— 原来 `ban_edit['deadline'] >
   datetime.now().isoformat()` 比的是字符串，而 deadline 有两种写法
   （`T` 分隔 / 空格分隔），同一天的封禁会被误判。现已统一走
   `utils/users/bans.is_ban_active()`，先解析成 datetime 再比。

已知的原实现问题（本次**刻意不改**，保持行为一致，另行修复）
----------------------------------------------------------
1. `create_directly()` 用 `fetch_previous_records(limit=1)` 取新插入行的 id，
   而不用 `cursor.lastrowid`。并发插入时可能取到**别人的行 id**。
2. `bump_edit_count()` 是"先读再写"（`count + 1`），并发下会丢更新。
"""
import json
from dataclasses import dataclass, field, replace
from typing import Callable

from flask import abort, jsonify, render_template, request, session

from utils.data.repositories import resource_forms as forms_repo
from utils.data.repositories import users as users_repo
from utils.site import site_data
from utils.messaging import feed
from utils.time import datetime_fmt
from utils.text.sanitize import sanitize_html
from utils.users.bans import is_ban_active
from utils.imaging.image_store import save_data_uri_image
from utils.users.permissions import (
    update_edit_daily, save_resource_version, add_edit_history,
)
from utils.reviews.review import append_review_history

# 角色名映射（三个副本里各写了一遍，逐字相同）
ROLE_NAMES = {0: '已封禁用户', 1: '工坊成员', 2: '工坊工匠',
              3: '精英工匠', 4: '工坊主管'}

# 可以跳过审核的角色门槛
SKIP_REVIEW_ROLE = 3


# ============================================================
# 资源类型规格表 —— 唯一的差异来源
# ============================================================
@dataclass(frozen=True)
class TypeSpec:
    """一个资源类型在表单流程里的全部差异。"""

    type_key: str                 # 'resourcepack' / 'shaderpack' / 'map'
    table: str                    # 主表
    review_table: str             # 审核表
    review_fk: str                # 审核表指向主表的外键列
    template: str                 # 表单模板
    label: str                    # 中文名，用于动态/日志文案
    settings_key: str             # site_data.edit() 里的键
    option_setting: str           # 设置里的下拉选项键（categories/styles/map_types）
    option_var: str               # 模板变量名（categories/styles/map_types）
    content_fields: dict          # 该类型在 content 里额外/不同的字段
    action_suffix: str            # 日志 action 里用的后缀
    submit_action: str            # 提交新资源的日志 action 名（历史命名不统一）

    # 变体钩子：默认值即多数类型的实现，个别类型可覆盖
    status_default: str = 'active'
    normalize_status: bool = True
    image_required: bool = True   # 新建流程用 data['cover']，编辑流程用 .get


def _resourcepack_spec() -> TypeSpec:
    return TypeSpec(
        type_key='resourcepack',
        table='resourcepacks',
        review_table='resourcepack_review',
        review_fk='resourcepack_id',
        template='resource/edit/resourcepack_edit_new.html',
        label='资源包',
        settings_key='resourcepack',
        option_setting='categories',
        option_var='categories',
        content_fields={'category': 'data'},
        action_suffix='resourcepack',
        submit_action='submit_new_resourcepack',
    )


def _shaderpack_spec() -> TypeSpec:
    return TypeSpec(
        type_key='shaderpack',
        table='shaderpacks',
        review_table='shaderpack_review',
        review_fk='shaderpack_id',
        template='resource/edit/shaderpack_edit_new.html',
        label='光影包',
        settings_key='shaderpack',
        option_setting='styles',
        option_var='styles',
        content_fields={'style': 'data', 'engines': 'data'},
        action_suffix='shaderpack',
        submit_action='submit_new_shaderpack',
    )


def _map_spec() -> TypeSpec:
    return TypeSpec(
        type_key='map',
        table='maps',
        review_table='map_review',
        review_fk='map_id',
        template='resource/edit/map_edit_new.html',
        label='地图',
        settings_key='map',
        option_setting='map_types',
        option_var='map_types',
        content_fields={
            'map_type': 'data',
            'player_count': 'data',           # 新建流程必填
            'multiplayer_details': 'data.get',
            'mods': 'data.get',
        },
        action_suffix='map',
        submit_action='submit_new_map',
    )


SPECS = {
    'resourcepack': _resourcepack_spec(),
    'shaderpack': _shaderpack_spec(),
    'map': _map_spec(),
}


# ============================================================
# 通用辅助
# ============================================================
def save_image_if_data_uri(image_str, target='detail'):
    """data URI 图片落盘，返回可访问的 URL。非 data URI 原样返回。"""
    if image_str and isinstance(image_str, str) and image_str.startswith('data:image/'):
        return save_data_uri_image(image_str, target=target)
    return image_str


def normalize_status(raw_status):
    """把官方状态字段归一化到一个有限集合。"""
    valid = {'active', 'semi', 'inactive', 'unknown'}
    if raw_status in valid:
        return raw_status
    return 'unknown'


def extract_reject_reason(review_data):
    """从 review 字段里取最近一次 rejected 操作的附言。"""
    if not review_data:
        return None
    try:
        history = json.loads(review_data) if isinstance(review_data, str) else review_data
        if not isinstance(history, list):
            return None
        for entry in reversed(history):
            if isinstance(entry, dict) and entry.get('action') == 'rejected':
                return entry.get('note')
    except Exception:
        pass
    return None


def page_context(spec):
    """GET 分支公用的上下文：设置、当前用户、角色、是否可免审核。"""
    settings = site_data.edit()[spec.settings_key]
    current_user_id = session.get('user_info')['id']
    role = users_repo.get_role(current_user_id)
    return settings, current_user_id, role, role >= SKIP_REVIEW_ROLE


def render_form(spec, settings, resource, *, can_skip_review, **extra):
    """渲染表单，按规格表决定下拉选项变量名。"""
    context = {
        'versions': settings['versions'],
        spec.option_var: settings[spec.option_setting],
        'resource': resource,
        'can_skip_review': can_skip_review,
        'role_names': ROLE_NAMES,
    }
    context.update(extra)
    return render_template(spec.template, **context)


# ============================================================
# 读取：新建流程的 GET（按 review_id 预填）
# ============================================================
def load_for_new(spec, review_id, current_user_id, can_skip_review):
    """`/xxx/new?id=N` 的预填逻辑。

    管理员直接编辑已发布资源；普通用户从审核列表"再编辑"。
    返回 (resource, change_summary, messenger, reject_reason)。
    """
    if not review_id:
        return None, '', '', None

    if can_skip_review:
        row = forms_repo.get_content(spec.table, review_id)
        if not row:
            abort(404)
        resource = json.loads(row['content'])
        resource['id'] = int(review_id)
        return resource, '', '', None

    result = forms_repo.get_review_for_edit(spec.review_table, review_id)
    if not result:
        abort(404)
    row = result[0]
    if row['submitter'] != current_user_id:
        abort(403, description="您无权操作他人的审核项")
    if row['status'] == 'passed':
        abort(403, description="已通过审核的内容不可编辑")
    resource = json.loads(row['content'])
    resource['id'] = int(review_id)
    return (
        resource,
        row.get('change_summary', '') or '',
        row.get('messenger', '') or '',
        extract_reject_reason(row.get('review')) if row['status'] == 'rejected' else None,
    )


def _load_ban(user_id):
    """读取用户的 ban 字段并解析（统一走仓储的容错解析）。"""
    return users_repo.get_ban_parsed(user_id)


def check_edit_ban(spec, current_user_id, target_id, *, action):
    """编辑封禁检查。被封禁时返回 Flask 响应，否则返回 None。

    保留原实现的字符串比较与 `except: pass`（见模块 docstring 的已知问题 3）。
    """
    ban_data = _load_ban(current_user_id)
    if not ban_data:
        return None
    ban_edit = ban_data.get('edit')
    if not is_ban_active(ban_edit):
        return None

    log_kwargs = dict(
        user_id=current_user_id,
        action=action,
        level='WARNING',
        request_data={'reason': 'edit_banned'},
    )
    if target_id is not None:
        log_kwargs['target_type'] = spec.type_key
        log_kwargs['target_id'] = target_id
    from mcres import log_action
    log_action(**log_kwargs)
    return jsonify({
        'message': f'您已被禁止编辑，截止至 {ban_edit["deadline"]}，'
                   f'原因：{ban_edit.get("reason", "无")}'
    }), 403


# ============================================================
# 构建 content
# ============================================================
def build_content(spec, data, *, new_flow: bool):
    """把请求体转成 content_dict。

    `new_flow=True` 走 `new.py` 的取值方式（必填键直接下标访问），
    `new_flow=False` 走 `edit.py` 的取值方式（全部 `.get` 带默认值）。
    两者的差异是**既有的**，这里如实保留。
    """
    if new_flow:
        cover = save_image_if_data_uri(data['cover'])
        screenshots = [save_image_if_data_uri(img) for img in data['screenshots']]
    else:
        cover = save_image_if_data_uri(data.get('cover', ''))
        screenshots = [save_image_if_data_uri(img)
                       for img in data.get('screenshots', [])]

    safe_description = sanitize_html(data.get('description', ''))

    if new_flow:
        get = lambda k, d: data[k]                       # noqa: E731
    else:
        get = lambda k, d: data.get(k, d)                # noqa: E731

    content = {
        'main_name': get('main_name', ''),
        'sub_name': get('sub_name', ''),
        'abbr': get('abbr', ''),
    }
    # 各类型在 abbr 之后插入自己的字段（map 的 player_count 等）
    for key, source in spec.content_fields.items():
        content[key] = data.get(key, '') if source == 'data.get' else get(key, '')

    content.update({
        'summary': get('summary', ''),
        'cover': cover,
        'screenshots': screenshots,
        'description': safe_description,
        'platforms': get('platforms', []),
        'versions': get('versions', []),
    })
    # resourcepack/shaderpack 有 features；map 没有
    if spec.type_key != 'map':
        content['features'] = get('features', [])
    content.update({
        'authors': get('authors', []),
        'status': (normalize_status(get('status', spec.status_default))
                   if spec.normalize_status else get('status', spec.status_default)),
        'download_links': get('download_links', []),
        'keywords': get('keywords', ''),
        'license': get('license', ''),
        'mcmod_id': data.get('mcmod_id', ''),
        'curseforge_id': data.get('curseforge_id', ''),
        'modrinth_id': data.get('modrinth_id', ''),
        'bilibili_video': data.get('bilibili_video', ''),
    })
    return content


# ============================================================
# 写：直接落库（高权限角色）
# ============================================================
def update_directly(spec, content, content_json, target_id):
    """直接更新已发布资源（视为编辑）。"""
    forms_repo.update_content(spec.table, content_json, target_id)


def create_directly(spec, content, content_json):
    """直接插入新资源，返回新 id。

    注意：原实现用 `fetch_previous_records(limit=1)` 猜新行 id，
    并发下有取错行的风险。此处**保持原语义**，未改用 lastrowid。
    """
    from mcres import log_action  # noqa: F401  (调用方仍需 log_action)
    forms_repo.insert_resource(spec.table, content_json, datetime_fmt.now())
    return forms_repo.last_inserted_resource_id(spec.table)


def bump_edit_count(current_user_id):
    """用户 edit_count +1。

    原实现是"先读再写"，并发下丢更新。此处保持原样。
    """
    users_repo.bump_edit_count(current_user_id)


def add_feed_added(spec, current_user_id, content):
    """写一条"添加了X"动态。"""
    feed.add_feed(current_user_id, f"添加了{spec.label}",
                  f"「{content['main_name']}」")


def log_resource_action(spec, *, action, current_user_id, target_id,
                        content, mode, role, change_summary, messenger):
    """记录资源创建/更新的操作日志。"""
    from mcres import log_action
    log_action(
        user_id=current_user_id,
        action=action,
        level='INFO',
        target_type=spec.type_key,
        target_id=target_id,
        request_data={
            'main_name': content['main_name'],
            'mode': mode,
            'role': role,
            'change_summary': change_summary,
            'messenger': messenger,
        },
    )


# ============================================================
# 写：审核表（普通用户）
# ============================================================
def assert_review_editable(spec, review_id, current_user_id):
    """校验审核项存在、属于本人、且未通过。"""
    check = forms_repo.get_review_submitter_status(spec.review_table, review_id)
    if not check:
        abort(404)
    if check[0]['submitter'] != current_user_id:
        abort(403, description="您无权操作他人的审核项")
    if check[0]['status'] == 'passed':
        abort(403, description="已通过审核的内容不可编辑")


def refresh_review(spec, review_id, content, content_json,
                   change_summary, messenger, current_user_id):
    """更新已有审核项为 pending，并追加审核时间线。"""
    row = forms_repo.get_review_field(spec.review_table, review_id)
    review_json = append_review_history(
        review_data=row.get('review') if row else None,
        action='pending',
        user=current_user_id,
        note=None,
        content=content,
    )
    forms_repo.update_pending_review(
        spec.review_table, content_json, datetime_fmt.now(), change_summary,
        messenger, review_json, review_id,
    )


def insert_review(spec, content, content_json, change_summary, messenger,
                  current_user_id):
    """首次提交：新增一条审核记录。"""
    review_json = append_review_history(
        review_data=None, action='pending', user=current_user_id,
        note=None, content=content,
    )
    forms_repo.insert_pending_review(
        spec.review_table, current_user_id, datetime_fmt.now(), content_json,
        change_summary, messenger, review_json,
    )


def log_review_action(spec, *, action, current_user_id, target_id,
                      content, mode, change_summary, messenger):
    """记录审核提交/更新的操作日志。"""
    from mcres import log_action
    log_action(
        user_id=current_user_id,
        action=action,
        level='INFO',
        target_type=spec.type_key if target_id else None,
        target_id=target_id,
        request_data={
            'main_name': content['main_name'],
            'mode': mode,
            'change_summary': change_summary,
            'messenger': messenger,
        },
    )


def append_pending_history(spec, resource_id, current_user_id, content):
    """编辑流程：读取该资源最近的审核时间线并追加一条 pending。

    原实现按资源取最近一条 review（不限 operation）作为基线。
    """
    row = forms_repo.get_latest_review_field(
        spec.review_table, spec.review_fk, resource_id)
    return append_review_history(
        review_data=row.get('review') if row else None,
        action='pending',
        user=current_user_id,
        note=None,
        content=content,
    )
