# views/file.py
import os
import json
import hashlib
import zlib
import time
import hmac
import base64
import re
from datetime import datetime
from flask import Blueprint, send_from_directory, abort, jsonify, request, send_file, session, render_template, redirect
from utils.time import datetime_fmt
from utils.users import permissions
from utils.db import execute_update, fetch_one, execute_query
from utils.constants import RESOURCE_TABLE, RESOURCE_TYPES

# 蓝图定义
im = Blueprint('file', __name__)

# 允许的类型及表名映射（定义已收敛到 utils/constants.py，这里只做别名引用）
ALLOWED_TYPES = RESOURCE_TYPES
TYPE_TO_TABLE = RESOURCE_TABLE
STORAGE_ROOT = os.path.join(os.getcwd(), 'mcres', 'storage')
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# ========== 下载 Token 配置 ==========
DOWNLOAD_SECRET = os.environ.get('DOWNLOAD_SECRET', 'CHANGE_ME_DOWNLOAD_SECRET')
TOKEN_EXPIRE_SECONDS = 300  # 5分钟

# ========== 文件 API 认证配置（供 admin 域调用） ==========
FILE_API_KEY = os.environ.get('FILE_API_KEY', 'CHANGE_ME_FILE_API_KEY')

# ========== 背景图 type 白名单 ==========
# 只有这些 type 才会走 background/<type>/ 子目录，其余（含未知、空、乱填）走根目录
BG_TYPES_WITH_SUBDIR = {'sel', 'tea'}
_BG_TYPE_RE = re.compile(r'^[a-z0-9_-]{1,32}$')


# ========== 认证辅助函数 ==========
def _is_api_call():
    """判断是否为 admin 域的 API 调用（通过 X-API-Key 头）"""
    api_key = request.headers.get('X-API-Key')
    return bool(api_key and api_key == FILE_API_KEY)


def _get_api_user_id():
    """从 API 头中获取用户 ID（用于记录日志/归属）"""
    uid = request.headers.get('X-User-Id')
    if uid:
        try:
            return int(uid)
        except (ValueError, TypeError):
            pass
    return None


# ========== Token 生成与验证 ==========
def generate_download_token(resource_type, resource_id, filename):
    expires = int(time.time()) + TOKEN_EXPIRE_SECONDS
    message = f"{resource_type}:{resource_id}:{filename}:{expires}"
    signature = hmac.new(DOWNLOAD_SECRET.encode(), message.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
    return f"{expires}.{sig_b64}"


def verify_download_token(resource_type, resource_id, filename, token):
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return False
        expires_str, sig_b64 = parts
        expires = int(expires_str)
        if expires < int(time.time()):
            return False
        message = f"{resource_type}:{resource_id}:{filename}:{expires}"
        expected = hmac.new(DOWNLOAD_SECRET.encode(), message.encode(), hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected).decode().rstrip('=')
        return sig_b64 == expected_b64
    except:
        return False


# ========== 辅助函数 ==========
def _safe_join(base_dir, filename):
    """
    安全拼接路径，防止目录穿越。
    """
    safe_name = os.path.basename(filename)
    full_path = os.path.join(base_dir, safe_name)
    real_base = os.path.realpath(base_dir)
    real_full = os.path.realpath(full_path)
    if not real_full.startswith(real_base + os.sep) or real_full == real_base:
        raise ValueError(f"Path traversal detected: {filename}")
    return full_path


def _get_file_obj(table_name, project_id):
    """从数据库读取 file 列，返回包含 auth_image 和 files 的字典，并补全缺失字段"""
    row = fetch_one(f"SELECT file FROM {table_name} WHERE id = %s", (project_id,))
    if row and row.get('file'):
        try:
            file_obj = json.loads(row['file'])
            if 'files' in file_obj and isinstance(file_obj['files'], list):
                for f in file_obj['files']:
                    if 'download_count' not in f:
                        f['download_count'] = 0
                    if 'checksums' not in f:
                        f['checksums'] = {}
            return file_obj
        except:
            pass
    return {"auth_image": None, "files": []}


def _update_file_obj(table_name, project_id, file_obj):
    """将 file_obj 序列化并更新数据库"""
    json_str = json.dumps(file_obj, ensure_ascii=False)
    execute_update(
        f"UPDATE {table_name} SET file = %s WHERE id = %s",
        (json_str, project_id)
    )


def _check_file_permission(user_id, category, project_id):
    """检查用户是否拥有该项目的文件管辖权 (file_area)"""
    user = fetch_one('SELECT file_area FROM user_info WHERE id = %s', (user_id,))
    if not user or not user.get('file_area'):
        return False
    try:
        file_area = json.loads(user['file_area'])
    except:
        return False
    if category not in file_area:
        return False
    cat_data = file_area[category]
    if cat_data.get('all') == True:
        return True
    if project_id in cat_data.get('detail', []):
        return True
    return False


def compute_file_checksums(file_path):
    """计算文件的 MD5, CRC32, SHA256"""
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    crc32 = 0
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5.update(chunk)
            sha256.update(chunk)
            crc32 = zlib.crc32(chunk, crc32)
    return {
        'md5': md5.hexdigest(),
        'sha256': sha256.hexdigest(),
        'crc32': f'{crc32 & 0xffffffff:08x}'
    }


# ========== 静态资源路由 ==========
@im.route('/images/<path:filename>')
def image(filename):
    if not (filename.endswith('.jpg') or filename.endswith('.png')):
        abort(404)
    folder = os.path.join(os.getcwd(), 'mcres', 'static', 'images')
    return send_from_directory(folder, filename)


# ================================================================
# 背景图路由 - 重定向到 img.mcresource.cn
# ================================================================
# 说明：
#   - 不带 type         → background/<时间>.jpg          （主站，保持原行为）
#   - ?type=sel         → background/sel/<时间>.jpg      （选料）
#   - ?type=tea         → background/tea/<时间>.jpg      （茶室）
#   - 其它未知 type     → 回退到根目录 background/<时间>.jpg
#   - type 必须满足 [a-z0-9_-]{1,32}，否则视为无 type
# ================================================================
@im.route('/background')
def background():
    """根据当前时间段返回对应的背景图，重定向到 img 域。"""
    now = datetime.now()
    hour = now.hour

    if 9 <= hour <= 12:
        filename = '9~12.jpg'
    elif 13 <= hour <= 16:
        filename = '13~16.jpg'
    elif 17 <= hour <= 20:
        filename = '17~20.jpg'
    elif hour >= 21 or hour == 0:
        filename = '21~24.jpg'
    elif 1 <= hour <= 4:
        filename = '1~4.jpg'
    elif 5 <= hour <= 8:
        filename = '5~8.jpg'
    else:
        filename = '9~12.jpg'

    # ---------- 解析 type 参数 ----------
    bg_type = (request.args.get('type') or '').strip().lower()

    if bg_type and _BG_TYPE_RE.match(bg_type) and bg_type in BG_TYPES_WITH_SUBDIR:
        path = f"background/{bg_type}/{filename}"
    else:
        path = f"background/{filename}"

    # ---------- 组装重定向 URL ----------
    image_base_url = os.getenv('IMAGE_BASE_URL', 'https://img.mcresource.cn').rstrip('/')
    redirect_url = f"{image_base_url}/{path}"
    return redirect(redirect_url, code=302)


# ================================================================
# 文件上传（支持 session 和 API key 双认证）
# ================================================================
@im.route('/file/upload/<type>/<int:id>/<filename>', methods=['POST'])
def upload_file(type, id, filename):
    """上传文件。支持：
    - 普通用户 session 认证（走文件管辖权检查）
    - admin 域 API key 认证（通过 X-API-Key 头，信任 admin 域的权限检查）
    """
    # 安全处理：净化文件名，防止目录穿越
    filename = os.path.basename(filename)

    if type not in ALLOWED_TYPES:
        abort(400, description=f"Invalid type. Allowed: {', '.join(ALLOWED_TYPES)}")

    table_name = TYPE_TO_TABLE.get(type)
    if not table_name:
        abort(400, description="Unknown type")

    # 检查项目是否存在
    project = fetch_one(f"SELECT id FROM {table_name} WHERE id = %s", (id,))
    if not project:
        abort(404, description=f"Project with id {id} not found")

    # ================================================================
    # 认证：优先 API key（admin 域转发），否则走 session
    # ================================================================
    if _is_api_call():
        # admin 域已做权限检查，主站信任
        user_id = _get_api_user_id()
        if not user_id:
            abort(400, description="Missing X-User-Id header")
    else:
        # 普通用户 session 认证
        user_id = session.get('user_info', {}).get('id')
        if not user_id:
            abort(401, description="请先登录")
        if not _check_file_permission(user_id, type, id):
            abort(403, description="您没有权限管理此项目的文件")

    # ================================================================
    # 以下为共用逻辑
    # ================================================================
    if 'file' not in request.files:
        abort(400, description="No file part")
    file_obj = request.files['file']
    if file_obj.filename == '':
        abort(400, description="No selected file")

    if not filename.endswith('.zip'):
        abort(400, description="Filename must end with .zip")

    # 构建存储路径
    target_dir = os.path.join(STORAGE_ROOT, type, str(id))
    os.makedirs(target_dir, exist_ok=True)
    try:
        save_path = _safe_join(target_dir, filename)
    except ValueError as e:
        abort(400, description=str(e))

    # 若文件已存在，拒绝覆盖
    if os.path.exists(save_path):
        abort(409, description="File already exists. Please use a different filename.")

    # 保存文件并检查大小
    file_obj.save(save_path)
    file_size = os.path.getsize(save_path)
    if file_size > MAX_FILE_SIZE:
        os.remove(save_path)
        abort(413, description=f"File size exceeds limit of {MAX_FILE_SIZE // (1024*1024)}MB")

    # 获取版本信息
    version = request.form.get('version', '1.0').strip()
    game_version = request.form.get('game_version', '1.20').strip()
    original_name = file_obj.filename
    download_url = f"/file/download/{type}/{id}/{filename}"
    upload_time = datetime_fmt.now()
    uploader_uid = user_id

    # 构建新文件条目
    new_entry = {
        "filename": filename,
        "original_name": original_name,
        "version": version,
        "game_version": game_version,
        "size": file_size,
        "upload_time": upload_time,
        "url": download_url,
        "uploader_uid": uploader_uid,
        "download_count": 0,
        "checksums": {}
    }

    # 读取现有 file 对象，追加新文件
    file_data = _get_file_obj(table_name, id)
    if 'files' not in file_data or not isinstance(file_data['files'], list):
        file_data['files'] = []

    # 计算 order（取现有最大值 +1）
    max_order = max([f.get('order', 0) for f in file_data['files']], default=-1) + 1
    new_entry['order'] = max_order

    file_data['files'].append(new_entry)

    # 写回数据库
    _update_file_obj(table_name, id, file_data)

    return jsonify({
        "status": "success",
        "message": "File uploaded successfully",
        "filename": filename,
        "original_name": original_name,
        "version": version,
        "game_version": game_version,
        "size": file_size,
        "upload_time": upload_time,
        "url": download_url
    }), 201


# ================================================================
# 文件下载（需 Token 验证，防盗链）
# ================================================================
@im.route('/file/download/<type>/<int:id>/<filename>', methods=['GET'])
def download_file(type, id, filename):
    filename = os.path.basename(filename)

    if type not in ALLOWED_TYPES:
        abort(404)
    token = request.args.get('token')
    if not token:
        abort(403, description="Missing download token")
    if not verify_download_token(type, id, filename, token):
        abort(403, description="Invalid or expired download token")

    target_dir = os.path.join(STORAGE_ROOT, type, str(id))
    try:
        file_path = _safe_join(target_dir, filename)
    except ValueError as e:
        abort(400, description=str(e))

    if not os.path.exists(file_path):
        abort(404)

    table_name = TYPE_TO_TABLE.get(type)
    file_obj = _get_file_obj(table_name, id)
    files = file_obj.get('files', [])
    original_name = filename
    for f in files:
        if f.get('filename') == filename:
            original_name = f.get('original_name', filename)
            break

    if not original_name.lower().endswith('.zip'):
        original_name += '.zip'

    return send_file(file_path, as_attachment=True, download_name=original_name)


# ================================================================
# 编辑文件版本信息（支持 session 和 API key）
# ================================================================
@im.route('/file/edit/<type>/<int:id>/<filename>', methods=['PUT'])
def edit_file(type, id, filename):
    filename = os.path.basename(filename)

    if type not in ALLOWED_TYPES:
        abort(400)
    table_name = TYPE_TO_TABLE.get(type)
    if not table_name:
        abort(400)

    # ===== 认证 =====
    if _is_api_call():
        user_id = _get_api_user_id()
    else:
        user_id = session.get('user_info', {}).get('id')
        if not user_id:
            abort(401, description="请先登录")
        if not _check_file_permission(user_id, type, id):
            abort(403, description="您没有权限管理此项目的文件")

    data = request.get_json()
    if not data:
        abort(400, description="Missing JSON body")

    new_version = data.get('version')
    new_game_version = data.get('game_version')
    if new_version is None and new_game_version is None:
        abort(400, description="At least one field (version or game_version) must be provided")

    file_data = _get_file_obj(table_name, id)
    files = file_data.get('files', [])

    found = False
    for entry in files:
        if entry.get('filename') == filename:
            if new_version is not None:
                entry['version'] = new_version.strip()
            if new_game_version is not None:
                entry['game_version'] = new_game_version.strip()
            found = True
            break

    if not found:
        abort(404, description="File not found")

    _update_file_obj(table_name, id, file_data)
    return jsonify({"success": True, "message": "File updated"})


# ================================================================
# 重命名文件（修改显示名称，支持 session 和 API key）
# ================================================================
@im.route('/file/rename/<type>/<int:id>/<filename>', methods=['PUT'])
def rename_file(type, id, filename):
    filename = os.path.basename(filename)

    if type not in ALLOWED_TYPES:
        abort(400)
    table_name = TYPE_TO_TABLE.get(type)
    if not table_name:
        abort(400)

    # ===== 认证 =====
    if _is_api_call():
        user_id = _get_api_user_id()
    else:
        user_id = session.get('user_info', {}).get('id')
        if not user_id:
            abort(401, description="请先登录")
        if not _check_file_permission(user_id, type, id):
            abort(403, description="您没有权限管理此项目的文件")

    data = request.get_json()
    if not data or 'new_name' not in data:
        abort(400, description="Missing 'new_name' in JSON body")

    new_original_name = data['new_name'].strip()
    if not new_original_name:
        abort(400, description="New name cannot be empty")

    file_data = _get_file_obj(table_name, id)
    files = file_data.get('files', [])

    found = False
    for entry in files:
        if entry.get('filename') == filename:
            entry['original_name'] = new_original_name
            found = True
            break

    if not found:
        abort(404, description="File not found")

    _update_file_obj(table_name, id, file_data)
    return jsonify({"success": True, "message": "File renamed"})


# ================================================================
# 删除文件（支持 session 和 API key）
# ================================================================
@im.route('/file/delete/<type>/<int:id>/<filename>', methods=['DELETE'])
def delete_file(type, id, filename):
    filename = os.path.basename(filename)

    if type not in ALLOWED_TYPES:
        abort(400)
    table_name = TYPE_TO_TABLE.get(type)
    if not table_name:
        abort(400)

    # ===== 认证 =====
    if _is_api_call():
        user_id = _get_api_user_id()
    else:
        user_id = session.get('user_info', {}).get('id')
        if not user_id:
            abort(401, description="请先登录")
        if not _check_file_permission(user_id, type, id):
            abort(403, description="您没有权限管理此项目的文件")

    file_data = _get_file_obj(table_name, id)
    files = file_data.get('files', [])

    found = False
    new_files = []
    for entry in files:
        if entry.get('filename') == filename:
            found = True
            target_dir = os.path.join(STORAGE_ROOT, type, str(id))
            try:
                file_path = _safe_join(target_dir, filename)
            except ValueError as e:
                abort(400, description=str(e))
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
        else:
            new_files.append(entry)

    if not found:
        abort(404, description="File not found")

    file_data['files'] = new_files
    _update_file_obj(table_name, id, file_data)
    return jsonify({"success": True, "message": "File deleted"})


# ================================================================
# 区域清除授权（供区域文件管理使用）
# ================================================================
@im.route('/file/clear_auth/<type>/<int:id>', methods=['POST'])
@permissions.login_required()
def clear_auth(type, id):
    if type not in ALLOWED_TYPES:
        abort(400)
    table_name = TYPE_TO_TABLE.get(type)
    if not table_name:
        abort(400)

    user_id = session.get('user_info', {}).get('id')
    if not user_id:
        abort(401, description="请先登录")
    if not _check_file_permission(user_id, type, id):
        abort(403, description="您没有权限管理此项目的文件")

    file_data = _get_file_obj(table_name, id)
    if file_data.get('auth_image'):
        file_data['auth_image'] = None
        _update_file_obj(table_name, id, file_data)
        return jsonify({"success": True, "message": "Auth image cleared"})
    else:
        return jsonify({"success": False, "message": "No auth image to clear"}), 400


# ================================================================
# 下载页面（展示文件列表和授权）
# ================================================================
@im.route('/download/<string:type>/<int:id>')
def download_page(type, id):
    if type not in ALLOWED_TYPES:
        abort(404)
    table_name = TYPE_TO_TABLE.get(type)
    if not table_name:
        abort(404)
    row = fetch_one(f'SELECT content, file FROM {table_name} WHERE id = %s', (id,))
    if not row:
        abort(404)
    try:
        content = json.loads(row['content'])
    except:
        content = {}
    file_obj = _get_file_obj(table_name, id)
    files = file_obj.get('files', [])

    # 按 order 降序排序
    for f in files:
        if 'order' not in f:
            f['order'] = 0
    files.sort(key=lambda f: f.get('order', 0), reverse=True)

    for f in files:
        if 'size' in f:
            size = f['size']
            if size < 1024:
                f['size_display'] = f'{size} B'
            elif size < 1024*1024:
                f['size_display'] = f'{size/1024:.1f} KB'
            else:
                f['size_display'] = f'{size/(1024*1024):.1f} MB'
        else:
            f['size_display'] = '未知'
        if 'upload_time' in f:
            f['upload_time_display'] = f['upload_time']
        else:
            f['upload_time_display'] = '未知'
    auth_image = file_obj.get('auth_image')
    name = content.get('main_name', f'未命名#{id}')
    authors = content.get('authors', [])

    # 游客限免
    from datetime import datetime
    user_id = session.get('user_info', {}).get('id')
    is_logged_in = bool(user_id)
    guest_remaining = None
    if not is_logged_in:
        today = datetime.now().date().isoformat()
        guest_data = session.get('guest_downloads', {})
        if guest_data.get('date') != today:
            guest_remaining = 2
        else:
            guest_remaining = max(0, 2 - guest_data.get('count', 0))

    return render_template(
        'download_page.html',
        resource_type=type,
        resource_id=id,
        resource_name=name,
        authors=authors,
        auth_image=auth_image,
        files=files,
        is_logged_in=is_logged_in,
        guest_remaining=guest_remaining
    )


# ================================================================
# 获取文件校验和（MD5, CRC32, SHA256）
# ================================================================
@im.route('/download/<string:type>/<int:id>/<filename>/checksum')
def get_checksum(type, id, filename):
    filename = os.path.basename(filename)

    if type not in ALLOWED_TYPES:
        abort(400)
    table_name = TYPE_TO_TABLE.get(type)
    if not table_name:
        abort(400)
    project = fetch_one(f'SELECT id FROM {table_name} WHERE id = %s', (id,))
    if not project:
        abort(404)
    file_obj = _get_file_obj(table_name, id)
    files = file_obj.get('files', [])
    target = None
    for f in files:
        if f.get('filename') == filename:
            target = f
            break
    if not target:
        abort(404)
    if target.get('checksums') and target['checksums'].get('md5'):
        return jsonify({'success': True, 'checksums': target['checksums']})
    target_dir = os.path.join(STORAGE_ROOT, type, str(id))
    try:
        file_path = _safe_join(target_dir, filename)
    except ValueError as e:
        abort(400, description=str(e))
    if not os.path.exists(file_path):
        abort(404)
    checksums = compute_file_checksums(file_path)
    target['checksums'] = checksums
    _update_file_obj(table_name, id, file_obj)
    return jsonify({'success': True, 'checksums': checksums})


# ================================================================
# 请求下载（验证验证码，增加下载计数，返回带 Token 的下载链接）
# ================================================================
@im.route('/download/<string:type>/<int:id>/<filename>/request_download', methods=['POST'])
def request_download(type, id, filename):
    filename = os.path.basename(filename)

    if type not in ALLOWED_TYPES:
        abort(400)
    table_name = TYPE_TO_TABLE.get(type)
    if not table_name:
        abort(400)
    project = fetch_one(f'SELECT id FROM {table_name} WHERE id = %s', (id,))
    if not project:
        abort(404)

    # 获取表单数据
    user_captcha = request.form.get('captcha', '').strip().upper()
    session_captcha = session.get('captcha', '').upper()
    if not user_captcha or user_captcha != session_captcha:
        return jsonify({'success': False, 'message': '验证码错误'}), 400
    session.pop('captcha', None)

    # ========== 游客限流检查 ==========
    user_id = session.get('user_info', {}).get('id')

    if not user_id:
        from datetime import datetime
        today = datetime.now().date().isoformat()
        guest_data = session.get('guest_downloads', {})

        if guest_data.get('date') != today:
            guest_data = {'date': today, 'count': 0}

        if guest_data.get('count', 0) >= 2:
            return jsonify({
                'success': False,
                'message': '今日下载次数已用完，注册后不限次免费下载',
                'code': 'GUEST_LIMIT_REACHED'
            }), 403

        guest_data['count'] = guest_data.get('count', 0) + 1
        session['guest_downloads'] = guest_data

    # 增加下载计数
    file_obj = _get_file_obj(table_name, id)
    files = file_obj.get('files', [])
    target = None
    for f in files:
        if f.get('filename') == filename:
            target = f
            break
    if not target:
        abort(404)
    target['download_count'] = target.get('download_count', 0) + 1
    _update_file_obj(table_name, id, file_obj)

    # 生成下载 token
    token = generate_download_token(type, id, filename)
    download_url = f"/file/download/{type}/{id}/{filename}?token={token}"
    return jsonify({'success': True, 'url': download_url})