"""
用户头像生成工具
基于远程默认头像生成个性化头像：
1. 下载默认头像作为底图
2. 根据 user_id + nickname 算出 HSV 色值
3. 对底图做色相旋转 + 饱和度/亮度缩放
4. 上传到远程/本地并返回 URL
"""

import hashlib
import io
import logging
import time

import requests
from io import BytesIO
from PIL import Image, ImageOps

from utils.imaging.image_store import save_image_file

logger = logging.getLogger(__name__)

# ---------- 默认底图 ----------
DEFAULT_AVATAR_URL = "https://img.mcresource.cn/user/avatar/default.jpg"

# 进程级缓存，避免每次注册都重新下载
_default_avatar_cache = None


# ============================================================
# 色彩种子
# ============================================================
def get_user_color_seed(user_id, nickname):
    """
    根据用户 ID 和昵称生成稳定的色彩参数
    返回 (hue, saturation, lightness)
        hue: 0-360
        saturation: 0.3-0.9
        lightness: 0.5-0.9
    """
    seed_str = f"{user_id}-{nickname}"
    hash_obj = hashlib.md5(seed_str.encode())
    hash_hex = hash_obj.hexdigest()

    hue = int(hash_hex[:3], 16) % 360
    saturation_raw = int(hash_hex[3:5], 16) % 100
    saturation = 0.3 + (saturation_raw / 100) * 0.6
    lightness_raw = int(hash_hex[5:7], 16) % 100
    lightness = 0.5 + (lightness_raw / 100) * 0.4

    return hue, saturation, lightness


# ============================================================
# HSV 调色
# ============================================================
def apply_color_to_avatar(image, hue, saturation, lightness):
    """
    对图片应用色相/饱和度/亮度变换
    跳过近乎灰白/纯黑的像素，保留底图明暗结构
    """
    img_hsv = image.convert('HSV')
    pixels = img_hsv.load()
    width, height = img_hsv.size

    # PIL HSV 中 H 为 0-255，把 0-360 的 hue 映射过去
    hue_shift = int((hue / 360.0) * 255)

    for x in range(width):
        for y in range(height):
            h, s, v = pixels[x, y]

            # 跳过极低饱和（灰）、极暗（黑）、极亮（白）像素
            if s < 10 or v < 20 or v > 240:
                continue

            new_h = (h + hue_shift) % 256
            new_s = int(s * saturation)
            if new_s > 255:
                new_s = 255
            if new_s < 0:
                new_s = 0

            new_v = int(v * lightness)
            if new_v > 255:
                new_v = 255
            if new_v < 0:
                new_v = 0

            pixels[x, y] = (new_h, new_s, new_v)

    return img_hsv.convert('RGB')


# ============================================================
# 默认头像下载 & 缓存
# ============================================================
def _get_default_avatar(size=(200, 200)):
    """
    获取默认头像底图（RGB，size 大小）
    优先使用内存缓存；下载失败时降级为纯色画布
    """
    global _default_avatar_cache

    if _default_avatar_cache is None:
        try:
            resp = requests.get(DEFAULT_AVATAR_URL, timeout=10)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content)).convert('RGB')
            # 居中裁剪为正方形，避免拉伸变形
            img = ImageOps.fit(img, size, Image.LANCZOS)
            _default_avatar_cache = img
            logger.info(f"默认头像底图下载成功: {DEFAULT_AVATAR_URL}")
        except Exception as e:
            logger.error(f"下载默认头像失败，降级到纯色底图: {e}")
            _default_avatar_cache = Image.new('RGB', size, '#2a2f3a')

    # 返回副本，避免被调色函数原地修改污染缓存
    return _default_avatar_cache.copy()


# ============================================================
# 主函数：生成并保存头像
# ============================================================
def generate_and_save_avatar(user_id, nickname):
    """
    生成用户头像并上传到远程图片服务
    :param user_id: 用户 ID
    :param nickname: 用户昵称
    :return: 头像 URL
    """
    # ---------- 1. 获取底图 ----------
    base_img = _get_default_avatar((200, 200))

    # ---------- 2. 计算专属色值 ----------
    hue, saturation, lightness = get_user_color_seed(user_id, nickname)

    # ---------- 3. 对底图调色 ----------
    result_img = apply_color_to_avatar(base_img, hue, saturation, lightness)

    # ---------- 4. 编码为 JPEG ----------
    output = io.BytesIO()
    result_img.save(output, format='JPEG', quality=90, optimize=True)
    image_bytes = output.getvalue()

    # ---------- 5. 上传 ----------
    try:
        avatar_url = save_image_file(
            image_bytes,
            filename=f'{user_id}.jpg',
            target='avatar',
            use_custom_name=True,
            generate_thumbnail=False
        )
        logger.info(f"用户头像生成成功: user_id={user_id}, url={avatar_url}")
        # 加时间戳避免浏览器缓存旧头像
        return f"{avatar_url}?v={int(time.time())}"
    except Exception as e:
        logger.error(f"用户头像上传失败 (user_id={user_id}): {e}")
        raise