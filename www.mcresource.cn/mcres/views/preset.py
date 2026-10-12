# preset.py
from flask import Blueprint, render_template, request, abort, jsonify, session
import json
from utils import db
from utils.imaging import image_store
from utils.messaging import feed
from utils.time import datetime_fmt
from utils.users import permissions
from utils.users.permissions import update_edit_daily, save_resource_version, add_edit_history
from utils.data.repositories import presets as presets_repo
from utils.data.repositories import users as users_repo
from utils.resource_forms import preset_flows
from utils.data.repositories import resources as resources_repo
from utils.imaging.image_store import get_thumbnail_url
from utils.site.security import process_external_links
from utils.reviews.review import append_review_history
from utils.text.sanitize import sanitize_html  # noqa: F401  (供本模块及外部调用)
from datetime import datetime
from .. import log_action

preset_bp = Blueprint('preset', __name__)


# ================================================================
# 改造点：save_image_if_data_uri 增加 target='detail' 参数
# ================================================================
def save_image_if_data_uri(image_str):
    if image_str and isinstance(image_str, str) and image_str.startswith('data:image/'):
        return image_store.save_data_uri_image(image_str, target='detail')
    return image_str


# 注：`extract_reject_reason` 与 `is_in_edit_area` 原先在本文件各有一份，
# 与其它视图的副本重复；现已移入 utils/resource_forms/ 共用
# （common.extract_reject_reason / preset_flows.is_in_edit_area）。


# ==================== 资源包预览 ====================
def categorize_items_by_registry(items, mode='first'):
    """
    按注册名分类，mode='first' 按第一个 _ 前的部分，mode='last' 按最后一个 _ 后的部分
    先去除命名空间（: 前的部分），再按 _ 分割。
    单物品类别会进行二次分类（先按第一段，单物品再按最后一段），仍单物品归入其他
    """
    first_cats = {}
    for item in items:
        registry = item['registry']
        if ':' in registry:
            base = registry.split(':', 1)[1]
        else:
            base = registry
        if '_' in base:
            if mode == 'first':
                cat = base.split('_')[0]
            else:
                cat = base.split('_')[-1]
        else:
            cat = base
        first_cats.setdefault(cat, []).append(item)

    single_items = []
    multi_cats = {}
    for cat, item_list in first_cats.items():
        if len(item_list) == 1:
            single_items.extend(item_list)
        else:
            multi_cats[cat] = item_list

    second_mode = 'last' if mode == 'first' else 'first'
    second_cats = {}
    for item in single_items:
        registry = item['registry']
        if ':' in registry:
            base = registry.split(':', 1)[1]
        else:
            base = registry
        if '_' in base:
            if second_mode == 'first':
                cat = base.split('_')[0]
            else:
                cat = base.split('_')[-1]
        else:
            cat = base
        second_cats.setdefault(cat, []).append(item)

    final_cats = multi_cats.copy()
    others = []
    for cat, item_list in second_cats.items():
        if len(item_list) > 1:
            if cat in final_cats:
                final_cats[cat].extend(item_list)
            else:
                final_cats[cat] = item_list
        else:
            others.extend(item_list)

    if others:
        final_cats['其他'] = others

    sorted_cats = sorted(final_cats.items(), key=lambda x: x[0])
    return sorted_cats


# ================================================================
# 改造点：分页 + 无限滚动加载
# ================================================================
@preset_bp.route('/preview/resourcepack/<int:id>')
def preview_resourcepack(id):
    row = resources_repo.get_for_preview(id)
    if not row:
        abort(404)
    content = json.loads(row['content']) if row.get('content') else {}
    texture_data = json.loads(row['texture']) if row.get('texture') else {}
    if not texture_data:
        abort(404, description="此资源包暂无预览数据")

    main_name = content.get('main_name', f'未命名#{id}')
    items = []
    for registry, data in texture_data.items():
        items.append({
            'registry': registry,
            'name': data.get('name', ''),
            'texture_url': data.get('texture_url', '')
        })
    items.sort(key=lambda x: x['registry'])

    search = request.args.get('search', '').strip()
    mode = request.args.get('mode', 'first')
    if mode not in ('first', 'last'):
        mode = 'first'

    if search:
        search_lower = search.lower()
        items = [item for item in items if
                 search_lower in item.get('name', '').lower() or
                 search_lower in item.get('registry', '').lower()]

    # ---------- 分页参数 ----------
    try:
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = int(request.args.get('limit', 50))
    except (TypeError, ValueError):
        limit = 50
    if offset < 0:
        offset = 0
    if limit <= 0:
        limit = 50
    if limit > 200:          # 防止被恶意拉大
        limit = 200

    total = len(items)
    page_items = items[offset:offset + limit]
    has_more = (offset + len(page_items)) < total

    categories = categorize_items_by_registry(page_items, mode)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'main_name': main_name,
            'resource_id': id,
            'mode': mode,
            'categories': [{'name': cat, 'items': c_items} for cat, c_items in categories],
            'total': total,
            'offset': offset,
            'limit': limit,
            'has_more': has_more,
        })

    # 首屏 SSR：只渲染前 limit 条（默认 50）
    return render_template('resource/detail/children/preview_resourcepack.html',
                           main_name=main_name,
                           resource_id=id,
                           categories=categories,
                           total_items=total,
                           mode=mode)


# ==================== 预设投稿（新增） ====================
@preset_bp.route('/shaderpack/<int:shaderpack_id>/preset/new', methods=['GET', 'POST'])
@permissions.login_required()
def shaderpack_preset_new(shaderpack_id):
    """新增预设。流程实现见 utils/resource_forms/preset_flows.py。"""
    current_user_id = session.get('user_info')['id']
    role = presets_repo.get_user_role(current_user_id)
    _, shader_name = preset_flows.load_shaderpack(shaderpack_id)
    can_skip_review = preset_flows.compute_can_skip_review(
        role, current_user_id, shaderpack_id)

    if request.method != 'GET':
        return preset_flows.handle_new_post(
            shaderpack_id, current_user_id, shader_name)

    resource = None
    review_id = request.args.get('id', type=int)
    change_summary = ''
    messenger = ''
    reject_reason = None
    if review_id:
        (resource, review_id, change_summary, messenger,
         reject_reason) = preset_flows.load_review_form(
            review_id, shaderpack_id, current_user_id, can_skip_review)

    return preset_flows.render_preset_form(
        shaderpack_id, shader_name,
        resource=resource,
        can_skip_review=can_skip_review,
        review_id=review_id,
        change_summary=change_summary,
        messenger=messenger,
        reject_reason=reject_reason,
    )


# ==================== 预设编辑（修改已发布的预设） ====================
@preset_bp.route('/shaderpack/<int:shaderpack_id>/preset/edit/<int:preset_id>', methods=['GET', 'POST'])
@permissions.login_required()
def shaderpack_preset_edit(shaderpack_id, preset_id):
    """编辑已发布预设。流程实现见 utils/resource_forms/preset_flows.py。"""
    current_user_id = session.get('user_info')['id']
    role = presets_repo.get_user_role(current_user_id)
    _, shader_name = preset_flows.load_shaderpack(shaderpack_id)

    preset_row = presets_repo.get_preset(shaderpack_id, preset_id)
    if not preset_row:
        abort(404, description="预设不存在")
    resource = json.loads(preset_row['content'])

    # 锁定提示（仅编辑页显示）
    lock = False
    lock_submitter = ''
    lock_time = ''
    review = users_repo.get_pending_edit(shaderpack_id)
    if review:
        lock = True
        lock_submitter = users_repo.get_nickname(review['submitter'])
        lock_time = review['submit_time']

    can_skip_review = preset_flows.compute_can_skip_review(
        role, current_user_id, shaderpack_id)

    if request.method != 'GET':
        return preset_flows.handle_edit_post(
            shaderpack_id, preset_id, current_user_id, shader_name,
            can_skip_review)

    return preset_flows.render_preset_form(
        shaderpack_id, shader_name,
        resource=resource,
        can_skip_review=can_skip_review,
        preset_id=preset_id,
        lock=lock,
        lock_submitter=lock_submitter,
        lock_time=lock_time,
    )


# ==================== 预设列表 ====================
@preset_bp.route('/shaderpack/<int:shaderpack_id>/presets')
def shaderpack_presets(shaderpack_id):
    shader_row = presets_repo.get_shaderpack_content(shaderpack_id)
    if not shader_row:
        abort(404)
    shader_content = json.loads(shader_row['content'])
    shader_name = shader_content.get('main_name', f'未命名#{shaderpack_id}')

    rows = presets_repo.list_presets(shaderpack_id)

    # 先解析 content 并**批量**取昵称：原实现是在循环里逐条
    # users_repo.get_nickname()，预设一多就是 N 次数据库往返（B 批 N+1）
    parsed = [(row, json.loads(row['content'])) for row in rows]
    nick_map = users_repo.get_nicknames(
        content.get('submitter') for _, content in parsed if content.get('submitter'))

    presets = []
    for row, content in parsed:
        raw_screenshots = content.get('screenshots', [])
        screenshots_thumb = [get_thumbnail_url(url) for url in raw_screenshots if url]

        submitter = content.get('submitter')
        submitter_nick = (nick_map.get(submitter, '未知用户') if submitter
                          else '未知用户')

        desc = content.get('description', '')
        if desc:
            desc = process_external_links(desc)

        presets.append({
            'id': row['id'],
            'name': content.get('name', '未命名预设'),
            'shader_version': content.get('shader_version', ''),
            'mc_version': content.get('mc_version', ''),
            'description': desc,
            'screenshots': screenshots_thumb,
            'submitter_nick': submitter_nick,
            'submitter_id': submitter,
            'submit_time': content.get('submit_time'),
            'date_added': row['date_added'],
            'config_notes': content.get('config_notes', '')
        })

    return render_template(
        'resource/list/children/shaderpack_presets.html',
        shaderpack={'id': shaderpack_id, 'main_name': shader_name},
        presets=presets,
        preset_count=len(presets)
    )


# ==================== 预设详情 ====================
@preset_bp.route('/shaderpack/<int:shaderpack_id>/preset/<int:preset_id>')
def shaderpack_preset_detail(shaderpack_id, preset_id):
    shader_row = presets_repo.get_shaderpack_content(shaderpack_id)
    if not shader_row:
        abort(404)
    shader_content = json.loads(shader_row['content'])
    shader_name = shader_content.get('main_name', f'未命名#{shaderpack_id}')

    row = presets_repo.get_preset(shaderpack_id, preset_id)
    if not row:
        abort(404)

    content = json.loads(row['content'])
    screenshots = content.get('screenshots', [])

    submitter = content.get('submitter')
    submitter_nick = (users_repo.get_nickname(submitter) if submitter
                      else '未知用户')

    desc = content.get('description', '')
    if desc:
        desc = process_external_links(desc)

    preset = {
        'id': row['id'],
        'name': content.get('name', '未命名预设'),
        'shader_version': content.get('shader_version', ''),
        'mc_version': content.get('mc_version', ''),
        'description': desc,
        'screenshots': screenshots,
        'config_code': content.get('config_code', ''),
        'config_notes': content.get('config_notes', ''),
        'submitter_nick': submitter_nick,
        'submitter_id': submitter,
        'submit_time': content.get('submit_time'),
        'date_added': row['date_added'],
    }

    can_edit = False
    user_info = session.get('user_info')
    if user_info:
        can_edit = True

    return render_template(
        'resource/detail/children/preset_detail.html',
        shaderpack={'id': shaderpack_id, 'main_name': shader_name},
        preset=preset,
        can_edit=can_edit
    )


# ==================== 预设历史版本列表 ====================
@preset_bp.route('/shaderpack/<int:shaderpack_id>/preset/<int:preset_id>/diff')
def preset_diff(shaderpack_id, preset_id):
    row = presets_repo.get_preset_content(shaderpack_id, preset_id)
    if not row:
        abort(404)
    content = json.loads(row['content'])
    resource_name = content.get('name', f'未命名预设#{preset_id}')

    rows = presets_repo.list_versions(
        'shaderpack_preset', preset_id,
        'id, change_summary, created_at, created_by')

    versions = []
    user_map = users_repo.get_nicknames(
        row['created_by'] for row in rows if row['created_by'])

    for row in rows:
        versions.append({
            'id': row['id'],
            'change_summary': row['change_summary'] or '（无改动说明）',
            'created_at': row['created_at'],
            'created_by': row['created_by'],
            'creator_name': user_map.get(row['created_by'], '未知用户')
        })

    return render_template(
        'resource/diff/children/preset_diff_versions.html',
        shaderpack_id=shaderpack_id,
        preset_id=preset_id,
        resource_name=resource_name,
        versions=versions
    )


# ==================== 预设版本对比详情 ====================
@preset_bp.route('/shaderpack/<int:shaderpack_id>/preset/<int:preset_id>/diff/compare')
def preset_diff_compare(shaderpack_id, preset_id):
    ids_param = request.args.get('ids')
    if not ids_param:
        abort(400, "缺少版本ID参数")

    ids = ids_param.split(',')
    if len(ids) != 2:
        abort(400, "需要两个版本ID")

    try:
        vid_a, vid_b = int(ids[0]), int(ids[1])
    except ValueError:
        abort(400, "版本ID格式错误")

    rows = presets_repo.get_versions_by_ids(
        (vid_a, vid_b), 'shaderpack_preset', preset_id)

    if len(rows) != 2:
        abort(404, "版本不存在或不属于该预设")

    user_map = users_repo.get_nicknames(
        row['created_by'] for row in rows if row['created_by'])

    preset_row = presets_repo.get_preset_content(shaderpack_id, preset_id)
    resource_name = '未命名预设'
    if preset_row:
        try:
            pc = json.loads(preset_row['content'])
            resource_name = pc.get('name', '未命名预设')
        except:
            pass

    version_data = {}
    for row in rows:
        try:
            content_data = json.loads(row['content']) if row['content'] else {}
        except:
            content_data = {}
        content_json = json.dumps(content_data, indent=2, ensure_ascii=False)
        version_data[row['id']] = {
            'id': row['id'],
            'content_json': content_json,
            'content': content_data,
            'created_at': row['created_at'],
            'created_by': row['created_by'],
            'change_summary': row['change_summary'] or '（无改动说明）',
            'creator_name': user_map.get(row['created_by'], '未知用户')
        }

    return render_template(
        'resource/diff/children/preset_diff_compare.html',
        shaderpack_id=shaderpack_id,
        preset_id=preset_id,
        resource_name=resource_name,
        version_a=version_data.get(vid_a),
        version_b=version_data.get(vid_b)
    )