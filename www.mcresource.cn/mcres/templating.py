# mcres/templating.py
import json
from datetime import datetime

from flask import session, current_app


from utils.data.repositories.profiles import get_user
from utils.data.repositories.users import set_ban
from utils.users.bans import is_ban_active

from .config import USE_SUBDOMAIN

from .url_helpers import asset_url, image_url, admin_url, main_url


# ============================================================
# 上下文处理器
# ============================================================
def register_context(app):

    @app.context_processor
    def context_processor():
        user_info = None
        is_impersonating = False

        if "user_info" in session:
            uid = session.get('user_info')['id']
            user = get_user(uid)
            if user:
                # ---------- ban 过期清理 ----------
                ban_str = user.get('ban')
                if ban_str:
                    try:
                        ban_data = json.loads(ban_str)
                        changed = False
                        now = datetime.now()
                        for key in list(ban_data.keys()):
                            item = ban_data.get(key)
                            # 无 deadline 的条目不参与判定（与原守卫一致）；
                            # 有 deadline 的必须解析成 datetime 再比 ——
                            # 原先比字符串，同一天的封禁会被误判成"已过期"删掉
                            if item and item.get('deadline') and not is_ban_active(item, now):
                                del ban_data[key]
                                changed = True
                        if changed:
                            new_ban = json.dumps(ban_data, ensure_ascii=False) if ban_data else None
                            set_ban(uid, new_ban)
                            user['ban'] = new_ban
                    except Exception:
                        pass

                # ============================================================
                # 【Phase 4 · Step 4.4c】未读数改为实时计算
                # ============================================================
                # 旧逻辑：从 user_info.message JSON 读 unread.{reply,system,board}
                # 新逻辑：调用 get_unread_counts（SQL 实时算）
                #         + get_tea_unread_count（茶室，独立）
                # ============================================================
                total_unread = 0

                try:
                    from utils.messaging.msg import get_unread_counts, get_tea_unread_count

                    # ---- 主站三类未读 ----
                    station_counts = get_unread_counts(uid)
                    total_unread += sum(station_counts.values())

                    # ---- 茶室未读（从 message JSON 读 tea_last_read，其余实时算）----
                    tea_last_read = None
                    msg_str = user.get('message')
                    if msg_str:
                        try:
                            msg_data = json.loads(msg_str)
                            if isinstance(msg_data, dict):
                                tea_last_read = msg_data.get('tea_last_read')
                        except Exception:
                            pass

                    notif = None
                    notif_raw = user.get('notification_settings')
                    if notif_raw:
                        try:
                            notif = (
                                json.loads(notif_raw)
                                if isinstance(notif_raw, str)
                                else notif_raw
                            )
                        except Exception:
                            notif = None

                    total_unread += get_tea_unread_count(uid, tea_last_read, notif)

                except Exception as e:
                    try:
                        current_app.logger.error(f"计算未读数失败: {e}")
                    except Exception:
                        pass

                user_info = {
                    'id': user['id'],
                    'nickname': user['nickname'],
                    'email': user['email'],
                    'role': user['role'],
                    'avatar': user['avatar'],
                    'message_unread_total': total_unread,
                }
                if '_impersonator_id' in session:
                    is_impersonating = True

        return dict(
            user_info=user_info,
            is_impersonating=is_impersonating,
            asset_url=asset_url,
            image_url=image_url,
            admin_url=admin_url,
            main_url=main_url,
            USE_SUBDOMAIN=USE_SUBDOMAIN,
            vx='1.2',
        )


# ============================================================
# 模板过滤器
# ============================================================
def register_template_filters(app):

    @app.template_filter('asset')
    def asset_filter(path):
        return asset_url(path)

    @app.template_filter('image')
    def image_filter(path):
        return image_url(path)

    @app.template_filter('admin')
    def admin_filter(path=''):
        return admin_url(path)

    @app.template_filter('number_format')
    def number_format(value):
        if value is None:
            return '0'
        try:
            return f"{int(value):,}"
        except Exception:
            return str(value)