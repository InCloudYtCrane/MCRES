# utils/image_store.py
import os
import base64
import hashlib
import io
import logging
from urllib.parse import unquote
from PIL import Image
from typing import Optional

from utils.imaging.remote_upload import upload_image_to_remote

logger = logging.getLogger(__name__)

USE_REMOTE = os.getenv('USE_REMOTE_IMAGE_SERVICE', 'True').lower() == 'true'
LOCAL_IMAGE_DIR = os.path.join(os.getcwd(), 'mcres', 'static', 'images')


# ============================================================
# 上传类型白名单（安全批次 A3：存储型 XSS 修复）
# ============================================================
# 原先接受 `image/svg+xml` 并原样落地（本地写 .svg；开了图床就整条 data URI
# 转给 img.mcresource.cn）。SVG 是**可执行文档**：可以内嵌 <script>、
# <foreignObject>、外链资源，浏览器按 image/svg+xml 打开就会执行脚本。
# 站点用二级域名且 Cookie 作用域是 .mcresource.cn，因此在图片域上执行脚本
# 足以读到主站会话 —— 这是存储型 XSS，不只是"图片格式问题"。
#
# 处理方式：白名单只留**位图**（raster）格式，SVG/XML 一律拒收。
ALLOWED_IMAGE_MIME = frozenset({
    'image/png', 'image/jpeg', 'image/jpg', 'image/gif',
    'image/webp', 'image/bmp', 'image/x-icon', 'image/vnd.microsoft.icon',
})

ALLOWED_IMAGE_EXT = frozenset({
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico',
})

#: 内容嗅探特征：像标记语言的一律拒收，防"改个 MIME 混进来"
_MARKUP_SIGNATURES = (b'<svg', b'<?xml', b'<!doctype', b'<html', b'<script', b'<xhtml')


def data_uri_mime(data_uri):
    """取 data URI 的 MIME：`data:image/png;base64,...` → `image/png`。"""
    if not isinstance(data_uri, str) or not data_uri.startswith('data:'):
        return ''
    header = data_uri[5:].split(',', 1)[0]
    return header.split(';', 1)[0].strip().lower()


def looks_like_markup(data):
    """内容开头是否像 SVG / HTML / XML。

    只看头部 1KB，够用且开销可忽略。拿不准时返回 False（不误伤正常图片）。
    """
    if not data:
        return False
    try:
        head = data.encode('utf-8', 'ignore') if isinstance(data, str) else bytes(data[:1024])
    except (TypeError, ValueError):
        return False
    probe = head.lstrip(b'\xef\xbb\xbf \t\r\n').lower()
    return any(probe.startswith(sig) for sig in _MARKUP_SIGNATURES)


def _sniff_data_uri(data_uri):
    """对 data URI 的**内容头部**做一次标记语言嗅探。"""
    if ',' not in data_uri:
        return False
    header, payload = data_uri.split(',', 1)
    if 'base64' in header.lower():
        chunk = payload[:2048]
        chunk += '=' * (-len(chunk) % 4)   # 截断处的补齐，避免解码报错
        try:
            raw = base64.b64decode(chunk, validate=False)
        except Exception:
            return False
    else:
        raw = unquote(payload[:2048]).encode('utf-8', 'ignore')
    return looks_like_markup(raw)


def is_allowed_image_mime(mime_type):
    """MIME 是否在可接受白名单里（SVG 与任何 `+xml` 都不在）。"""
    return (mime_type or '').strip().lower() in ALLOWED_IMAGE_MIME


def is_allowed_image_name(filename):
    """扩展名是否在可接受白名单里。"""
    return os.path.splitext(filename or '')[1].lower() in ALLOWED_IMAGE_EXT


def save_data_uri_image(data_uri: str, target: str = 'detail', use_custom_name: bool = False, generate_thumbnail: bool = True) -> str:
    """
    保存 Data URI 图片（用于封面、截图、预设截图等）

    只接受白名单里的位图格式（不含 SVG，见 `ALLOWED_IMAGE_MIME`）。
    类型不合法时记 warning 并返回 `''`，与"没有图片"的既有约定一致 ——
    不抛异常，免得把调用方的整个表单请求打成 500。
    """
    if not data_uri or not data_uri.startswith('data:image/'):
        return ''

    mime = data_uri_mime(data_uri)
    if not is_allowed_image_mime(mime):
        logger.warning(f"拒绝上传的图片类型: {mime!r}（只接受位图，SVG/XML 不允许）")
        return ''
    if _sniff_data_uri(data_uri):
        logger.warning(f"拒绝伪装成图片的标记内容: mime={mime!r}")
        return ''

    if USE_REMOTE:
        try:
            return upload_image_to_remote(
                data_uri,
                target=target,
                as_data_uri=True,
                use_custom_name=use_custom_name,
                generate_thumbnail=generate_thumbnail
            )
        except Exception as e:
            logger.error(f"远程上传失败，降级到本地: {e}")
            return _save_data_uri_local(data_uri)

    return _save_data_uri_local(data_uri)


def save_image_file(
    file_data: bytes,
    filename: str,
    target: str = 'detail',
    use_custom_name: bool = False,
    generate_thumbnail: bool = True
) -> str:
    """
    直接保存文件流到远程或本地

    只接受白名单扩展名的位图（不含 .svg，见 `ALLOWED_IMAGE_EXT`），
    并做一次内容嗅探。不合法时记 warning 并返回 `''`。
    """
    if not file_data:
        return ''

    if not is_allowed_image_name(filename) or looks_like_markup(file_data):
        logger.warning(f"拒绝上传的图片文件: {filename!r}（只接受位图，SVG/XML 不允许）")
        return ''

    if USE_REMOTE:
        try:
            return upload_image_to_remote(
                file_data,
                target=target,
                filename=filename,
                as_data_uri=False,
                use_custom_name=use_custom_name,
                generate_thumbnail=generate_thumbnail
            )
        except Exception as e:
            logger.error(f"远程上传失败，降级到本地: {e}")
            return _save_file_local(file_data, filename)

    return _save_file_local(file_data, filename)


def _save_data_uri_local(data_uri: str) -> str:
    """本地保存 Data URI（原逻辑）"""
    if ',' not in data_uri:
        raise ValueError("无效的 Data URI 格式")

    header, encoded_data = data_uri.split(',', 1)
    header = header[5:]
    parts = header.split(';')
    mime_type = parts[0]
    is_base64 = 'base64' in parts

    if is_base64:
        raw_data = base64.b64decode(encoded_data, validate=False)
    else:
        raw_data = unquote(encoded_data).encode('utf-8')

    ext_map = {
        'image/png': '.png',
        'image/jpeg': '.jpg',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'image/bmp': '.bmp',
        'image/x-icon': '.ico',
        # 刻意不再接受 'image/svg+xml' —— SVG 是可执行文档，见文件顶部 A3 说明
    }
    extension = ext_map.get(mime_type, '.bin')

    file_hash = hashlib.sha256(raw_data).hexdigest()
    filename = f"{file_hash}{extension}"

    os.makedirs(LOCAL_IMAGE_DIR, exist_ok=True)
    file_path = os.path.join(LOCAL_IMAGE_DIR, filename)
    with open(file_path, 'wb') as f:
        f.write(raw_data)

    try:
        img = Image.open(io.BytesIO(raw_data))
        img.thumbnail((400, 400))
        thumb_filename = f"{file_hash}_thumb.jpg"
        thumb_path = os.path.join(LOCAL_IMAGE_DIR, thumb_filename)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        img.save(thumb_path, 'JPEG', quality=85, optimize=True)
    except Exception as e:
        logger.warning(f"缩略图生成失败: {e}")

    return "/images/" + filename


def _save_file_local(file_data: bytes, filename: str) -> str:
    """本地保存文件流"""
    file_hash = hashlib.sha256(file_data).hexdigest()
    ext = os.path.splitext(filename)[1].lower()
    if not ext or ext not in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
        ext = '.jpg'
    save_filename = f"{file_hash}{ext}"

    os.makedirs(LOCAL_IMAGE_DIR, exist_ok=True)
    file_path = os.path.join(LOCAL_IMAGE_DIR, save_filename)
    with open(file_path, 'wb') as f:
        f.write(file_data)

    try:
        img = Image.open(io.BytesIO(file_data))
        img.thumbnail((400, 400))
        thumb_filename = f"{file_hash}_thumb.jpg"
        thumb_path = os.path.join(LOCAL_IMAGE_DIR, thumb_filename)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        img.save(thumb_path, 'JPEG', quality=85, optimize=True)
    except Exception as e:
        logger.warning(f"缩略图生成失败: {e}")

    return f"/images/{save_filename}"


def get_thumbnail_url(original_url: str) -> str:
    if not original_url:
        return ''
    base, ext = os.path.splitext(original_url)
    return f"{base}_thumb.jpg"


def is_remote_enabled() -> bool:
    return USE_REMOTE