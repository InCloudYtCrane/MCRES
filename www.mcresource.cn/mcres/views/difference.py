# mcres/views/difference.py
import json
from flask import Blueprint, render_template, abort, request

from utils.constants import is_valid_resource_type
from utils.data.repositories import resources
from utils.data.repositories.users import get_nicknames


diff_bp = Blueprint('difference', __name__, url_prefix='')


# ============================================================
# 版本列表页面
# ============================================================
@diff_bp.route('/resourcepack/<int:id>/diff')
def resourcepack_diff(id):
    return render_diff_page('resourcepack', id)


@diff_bp.route('/shaderpack/<int:id>/diff')
def shaderpack_diff(id):
    return render_diff_page('shaderpack', id)


@diff_bp.route('/map/<int:id>/diff')
def map_diff(id):
    return render_diff_page('map', id)


# ============================================================
# 版本对比详情页
# ============================================================
@diff_bp.route('/<string:resource_type>/<int:resource_id>/diff/compare')
def diff_compare(resource_type, resource_id):
    """对比两个版本的详情页"""
    if not is_valid_resource_type(resource_type):
        abort(404)

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

    # 查询两个版本，验证都属于该资源
    rows = resources.list_versions_by_ids(
        (vid_a, vid_b), resource_type, resource_id)

    if len(rows) != 2:
        abort(404, "版本不存在或不属于该资源")

    user_ids = [row['created_by'] for row in rows if row['created_by']]
    user_map = get_nicknames(user_ids) if user_ids else {}

    version_data = {}
    for row in rows:
        try:
            content_data = json.loads(row['content']) if row['content'] else {}
        except:
            content_data = {}
        # 在 Python 端转为格式化的 JSON 字符串
        content_json = json.dumps(content_data, indent=2, ensure_ascii=False)
        version_data[row['id']] = {
            'id': row['id'],
            'content_json': content_json,  # 用于模板显示
            'content': content_data,  # 保留备用
            'created_at': row['created_at'],
            'created_by': row['created_by'],
            'change_summary': row['change_summary'] or '（无改动说明）',
            'creator_name': user_map.get(row['created_by'], '未知用户')
        }

    # 获取资源名称
    resource_row = resources.get_content(resource_type, resource_id)
    resource_name = '未知资源'
    if resource_row is not None:
        if resource_row:
            try:
                rc = json.loads(resource_row['content'])
                resource_name = rc.get('main_name', f'未命名#{resource_id}')
            except:
                resource_name = f'未命名#{resource_id}'
    return render_template(
        'resource/diff/diff_compare.html',
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        version_a=version_data.get(vid_a),
        version_b=version_data.get(vid_b)
    )


# ============================================================
# 核心渲染函数（版本列表）
# ============================================================
def render_diff_page(resource_type, resource_id):
    """渲染编辑历史对比列表页"""
    if not is_valid_resource_type(resource_type):
        abort(404)

    resource_row = resources.get_content(resource_type, resource_id)
    if not resource_row:
        abort(404)

    try:
        content = json.loads(resource_row['content'])
        resource_name = content.get('main_name', f'未命名#{resource_id}')
    except:
        resource_name = f'未命名#{resource_id}'

    rows = resources.list_versions(resource_type, resource_id)

    versions = []
    user_ids = [row['created_by'] for row in rows if row['created_by']]
    user_map = get_nicknames(user_ids) if user_ids else {}

    for row in rows:
        versions.append({
            'id': row['id'],
            'change_summary': row['change_summary'] or '（无改动说明）',
            'created_at': row['created_at'],
            'created_by': row['created_by'],
            'creator_name': user_map.get(row['created_by'], '未知用户')
        })

    return render_template(
        'resource/diff/diff_versions.html',
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        versions=versions
    )