# utils/remote_upload.py
"""
远程图片上传工具
将图片数据上传到 img.mcresource.cn 服务
"""

import os
import base64
import logging
import requests
from typing import Optional, Union

logger = logging.getLogger(__name__)

# 从环境变量读取配置
IMAGE_SERVICE_URL = os.getenv('IMAGE_SERVICE_URL', 'https://img.mcresource.cn')
UPLOAD_API_KEY = os.getenv('UPLOAD_API_KEY')

# ===== 目标目录映射（仅用于校验） =====
ALLOWED_TARGETS = {'detail', 'avatar', 'auth', 'rppw', 'gallery'}


def upload_image_to_remote(
    image_data: Union[bytes, str],
    target: str = 'detail',
    filename: Optional[str] = None,
    as_data_uri: bool = False,
    use_custom_name: bool = False,
    generate_thumbnail: bool = True
) -> str:
    """
    上传图片到远程图片服务

    :param image_data: 图片数据，可以是 bytes 或 data URI 字符串
    :param target: 目标目录，可选 'detail', 'avatar', 'auth', 'rppw', 'gallery'
    :param filename: 文件名（仅 multipart 时有效）
    :param as_data_uri: 若 True，则 image_data 为 data URI 字符串
    :param use_custom_name: 是否使用自定义文件名（若 True，则使用 filename）
    :param generate_thumbnail: 是否生成缩略图
    :return: 上传后的图片 URL（完整路径）
    :raises RuntimeError: 上传失败时抛出
    """
    if not UPLOAD_API_KEY:
        raise RuntimeError("UPLOAD_API_KEY 环境变量未设置，请配置")

    if target not in ALLOWED_TARGETS:
        raise ValueError(f"无效的 target: {target}，可选: {list(ALLOWED_TARGETS)}")

    # 构建请求
    upload_url = f"{IMAGE_SERVICE_URL}/upload"
    headers = {'X-API-Key': UPLOAD_API_KEY}

    # 准备数据
    if as_data_uri:
        if not isinstance(image_data, str):
            raise ValueError("as_data_uri=True 时 image_data 必须为字符串")
        payload = {
            'target': target,
            'image': image_data,
            'use_custom_name': use_custom_name,
            'generate_thumbnail': generate_thumbnail,
            'custom_filename': filename or '',
        }
        try:
            resp = requests.post(upload_url, json=payload, headers=headers, timeout=30)
        except requests.RequestException as e:
            logger.error(f"远程上传请求失败: {e}")
            raise RuntimeError(f"上传请求失败: {e}")
    else:
        if not isinstance(image_data, bytes):
            raise ValueError("as_data_uri=False 时 image_data 必须为 bytes")
        if filename is None:
            filename = 'image.jpg'
        files = {'file': (filename, image_data)}
        data = {
            'target': target,
            'use_custom_name': 'true' if use_custom_name else 'false',
            'generate_thumbnail': 'true' if generate_thumbnail else 'false',
            'custom_filename': filename,
        }
        try:
            resp = requests.post(upload_url, data=data, files=files, headers=headers, timeout=30)
        except requests.RequestException as e:
            logger.error(f"远程上传请求失败: {e}")
            raise RuntimeError(f"上传请求失败: {e}")

    # 检查响应
    if resp.status_code != 200:
        error_msg = resp.text or "未知错误"
        logger.error(f"远程上传失败 (HTTP {resp.status_code}): {error_msg}")
        raise RuntimeError(f"上传失败: {error_msg}")

    try:
        result = resp.json()
    except ValueError:
        logger.error(f"远程响应无效 JSON: {resp.text}")
        raise RuntimeError("远程服务响应格式错误")

    url = result.get('url')
    if not url:
        logger.error(f"响应中缺少 url 字段: {result}")
        raise RuntimeError("远程服务未返回图片 URL")

    if url.startswith('/'):
        url = IMAGE_SERVICE_URL + url

    return url


def get_thumbnail_url(original_url: str) -> str:
    """
    根据原图 URL 获取缩略图 URL
    """
    if not original_url:
        return ''
    base, _ = os.path.splitext(original_url)
    return f"{base}_thumb.jpg"