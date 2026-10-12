# mcres/views/api.py
import json
import os

from flask import Blueprint, request, jsonify, current_app

from utils.data.repositories.resources import (
    API_LOOKUP_TABLES,
    find_ids_by_content_field,
    find_ids_by_mcmod_id,
    get_content,
)
from utils.data.repositories.reviews import (
    insert_new_review,
    last_inserted_id,
)
from utils.data.repositories.site import list_active_rules
from utils.data.repositories.users import find_id_and_pwd_by_email
from utils.imaging import image_store
from utils.site import site_data
from utils.time import datetime_fmt
from utils.constants import RESOURCE_TABLE, is_valid_resource_type
from utils.text.sanitize import sanitize_html
from werkzeug.security import check_password_hash
from .. import log_action

api_bp = Blueprint('api', __name__, url_prefix='/api')

BASE_URL = 'https://www.mcresource.cn'

# ========== 机器人接口密钥（安全批次 A2） ==========
# 原先硬编码在源码里，任何拿到仓库的人都能直接调用这些接口。
# 现在统一从环境变量读（`mcres/config.py` 的 `load_dotenv()` 会加载站点根目录的
# `.env`），**保留原值作为兜底**，这样部署方还没配 `.env` 时站点行为不变。
# 上线步骤（需要你配合）：
#   1. 云端 `.env` 增加 MCMOD_KEY / BHL_KEY / IMPORT_API_KEY 三行（用新随机值）
#   2. 重启服务
#   3. 通知调用方（mcmod 机器人 / bhl 机器人 / admin 导入脚本）同步换 key
#   4. 确认无调用后，再删掉这里的兜底默认值
MCMOD_KEY = os.environ.get('MCMOD_KEY', 'CHANGE_ME_MCMOD_KEY')
BHL_KEY = os.environ.get('BHL_KEY', 'CHANGE_ME_BHL_KEY')
IMPORT_API_KEY = os.environ.get('IMPORT_API_KEY', 'CHANGE_ME_IMPORT_API_KEY')


# ========== 原有路由（未改动） ==========
@api_bp.route('/mcmod/<string:resource_type>/<int:resource_id>')
def get_mcmod_id(resource_type, resource_id):
    """正向查询：输入 MCRES 类型+ID，返回 mcmod_id"""
    key = request.args.get('key')
    if key != MCMOD_KEY:
        return jsonify({'code': 401, 'message': 'Invalid or missing key'}), 401

    table = RESOURCE_TABLE.get(resource_type)
    if not table:
        return jsonify({'code': 400, 'message': 'Invalid resource type'}), 400

    row = get_content(resource_type, resource_id)
    if not row:
        return jsonify({'code': 404, 'message': f'{resource_type} with id {resource_id} not found'}), 404

    try:
        content = json.loads(row['content'])
    except:
        return jsonify({'code': 500, 'message': 'Invalid JSON content'}), 500

    mcmod_id = content.get('mcmod_id')
    if not mcmod_id:
        return jsonify({'code': 404, 'message': f'{resource_type} {resource_id} has no associated mcmod_id'}), 404

    return jsonify({'code': 0, 'mcmod_id': mcmod_id})


@api_bp.route('/resource_by_mcmod/<string:mcmod_id>')
def get_resource_by_mcmod(mcmod_id):
    """反向查询：输入 mcmod_id，返回 MCRES 平台对应的所有资源列表"""
    key = request.args.get('key')
    if key != MCMOD_KEY:
        return jsonify({'code': 401, 'message': 'Invalid or missing key'}), 401


    result_list = []
    for table, type_name in API_LOOKUP_TABLES:
        rows = find_ids_by_mcmod_id(table, mcmod_id)
        for row in rows:
            result_list.append({
                'resource_type': type_name,
                'resource_id': row['id']
            })

    if not result_list:
        return jsonify({'code': 404, 'message': f'No resource found with mcmod_id {mcmod_id}'}), 404

    return jsonify({
        'code': 0,
        'resources': result_list
    })


def _make_absolute_urls(content):
    """将 content 中的封面和截图相对路径补全为绝对 URL"""
    if not content:
        return content
    cover = content.get('cover')
    if cover and isinstance(cover, str) and cover.startswith('/images/'):
        content['cover'] = BASE_URL + cover
    screenshots = content.get('screenshots')
    if screenshots and isinstance(screenshots, list):
        new_screenshots = []
        for s in screenshots:
            if s and isinstance(s, str) and s.startswith('/images/'):
                new_screenshots.append(BASE_URL + s)
            else:
                new_screenshots.append(s)
        content['screenshots'] = new_screenshots
    return content


@api_bp.route('/bhl/lookup', methods=['GET'])
def bhl_lookup():
    """反查：根据 provider + project_id 查询 MCRES 资源"""
    key = request.args.get('key')
    if key != BHL_KEY:
        return jsonify({'code': 401, 'message': 'Invalid or missing key'}), 401

    provider = request.args.get('provider', '').lower()
    project_id = request.args.get('project_id', '').strip()

    if provider not in ('curseforge', 'modrinth'):
        return jsonify({'code': 400, 'message': 'Invalid provider. Must be "curseforge" or "modrinth"'}), 400

    if not project_id:
        return jsonify({'code': 400, 'message': 'Missing project_id'}), 400

    field = 'curseforge_id' if provider == 'curseforge' else 'modrinth_id'

    result = []
    for table, type_name in API_LOOKUP_TABLES:
        rows = find_ids_by_content_field(table, field, project_id)
        for row in rows:
            result.append({
                'resource_type': type_name,
                'resource_id': row['id']
            })

    if not result:
        return jsonify({'code': 404, 'message': f'No resource found with {provider}_id = {project_id}'}), 404

    return jsonify({'code': 0, 'resources': result})


@api_bp.route('/bhl/detail/<string:resource_type>/<int:resource_id>', methods=['GET'])
def bhl_detail(resource_type, resource_id):
    """详情：根据 MCRES 资源类型和 ID 返回完整 content（封面和截图 URL 补全为绝对路径）"""
    key = request.args.get('key')
    if key != BHL_KEY:
        return jsonify({'code': 401, 'message': 'Invalid or missing key'}), 401

    table = RESOURCE_TABLE.get(resource_type)
    if not table:
        return jsonify({'code': 400, 'message': 'Invalid resource type'}), 400

    row = get_content(resource_type, resource_id)
    if not row:
        return jsonify({'code': 404, 'message': f'{resource_type} with id {resource_id} not found'}), 404

    try:
        content = json.loads(row['content'])
    except Exception:
        return jsonify({'code': 500, 'message': 'Invalid JSON content'}), 500

    content = _make_absolute_urls(content)
    detail_url = f"{BASE_URL}/{resource_type}/{resource_id}"

    return jsonify({
        'code': 0,
        'content': content,
        'url': detail_url
    })


@api_bp.route('/rules/list')
def get_rules_list():
    """获取所有活跃规则的简要列表（用于侧边栏加载）"""
    rows = list_active_rules()
    return jsonify({
        'success': True,
        'data': [{'rule_key': r['rule_key'], 'title': r['title']} for r in rows]
    })


# ===== 获取光影风格列表 =====
@api_bp.route('/shader/styles', methods=['GET'])
def get_shader_styles():
    """返回光影包风格列表（从 sts 配置读取）"""
    styles = site_data.edit()['shaderpack']['styles']
    return jsonify({'code': 0, 'styles': styles})


# ================================================================
# 改造点：光影包提交审核 API
# ================================================================
@api_bp.route('/shader/submit', methods=['POST'])
def submit_shaderpack_review():
    """
    接收机器人提交的光影包数据，插入审核表。
    请求体 JSON 需包含：
        key: 固定 API 密钥
        email: 提交者邮箱（用于登录验证）
        password: 提交者密码（明文）
        以及光影包所有字段（与网站新提交格式一致）

    图片处理：将 Base64 转为文件 URL（调用 image_store.save_data_uri_image）
    描述清洗：调用 sanitize_html 去除非法标签
    """
    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': '无效的 JSON 数据'}), 400

    # ---------- 身份验证 ----------
    api_key = data.get('key')
    if api_key != IMPORT_API_KEY:
        return jsonify({'code': 401, 'message': '无效的 API Key'}), 401

    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'code': 400, 'message': '缺少邮箱或密码'}), 400

    user_row = find_id_and_pwd_by_email(email)
    if not user_row or not check_password_hash(user_row['pwd'], password):
        return jsonify({'code': 403, 'message': '邮箱或密码错误'}), 403

    submitter_id = user_row['id']

    # ---------- 提取字段 ----------
    required_fields = ['main_name', 'summary', 'cover', 'screenshots', 'description',
                       'style', 'performance', 'platforms', 'versions', 'engines',
                       'features', 'authors', 'download_links', 'license', 'modrinth_id']
    for field in required_fields:
        if field not in data:
            return jsonify({'code': 400, 'message': f'缺少必填字段: {field}'}), 400

    # ================================================================
    # 改造点：图片处理 - 使用改造后的 sv_img，自动走远程上传
    # ================================================================
    # 原逻辑：image_store.save_data_uri_image(data['cover'])
    # 新逻辑：默认 target='detail'，上传到 img.mcresource.cn/resource/detail/
    cover_url = image_store.save_data_uri_image(data.get('cover'), target='detail') if data.get('cover') else ''
    screenshot_urls = []
    for img in data.get('screenshots', []):
        if img:
            url = image_store.save_data_uri_image(img, target='detail')
            if url:
                screenshot_urls.append(url)

    # ---------- 描述清洗 ----------
    safe_description = sanitize_html(data.get('description', ''))

    # ---------- 构建 content 字典 ----------
    content_dict = {
        'main_name': data['main_name'].strip(),
        'sub_name': data.get('sub_name', '').strip(),
        'abbr': data.get('abbr', '').strip(),
        'style': data['style'],
        'performance': data['performance'],
        'summary': data['summary'].strip(),
        'cover': cover_url,
        'screenshots': screenshot_urls,
        'description': safe_description,
        'platforms': data['platforms'],
        'versions': data['versions'],
        'engines': data['engines'],
        'features': data['features'],
        'authors': data['authors'],
        'status': data.get('status', 'active'),
        'download_links': data['download_links'],
        'keywords': data.get('keywords', ''),
        'license': data['license'],
        'mcmod_id': data.get('mcmod_id', ''),
        'curseforge_id': data.get('curseforge_id', ''),
        'modrinth_id': data['modrinth_id']
    }

    change_summary = data.get('change_summary', '从 Modrinth 自动导入')

    # ---------- 插入审核表 ----------
    content_json = json.dumps(content_dict, ensure_ascii=False)
    try:
        insert_new_review(
            'shaderpack_review', submitter_id, datetime_fmt.now(),
            content_json, change_summary
        )
        review_id = last_inserted_id('shaderpack_review')
    except Exception as e:
        current_app.logger.error(f"提交审核插入失败: {e}")
        return jsonify({'code': 500, 'message': f'数据库错误: {str(e)}'}), 500

    # ---------- 记录日志 ----------
    log_action(
        user_id=submitter_id,
        action='submit_shaderpack_review_api',
        level='INFO',
        target_type='shaderpack',
        request_data={
            'modrinth_id': data['modrinth_id'],
            'main_name': content_dict['main_name'],
            'review_id': review_id
        }
    )

    return jsonify({
        'code': 0,
        'message': '已提交审核',
        'review_id': review_id
    })


# ================================================================
# 改造点：资源包提交审核 API
# ================================================================
@api_bp.route('/resourcepack/submit', methods=['POST'])
def submit_resourcepack_review():
    """
    接收机器人提交的资源包数据，插入审核表。
    请求体 JSON 需包含：
        key: 固定 API 密钥
        email: 提交者邮箱（用于登录验证）
        password: 提交者密码（明文）
        以及资源包所有字段（与网站新提交格式一致）
    """
    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': '无效的 JSON 数据'}), 400

    # ---------- 身份验证 ----------
    api_key = data.get('key')
    if api_key != IMPORT_API_KEY:
        return jsonify({'code': 401, 'message': '无效的 API Key'}), 401

    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'code': 400, 'message': '缺少邮箱或密码'}), 400

    user_row = find_id_and_pwd_by_email(email)
    if not user_row or not check_password_hash(user_row['pwd'], password):
        return jsonify({'code': 403, 'message': '邮箱或密码错误'}), 403

    submitter_id = user_row['id']

    # ---------- 提取字段 ----------
    required_fields = ['main_name', 'summary', 'cover', 'screenshots', 'description',
                       'category', 'platforms', 'versions', 'features', 'authors',
                       'download_links', 'license', 'modrinth_id']
    for field in required_fields:
        if field not in data:
            return jsonify({'code': 400, 'message': f'缺少必填字段: {field}'}), 400

    # ================================================================
    # 改造点：图片处理 - 使用改造后的 sv_img，自动走远程上传
    # ================================================================
    cover_url = image_store.save_data_uri_image(data.get('cover'), target='detail') if data.get('cover') else ''
    screenshot_urls = []
    for img in data.get('screenshots', []):
        if img:
            url = image_store.save_data_uri_image(img, target='detail')
            if url:
                screenshot_urls.append(url)

    # ---------- 描述清洗 ----------
    safe_description = sanitize_html(data.get('description', ''))

    # ---------- 构建 content 字典 ----------
    content_dict = {
        'main_name': data['main_name'].strip(),
        'sub_name': data.get('sub_name', '').strip(),
        'abbr': data.get('abbr', '').strip(),
        'category': data['category'],
        'summary': data['summary'].strip(),
        'cover': cover_url,
        'screenshots': screenshot_urls,
        'description': safe_description,
        'platforms': data['platforms'],
        'versions': data['versions'],
        'features': data['features'],
        'authors': data['authors'],
        'status': data.get('status', 'active'),
        'download_links': data['download_links'],
        'keywords': data.get('keywords', ''),
        'license': data['license'],
        'mcmod_id': data.get('mcmod_id', ''),
        'curseforge_id': data.get('curseforge_id', ''),
        'modrinth_id': data['modrinth_id']
    }

    change_summary = data.get('change_summary', '从 Modrinth 自动导入')

    # ---------- 插入审核表（resourcepack_review） ----------
    content_json = json.dumps(content_dict, ensure_ascii=False)
    try:
        insert_new_review(
            'resourcepack_review', submitter_id, datetime_fmt.now(),
            content_json, change_summary
        )
        review_id = last_inserted_id('resourcepack_review')
    except Exception as e:
        current_app.logger.error(f"提交资源包审核插入失败: {e}")
        return jsonify({'code': 500, 'message': f'数据库错误: {str(e)}'}), 500

    # ---------- 记录日志 ----------
    log_action(
        user_id=submitter_id,
        action='submit_resourcepack_review_api',
        level='INFO',
        target_type='resourcepack',
        request_data={
            'modrinth_id': data['modrinth_id'],
            'main_name': content_dict['main_name'],
            'review_id': review_id
        }
    )

    return jsonify({
        'code': 0,
        'message': '已提交审核',
        'review_id': review_id
    })


# ================================================================
# 重复检测 API（未改动）
# ================================================================
@api_bp.route('/check_duplicate', methods=['GET'])
def check_duplicate():
    """
    检测资源是否重复
    参数：
        type: resourcepack | shaderpack | map
        field: main_name | curseforge_id | modrinth_id | mcmod_id
        value: 要检测的值
    返回：
        {
            "exists": true/false,
            "ids": [123, 456]  # 重复的资源 ID 列表
        }
    """
    resource_type = request.args.get('type')
    field = request.args.get('field')
    value = request.args.get('value', '').strip()

    # ===== 参数校验 =====
    if not resource_type or not field or not value:
        return jsonify({'exists': False, 'ids': [], 'error': '缺少必要参数'}), 400

    if not is_valid_resource_type(resource_type):
        return jsonify({'exists': False, 'ids': [], 'error': '无效的资源类型'}), 400

    valid_fields = {'main_name', 'curseforge_id', 'modrinth_id', 'mcmod_id'}
    if field not in valid_fields:
        return jsonify({'exists': False, 'ids': [], 'error': '无效的检测字段'}), 400

    # ===== 表名映射（来源：utils/constants.py）=====
    table = RESOURCE_TABLE[resource_type]

    # ===== 构建查询 =====
    rows = find_ids_by_content_field(
        table, field, value, case_insensitive=(field == 'main_name')
    )

    # ===== 提取 ID 列表 =====
    ids = [row['id'] for row in rows]

    return jsonify({
        'exists': len(ids) > 0,
        'ids': ids
    })