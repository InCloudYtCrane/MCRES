# mcres/__init__.py
import logging
import os
import sys
from datetime import timedelta
from logging.handlers import RotatingFileHandler

from flask import Flask

# ============================================================
# 控制台编码兜底（必须在任何模块 print 之前执行）
# ============================================================
# 代码里大量 print("✅ ...") / print("⚠️ ...")。在 Windows 默认的 GBK 控制台下，
# print 本身就会抛 UnicodeEncodeError —— 更糟的是它发生在 except 分支里
# （例如 ip_service._load_division_code_map 读取缺失文件后的告警），
# 会把一个"文件不存在"的良性告警升级成整个应用起不来。
# 这里统一把标准流切到 UTF-8；已经是 UTF-8（Linux 生产环境）时无副作用。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError, ValueError):
        pass

from utils.scheduling.scheduler_manager import init_scheduler
from utils.time.time_utils import timesince

from .config import SECRET_KEY, RESET
from .cors import setup_cors
from .ip_service import (
    init_ip_database,
    get_real_ip, get_ip_region, get_ip_region_city, get_blacklist, hash_ip,
)
from .audit import log_action
from .url_helpers import asset_url, image_url, admin_url, main_url
from . import middleware, templating, error_handlers

# 重新导出，保持向后兼容
# （views/account.py、utils/sessions.py 等
#   通过 `from mcres import log_action` / `from .. import ...` 使用这些）
__all__ = [
    'create_app',
    'log_action', 'get_real_ip', 'get_ip_region', 'get_ip_region_city', 'get_blacklist', 'hash_ip',
    'asset_url', 'image_url', 'admin_url', 'main_url',
]


# ============================================================
# 内部工具
# ============================================================
def _configure_session(app):
    """跨子域名共享 Session"""
    app.secret_key = SECRET_KEY
    app.config['SESSION_COOKIE_NAME'] = 'mcres_session'
    app.config['SESSION_COOKIE_DOMAIN'] = '.mcresource.cn'
    app.config['SESSION_COOKIE_PATH'] = '/'
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    app.permanent_session_lifetime = timedelta(days=30)


def _configure_logging(app):
    if app.debug:
        return
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/mcres.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('MCRES 应用启动')


def _register_blueprints(app):
    from .views import (account, file, index, resource_create,
                        detail, resource_edit, comment, message,
                        search, api, site, difference,
                        rule, preset, target, profile,
                        interaction)
    app.register_blueprint(index.ix)
    app.register_blueprint(account.ac)
    app.register_blueprint(file.im)
    app.register_blueprint(resource_create.nw)
    app.register_blueprint(detail.dl)
    app.register_blueprint(resource_edit.et)
    app.register_blueprint(comment.cmt)
    app.register_blueprint(message.msg_bp)
    app.register_blueprint(search.sch)
    app.register_blueprint(api.api_bp)
    app.register_blueprint(site.site_bp)
    app.register_blueprint(difference.diff_bp)
    app.register_blueprint(rule.rule_bp)
    app.register_blueprint(preset.preset_bp)
    app.register_blueprint(target.redirect_bp)
    app.register_blueprint(profile.profile_bp)
    app.register_blueprint(interaction.interaction_bp)


# ============================================================
# 应用工厂
# ============================================================
def create_app():
    app = Flask(__name__)

    # 1. Session / 日志
    _configure_session(app)
    _configure_logging(app)

    # 2. IP 属地数据库
    init_ip_database()

    # 3. RESET 全量重置（可选）
    if RESET == 'true':
        from utils.reset import reset_all
        reset_all()

    # 4. 定时调度器
    with app.app_context():
        init_scheduler(app)
        print("✅ 定时调度器已启动")

    # 5. 中间件（注册顺序即执行顺序，after_request 逆序执行）
    middleware.register_impersonation_check(app)
    middleware.register_maintenance_mode(app)   # 含 /maintenance 路由
    middleware.register_root_redirect(app)
    middleware.register_start_timer(app)
    middleware.register_ip_blacklist(app)
    middleware.register_request_logger(app)
    middleware.register_ban_check(app)
    middleware.register_achievement_eval(app)   # ★ 新增：成就自动评定
    middleware.register_session_token_check(app)
    middleware.register_favicon(app)            # after_request（早注册）
    middleware.register_access_log(app)         # after_request（后注册）

    # 6. 上下文处理器 + 模板过滤器
    templating.register_context(app)
    templating.register_template_filters(app)

    # 7. 错误页
    error_handlers.register_error_handlers(app)

    # 8. 蓝图
    _register_blueprints(app)

    # 9. 应用级配置
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
    app.jinja_env.filters['timesince'] = timesince
    app.url_map.strict_slashes = False
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    # 10. CORS（最后注册 → after_request 最先执行，保持原语义）
    setup_cors(app)

    return app