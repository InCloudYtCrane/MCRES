# mcres/middleware.py
import json
import os
import time
from datetime import datetime, timedelta

from flask import (
    session, request, redirect, flash, render_template, Response,
)


from utils.data.repositories.impersonation import (
    close_expired_impersonation,
)
from utils.data.repositories.logging import (
    insert_access_log,
)
from utils.data.repositories.users import (
    find_id_only,
    get_role_ban,
    get_role_row,
)
from utils.site import announce as announce_core
from utils.users.bans import is_ban_active

from utils.site.anti_fraud import get_anti_fraud_config

from .config import BAN_EXCLUDED_HOSTS
from .ip_service import (
    get_real_ip, get_ip_region, get_ip_region_city, hash_ip,
    get_blacklist,
    is_whitelisted, is_blocked, record_block_hit,
    is_sensitive_path, is_bad_user_agent, is_rate_limited,
    count_4xx, consume_4xx_bucket,
    report_violation,
    RATE_WINDOW_SECONDS, RATE_MAX_REQUESTS,
    FOURXX_WINDOW_SECONDS, FOURXX_MAX_COUNT,
)
from .audit import (
    log_action, get_visitor_key, should_record_global_view,
)


# ============================================================
# 豁免子域判断
# ============================================================
def _is_excluded_host():
    """当前请求的 host 是否在 IP 封禁豁免名单里（img 等）"""
    try:
        host = request.host.split(':')[0].lower()
    except Exception:
        return False
    return host in BAN_EXCLUDED_HOSTS


# ============================================================
# 模拟登录过期检查（必须最先执行）
# ============================================================
def register_impersonation_check(app):
    @app.before_request
    def check_impersonation_expiry():
        if '_impersonate_expiry' not in session:
            return
        try:
            expiry = float(session.get('_impersonate_expiry') or 0)
        except (ValueError, TypeError):
            expiry = 0
        if time.time() <= expiry:
            return

        impersonator_id = session.get('_impersonator_id')
        target_user_id = (session.get('user_info') or {}).get('id')

        if impersonator_id and target_user_id:
            try:
                close_expired_impersonation(impersonator_id, target_user_id)
            except Exception as e:
                app.logger.error(f"清理过期模拟登录记录失败: {e}")

        restored = False
        if impersonator_id:
            admin = find_id_only(impersonator_id)
            if admin:
                session['user_info'] = {'id': admin['id']}
                restored = True

        if not restored:
            session.pop('user_info', None)

        original_token = session.pop('_impersonator_original_token', None)
        if original_token:
            session['session_token'] = original_token
        else:
            session.pop('session_token', None)

        session.pop('_impersonator_id', None)
        session.pop('_impersonate_expiry', None)
        session.modified = True
        flash('模拟登录已超时，已自动退出', 'warning')


# ============================================================
# 全局维护模式
# ============================================================
def register_maintenance_mode(app):
    @app.before_request
    def maintenance_mode():
        stop = os.getenv("STOP", "false").strip().lower()
        if stop not in ('true', '1', 'on'):
            return

        if request.path.startswith('/static') or request.path.startswith('/images'):
            return
        if request.path == '/captcha':
            return
        if request.path == '/login' or request.path == '/maintenance' or request.path.startswith('/login'):
            return

        user_info = session.get('user_info')
        if user_info:
            user_id = user_info.get('id')
            if user_id:
                user = get_role_row(user_id)
                if user and user.get('role') == 4:
                    return
        return redirect('/maintenance')

    @app.route('/maintenance')
    def maintenance_page():
        announcements = []
        try:
            announcements = announce_core.get_active_announcements()
        except Exception as e:
            app.logger.error(f"加载公告失败: {e}")
        return render_template('stop.html', announcements=announcements), 503


# ============================================================
# 根域名 → www 重定向
# ============================================================
def register_root_redirect(app):
    @app.before_request
    def redirect_to_www():
        host = request.host.split(':')[0]
        if host == 'mcresource.cn':
            return redirect(f"https://www.mcresource.cn{request.full_path}", code=301)


# ============================================================
# 请求计时
# ============================================================
def register_start_timer(app):
    @app.before_request
    def start_timer():
        request.start_time = time.time()


# ============================================================
# IP 黑名单封禁 + 自动检测（跨子域共享）
# ============================================================
def register_ip_blacklist(app):
    @app.before_request
    def block_ip_middleware():
        if _is_excluded_host():
            return None

        ip = get_real_ip()

        if is_whitelisted(ip):
            return None

        if is_blocked(ip):
            record_block_hit(ip)
            entry = get_blacklist().get(ip) or {}

            banned_time = entry.get('created_at')
            if banned_time:
                try:
                    banned_time = banned_time.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    banned_time = str(banned_time)
            else:
                banned_time = '未知'

            return render_template(
                'errors/ip_banned.html',
                banned_ip=ip,
                banned_time=banned_time,
                banned_reason=entry.get('reason') or '未知',
            ), 403

        if is_sensitive_path(request.path):
            report_violation(ip, 'sensitive_scan', 3,
                             f'{request.method} {request.path[:100]}')
            return Response('Forbidden', status=403, mimetype='text/plain')

        ua = request.headers.get('User-Agent', '')
        if is_bad_user_agent(ua):
            report_violation(ip, 'bad_user_agent', 5, f'UA={ua[:80]}')
            return Response('Forbidden', status=403, mimetype='text/plain')

        if is_rate_limited(ip):
            report_violation(ip, 'rate_limit', 2,
                             f'{RATE_WINDOW_SECONDS}s 内 > {RATE_MAX_REQUESTS} 次')
            return Response('Too Many Requests', status=429,
                            mimetype='text/plain')

        return None


# ============================================================
# 全局请求日志
# ============================================================
def register_request_logger(app):
    @app.before_request
    def log_request_info():
        client_ip = get_real_ip()
        print(f"{client_ip} - - [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
              f"\"{request.method} {request.path}\"")


# ============================================================
# 账号封禁检查
# ============================================================
def register_ban_check(app):
    @app.before_request
    def check_ban_before_request():
        public_paths = [
            '/login', '/logout', '/captcha', '/register',
            '/send_email_code', '/send_reset_code', '/reset_password',
            '/forgot_password', '/terms', '/privacy',
            '/static', '/images', '/background',
        ]
        path = request.path
        for prefix in public_paths:
            if path.startswith(prefix):
                return

        if 'user_info' not in session:
            return

        user_id = session['user_info']['id']
        user = get_role_ban(user_id)
        if not user:
            session.pop('user_info', None)
            return redirect('/login')

        if user['role'] == 0:
            session.pop('user_info', None)
            flash('您的账号已被封禁，请联系管理员了解详情', 'errors')
            return redirect('/login')

        ban_str = user.get('ban')
        if ban_str:
            try:
                ban_data = json.loads(ban_str)
                login_ban = ban_data.get('login')
                if is_ban_active(login_ban):
                    session.pop('user_info', None)
                    flash(f'您的账号已被封禁登录权限，截止至 {login_ban["deadline"]}，'
                          f'原因：{login_ban.get("reason", "无")}', 'errors')
                    return redirect('/login')
            except Exception:
                pass


# ============================================================
# 登录设备会话校验
# ============================================================
def register_session_token_check(app):
    @app.before_request
    def check_session_token():
        if session.get('_impersonator_id') or session.get('_impersonate_expiry'):
            return

        user_info = session.get('user_info')
        if not user_info:
            return
        user_id = user_info.get('id')
        if not user_id:
            return

        token = session.get('session_token')

        if not token:
            try:
                from utils.users.sessions import create_user_session
                ip = get_real_ip()
                # 【Phase 6 · 6.2】统一用 get_ip_region_city（省 市）
                region = '本地' if ip in ('127.0.0.1', '::1') else get_ip_region_city(ip)
                ua = request.headers.get('User-Agent', '')
                token = create_user_session(user_id, ip, region, ua)
                session['session_token'] = token
                session.modified = True
            except Exception as e:
                app.logger.error(f"自动补建 user_sessions 记录失败: {e}")
            return

        try:
            from utils.users.sessions import is_session_valid, touch_session
            if not is_session_valid(user_id, token):
                session.pop('user_info', None)
                session.pop('session_token', None)
                flash('您的登录状态已在其它设备上退出，请重新登录', 'warning')
                return redirect('/login')
            touch_session(token)
        except Exception as e:
            app.logger.error(f"会话校验失败: {e}")


# ============================================================
# favicon 自动注入
# ============================================================
def register_favicon(app):
    @app.after_request
    def add_favicon_by_path(response):
        if response.content_type and 'text/html' in response.content_type:
            content = response.get_data(as_text=True)
            if 'rel="icon"' not in content and 'rel="shortcut icon"' not in content:
                host = request.host.split(':')[0]
                if host == 'admin.mcresource.cn':
                    icon_url = 'https://img.mcresource.cn/icon/logo/logo_admin.png'
                    icon_type = 'image/png'
                else:
                    icon_url = 'https://img.mcresource.cn/icon/logo/logo.png'
                    icon_type = 'image/x-icon'
                link_tag = f'<link rel="icon" href="{icon_url}" type="{icon_type}">'
                content = content.replace('<head>', f'<head>{link_tag}')
                response.set_data(content)
        return response


# ============================================================
# 访问日志记录（含 4xx 洪水检测）
# ============================================================
def register_access_log(app):
    @app.after_request
    def record_access_log(response):
        path = request.path
        ignore_prefixes = (
            '/static', '/images', '/captcha', '/background', '/favicon.ico',
            '/suggest', '/login/qrcode/status',
        )
        if path.startswith(ignore_prefixes):
            return response

        if 400 <= response.status_code < 500 and not _is_excluded_host():
            try:
                ip = get_real_ip()
                if not is_whitelisted(ip):
                    if count_4xx(ip):
                        report_violation(
                            ip, f'http_{response.status_code}', 3,
                            f'{FOURXX_WINDOW_SECONDS}s 内 {FOURXX_MAX_COUNT}+ 次 4xx'
                        )
                        consume_4xx_bucket(ip)
            except Exception:
                pass

        try:
            real_ip = get_real_ip()
            region = '未知'
            if real_ip and real_ip not in ('127.0.0.1', '::1'):
                region = get_ip_region(real_ip)
            if real_ip in ('127.0.0.1', '::1'):
                region = '本地'

            user_info = session.get('user_info')
            user_id = user_info.get('id') if user_info else None
            visitor_key = get_visitor_key()

            duration_ms = 0
            if hasattr(request, 'start_time'):
                duration_ms = int((time.time() - request.start_time) * 1000)

            if request.method == 'GET':
                config = get_anti_fraud_config()
                global_session_minutes = config.get('global_session_minutes', 1)
                global_window_minutes = config.get('global_window_minutes', 10)

                session_key = 'last_global_view'
                last_view_str = session.get(session_key)
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                should_record = True

                if last_view_str:
                    try:
                        last_time = datetime.strptime(last_view_str, '%Y-%m-%d %H:%M:%S')
                        if (datetime.now() - last_time) < timedelta(minutes=global_session_minutes):
                            should_record = False
                    except Exception:
                        pass

                if should_record and not should_record_global_view(visitor_key, global_window_minutes):
                    should_record = False

                if should_record:
                    insert_access_log(
                        path, hash_ip(real_ip), region, user_id, visitor_key,
                        response.status_code, duration_ms
                    )
                    session[session_key] = now_str

            if response.status_code >= 500:
                level = 'ERROR'
            elif response.status_code >= 400:
                level = 'WARNING'
            else:
                level = 'INFO'

            log_action(
                user_id=user_id,
                action='page_view',
                level=level,
                method=request.method,
                path=request.full_path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                ip=real_ip,
                user_agent=request.headers.get('User-Agent', ''),
            )
        except Exception as e:
            print(f"⚠️ 记录日志失败: {e}")
            app.logger.error(f"记录日志失败: {e}")

        return response
        
# ============================================================
# 成就自动评定（每个页面请求触发，引擎内部有 10 秒防抖）
# ============================================================
def register_achievement_eval(app):
    """
    每个请求尝试评定一次当前登录用户的成就。
    · 未登录跳过
    · 静态资源 / 心跳 / favicon 跳过
    · evaluate_user 内部有 EVAL_DEBOUNCE_SECONDS 防抖（10 秒），
      因此同一用户高频请求时不会反复跑判定
    · 异常全部吞掉，不影响主流程
    """
    # 跳过的 endpoint（Flask 的内部名）
    _SKIP_ENDPOINTS = {
        'static',
        'file.image',
        'favicon',
    }
    # 跳过的路径前缀
    _SKIP_PREFIXES = (
        '/static',
        '/images',
        '/favicon.ico',
        '/login/qrcode/status',
    )

    @app.before_request
    def _eval_achievements():
        user_info = session.get('user_info')
        if not user_info:
            return

        endpoint = request.endpoint or ''
        if endpoint in _SKIP_ENDPOINTS:
            return

        path = request.path or ''
        for prefix in _SKIP_PREFIXES:
            if path.startswith(prefix):
                return

        try:
            from utils.achievements import evaluate_user
            evaluate_user(user_info['id'])
        except Exception:
            # 成就系统异常不能影响正常请求
            try:
                app.logger.warning(
                    f"[achievements] 自动评定失败 user={user_info.get('id')}",
                    exc_info=True
                )
            except Exception:
                pass