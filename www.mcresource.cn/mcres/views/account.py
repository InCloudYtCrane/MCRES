# mcres/views/account/account.py
from flask import Blueprint, render_template, request, session, redirect, flash, send_file, jsonify, current_app
from utils import db
from utils.messaging import feed
from utils.time import datetime_fmt
from utils.data.repositories import sessions as sessions_repo
from utils.data.repositories import users as users_repo
from utils.users import permissions
from utils.users.bans import is_ban_active
from utils.imaging.image_store import save_image_file
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
from PIL import Image, ImageDraw, ImageFont
import io
import random
import string
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import time
from datetime import datetime, timedelta
import json
import requests
import urllib.parse
import secrets
import uuid

from dotenv import load_dotenv
from .. import log_action, get_real_ip, get_ip_region, get_ip_region_city
from utils.imaging.avatar import generate_and_save_avatar
from utils.users.sessions import create_user_session, delete_other_sessions

ac = Blueprint('account', __name__)

load_dotenv()

# ---------- QQ 登录配置（心月云）----------
QQ_LOGIN_TOKEN = os.getenv('QQ_LOGIN_TOKEN')
QQ_LOGIN_URL = 'https://qq.wch666.com/api/qq.php'
QQ_USER_INFO_URL = 'https://qq.wch666.com/api/get_user_info.php'

# ---------- GitHub 登录配置 ----------
GITHUB_CLIENT_ID = 'Ov23liaVTcwIopIut3so'
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_LOGIN_TOKEN')
GITHUB_REDIRECT_URI = 'https://www.mcresource.cn/login/github/callback'
GITHUB_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
GITHUB_USER_URL = 'https://api.github.com/user'
GITHUB_EMAILS_URL = 'https://api.github.com/user/emails'

# ---------- 邮件配置 ----------
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SMTP_USER = "2144152498@qq.com"
SMTP_PASSWORD = os.getenv('MAIL_KEY')

# ---------- 邮箱白名单 ----------
ALLOWED_EMAIL_DOMAINS = {
    'qq.com', 'foxmail.com',
    '163.com', '126.com', 'yeah.net',
    '139.com', '189.cn', 'wo.cn',
    'sina.com', 'sohu.com', 'aliyun.com',
    'gmail.com', 'outlook.com', 'hotmail.com', 'live.com',
    'icloud.com', 'me.com', 'mac.com',
    'yahoo.com', 'protonmail.com', 'proton.me',
}

def is_allowed_email(email):
    if not email or '@' not in email:
        return False
    domain = email.split('@')[1].lower()
    return domain in ALLOWED_EMAIL_DOMAINS

def is_qq_email(email):
    return email.lower().endswith('@qq.com')

def is_qq_openid_email(email):
    """判断是否为 QQ 登录用户的虚拟邮箱（以 qq_ 开头）"""
    return email and email.startswith('qq_')

def is_github_openid_email(email):
    """判断是否为 GitHub 登录用户的虚拟邮箱（以 github_ 开头）"""
    return email and email.startswith('github_')

# ---------- 图形验证码 ----------
CAPTCHA_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'

def generate_captcha():
    width, height = 150, 50
    code_len = 4
    code = ''.join(random.choices(CAPTCHA_CHARS, k=code_len))

    bg_color = (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255))
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    font_paths = [
        "arial.ttf", "times.ttf", "cour.ttf", "verdana.ttf", "Georgia.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    font = None
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, random.randint(28, 36))
            break
        except:
            continue
    if font is None:
        font = ImageFont.load_default()

    for i, char in enumerate(code):
        color = (random.randint(0, 80), random.randint(0, 80), random.randint(0, 80))
        angle = random.randint(-35, 35)

        char_img = Image.new('RGBA', (40, 50), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        bbox = char_draw.textbbox((0, 0), char, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (40 - w) // 2
        y = (50 - h) // 2 - 2
        char_draw.text((x, y), char, fill=color, font=font)

        char_img = char_img.rotate(angle, expand=1, fillcolor=(0, 0, 0, 0))
        paste_x = 10 + i * 30 + random.randint(-3, 3)
        paste_y = random.randint(0, 8)
        img.paste(char_img, (paste_x, paste_y), char_img)

    for _ in range(8):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        line_color = (random.randint(0, 150), random.randint(0, 150), random.randint(0, 150))
        draw.line((x1, y1, x2, y2), fill=line_color, width=random.randint(1, 2))

    for _ in range(300):
        x = random.randint(0, width)
        y = random.randint(0, height)
        dot_color = (random.randint(0, 200), random.randint(0, 200), random.randint(0, 200))
        draw.point((x, y), fill=dot_color)

    buf = BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return code, buf

@ac.route('/captcha')
def captcha():
    code, buf = generate_captcha()
    session['captcha'] = code
    resp = send_file(buf, mimetype='image/png')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    resp.headers['Vary'] = 'Cookie'
    return resp


# ---------- 第三方头像下载工具 ----------
def download_and_save_thirdparty_avatar(user_id, avatar_url, source=None):
    """
    下载第三方头像（QQ / GitHub）→ 居中裁剪为 200×200 → 通过 save_image_file 存入图床。
    文件名统一为 {user_id}.jpg，与手动上传头像共用同一文件名。
    source 参数保留仅为向后兼容，已不参与文件名拼接。
    失败返回 None（不抛异常，让上层决定是否回滚）。

    【Phase 6 · 6.4】返回时带上 ?v= 时间戳（与 utils/avatar.py 一致），
                     避免浏览器缓存旧头像。
    """
    if not avatar_url:
        return None
    try:
        resp = requests.get(
            avatar_url,
            timeout=15,
            headers={'User-Agent': 'MCRES/1.0'}
        )
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))

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
        if not saved_url:
            return None
        # 【Phase 6 · 6.4】带时间戳，避免浏览器缓存旧头像
        return f"{saved_url}?v={int(time.time())}"
    except Exception as e:
        current_app.logger.error(f"下载第三方头像失败 (user_id={user_id}, source={source}): {e}")
        return None


# ---------- 默认昵称工具 ----------
def _make_default_qq_nickname(user_id, exclude_user_id=None):
    """小Q同学{user_id前6位}"""
    return f"小Q同学{str(user_id)[:6]}"


def _make_default_github_nickname(user_id, exclude_user_id=None):
    """章鱼猫{user_id前6位}"""
    return f"章鱼猫{str(user_id)[:6]}"


def _sanitize_nickname(raw):
    """
    清洗昵称，规则与 settings.py 的 update_nickname 保持一致：
      · 只允许中文、英文、数字、下划线
      · 其他字符替换为 _
      · 长度 2-20（超长截断到 20；过短视为无效，返回 None）
    返回清洗后的昵称，或 None（表示清洗后仍不符合长度要求）。
    """
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    sanitized = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_]', '_', raw)
    if len(sanitized) > 20:
        sanitized = sanitized[:20]
    if len(sanitized) < 2:
        return None
    return sanitized


# ---------- 邮件发送 ----------
def send_email_code(recipient, code):
    subject = '【MCRES】注册验证码'
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MCRES 验证码</title>
    </head>
    <body style="margin:0; padding:0; font-family: 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif; background-color:#f5f7fa;">

        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa; padding:30px 0;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:16px; box-shadow:0 8px 30px rgba(0,0,0,0.08); overflow:hidden;">
                        <tr>
                            <td style="background:linear-gradient(135deg, #1e2a3a 0%, #2c3e50 100%); padding:30px 40px; text-align:center;">
                                <h1 style="color:#55d88b; font-size:28px; margin:0; letter-spacing:2px; font-weight:800;">MC<span style="color:#ffffff;">RES</span></h1>
                                <p style="color:#b0c4de; margin:8px 0 0; font-size:14px; letter-spacing:1px;">探索 · 分享 · 创造</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:40px 40px 30px;">
                                <p style="font-size:16px; color:#333; margin:0 0 20px;">尊敬的 <strong>{recipient}</strong>，您好：</p>
                                <p style="font-size:15px; color:#555; line-height:1.8; margin:0 0 25px;">
                                    您正在 <strong>MCRES</strong> 平台进行注册，请使用以下验证码完成验证。
                                </p>
                                <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f7ff; border-radius:12px; border-left:6px solid #55d88b; margin:0 0 30px;">
                                    <tr>
                                        <td align="center" style="padding:20px 0;">
                                            <span style="font-size:36px; font-weight:bold; color:#1e2a3a; letter-spacing:8px;">{code}</span>
                                        </td>
                                    </tr>
                                </table>
                                <p style="font-size:14px; color:#777; line-height:1.6; margin:0 0 10px;">⏱ 验证码有效期为 <strong>5 分钟</strong></p>
                                <p style="font-size:14px; color:#777; line-height:1.6; margin:0 0 25px;">🔒 请勿将验证码告知他人</p>
                                <hr style="border:0; border-top:1px solid #e8ecf0; margin:25px 0 20px;">
                                <p style="font-size:13px; color:#999; text-align:center; margin:0;">
                                    此邮件由系统自动发送，请勿直接回复。<br>
                                    如有疑问，请联系我们：<a href="mailto:1399885823@qq.com" style="color:#55d88b; text-decoration:none;">1399885823@qq.com</a>
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background:#f8fafc; padding:16px 40px; text-align:center; border-top:1px solid #e8ecf0;">
                                <p style="font-size:12px; color:#aaa; margin:0;">©Copyright 2026 MCRES</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = SMTP_USER
    msg['To'] = recipient

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [recipient], msg.as_string())
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False

def send_reset_email_code(recipient, code):
    subject = '【MCRES】重置密码'
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MCRES 重置密码验证码</title>
    </head>
    <body style="margin:0; padding:0; font-family: 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif; background-color:#f5f7fa;">

        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa; padding:30px 0;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:16px; box-shadow:0 8px 30px rgba(0,0,0,0.08); overflow:hidden;">
                        <tr>
                            <td style="background:linear-gradient(135deg, #1e2a3a 0%, #2c3e50 100%); padding:30px 40px; text-align:center;">
                                <h1 style="color:#55d88b; font-size:28px; margin:0; letter-spacing:2px; font-weight:800;">MC<span style="color:#ffffff;">RES</span></h1>
                                <p style="color:#b0c4de; margin:8px 0 0; font-size:14px; letter-spacing:1px;">探索 · 分享 · 创造</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:40px 40px 30px;">
                                <p style="font-size:16px; color:#333; margin:0 0 20px;">尊敬的用户，您好：</p>
                                <p style="font-size:15px; color:#555; line-height:1.8; margin:0 0 25px;">
                                    我们收到了您对 <strong>MCRES</strong> 账号的 <strong>密码重置请求</strong>。
                                </p>
                                <table width="100%" cellpadding="0" cellspacing="0" style="background:#fff5e6; border-radius:12px; border-left:6px solid #ff9a3c; margin:0 0 30px;">
                                    <tr>
                                        <td align="center" style="padding:20px 0;">
                                            <span style="font-size:36px; font-weight:bold; color:#1e2a3a; letter-spacing:8px;">{code}</span>
                                        </td>
                                    </tr>
                                </table>
                                <p style="font-size:14px; color:#777; line-height:1.6; margin:0 0 10px;">⏱ 验证码有效期为 <strong>5 分钟</strong></p>
                                <p style="font-size:14px; color:#777; line-height:1.6; margin:0 0 25px;">🔒 如非本人操作，请忽略此邮件</p>
                                <hr style="border:0; border-top:1px solid #e8ecf0; margin:25px 0 20px;">
                                <p style="font-size:13px; color:#999; text-align:center; margin:0;">
                                    此邮件由系统自动发送，请勿直接回复。<br>
                                    如有疑问，请联系我们：<a href="mailto:1399885823@qq.com" style="color:#55d88b; text-decoration:none;">1399885823@qq.com</a>
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background:#f8fafc; padding:16px 40px; text-align:center; border-top:1px solid #e8ecf0;">
                                <p style="font-size:12px; color:#aaa; margin:0;">© 2026 MCRES</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = SMTP_USER
    msg['To'] = recipient

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [recipient], msg.as_string())
        return True
    except Exception as e:
        print(f"重置密码邮件发送失败: {e}")
        return False

# ---------- 发送重置验证码 ----------
@ac.route('/send_reset_code', methods=['POST'])
def send_reset_code():
    email = request.form.get('email', '').strip()
    user_captcha = request.form.get('captcha', '').strip().upper()

    session_captcha = session.get('captcha', '').upper()
    if not user_captcha or user_captcha != session_captcha:
        log_action(
            user_id=None,
            action='send_reset_code',
            level='WARNING',
            request_data={'email': email, 'reason': 'captcha_error'}
        )
        return jsonify({'success': False, 'message': '图形验证码错误'})

    if not email or '@' not in email:
        return jsonify({'success': False, 'message': '邮箱格式不正确'})

    if is_qq_openid_email(email):
        return jsonify({'success': False, 'message': 'QQ登录账号无需重置密码，请使用QQ登录'})

    if is_github_openid_email(email):
        return jsonify({'success': False, 'message': 'GitHub登录账号无需重置密码，请使用GitHub登录'})

    user = users_repo.find_id_by_email(email)
    if not user:
        log_action(
            user_id=None,
            action='send_reset_code',
            level='WARNING',
            request_data={'email': email, 'reason': 'email_not_registered'}
        )
        return jsonify({'success': False, 'message': '该邮箱未注册'})

    code = ''.join(random.choices(string.digits, k=6))
    session['reset_code_data'] = {
        'email': email,
        'code': code,
        'timestamp': time.time()
    }

    if send_reset_email_code(email, code):
        log_action(
            user_id=None,
            action='send_reset_code',
            level='INFO',
            target_type='user',
            target_id=user['id'],
            request_data={'email': email}
        )
        return jsonify({'success': True, 'message': '重置验证码已发送至您的邮箱'})
    else:
        log_action(
            user_id=None,
            action='send_reset_code',
            level='ERROR',
            target_type='user',
            target_id=user['id'],
            request_data={'email': email, 'reason': 'email_send_failed'}
        )
        return jsonify({'success': False, 'message': '邮件发送失败，请稍后重试'})

# ---------- 发送邮箱验证码 ----------
@ac.route('/send_email_code', methods=['POST'])
def send_email_code_route():
    email = request.form.get('email', '').strip()
    user_captcha = request.form.get('captcha', '').strip().upper()

    if not user_captcha:
        email_code_data = session.get('email_code_data')
        if email_code_data and email_code_data.get('email') == email:
            if time.time() - email_code_data.get('timestamp', 0) <= 300:
                code = ''.join(random.choices(string.digits, k=6))
                session['email_code_data'] = {
                    'email': email,
                    'code': code,
                    'timestamp': time.time()
                }
                if send_email_code(email, code):
                    log_action(
                        user_id=None,
                        action='send_email_code',
                        level='INFO',
                        request_data={'email': email, 'resend': True}
                    )
                    return jsonify({'success': True, 'message': '验证码已重新发送'})
                else:
                    return jsonify({'success': False, 'message': '邮件发送失败'})
            else:
                return jsonify({'success': False, 'message': '验证码已过期，请重新输入图形验证码'})
        else:
            return jsonify({'success': False, 'message': '请重新输入图形验证码'})

    session_captcha = session.get('captcha', '').upper()
    if not user_captcha or user_captcha != session_captcha:
        log_action(
            user_id=None,
            action='send_email_code',
            level='WARNING',
            request_data={'email': email, 'reason': 'captcha_error'}
        )
        return jsonify({'success': False, 'message': '图形验证码错误'})

    if not email or '@' not in email:
        return jsonify({'success': False, 'message': '邮箱格式不正确'})

    if is_qq_openid_email(email):
        return jsonify({'success': False, 'message': '邮箱格式不正确'})

    if is_github_openid_email(email):
        return jsonify({'success': False, 'message': '邮箱格式不正确'})

    if not is_allowed_email(email):
        return jsonify({'success': False, 'message': '该邮箱域名不在支持列表中'})

    existing = users_repo.find_id_by_email(email)
    if existing:
        log_action(
            user_id=None,
            action='send_email_code',
            level='WARNING',
            request_data={'email': email, 'reason': 'email_exists'}
        )
        return jsonify({'success': False, 'message': '该邮箱已被注册'})

    code = ''.join(random.choices(string.digits, k=6))
    session['email_code_data'] = {
        'email': email,
        'code': code,
        'timestamp': time.time()
    }

    if send_email_code(email, code):
        log_action(
            user_id=None,
            action='send_email_code',
            level='INFO',
            request_data={'email': email}
        )
        return jsonify({'success': True, 'message': '验证码已发送至您的邮箱'})
    else:
        log_action(
            user_id=None,
            action='send_email_code',
            level='ERROR',
            request_data={'email': email, 'reason': 'email_send_failed'}
        )
        return jsonify({'success': False, 'message': '邮件发送失败'})

# ---------- 验证邮箱验证码 ----------
@ac.route('/verify_email_code', methods=['POST'])
def verify_email_code():
    email = request.form.get('email', '').strip()
    user_email_code = request.form.get('email_code', '').strip()

    email_code_data = session.get('email_code_data')
    if not email_code_data:
        return jsonify({'success': False, 'message': '请先获取邮箱验证码'})
    if email_code_data.get('email') != email:
        log_action(
            user_id=None,
            action='verify_email_code',
            level='WARNING',
            request_data={'email': email, 'reason': 'email_mismatch'}
        )
        return jsonify({'success': False, 'message': '邮箱与验证码不匹配'})
    if time.time() - email_code_data.get('timestamp', 0) > 300:
        return jsonify({'success': False, 'message': '邮箱验证码已过期'})
    if user_email_code != email_code_data.get('code'):
        log_action(
            user_id=None,
            action='verify_email_code',
            level='WARNING',
            request_data={'email': email, 'reason': 'code_error'}
        )
        return jsonify({'success': False, 'message': '邮箱验证码错误'})

    session['email_verified'] = True
    session['verified_email'] = email
    session.pop('email_code_data', None)

    log_action(
        user_id=None,
        action='verify_email_code',
        level='INFO',
        request_data={'email': email, 'verified': True}
    )
    return jsonify({'success': True, 'message': '验证成功'})

# ---------- 注册 ----------
@ac.route('/register', methods=['GET', 'POST'])
def register():
    user_info = session.get('user_info')
    if user_info:
        return redirect(f'/profile/{user_info["id"]}')

    if request.method == 'GET':
        return render_template('account/register.html')

    if not session.get('email_verified'):
        return render_template('account/register.html', error='请先完成邮箱验证')
    verified_email = session.get('verified_email')
    email = request.form.get('email', '').strip()
    if email != verified_email:
        return render_template('account/register.html', error='邮箱信息不一致')

    if not is_allowed_email(email):
        return render_template('account/register.html', error='该邮箱域名不在支持列表中')
    if is_qq_openid_email(email):
        return render_template('account/register.html', error='邮箱格式不正确')
    if is_github_openid_email(email):
        return render_template('account/register.html', error='邮箱格式不正确')

    nickname = request.form.get('nickname', '').strip()
    pwd_plain = request.form.get('pwd')
    agree = request.form.get('agree')

    if not agree:
        return render_template('account/register.html', error='请先同意用户协议')

    existing = users_repo.find_id_by_email(email)
    if existing:
        log_action(
            user_id=None,
            action='register',
            level='WARNING',
            request_data={'email': email, 'reason': 'email_conflict'}
        )
        return render_template('account/register.html', error='该邮箱已被注册')

    if len(pwd_plain) < 8:
        return render_template('account/register.html', error='密码长度不能少于8位')

    pwd_hash = generate_password_hash(pwd_plain)
    registration_time = datetime_fmt.now()
    users_repo.create_user(nickname, email, pwd_hash, registration_time)
    new_user = users_repo.find_id_by_email(email)

    if new_user:
        feed.add_feed(new_user['id'], "注册")

        # ===== 生成用户头像 =====
        try:
            avatar_url = generate_and_save_avatar(new_user['id'], nickname)
            users_repo.set_avatar(new_user['id'], avatar_url)
            current_app.logger.info(f"用户头像生成成功: user_id={new_user['id']}, url={avatar_url}")
        except Exception as e:
            current_app.logger.error(f"生成用户头像失败 (user_id={new_user['id']}): {e}")

    log_action(
        user_id=new_user['id'],
        action='register',
        level='INFO',
        target_type='user',
        target_id=new_user['id'],
        request_data={'email': email, 'nickname': nickname}
    )

    session.pop('email_verified', None)
    session.pop('verified_email', None)

    return render_template('account/register_success.html')

# ---------- 忘记密码 ----------
@ac.route('/forgot_password', methods=['GET'])
def forgot_password():
    if session.get('user_info'):
        return redirect(f'/profile/{session["user_info"]["id"]}')
    return render_template('account/forgot_password.html')

# ---------- 重置密码 ----------
@ac.route('/reset_password', methods=['POST'])
def reset_password():
    if session.get('user_info'):
        return redirect(f'/profile/{session["user_info"]["id"]}')

    email = request.form.get('email', '').strip()
    user_captcha = request.form.get('captcha', '').strip().upper()
    user_email_code = request.form.get('email_code', '').strip()
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    session_captcha = session.get('captcha', '').upper()
    if not user_captcha or user_captcha != session_captcha:
        log_action(
            user_id=None,
            action='reset_password',
            level='WARNING',
            request_data={'email': email, 'reason': 'captcha_error'}
        )
        return render_template('account/forgot_password.html', error='图形验证码错误')

    if is_qq_openid_email(email):
        return render_template('account/forgot_password.html', error='QQ登录账号无需重置密码')

    if is_github_openid_email(email):
        return render_template('account/forgot_password.html', error='GitHub登录账号无需重置密码')

    reset_data = session.get('reset_code_data')
    if not reset_data:
        return render_template('account/forgot_password.html', error='请先获取重置验证码')

    if reset_data.get('email') != email:
        log_action(
            user_id=None,
            action='reset_password',
            level='WARNING',
            request_data={'email': email, 'reason': 'email_mismatch'}
        )
        return render_template('account/forgot_password.html', error='邮箱与验证码不匹配')

    if time.time() - reset_data.get('timestamp', 0) > 300:
        session.pop('reset_code_data', None)
        return render_template('account/forgot_password.html', error='验证码已过期')

    if user_email_code != reset_data.get('code'):
        log_action(
            user_id=None,
            action='reset_password',
            level='WARNING',
            request_data={'email': email, 'reason': 'code_error'}
        )
        return render_template('account/forgot_password.html', error='邮箱验证码错误')

    session.pop('reset_code_data', None)
    session.pop('captcha', None)

    if len(new_password) < 8:
        return render_template('account/forgot_password.html', error='密码长度不能少于8位')
    if new_password != confirm_password:
        return render_template('account/forgot_password.html', error='两次输入的密码不一致')

    user = users_repo.find_id_by_email(email)

    pwd_hash = generate_password_hash(new_password)
    users_repo.update_password_by_email(email, pwd_hash)

    log_action(
        user_id=user['id'] if user else None,
        action='reset_password',
        level='INFO',
        target_type='user',
        target_id=user['id'] if user else None,
        request_data={'email': email, 'reset_success': True}
    )

    flash('密码重置成功，请使用新密码登录', 'success')
    return redirect('/login')

# ============================================================
# QQ 一键登录（含 CSRF 防护）
# ============================================================

@ac.route('/login/qq')
def login_qq():
    """QQ 一键登录入口（带 state CSRF 防护）"""
    next_url = request.args.get('next') or request.referrer or '/'
    if next_url in ('/login', '/login/', None) or not next_url:
        next_url = '/'

    state = secrets.token_urlsafe(16)
    session['qq_oauth_state'] = state

    msg = json.dumps({'redirect': next_url, 'state': state})
    msg_encoded = urllib.parse.quote(msg)

    qq_auth_url = f'{QQ_LOGIN_URL}?token={QQ_LOGIN_TOKEN}&msg={msg_encoded}'

    log_action(
        user_id=None,
        action='qq_login_init',
        level='INFO',
        request_data={'next': next_url}
    )

    return redirect(qq_auth_url)

@ac.route('/login/qq/callback')
def qq_callback():
    """QQ 登录回调（含 state CSRF 校验）"""
    code = request.args.get('code')
    msg = request.args.get('msg')

    if not code:
        flash('QQ登录授权失败，请重试', 'error')
        log_action(
            user_id=None,
            action='qq_login_callback',
            level='WARNING',
            request_data={'reason': 'no_code'}
        )
        return redirect('/login')

    try:
        msg_data = json.loads(msg) if msg else {}
    except Exception:
        msg_data = {}

    received_state = msg_data.get('state')
    expected_state = session.pop('qq_oauth_state', None)

    if not expected_state or received_state != expected_state:
        flash('登录请求无效，请重试', 'error')
        log_action(
            user_id=None,
            action='qq_login_callback',
            level='WARNING',
            request_data={'reason': 'csrf_mismatch', 'received': received_state, 'expected': expected_state}
        )
        return redirect('/login')

    try:
        resp = requests.get(
            f'{QQ_USER_INFO_URL}?code={code}',
            timeout=10
        )
        resp.raise_for_status()
        user_data = resp.json()
    except requests.exceptions.RequestException as e:
        flash('QQ登录服务异常，请稍后重试', 'error')
        log_action(
            user_id=None,
            action='qq_login_callback',
            level='ERROR',
            request_data={'reason': 'api_error', 'error': str(e)}
        )
        return redirect('/login')
    except ValueError as e:
        flash('QQ登录返回数据异常，请稍后重试', 'error')
        log_action(
            user_id=None,
            action='qq_login_callback',
            level='ERROR',
            request_data={'reason': 'json_parse_error', 'error': str(e)}
        )
        return redirect('/login')

    openid = user_data.get('open_id')
    if not openid:
        flash('获取用户信息失败，请重试', 'error')
        log_action(
            user_id=None,
            action='qq_login_callback',
            level='WARNING',
            request_data={'reason': 'no_openid', 'user_data': user_data}
        )
        return redirect('/login')

    qq_nickname = (user_data.get('nickname') or '').strip()
    base_nickname = qq_nickname if qq_nickname else f"小Q同学{openid[:6]}"

    nickname = base_nickname

    qq_email = f'qq_{openid}'
    user = users_repo.find_by_email(qq_email)

    is_new_user = False

    if not user:
        is_new_user = True
        registration_time = datetime_fmt.now()
        users_repo.create_user(nickname, qq_email, '', registration_time)
        user = users_repo.find_by_email(qq_email)

        try:
            avatar_url = generate_and_save_avatar(user['id'], nickname)
            users_repo.set_avatar(user['id'], avatar_url)
            current_app.logger.info(f"QQ用户头像生成成功: user_id={user['id']}, url={avatar_url}")
        except Exception as e:
            current_app.logger.error(f"生成QQ用户头像失败 (user_id={user['id']}): {e}")

        log_action(
            user_id=user['id'],
            action='register',
            level='INFO',
            target_type='user',
            target_id=user['id'],
            request_data={'qq_openid': openid, 'nickname': nickname, 'via': 'qq'}
        )
        feed.add_feed(user['id'], "注册")

    if user.get('role') == 0:
        flash('账号已被封禁，请联系管理员', 'error')
        log_action(
            user_id=user['id'],
            action='qq_login_callback',
            level='WARNING',
            target_type='user',
            target_id=user['id'],
            request_data={'reason': 'account_banned'}
        )
        return redirect('/login')

    # ★ 记录登录设备（市级）
    ip = get_real_ip()
    region = '本地' if ip in ('127.0.0.1', '::1') else get_ip_region_city(ip)
    ua = request.headers.get('User-Agent', '')
    token = create_user_session(user['id'], ip, region, ua)

    try:
        privacy_row = users_repo.get_privacy_settings(user['id'])
        privacy = {}
        if privacy_row and privacy_row.get('privacy_settings'):
            privacy = json.loads(privacy_row['privacy_settings'])
    except Exception:
        privacy = {}
    if not privacy.get('allow_multi_device', True):
        delete_other_sessions(user['id'], token)

    session['user_info'] = {'id': user['id']}
    session['session_token'] = token
    session.permanent = True

    log_action(
        user_id=user['id'],
        action='login',
        level='INFO',
        target_type='user',
        target_id=user['id'],
        request_data={'via': 'qq', 'login_success': True}
    )
    feed.add_feed(user['id'], "登录")

    if is_new_user:
        qq_avatar = (
            user_data.get('figureurl_qq_2') or
            user_data.get('figureurl_2') or
            user_data.get('figureurl') or
            user_data.get('figureurl_qq_1') or
            user_data.get('figureurl_1') or
            ''
        )
        session['qq_sync_data'] = {
            'user_id': user['id'],
            'nickname': qq_nickname,
            'avatar_url': qq_avatar,
        }
        return redirect('/login/qq/sync')

    redirect_url = msg_data.get('redirect', '/')
    if redirect_url.startswith(('http://', 'https://')):
        from urllib.parse import urlparse
        host = urlparse(redirect_url).netloc
        if host and host != request.host:
            redirect_url = '/'

    return redirect(f'/profile/{user["id"]}')


# ============================================================
# QQ 首次登录资料同步
# ============================================================

@ac.route('/login/qq/sync', methods=['GET', 'POST'])
def qq_sync_profile():
    """QQ 首次登录后，让用户勾选要同步到本地的资料：昵称 / 头像"""
    user_info = session.get('user_info')
    if not user_info:
        return redirect('/login')

    sync_data = session.get('qq_sync_data')
    if not sync_data or sync_data.get('user_id') != user_info['id']:
        return redirect(f'/profile/{user_info["id"]}')

    user_id = user_info['id']

    if request.method == 'GET':
        return render_template(
            'account/qq_sync.html',
            qq_nickname=sync_data.get('nickname', ''),
            qq_avatar=sync_data.get('avatar_url', ''),
        )

    apply_nickname = request.form.get('sync_nickname') == '1'
    apply_avatar = request.form.get('sync_avatar') == '1'

    updates = []
    params = []
    applied = {'nickname': False, 'avatar': False}

    final_nickname = None

    if apply_nickname and sync_data.get('nickname'):
        raw = (request.form.get('nickname') or '').strip()
        sanitized = _sanitize_nickname(raw)
        if sanitized:
            final_nickname = sanitized

    if not final_nickname:
        final_nickname = _make_default_qq_nickname(user_id)

    updates.append('nickname = %s')
    params.append(final_nickname)
    applied['nickname'] = True

    if apply_avatar and sync_data.get('avatar_url'):
        saved = download_and_save_thirdparty_avatar(user_id, sync_data['avatar_url'], 'qq')
        if saved:
            updates.append('avatar = %s')
            params.append(saved)
            applied['avatar'] = True

    if updates:
        users_repo.update_profile_fields(user_id, updates, params)

    session.pop('qq_sync_data', None)

    log_action(
        user_id=user_id,
        action='qq_sync_profile',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data=applied
    )

    flash('资料同步完成，欢迎来到 MCRES！', 'success')
    return redirect(f'/profile/{user_id}')


@ac.route('/login/qq/sync/skip', methods=['POST'])
def qq_sync_skip():
    """跳过同步：昵称设为「小Q同学{user_id前6位}」，头像保留系统默认"""
    user_info = session.get('user_info')
    if not user_info:
        return redirect('/login')

    user_id = user_info['id']
    sync_data = session.get('qq_sync_data')

    if sync_data and sync_data.get('user_id') == user_id:
        default_nickname = _make_default_qq_nickname(user_id)
        users_repo.set_nickname(user_id, default_nickname)
        log_action(
            user_id=user_id,
            action='qq_sync_skip',
            level='INFO',
            target_type='user',
            target_id=user_id,
            request_data={'nickname': default_nickname}
        )

    session.pop('qq_sync_data', None)
    return redirect(f'/profile/{user_id}')


# ============================================================
# GitHub 一键登录
# ============================================================

@ac.route('/login/github')
def login_github():
    """GitHub 一键登录入口（带 state CSRF 防护）"""
    next_url = request.args.get('next') or '/'
    if next_url in ('/login', '/login/', None) or not next_url:
        next_url = '/'

    state = secrets.token_urlsafe(16)
    combined_state = f"{state}|{next_url}"
    session['github_oauth_state'] = combined_state

    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': GITHUB_REDIRECT_URI,
        'scope': 'read:user user:email',
        'state': combined_state,
    }
    auth_url = GITHUB_AUTHORIZE_URL + '?' + urllib.parse.urlencode(params)

    log_action(
        user_id=None,
        action='github_login_init',
        level='INFO',
        request_data={'next': next_url}
    )

    return redirect(auth_url)


@ac.route('/login/github/callback')
def github_callback():
    """GitHub 登录回调（含 state CSRF 校验）"""
    code = request.args.get('code')
    state = request.args.get('state', '')

    if not code:
        flash('GitHub 授权失败，请重试', 'error')
        log_action(user_id=None, action='github_login_callback', level='WARNING',
                   request_data={'reason': 'no_code'})
        return redirect('/login')

    expected_state = session.pop('github_oauth_state', None)

    if not expected_state or state != expected_state:
        flash('登录请求无效，请重试', 'error')
        log_action(user_id=None, action='github_login_callback', level='WARNING',
                   request_data={'reason': 'csrf_mismatch',
                                 'received': state, 'expected': expected_state})
        return redirect('/login')

    try:
        _, next_url = expected_state.split('|', 1)
    except Exception:
        next_url = '/'

    try:
        token_resp = requests.post(
            GITHUB_TOKEN_URL,
            data={
                'client_id': GITHUB_CLIENT_ID,
                'client_secret': GITHUB_CLIENT_SECRET,
                'code': code,
                'redirect_uri': GITHUB_REDIRECT_URI,
            },
            headers={
                'Accept': 'application/json',
                'User-Agent': 'MCRES/1.0',
            },
            timeout=15
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
    except requests.exceptions.RequestException as e:
        flash('GitHub 登录服务异常，请稍后重试', 'error')
        log_action(user_id=None, action='github_login_callback', level='ERROR',
                   request_data={'reason': 'token_request_failed', 'error': str(e)})
        return redirect('/login')

    access_token = token_data.get('access_token')
    if not access_token:
        flash('GitHub 授权失败，请重试', 'error')
        log_action(user_id=None, action='github_login_callback', level='WARNING',
                   request_data={'reason': 'no_access_token', 'response': token_data})
        return redirect('/login')

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'MCRES/1.0',
    }

    try:
        user_resp = requests.get(GITHUB_USER_URL, headers=headers, timeout=15)
        user_resp.raise_for_status()
        github_user = user_resp.json()
    except requests.exceptions.RequestException as e:
        flash('获取 GitHub 用户信息失败，请重试', 'error')
        log_action(user_id=None, action='github_login_callback', level='ERROR',
                   request_data={'reason': 'user_info_failed', 'error': str(e)})
        return redirect('/login')

    github_id = github_user.get('id')
    if not github_id:
        flash('GitHub 用户信息异常', 'error')
        log_action(user_id=None, action='github_login_callback', level='WARNING',
                   request_data={'reason': 'no_github_id', 'user_data': github_user})
        return redirect('/login')

    virtual_email = f"github_{github_id}"

    real_email = github_user.get('email')
    if not real_email:
        try:
            emails_resp = requests.get(
                GITHUB_EMAILS_URL, headers=headers, timeout=15
            )
            emails_resp.raise_for_status()
            for e in emails_resp.json():
                if e.get('primary') and e.get('verified'):
                    real_email = e.get('email')
                    break
        except Exception as e:
            current_app.logger.warning(f"获取 GitHub 邮箱列表失败: {e}")

    github_login = github_user.get('login', '')
    github_name = github_user.get('name') or github_login or f'章鱼猫{str(github_id)[:6]}'

    nickname = github_name.strip()

    user = users_repo.find_by_email(virtual_email)

    is_new_user = False

    if not user:
        is_new_user = True
        registration_time = datetime_fmt.now()
        users_repo.create_user(nickname, virtual_email, '', registration_time)
        user = users_repo.find_by_email(virtual_email)

        try:
            avatar_url = generate_and_save_avatar(user['id'], nickname)
            users_repo.set_avatar(user['id'], avatar_url)
            current_app.logger.info(f"GitHub用户头像生成成功: user_id={user['id']}, url={avatar_url}")
        except Exception as e:
            current_app.logger.error(f"生成GitHub用户头像失败 (user_id={user['id']}): {e}")

        log_action(user_id=user['id'], action='register', level='INFO',
                   target_type='user', target_id=user['id'],
                   request_data={
                       'github_id': github_id,
                       'github_login': github_login,
                       'real_email': real_email or '(未提供)',
                       'nickname': nickname,
                       'via': 'github'
                   })
        feed.add_feed(user['id'], "注册")

    if user.get('role') == 0:
        flash('账号已被封禁，请联系管理员', 'error')
        log_action(user_id=user['id'], action='github_login_callback', level='WARNING',
                   target_type='user', target_id=user['id'],
                   request_data={'reason': 'account_banned'})
        return redirect('/login')

    ip = get_real_ip()
    region = '本地' if ip in ('127.0.0.1', '::1') else get_ip_region_city(ip)
    ua = request.headers.get('User-Agent', '')
    token = create_user_session(user['id'], ip, region, ua)

    try:
        privacy_row = users_repo.get_privacy_settings(user['id'])
        privacy = {}
        if privacy_row and privacy_row.get('privacy_settings'):
            privacy = json.loads(privacy_row['privacy_settings'])
    except Exception:
        privacy = {}
    if not privacy.get('allow_multi_device', True):
        delete_other_sessions(user['id'], token)

    session['user_info'] = {'id': user['id']}
    session['session_token'] = token
    session.permanent = True

    log_action(user_id=user['id'], action='login', level='INFO',
               target_type='user', target_id=user['id'],
               request_data={'via': 'github', 'github_login': github_login,
                             'login_success': True})
    feed.add_feed(user['id'], "登录")

    if is_new_user:
        github_avatar = github_user.get('avatar_url', '')
        if github_avatar:
            sep = '&' if '?' in github_avatar else '?'
            github_avatar = f"{github_avatar}{sep}s=200"

        session['github_sync_data'] = {
            'user_id': user['id'],
            'nickname': github_name,
            'avatar_url': github_avatar,
        }
        return redirect('/login/github/sync')

    return redirect(f'/profile/{user["id"]}')


# ============================================================
# GitHub 首次登录资料同步
# ============================================================

@ac.route('/login/github/sync', methods=['GET', 'POST'])
def github_sync_profile():
    """GitHub 首次登录后，让用户勾选要同步到本地的资料：昵称 / 头像"""
    user_info = session.get('user_info')
    if not user_info:
        return redirect('/login')

    sync_data = session.get('github_sync_data')
    if not sync_data or sync_data.get('user_id') != user_info['id']:
        return redirect(f'/profile/{user_info["id"]}')

    user_id = user_info['id']

    if request.method == 'GET':
        return render_template(
            'account/github_sync.html',
            github_nickname=sync_data.get('nickname', ''),
            github_avatar=sync_data.get('avatar_url', ''),
        )

    apply_nickname = request.form.get('sync_nickname') == '1'
    apply_avatar = request.form.get('sync_avatar') == '1'

    updates = []
    params = []
    applied = {'nickname': False, 'avatar': False}

    final_nickname = None

    if apply_nickname and sync_data.get('nickname'):
        raw = (request.form.get('nickname') or '').strip()
        sanitized = _sanitize_nickname(raw)
        if sanitized:
            final_nickname = sanitized

    if not final_nickname:
        final_nickname = _make_default_github_nickname(user_id)

    updates.append('nickname = %s')
    params.append(final_nickname)
    applied['nickname'] = True

    if apply_avatar and sync_data.get('avatar_url'):
        saved = download_and_save_thirdparty_avatar(user_id, sync_data['avatar_url'], 'github')
        if saved:
            updates.append('avatar = %s')
            params.append(saved)
            applied['avatar'] = True

    if updates:
        users_repo.update_profile_fields(user_id, updates, params)

    session.pop('github_sync_data', None)

    log_action(
        user_id=user_id,
        action='github_sync_profile',
        level='INFO',
        target_type='user',
        target_id=user_id,
        request_data=applied
    )

    flash('资料同步完成，欢迎来到 MCRES！', 'success')
    return redirect(f'/profile/{user_id}')


@ac.route('/login/github/sync/skip', methods=['POST'])
def github_sync_skip():
    """跳过同步：昵称设为「章鱼猫{user_id前6位}」，头像保留系统默认"""
    user_info = session.get('user_info')
    if not user_info:
        return redirect('/login')

    user_id = user_info['id']
    sync_data = session.get('github_sync_data')

    if sync_data and sync_data.get('user_id') == user_id:
        default_nickname = _make_default_github_nickname(user_id)
        users_repo.set_nickname(user_id, default_nickname)
        log_action(
            user_id=user_id,
            action='github_sync_skip',
            level='INFO',
            target_type='user',
            target_id=user_id,
            request_data={'nickname': default_nickname}
        )

    session.pop('github_sync_data', None)
    return redirect(f'/profile/{user_id}')


# ============================================================
# 登录（含维护模式支持）
# ============================================================

@ac.route('/login', methods=['GET', 'POST'])
def login():
    stop = os.getenv("STOP", "false").strip().lower()
    is_maintenance_mode = stop in ('true', '1', 'on')

    user_info = session.get('user_info')
    if user_info:
        uid = user_info['id']
        user = users_repo.get_role_row(uid)
        if user:
            if is_maintenance_mode and user.get('role') != 4:
                session.pop('user_info', None)
                flash('当前处于维护模式，仅允许工坊主管访问', 'error')
                return redirect('/maintenance')
            return redirect(f'/profile/{uid}')
        else:
            session.pop('user_info', None)
            return redirect('/login')

    if request.method == 'GET':
        if is_maintenance_mode:
            return render_template('account/maintenance_login.html', error=None, qq_login_url='/login/qq')
        return render_template('account/login.html', qq_login_url='/login/qq')

    # ===== POST 登录 =====
    email = request.form.get('email', '').strip()
    plain_pwd = request.form.get('pwd', '')
    user_captcha = request.form.get('captcha', '').strip().upper()

    session_captcha = session.get('captcha', '').upper()
    if not user_captcha or user_captcha != session_captcha:
        if is_maintenance_mode:
            return render_template('account/maintenance_login.html', error='验证码错误，请重新输入',
                                   email=email, qq_login_url='/login/qq')
        return render_template('account/login.html', error="验证码错误，请重新输入",
                               email=email, captcha=user_captcha, qq_login_url='/login/qq')

    session.pop('captcha', None)

    if is_qq_openid_email(email):
        if is_maintenance_mode:
            return render_template('account/maintenance_login.html', error='该账号为QQ登录账号，请使用QQ一键登录',
                                   email=email, qq_login_url='/login/qq')
        return render_template('account/login.html', error="该账号为QQ登录账号，请点击「QQ一键登录」按钮登录",
                               email=email, captcha=user_captcha, qq_login_url='/login/qq')

    if is_github_openid_email(email):
        if is_maintenance_mode:
            return render_template('account/maintenance_login.html', error='该账号为GitHub登录账号，请使用GitHub一键登录',
                                   email=email, qq_login_url='/login/qq')
        return render_template('account/login.html', error="该账号为GitHub登录账号，请点击「GitHub一键登录」按钮登录",
                               email=email, captcha=user_captcha, qq_login_url='/login/qq')

    data = users_repo.find_by_email(email)
    if not data:
        if is_maintenance_mode:
            return render_template('account/maintenance_login.html', error='邮箱或密码错误',
                                   email=email, qq_login_url='/login/qq')
        return render_template('account/login.html', error="用户名或密码错误",
                               email=email, captcha=user_captcha, qq_login_url='/login/qq')

    if is_qq_openid_email(data.get('email', '')):
        if is_maintenance_mode:
            return render_template('account/maintenance_login.html', error='该账号为QQ登录账号，请使用QQ一键登录',
                                   email=email, qq_login_url='/login/qq')
        return render_template('account/login.html', error="该账号为QQ登录账号，请点击「QQ一键登录」按钮登录",
                               email=email, captcha=user_captcha, qq_login_url='/login/qq')

    if is_github_openid_email(data.get('email', '')):
        if is_maintenance_mode:
            return render_template('account/maintenance_login.html', error='该账号为GitHub登录账号，请使用GitHub一键登录',
                                   email=email, qq_login_url='/login/qq')
        return render_template('account/login.html', error="该账号为GitHub登录账号，请点击「GitHub一键登录」按钮登录",
                               email=email, captcha=user_captcha, qq_login_url='/login/qq')

    if not check_password_hash(data['pwd'], plain_pwd):
        if is_maintenance_mode:
            return render_template('account/maintenance_login.html', error='邮箱或密码错误',
                                   email=email, qq_login_url='/login/qq')
        return render_template('account/login.html', error="用户名或密码错误",
                               email=email, captcha=user_captcha, qq_login_url='/login/qq')

    # ===== 封禁检查 =====
    ban_str = data.get('ban')
    if ban_str:
        try:
            ban_data = json.loads(ban_str)
            changed = False
            now = datetime.now()
            if 'login' in ban_data and ban_data['login'] and ban_data['login'].get('deadline'):
                if not is_ban_active(ban_data['login'], now):
                    del ban_data['login']
                    changed = True
            if changed:
                new_ban = json.dumps(ban_data, ensure_ascii=False) if ban_data else None
                users_repo.set_ban(data['id'], new_ban)
                data['ban'] = new_ban
        except Exception:
            pass

    login_ban = None
    if data.get('ban'):
        try:
            ban_data = json.loads(data['ban']) if isinstance(data['ban'], str) else data['ban']
            login_ban = ban_data.get('login')
        except:
            pass
    if is_ban_active(login_ban):
        log_action(
            user_id=data['id'],
            action='login',
            level='WARNING',
            target_type='user',
            target_id=data['id'],
            request_data={'email': email, 'reason': 'account_banned'}
        )
        if is_maintenance_mode:
            return render_template('account/maintenance_login.html', error=f'账号已被封禁登录权限，截止至 {login_ban["deadline"]}',
                                   qq_login_url='/login/qq')
        return render_template('account/login.html', error=f'账号已被封禁登录权限，截止至 {login_ban["deadline"]}，原因：{login_ban.get("reason", "无")}',
                               qq_login_url='/login/qq')

    if data['role'] == 0:
        log_action(
            user_id=data['id'],
            action='login',
            level='WARNING',
            target_type='user',
            target_id=data['id'],
            request_data={'email': email, 'reason': 'role_banned'}
        )
        if is_maintenance_mode:
            return render_template('account/maintenance_login.html', error='账号已被封禁，请联系管理员',
                                   qq_login_url='/login/qq')
        return render_template('account/login.html', error="当前账户已被封禁，请联系管理员",
                               qq_login_url='/login/qq')

    if is_maintenance_mode and data['role'] != 4:
        log_action(
            user_id=data['id'],
            action='login',
            level='WARNING',
            target_type='user',
            target_id=data['id'],
            request_data={'email': email, 'reason': 'maintenance_mode_blocked'}
        )
        return render_template('account/maintenance_login.html',
                               error='当前处于维护模式，仅允许工坊主管登录',
                               email=email,
                               qq_login_url='/login/qq')

    # ===== 登录成功 =====
    if request.form.get('remember') == '1':
        session.permanent = True
    else:
        session.permanent = False

    ip = get_real_ip()
    region = '本地' if ip in ('127.0.0.1', '::1') else get_ip_region_city(ip)
    ua = request.headers.get('User-Agent', '')
    token = create_user_session(data['id'], ip, region, ua)

    try:
        privacy_row = users_repo.get_privacy_settings(data['id'])
        privacy = {}
        if privacy_row and privacy_row.get('privacy_settings'):
            privacy = json.loads(privacy_row['privacy_settings'])
    except Exception:
        privacy = {}
    if not privacy.get('allow_multi_device', True):
        delete_other_sessions(data['id'], token)

    session['user_info'] = {'id': data['id']}
    session['session_token'] = token
    feed.add_feed(data['id'], "登录")

    log_action(
        user_id=data['id'],
        action='login',
        level='INFO',
        target_type='user',
        target_id=data['id'],
        request_data={'email': email, 'login_success': True}
    )

    if is_maintenance_mode and data['role'] == 4:
        return redirect('/admin')

    return redirect(f'/profile/{data["id"]}')

@ac.route('/logout')
@permissions.login_required()
def logout():
    user_id = session.get('user_info', {}).get('id')
    if user_id:
        log_action(
            user_id=user_id,
            action='logout',
            level='INFO',
            target_type='user',
            target_id=user_id
        )
    current_token = session.get('session_token')
    if current_token:
        try:
            sessions_repo.delete_by_token(current_token)
        except Exception:
            pass

    session.pop('user_info', None)
    session.pop('session_token', None)
    return redirect('/login')

@ac.route('/terms')
def terms():
    return redirect('/rule/terms')

@ac.route('/privacy')
def privacy():
    return redirect('/rule/privacy')

# ============================================================
# 二维码扫码登录（支持电脑端快捷登录）
# ============================================================

qr_sessions = {}

def clean_expired_qr():
    """清理过期的二维码会话"""
    now = time.time()
    expired = [k for k, v in qr_sessions.items() if v.get('expires_at', 0) < now]
    for k in expired:
        del qr_sessions[k]

@ac.route('/login/qrcode/generate')
def generate_qr_code():
    """生成二维码登录会话"""
    clean_expired_qr()

    qr_id = str(uuid.uuid4()).replace('-', '')[:16]
    expires_at = time.time() + 300
    qr_sessions[qr_id] = {
        'status': 'waiting',
        'user_id': None,
        'expires_at': expires_at
    }

    base_url = request.host_url.rstrip('/')
    qr_content = f"{base_url}/login/qrcode/scan?qr_id={qr_id}"

    log_action(
        user_id=None,
        action='generate_qr_code',
        level='INFO',
        request_data={'qr_id': qr_id}
    )

    return jsonify({
        'success': True,
        'qr_id': qr_id,
        'qr_content': qr_content,
        'expires_in': 300
    })

@ac.route('/login/qrcode/scan')
def qr_scan_page():
    """扫码后跳转的页面（手机端扫码后打开的页面）"""
    qr_id = request.args.get('qr_id')
    if not qr_id or qr_id not in qr_sessions:
        return "二维码无效或已过期", 400

    user_info = session.get('user_info')
    if user_info:
        return redirect(f'/login/qrcode/confirm?qr_id={qr_id}')
    else:
        return render_template('account/qr_scan.html', qr_id=qr_id)

@ac.route('/login/qrcode/status/<qr_id>')
def qr_status(qr_id):
    """轮询二维码状态"""
    clean_expired_qr()
    if qr_id not in qr_sessions:
        return jsonify({'success': False, 'status': 'expired', 'message': '二维码已过期'})

    data = qr_sessions[qr_id]
    if data['status'] == 'confirmed':
        user = users_repo.get_identity(data['user_id'])
        return jsonify({
            'success': True,
            'status': 'confirmed',
            'user': user
        })
    else:
        return jsonify({
            'success': True,
            'status': data['status']
        })

@ac.route('/login/qrcode/confirm', methods=['POST'])
def qr_confirm_post():
    user_info = session.get('user_info')
    if not user_info:
        return jsonify({'success': False, 'message': '请先登录手机端账号'}), 401

    data = request.get_json()
    qr_id = data.get('qr_id')
    if not qr_id or qr_id not in qr_sessions:
        return jsonify({'success': False, 'message': '二维码无效或已过期'}), 400

    session_data = qr_sessions[qr_id]
    if session_data['status'] not in ('waiting', 'scanned'):
        return jsonify({'success': False, 'message': '二维码已使用或已过期'}), 400

    session_data['status'] = 'confirmed'
    session_data['user_id'] = user_info['id']

    log_action(
        user_id=user_info['id'],
        action='qr_confirm_login',
        level='INFO',
        target_type='user',
        target_id=user_info['id'],
        request_data={'qr_id': qr_id}
    )

    return jsonify({'success': True, 'message': '登录确认成功'})

@ac.route('/login/qrcode/confirm', methods=['GET'])
def qr_confirm_get():
    qr_id = request.args.get('qr_id')
    if not qr_id or qr_id not in qr_sessions:
        return "二维码无效或已过期", 400

    user_info = session.get('user_info')
    if not user_info:
        flash('请先登录手机端账号', 'error')
        return redirect('/login')

    session_data = qr_sessions[qr_id]
    if session_data['status'] != 'waiting':
        return "二维码已被使用或已过期", 400

    session_data['status'] = 'confirmed'
    session_data['user_id'] = user_info['id']

    log_action(
        user_id=user_info['id'],
        action='qr_confirm_login',
        level='INFO',
        target_type='user',
        target_id=user_info['id'],
        request_data={'qr_id': qr_id}
    )

    return "登录成功，请返回电脑端查看", 200

@ac.route('/login/qrcode/login', methods=['POST'])
def qr_code_login():
    """PC 端在轮询到 confirmed 之后调用它换取登录态。

    【安全修复 A1】原先从请求体取 `user_id` 直接建会话，
    **完全没有校验二维码是否已被确认** —— 任何人 POST `{"user_id": 1}`
    就能登录成任意用户（未授权接管）。

    现在只信服务端 `qr_sessions` 里的状态：
      1. 必须带 `qr_id`（不再接受 `user_id`）
      2. 该二维码必须存在且 `status == 'confirmed'`
      3. `user_id` 只从服务端会话里读，请求体里的同名字段一律忽略
      4. 兑换后立即置为 `used`，同一二维码只能用一次（防重放）
    """
    data = request.get_json(silent=True) or {}
    qr_id = data.get('qr_id')
    if not qr_id:
        return jsonify({'success': False, 'message': '缺少二维码标识'}), 400

    clean_expired_qr()
    session_data = qr_sessions.get(qr_id)
    if not session_data:
        return jsonify({'success': False, 'message': '二维码无效或已过期'}), 400
    if session_data.get('status') != 'confirmed':
        return jsonify({'success': False, 'message': '二维码尚未确认，请先在手机端确认'}), 403

    user_id = session_data.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': '二维码未绑定用户'}), 403

    user = users_repo.get_identity_with_role(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    # 一次性兑换：先作废再发会话，避免并发重放
    session_data['status'] = 'used'

    ip = get_real_ip()
    region = '本地' if ip in ('127.0.0.1', '::1') else get_ip_region_city(ip)
    ua = request.headers.get('User-Agent', '')
    token = create_user_session(user['id'], ip, region, ua)

    try:
        privacy_row = users_repo.get_privacy_settings(user['id'])
        privacy = {}
        if privacy_row and privacy_row.get('privacy_settings'):
            privacy = json.loads(privacy_row['privacy_settings'])
    except Exception:
        privacy = {}
    if not privacy.get('allow_multi_device', True):
        delete_other_sessions(user['id'], token)

    session['user_info'] = {'id': user['id']}
    session['session_token'] = token
    session.permanent = True

    log_action(
        user_id=user['id'],
        action='qr_code_login',
        level='INFO',
        target_type='user',
        target_id=user['id'],
        request_data={'via': 'qrcode'}
    )

    return jsonify({'success': True, 'message': '登录成功'})

@ac.route('/api/user/<int:user_id>')
def api_get_user(user_id):
    user = users_repo.get_identity(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    return jsonify({
        'success': True,
        'id': user['id'],
        'nickname': user['nickname'],
        'avatar': user.get('avatar', 'm/images/avatar/default.jpg')
    })

@ac.route('/login/qrcode/scanned', methods=['POST'])
def qr_scanned():
    data = request.get_json()
    qr_id = data.get('qr_id')
    if not qr_id or qr_id not in qr_sessions:
        return jsonify({'success': False, 'message': '二维码无效'}), 400

    session_data = qr_sessions[qr_id]
    if session_data['status'] != 'waiting':
        return jsonify({'success': False, 'message': '二维码已失效'}), 400

    session_data['status'] = 'scanned'
    return jsonify({'success': True, 'message': '已标记为已扫描'})