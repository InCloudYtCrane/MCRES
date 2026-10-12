# 【主站】mcres/views/profile/settings.py
# 位置：mcres/views/profile/settings.py
import json
import re
import secrets
import io
import time
from flask import render_template, request, session, redirect, flash, jsonify

from utils.users import permissions
from utils.data.repositories.profiles import (
    clear_titles,
    get_pwd_row,
    get_signature,
    get_titles,
    get_user,
    set_notification_settings,
    set_privacy_settings,
    set_pwd,
    set_signature,
    set_titles,
)
from utils.data.repositories.users import (
    get_notification_settings,
    get_nickname_row,
    get_privacy_settings,
    set_avatar,
    set_nickname,
)
from utils.data.repositories.sessions import find_session_token
from utils.text.titles import parse_titles
from utils.imaging.image_store import save_image_file
from utils.users.sessions import (
    list_user_sessions,
    delete_user_session,
    delete_other_sessions,
)
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
from mcres import log_action
from .blueprint import profile_bp


# ============================================================
# 通知设置默认值（含茶室三个开关 + 成就开关）
# ============================================================
_NOTIFICATION_DEFAULT = {
    'reply': True,
    'reaction': True,
    'board': True,
    'tea_reply': True,
    'tea_like': True,
    'tea_topic': True,
    'achievement': True,
}

# 隐私设置默认值（含隐藏在线状态 + 允许多设备登录）
_PRIVACY_DEFAULT = {
    'board': True,
    'show_favorites': True,
    'show_achievements': True,
    'search_visible': True,
    'hide_login': False,
    'hide_online_status': False,
    'allow_multi_device': True,
}


# ============================================================
# 辅助：判断第三方登录虚拟邮箱
# ============================================================
def _is_qq_virtual_email(email):
    return bool(email) and email.startswith('qq_')

def _is_github_virtual_email(email):
    return bool(email) and email.startswith('github_')


# ============================================================
# 渲染设置页面
# ============================================================
@profile_bp.route('/settings', methods=['GET'])
@permissions.login_required()
def settings():
    user_id = session['user_info']['id']
    user_info = get_user(user_id)

    email_raw = user_info.get('email', '')
    is_qq_user = _is_qq_virtual_email(email_raw)
    is_github_user = _is_github_virtual_email(email_raw)

    nickname = user_info['nickname']
    avatar_url = user_info['avatar'] or 'https://img.mcresource.cn/user/avatar/default.jpg'
    signature = user_info.get('signature', '')
    email = email_raw
    if is_qq_user:
        email = 'QQ登录用户（无邮箱）'
    elif is_github_user:
        email = 'GitHub登录用户（无邮箱）'

    # ---------- 通知设置 ----------
    notification_settings = dict(_NOTIFICATION_DEFAULT)
    raw_notif = user_info.get('notification_settings')
    if raw_notif:
        try:
            saved = json.loads(raw_notif)
            if isinstance(saved, dict):
                notification_settings.update(saved)
        except:
            pass

    # ---------- 隐私设置 ----------
    privacy_settings = dict(_PRIVACY_DEFAULT)
    raw_privacy = user_info.get('privacy_settings')
    if raw_privacy:
        try:
            saved = json.loads(raw_privacy)
            if isinstance(saved, dict):
                privacy_settings.update(saved)
        except:
            pass

    return render_template('profile/settings/settings.html',
                           nickname=nickname,
                           avatar_url=avatar_url,
                           signature=signature,
                           email=email,
                           is_qq_user=is_qq_user,
                           is_github_user=is_github_user,
                           notification_settings=notification_settings,
                           privacy_settings=privacy_settings)


# ============================================================
# API：获取通知设置
# ============================================================
@profile_bp.route('/settings/notifications', methods=['GET'])
@permissions.login_required()
def get_notification_settings():
    user_id = session['user_info']['id']
    user_info = get_notification_settings(user_id)

    settings = dict(_NOTIFICATION_DEFAULT)
    if user_info and user_info.get('notification_settings'):
        try:
            saved = json.loads(user_info['notification_settings'])
            if isinstance(saved, dict):
                settings.update(saved)
        except:
            pass

    return jsonify({'success': True, 'data': settings})


# ============================================================
# API：更新通知设置
# ============================================================
@profile_bp.route('/settings/notifications', methods=['POST'])
@permissions.login_required()
def update_notification_settings():
    user_id = session['user_info']['id']
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'message': '无效的请求数据'}), 400

    settings = {
        'reply': bool(data.get('reply', True)),
        'reaction': bool(data.get('reaction', True)),
        'board': bool(data.get('board', True)),
        'tea_reply': bool(data.get('tea_reply', True)),
        'tea_like': bool(data.get('tea_like', True)),
        'tea_topic': bool(data.get('tea_topic', True)),
        'achievement': bool(data.get('achievement', True)),
    }

    settings_json = json.dumps(settings, ensure_ascii=False)
    set_notification_settings(user_id, settings_json)

    log_action(
        user_id=user_id,
        action='update_notification_settings',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data=settings
    )

    return jsonify({'success': True, 'message': '通知设置已更新', 'data': settings})


# ============================================================
# API：获取隐私设置
# ============================================================
@profile_bp.route('/settings/privacy', methods=['GET'])
@permissions.login_required()
def get_privacy_settings():
    user_id = session['user_info']['id']
    user_info = get_privacy_settings(user_id)

    settings = dict(_PRIVACY_DEFAULT)
    if user_info and user_info.get('privacy_settings'):
        try:
            saved = json.loads(user_info['privacy_settings'])
            if isinstance(saved, dict):
                settings.update(saved)
        except:
            pass

    return jsonify({'success': True, 'data': settings})


# ============================================================
# API：更新隐私设置
# ------------------------------------------------------------
# 新增：
#   · allow_multi_device: 是否允许多设备登录
#   · 当该开关从 true → false 时，立刻踢掉当前用户的所有其他设备
# ============================================================
@profile_bp.route('/settings/privacy', methods=['POST'])
@permissions.login_required()
def update_privacy_settings():
    user_id = session['user_info']['id']
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'message': '无效的请求数据'}), 400

    # 读取旧设置，判断 allow_multi_device 是否从 true → false
    old_row = get_privacy_settings(user_id)
    old_settings = dict(_PRIVACY_DEFAULT)
    if old_row and old_row.get('privacy_settings'):
        try:
            saved = json.loads(old_row['privacy_settings'])
            if isinstance(saved, dict):
                old_settings.update(saved)
        except Exception:
            pass

    settings = {
        'board': bool(data.get('board', True)),
        'show_favorites': bool(data.get('show_favorites', True)),
        'show_achievements': bool(data.get('show_achievements', True)),
        'search_visible': bool(data.get('search_visible', True)),
        'hide_login': bool(data.get('hide_login', False)),
        'hide_online_status': bool(data.get('hide_online_status', False)),
        'allow_multi_device': bool(data.get('allow_multi_device', True)),
    }

    settings_json = json.dumps(settings, ensure_ascii=False)
    set_privacy_settings(user_id, settings_json)

    # ★ 从开 → 关：立即踢掉其他所有设备
    if old_settings.get('allow_multi_device', True) and not settings['allow_multi_device']:
        current_token = session.get('session_token')
        if current_token:
            try:
                delete_other_sessions(user_id, current_token)
            except Exception as e:
                log_action(
                    user_id=user_id,
                    action='kick_other_sessions_on_disable_multi_device',
                    level='ERROR',
                    target_type='user',
                    target_id=user_id,
                    request_data={'error': str(e)}
                )

    log_action(
        user_id=user_id,
        action='update_privacy_settings',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data=settings
    )

    return jsonify({'success': True, 'message': '隐私设置已更新', 'data': settings})


# ============================================================
# API：更新头像
# ------------------------------------------------------------
# 【Phase 6 · 6.4】落库时带上 ?v= 时间戳，与 utils/avatar.py 一致
# ============================================================
@profile_bp.route('/settings/avatar', methods=['POST'])
@permissions.login_required()
def update_avatar():
    user_id = session['user_info']['id']
    avatar_file = request.files.get('avatar')

    if not avatar_file or not avatar_file.filename:
        return jsonify({'success': False, 'message': '请选择图片'}), 400

    try:
        img_data = avatar_file.read()
        img = Image.open(io.BytesIO(img_data))

        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')

        width, height = img.size
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        img = img.crop((left, top, left + size, top + size))
        img = img.resize((200, 200), Image.Resampling.LANCZOS)

        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        image_bytes = output.getvalue()

        saved_url = save_image_file(
            image_bytes,
            filename=f'{user_id}.jpg',
            target='avatar',
            use_custom_name=True,
            generate_thumbnail=False
        )

        # 【Phase 6 · 6.4】加时间戳（与 utils/avatar.py 一致），落库带 ?v=
        avatar_url = f"{saved_url}?v={int(time.time())}" if saved_url else saved_url

        set_avatar(user_id, avatar_url)

        log_action(
            user_id=user_id,
            action='avatar_update',
            level='INFO',
            target_type='user',
            target_id=user_id,
            request_data={'avatar': avatar_url}
        )

        return jsonify({'success': True, 'avatar_url': avatar_url})

    except Exception as e:
        log_action(
            user_id=user_id,
            action='avatar_update',
            level='ERROR',
            target_type='user',
            target_id=user_id,
            request_data={'error': str(e)}
        )
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'}), 500


# ============================================================
# API：更新昵称
# ============================================================
@profile_bp.route('/settings/nickname', methods=['POST'])
@permissions.login_required()
def update_nickname():
    user_id = session['user_info']['id']
    data = request.get_json()
    nickname = data.get('nickname', '').strip() if data else ''

    if not nickname:
        return jsonify({'success': False, 'message': '昵称不能为空'}), 400
    if len(nickname) < 2 or len(nickname) > 20:
        return jsonify({'success': False, 'message': '昵称长度应在2-20个字符之间'}), 400
    if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9_]+$', nickname):
        return jsonify({'success': False, 'message': '昵称只能包含中文、英文、数字和下划线'}), 400

    old_nickname = get_nickname_row(user_id)['nickname']
    set_nickname(user_id, nickname)
    if old_nickname != nickname:
        log_action(
            user_id=user_id,
            action='nickname_change',
            level='INFO',
            target_type='user',
            target_id=user_id,
            request_data={'old': old_nickname, 'new': nickname}
        )
    return jsonify({'success': True, 'message': '昵称已更新'})


# ============================================================
# API：更新个性签名
# ============================================================
@profile_bp.route('/settings/signature', methods=['POST'])
@permissions.login_required()
def update_signature():
    user_id = session['user_info']['id']
    data = request.get_json()
    signature = data.get('signature', '').strip() if data else ''

    if len(signature) > 80:
        return jsonify({'success': False, 'message': '签名不能超过80个字符'}), 400

    old_signature = get_signature(user_id).get('signature', '')
    set_signature(user_id, signature)
    if old_signature != signature:
        log_action(
            user_id=user_id,
            action='signature_change',
            level='INFO',
            target_type='user',
            target_id=user_id,
            request_data={'changed': True}
        )
    return jsonify({'success': True, 'message': '签名已更新'})


# ============================================================
# 密码重置页面
# ============================================================
@profile_bp.route('/settings/pwd', methods=['GET'])
@permissions.login_required()
def pwd_page():
    user_id = session['user_info']['id']
    user_info = get_user(user_id)

    email_raw = user_info.get('email', '')
    is_qq_user = _is_qq_virtual_email(email_raw)
    is_github_user = _is_github_virtual_email(email_raw)

    if is_qq_user:
        flash('QQ登录用户无需设置密码，请使用QQ一键登录', 'info')
        return redirect('/profile/settings')
    if is_github_user:
        flash('GitHub登录用户无需设置密码，请使用GitHub一键登录', 'info')
        return redirect('/profile/settings')

    return render_template('profile/settings/pwd.html')


# ============================================================
# API：验证当前密码
# ============================================================
@profile_bp.route('/settings/pwd/verify', methods=['POST'])
@permissions.login_required()
def verify_password():
    user_id = session['user_info']['id']
    data = request.get_json()
    current_password = data.get('current_password', '')

    if not current_password:
        return jsonify({'success': False, 'message': '请输入当前密码'}), 400

    user_info = get_pwd_row(user_id)
    if not user_info or not check_password_hash(user_info['pwd'], current_password):
        log_action(
            user_id=user_id,
            action='verify_password',
            level='WARNING',
            target_type='user',
            target_id=user_id,
            request_data={'reason': 'wrong_password'}
        )
        return jsonify({'success': False, 'message': '当前密码错误'}), 400

    token = secrets.token_urlsafe(16)
    session['pwd_reset_token'] = token
    session['pwd_reset_verified'] = True

    return jsonify({'success': True, 'token': token})


# ============================================================
# API：重置密码
# ============================================================
@profile_bp.route('/settings/pwd/reset', methods=['POST'])
@permissions.login_required()
def reset_password():
    user_id = session['user_info']['id']
    data = request.get_json()

    token = data.get('token', '')
    if not session.get('pwd_reset_verified') or session.get('pwd_reset_token') != token:
        return jsonify({'success': False, 'message': '验证已过期，请重新验证当前密码'}), 401

    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if len(new_password) < 8:
        return jsonify({'success': False, 'message': '密码长度不能少于8位'}), 400
    if new_password != confirm_password:
        return jsonify({'success': False, 'message': '两次输入的密码不一致'}), 400

    pwd_hash = generate_password_hash(new_password)
    set_pwd(user_id, pwd_hash)

    session.pop('pwd_reset_token', None)
    session.pop('pwd_reset_verified', None)

    log_action(
        user_id=user_id,
        action='password_change',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data={'success': True}
    )

    return jsonify({'success': True, 'message': '密码修改成功'})


# ============================================================
# API：获取用户的头衔列表及当前选中
# ============================================================
@profile_bp.route('/settings/titles', methods=['GET'])
@permissions.login_required()
def get_user_titles():
    user_id = session['user_info']['id']
    row = get_titles(user_id)

    titles_data = parse_titles(row.get('titles') if row else None)
    return jsonify({'success': True, 'data': titles_data})


# ============================================================
# API：选择佩戴的头衔
# ============================================================
@profile_bp.route('/settings/titles/select', methods=['POST'])
@permissions.login_required()
def select_user_title():
    user_id = session['user_info']['id']
    data = request.get_json()
    index = data.get('index', -1)

    row = get_titles(user_id)
    titles_data = parse_titles(row.get('titles') if row else None)

    if index < -1 or index >= len(titles_data.get('list', [])):
        return jsonify({'success': False, 'message': '无效的头衔索引'}), 400

    titles_data['selected'] = index

    if not titles_data.get('list'):
        clear_titles(user_id)
    else:
        set_titles(user_id, json.dumps(titles_data, ensure_ascii=False))

    log_action(
        user_id=user_id,
        action='select_title',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data={'selected_index': index}
    )

    return jsonify({'success': True, 'message': '头衔已更新'})


# ============================================================
# 登录设备管理 API
# ============================================================

@profile_bp.route('/settings/sessions', methods=['GET'])
@permissions.login_required()
def get_user_sessions():
    """获取当前用户的所有登录设备列表"""
    user_id = session['user_info']['id']
    current_token = session.get('session_token')

    items = list_user_sessions(user_id, current_token)

    return jsonify({'success': True, 'data': items})


@profile_bp.route('/settings/sessions/<int:session_id>', methods=['DELETE'])
@permissions.login_required()
def remove_user_session(session_id):
    """
    退出指定设备：
    - 只能删除自己的会话
    - 若删除的是当前设备，则同时清空本地 session，让前端跳回登录页
    """
    user_id = session['user_info']['id']
    current_token = session.get('session_token')

    row = find_session_token(session_id, user_id)
    if not row:
        return jsonify({'success': False, 'message': '设备不存在'}), 404

    is_current = (row['session_token'] == current_token)

    delete_user_session(user_id, session_id)

    log_action(
        user_id=user_id,
        action='delete_session',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data={'session_id': session_id, 'is_current': is_current}
    )

    if is_current:
        session.pop('user_info', None)
        session.pop('session_token', None)

    return jsonify({'success': True, 'is_current': is_current, 'message': '该设备已退出登录'})