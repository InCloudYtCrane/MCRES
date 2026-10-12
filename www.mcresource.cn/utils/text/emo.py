# utils/emo.py
"""
站内表情包工具

工作目录下的 emo.json 定义 表情标识 → 图片 URL 的映射：
    {
        "smile": "https://img.mcresource.cn/emo/smile.png",
        "happy": "https://img.mcresource.cn/emo/happy.png"
    }

评论里的 [smile] 会在渲染时替换为 <img>。

XSS 安全策略：
    1. 先把整段评论文本做 HTML 转义（< > & " ' 全部转义）
    2. 再把 [xxx] 替换为 <img>，xxx 必须命中 emo.json 白名单
    3. URL 再次做属性转义
    —— 任何非表情内容都按纯文本处理，无法注入 HTML。
"""
import html as _html
import json
import logging
import os
import re
import threading

logger = logging.getLogger(__name__)

_EMO_FILE = os.path.join(os.getcwd(), 'emo.json')

# 表情标识符：字母、数字、下划线、连字符，1-32 位
_EMO_PATTERN = re.compile(r'\[([A-Za-z0-9_\-]{1,32})\]')
_KEY_PATTERN = re.compile(r'^[A-Za-z0-9_\-]{1,32}$')

_cache = {'mtime': 0.0, 'map': {}}
_lock = threading.Lock()


def _load():
    """加载/热更新 emo.json，返回 {key: url}"""
    if not os.path.exists(_EMO_FILE):
        return _cache['map']

    try:
        mtime = os.path.getmtime(_EMO_FILE)
    except OSError:
        return _cache['map']

    with _lock:
        if _cache['mtime'] == mtime and _cache['map']:
            return _cache['map']

        try:
            with open(_EMO_FILE, 'r', encoding='utf-8') as f:
                raw = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f'[emo] 读取 emo.json 失败: {e}')
            return _cache['map']

        result = {}
        if isinstance(raw, dict):
            for key, url in raw.items():
                if not isinstance(key, str) or not isinstance(url, str):
                    continue
                key = key.strip()
                url = url.strip()
                if not key or not url:
                    continue
                if not _KEY_PATTERN.match(key):
                    continue
                result[key] = url

        _cache['mtime'] = mtime
        _cache['map'] = result
        logger.info(f'[emo] 表情配置已加载，共 {len(result)} 个')
        return result


def get_emoji_map():
    return _load()


def get_emoji_list():
    """返回给前端：[{'key': ..., 'url': ...}, ...]"""
    return [{'key': k, 'url': v} for k, v in _load().items()]


def render_content(text):
    """
    把评论文本渲染为安全的 HTML 字符串：
        · 先 HTML 转义
        · 再把白名单内的 [xxx] 替换为 <img>
    """
    if not text:
        return ''

    escaped = _html.escape(text)
    emo_map = _load()
    if not emo_map:
        return escaped

    def _repl(m):
        key = m.group(1)
        url = emo_map.get(key)
        if not url:
            return m.group(0)          # 不在白名单，保留原文（已转义）
        safe_url = _html.escape(url, quote=True)
        safe_key = _html.escape(key, quote=True)
        return (
            f'<img class="comment-emoji" src="{safe_url}" '
            f'alt="[{safe_key}]" title="{safe_key}" loading="lazy">'
        )

    return _EMO_PATTERN.sub(_repl, escaped)