# mcres/audit.py
import hashlib
import json
import logging
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from flask import request, current_app

from utils.data.repositories.logging import (
    find_recent_visit,
    insert_action_log,
)
from utils.time import datetime_fmt
from .config import SECRET_KEY
from .ip_service import get_real_ip


# ==================== 敏感字段过滤 ====================
SENSITIVE_FIELDS = {
    'pwd', 'password', 'old_password', 'new_password', 'current_password',
    'confirm_password', 'password_confirm', 'passwd',
    'captcha', 'code', 'email_code', 'reset_code',
    'token', 'access_token', 'refresh_token',
    'secret', 'api_key', 'apikey', 'key',
    'email', 'phone', 'mobile',
    'openid', 'qq_openid',
    'cookie', 'session', 'csrf', 'csrf_token',
    'authorization', 'auth',
}

SENSITIVE_KEYWORDS = (
    'password', 'passwd', 'pwd',
    'secret', 'token', 'api_key', 'apikey',
    'access_key', 'private_key', 'credential',
    'authorization', 'cookie', 'session', 'csrf',
    'email', 'phone', 'mobile', 'openid',
    'id_card', '身份证', '银行卡',
)

VALID_LEVELS = {'DEBUG', 'INFO', 'NOTICE', 'WARNING', 'ERROR', 'CRITICAL'}


def _is_sensitive_key(key):
    k = str(key).lower()
    if k in SENSITIVE_FIELDS:
        return True
    return any(word in k for word in SENSITIVE_KEYWORDS)


def _sanitize_request_data(data):
    if data is None:
        return None
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            cleaned[k] = '***' if _is_sensitive_key(k) else _sanitize_request_data(v)
        return cleaned
    if isinstance(data, list):
        return [_sanitize_request_data(item) for item in data]
    return data


def _sanitize_path(path):
    """过滤 URL 查询参数中的敏感字段，例如 ?token=xxx&key=xxx"""
    if not path:
        return path
    try:
        parts = urlsplit(path)
        if not parts.query:
            return path
        qsl = parse_qsl(parts.query, keep_blank_values=True)
        new_qsl = [
            (k, '***') if _is_sensitive_key(k) else (k, v)
            for k, v in qsl
        ]
        new_query = urlencode(new_qsl, doseq=True, safe='*')
        return urlunsplit((
            parts.scheme, parts.netloc, parts.path, new_query, parts.fragment
        ))
    except Exception:
        return path


# ==================== 统一操作日志 ====================
def log_action(user_id, action='page_view', level='INFO', target_type=None, target_id=None,
               method=None, path=None, status_code=None, duration_ms=None,
               ip=None, user_agent=None, request_data=None):
    try:
        level = level.upper()
        if level not in VALID_LEVELS:
            level = 'INFO'

        if method is None:
            method = request.method
        if path is None:
            path = request.full_path
        path = _sanitize_path(path)
        if ip is None:
            ip = get_real_ip()
        if user_agent is None:
            user_agent = request.headers.get('User-Agent', '')

        final_request_data = None
        if request_data is not None:
            if isinstance(request_data, dict):
                cleaned = _sanitize_request_data(request_data)
                final_request_data = json.dumps(cleaned, ensure_ascii=False)[:2000]
            elif isinstance(request_data, str):
                try:
                    parsed = json.loads(request_data)
                    cleaned = _sanitize_request_data(parsed)
                    final_request_data = json.dumps(cleaned, ensure_ascii=False)[:2000]
                except Exception:
                    try:
                        if '=' in request_data and ('&' in request_data or request_data.count('=') == 1):
                            qsl = parse_qsl(request_data, keep_blank_values=True)
                            qsl = [(k, '***' if _is_sensitive_key(k) else v) for k, v in qsl]
                            final_request_data = urlencode(qsl, doseq=True, safe='*')[:2000]
                        else:
                            final_request_data = request_data[:2000]
                    except Exception:
                        final_request_data = request_data[:2000]
        else:
            if request.method in ('POST', 'PUT', 'PATCH'):
                try:
                    data = request.get_json(silent=True)
                    if data is None:
                        data = request.form.to_dict()
                    cleaned = _sanitize_request_data(data)
                    final_request_data = json.dumps(cleaned, ensure_ascii=False)[:2000]
                except Exception:
                    final_request_data = None

        insert_action_log(
            user_id, action, level, target_type, target_id, method, path,
            status_code, duration_ms, ip, user_agent, final_request_data,
            datetime_fmt.now()
        )

        log_level_map = {
            'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'NOTICE': logging.INFO,
            'WARNING': logging.WARNING, 'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL,
        }
        current_app.logger.log(
            log_level_map.get(level, logging.INFO),
            f"[action_log] {action} by user {user_id} on {target_type}#{target_id} | path: {path}"
        )
    except Exception as e:
        current_app.logger.error(f"记录 action_log 失败: {e}")


# ==================== 访问者标识 ====================
def get_visitor_key():
    from flask import session
    user_info = session.get('user_info')
    if user_info and user_info.get('id'):
        return f"user_{user_info['id']}"
    real_ip = get_real_ip()
    user_agent = request.headers.get('User-Agent', '')
    salt = SECRET_KEY or 'mcres-fixed-salt'
    raw_string = f"{real_ip}|{user_agent}|{salt}"
    hashed_key = hashlib.sha256(raw_string.encode()).hexdigest()[:16]
    return f"hash_{hashed_key}"


def should_record_global_view(visitor_key, window_minutes):
    window_ago = (datetime.now() - timedelta(minutes=window_minutes)).strftime('%Y-%m-%d %H:%M:%S')
    row = find_recent_visit(visitor_key, window_ago)
    return row is None