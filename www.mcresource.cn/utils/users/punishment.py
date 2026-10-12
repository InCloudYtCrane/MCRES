# utils/punishment.py
"""
处罚执行器 (Punishment System Module)
------------------------------------------------
主站版本：log_action 走 mcres（延迟导入，避免与 mcres/__init__.py 循环依赖）。
"""
import json
from datetime import datetime, timedelta

from utils.data.repositories import punishments as punishments_repo
from utils.data.repositories import users as users_repo
from utils.messaging.msg import add_system_message
from utils.text.forbidden_words import detector


def apply_punishment(user_id, level, matched_keywords, level_config):
    """
    执行处罚：只扣名誉，然后根据名誉差值计算处罚
    """
    # 延迟导入，避免 mcres/__init__.py 与 utils 之间的循环依赖
    from mcres import log_action

    if not user_id:
        return

    should_notify = detector.should_notify_user()
    should_log = detector.should_log_trigger()

    # ========== 1. 扣名誉 ==========
    deduct = level_config.get('reputation_deduct', 0)
    if deduct > 0:
        users_repo.deduct_reputation(user_id, deduct)

    # 获取扣分后的名誉值
    reputation_after = users_repo.get_reputation(user_id)
    if reputation_after is None:
        reputation_after = 100

    # ========== 2. 发送系统消息 ==========
    if should_notify:
        _send_notification(
            user_id,
            f'名誉 -{deduct}（当前: {reputation_after}）',
            f'您的评论包含违禁词（{", ".join(matched_keywords)}），名誉已扣除 {deduct} 分。'
        )

    # ========== 3. 记录日志 ==========
    if should_log:
        log_action(
            user_id=user_id,
            action='forbidden_trigger',
            level='WARNING' if level != 'WARN' else 'INFO',
            target_type='user',
            target_id=user_id,
            request_data={
                'level': level,
                'matched_keywords': matched_keywords,
                'reputation_deduct': deduct,
                'reputation_after': reputation_after
            }
        )
        _record_forbidden_log(user_id, level, matched_keywords, reputation_after,
                              level_config.get('punishment', ''))

    # ========== 4. 根据名誉差值计算并执行处罚 ==========
    _apply_reputation_based_punishment(user_id, reputation_after)


def _apply_reputation_based_punishment(user_id, reputation):
    """
    根据名誉值计算处罚天数

    规则：
    - ≤ 75：禁言 (75 - 名誉) 小时
    - ≤ 50：禁言 (50 - 名誉) 天
    - ≤ 25：登录封禁 (25 - 名誉) × 4 天
    - = 0：永久封号
    - 叠加规则：禁言 + 登录封禁可叠加
    """
    # 获取用户角色，管理员豁免
    role = users_repo.get_role(user_id)
    if role is None:
        return
    if role >= 3:
        return

    # ===== 永久封号 =====
    if reputation <= 0:
        users_repo.set_role(user_id, 0)
        _send_notification(user_id, '永久封号', '您的工坊名誉已归零，账号已被永久封禁。')
        return

    # ===== 计算处罚 =====
    mute_hours = 0   # 禁言（小时）
    mute_days = 0    # 禁言（天）
    login_days = 0   # 登录封禁（天）

    # 1. ≤ 75：禁言 (75 - 名誉) 小时
    if reputation <= 75:
        mute_hours = 75 - reputation

    # 2. ≤ 50：禁言 (50 - 名誉) 天
    if reputation <= 50:
        mute_days = 50 - reputation

    # 3. ≤ 25：登录封禁 (25 - 名誉) × 4 天
    if reputation <= 25:
        login_days = (25 - reputation) * 4

    # ===== 禁言：取最大值（小时和天统一转为小时比较） =====
    total_hours = max(mute_hours, mute_days * 24)

    # ===== 执行处罚（禁言 + 登录封禁可叠加） =====
    if total_hours > 0:
        if total_hours < 24:
            display_days = f'{total_hours} 小时'
            deadline = (datetime.now() + timedelta(hours=total_hours)).isoformat()
        else:
            days = total_hours // 24
            display_days = f'{days} 天'
            deadline = (datetime.now() + timedelta(days=days)).isoformat()

        _set_ban(user_id, 'comment', deadline, f'名誉 {reputation}，禁言 {display_days}')
        _send_notification(user_id, f'禁言 {display_days}',
                           f'因名誉降至 {reputation}，被禁言 {display_days}。')

    if login_days > 0:
        deadline = (datetime.now() + timedelta(days=login_days)).isoformat()
        _set_ban(user_id, 'login', deadline, f'名誉 {reputation}，登录封禁 {login_days} 天')
        _send_notification(user_id, f'登录封禁 {login_days} 天',
                           f'因名誉降至 {reputation}，被登录封禁 {login_days} 天。')

    if total_hours <= 0 and login_days <= 0 and reputation < 100:
        _send_notification(user_id, '名誉提醒', f'当前名誉 {reputation}，继续下降将触发处罚。')


def _set_ban(user_id, ban_type, deadline, reason):
    """设置封禁（写入 user_info.ban 字段）"""
    ban_data = {}
    raw_ban = users_repo.get_ban(user_id)
    if raw_ban:
        try:
            ban_data = json.loads(raw_ban)
        except Exception:
            pass

    ban_data[ban_type] = {
        'deadline': deadline,
        'reason': reason,
        'operator': 3
    }

    users_repo.set_ban(user_id, json.dumps(ban_data, ensure_ascii=False))


def _send_notification(user_id, title, content):
    """发送系统消息"""
    full_content = f'【{title}】{content}'
    add_system_message(user_id, 3, full_content)


def _record_forbidden_log(user_id, level, matched_keywords, reputation_after, punishment):
    """记录到 forbidden_log 表"""
    try:
        punishments_repo.insert_forbidden_log(
            user_id,
            level,
            json.dumps(matched_keywords, ensure_ascii=False),
            reputation_after,
            punishment,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )
    except Exception as e:
        print(f'[警告] forbidden_log 写入失败: {e}')