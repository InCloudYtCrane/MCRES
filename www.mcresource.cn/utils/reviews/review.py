# utils/review.py
"""
审核历史工具函数
管理审核表的 review 字段（JSON 数组格式）
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Union


def normalize_review_history(
        review_data: Optional[Union[Dict, List, str]],
        current_content: Optional[Dict] = None,
        current_status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    将 review 字段统一转为数组格式，兼容旧数据

    旧格式（对象）：
        {"reviewer": 123, "note": "内容合格", "latest_review": "2026-09-05 10:00:00"}

    新格式（数组）：
        [{"action": "pending", "user": 123, "time": "...", "note": null, "content": {...}}]

    Args:
        review_data: 原始 review 数据（可能是 dict、list、str 或 None）
        current_content: 当前记录的 content（用于旧数据迁移时填充 content）
        current_status: 当前记录的状态（用于推断旧数据的 action）

    Returns:
        数组格式的审核历史
    """
    # 如果是 None 或空字符串，返回空数组
    if not review_data:
        return []

    # 如果已经是字符串，尝试解析 JSON
    if isinstance(review_data, str):
        try:
            review_data = json.loads(review_data)
        except json.JSONDecodeError:
            return []

    # 如果已经是数组，直接返回（确保每个元素都有必要字段）
    if isinstance(review_data, list):
        normalized = []
        for item in review_data:
            if isinstance(item, dict):
                # 确保必要字段存在
                if 'action' not in item:
                    item['action'] = 'pending'
                if 'user' not in item:
                    item['user'] = None
                if 'time' not in item:
                    item['time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if 'note' not in item:
                    item['note'] = None
                # content 可以为空，保留原样
                normalized.append(item)
        return normalized

    # 旧格式：对象
    if isinstance(review_data, dict):
        # 推断 action
        if current_status:
            action = current_status
        elif review_data.get('latest_review'):
            # 有审核记录，但没有状态信息，默认认定为 passed（保守处理）
            action = 'passed'
        else:
            action = 'pending'

        # 构建单条记录
        return [{
            'action': action,
            'user': review_data.get('reviewer'),
            'time': review_data.get('latest_review') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'note': review_data.get('note'),
            'content': current_content
        }]

    # 未知格式，返回空数组
    return []


def append_review_history(
        review_data: Optional[Union[Dict, List, str]],
        action: str,
        user: int,
        note: Optional[str] = None,
        content: Optional[Dict] = None,
        current_content: Optional[Dict] = None
) -> str:
    """
    追加一条审核历史记录到 review 数组，返回 JSON 字符串

    Args:
        review_data: 原始 review 数据
        action: 操作类型（pending / passed / rejected / withdrawn）
        user: 操作者用户 ID
        note: 附言（可选）
        content: 该操作时的 content 快照（如果为 None，从 current_content 取）
        current_content: 当前记录的 content（当 content 为 None 时使用）

    Returns:
        JSON 字符串，可直接写入数据库的 review 字段
    """
    # 先规范化
    history = normalize_review_history(review_data, current_content)

    # 如果 content 为 None，使用 current_content
    if content is None:
        content = current_content

    # 构建新记录
    new_record = {
        'action': action,
        'user': user,
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'note': note,
        'content': content
    }

    history.append(new_record)

    return json.dumps(history, ensure_ascii=False)


def get_latest_review_action(review_data: Optional[Union[Dict, List, str]]) -> Optional[str]:
    """
    获取最新一条审核记录的操作类型
    """
    history = normalize_review_history(review_data)
    if not history:
        return None
    return history[-1].get('action')


def get_latest_review_user(review_data: Optional[Union[Dict, List, str]]) -> Optional[int]:
    """
    获取最新一条审核记录的操作者 ID
    """
    history = normalize_review_history(review_data)
    if not history:
        return None
    return history[-1].get('user')


def get_review_timeline(
        review_data: Optional[Union[Dict, List, str]],
        reverse: bool = True
) -> List[Dict[str, Any]]:
    """
    获取审核时间线，支持正序/倒序

    Args:
        review_data: 原始 review 数据
        reverse: True 表示最新在前，False 表示最早在前

    Returns:
        排序后的审核历史列表
    """
    history = normalize_review_history(review_data)
    if reverse:
        return list(reversed(history))
    return history


def get_review_status_color(action: str) -> str:
    """
    根据操作类型返回颜色标识
    """
    color_map = {
        'pending': '#f1c40f',  # 黄色
        'passed': '#55d88b',  # 绿色
        'rejected': '#ff6b6b',  # 红色
        'withdrawn': '#6b7480',  # 灰色
    }
    return color_map.get(action, '#6b7480')


def get_review_status_label(action: str) -> str:
    """
    根据操作类型返回中文标签
    """
    label_map = {
        'pending': '待审核',
        'passed': '已通过',
        'rejected': '已退回',
        'withdrawn': '已撤回',
    }
    return label_map.get(action, action)


def get_review_status_icon(action: str) -> str:
    """
    根据操作类型返回图标
    """
    icon_map = {
        'pending': 'fa-clock',
        'passed': 'fa-check-circle',
        'rejected': 'fa-times-circle',
        'withdrawn': 'fa-ban',
    }
    return icon_map.get(action, 'fa-circle')


def has_review_history(review_data: Optional[Union[Dict, List, str]]) -> bool:
    """
    判断是否有审核历史
    """
    history = normalize_review_history(review_data)
    return len(history) > 0


def get_review_count(review_data: Optional[Union[Dict, List, str]]) -> int:
    """
    获取审核记录总数
    """
    history = normalize_review_history(review_data)
    return len(history)


def get_last_rejected_note(review_data: Optional[Union[Dict, List, str]]) -> Optional[str]:
    """
    获取最近一次退回的附言（用于显示退回原因）
    """
    history = normalize_review_history(review_data)
    # 从最新往前找退回记录
    for item in reversed(history):
        if item.get('action') == 'rejected':
            return item.get('note')
    return None


def get_pending_content(review_data: Optional[Union[Dict, List, str]]) -> Optional[Dict]:
    """
    获取最新一条 pending 记录的 content（用于显示当前待审内容）
    """
    history = normalize_review_history(review_data)
    # 从最新往前找 pending 记录
    for item in reversed(history):
        if item.get('action') == 'pending':
            return item.get('content')
    return None