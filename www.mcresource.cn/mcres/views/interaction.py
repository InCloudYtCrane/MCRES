# views/interaction.py
import json
from flask import Blueprint, request, jsonify, session
from utils.interaction import (
    COIN_DAILY_LIMIT,
    COIN_MAX_PER_RESOURCE,
    _get_resource_counts,
    _update_resource_count,
    _get_user_interaction_status,
    _get_coins_remaining,
    _get_user_brick,
    _update_user_brick,
    _get_user_resource_coin_count
)
from utils.data.repositories.interaction import (
    delete_favorite,
    delete_like,
    find_daily_coins,
    find_favorite,
    find_like,
    find_resource_id,
    get_content,
    insert_coin,
    insert_daily_coins,
    increment_daily_coins,
    insert_favorite,
    insert_like,
)
from datetime import date
from .. import log_action

interaction_bp = Blueprint('interaction', __name__, url_prefix='/interaction')


@interaction_bp.route('', methods=['GET', 'POST'])
def interaction():
    json_body = request.get_json(silent=True) or {}

    resource_type = request.args.get('type') or request.form.get('type') or json_body.get('type')
    resource_id   = request.args.get('id')   or request.form.get('id')   or json_body.get('id')

    if not resource_type or resource_id is None:
        return jsonify({'code': 400, 'message': '缺少参数 type 或 id'}), 400
    try:
        resource_id = int(resource_id)
    except (ValueError, TypeError):
        return jsonify({'code': 400, 'message': 'id 必须是整数'}), 400

    if not find_resource_id(resource_type, resource_id):
        return jsonify({'code': 404, 'message': '资源不存在'}), 404

    # ===== GET 免登录，POST 必须登录 =====
    user_info = session.get('user_info')
    if request.method == 'POST' and not user_info:
        return jsonify({'code': 401, 'message': '请先登录'}), 401
    user_id = user_info['id'] if user_info else None

    # ---------- GET：读取互动数据 ----------
    if request.method == 'GET':
        counts = _get_resource_counts(resource_type, resource_id)

        if user_id is not None:
            liked, coined, favorited = _get_user_interaction_status(user_id, resource_type, resource_id)
            coins_remaining = _get_coins_remaining(user_id)
            user_coin_count = _get_user_resource_coin_count(user_id, resource_type, resource_id)
            brick           = _get_user_brick(user_id)
        else:
            liked = coined = favorited = False
            coins_remaining = 0
            user_coin_count = 0
            brick           = 0

        return jsonify({
            'code': 0,
            'data': {
                'likes_count':     counts['likes'],
                'coins_count':     counts['coins'],
                'favorites_count': counts['favorites'],
                'user_liked':      liked,
                'user_coined':     coined,
                'user_favorited':  favorited,
                'coins_remaining': coins_remaining,
                'brick':           brick,
                'user_coin_count': user_coin_count,
                'logged_in':       user_id is not None,
            }
        })

    # ---------- POST：执行互动（此时 user_id 一定非空） ----------
    data = json_body if request.is_json else request.form
    action = data.get('action')
    if action not in ('like', 'coin', 'favorite'):
        return jsonify({'code': 400, 'message': '无效的操作'}), 400

    if action == 'like':
        return _toggle_like(user_id, resource_type, resource_id)
    if action == 'coin':
        return _add_coin(user_id, resource_type, resource_id)
    return _toggle_favorite(user_id, resource_type, resource_id)


# =========================================================
# 以下是各动作的具体实现（逻辑未变，仅整理）
# =========================================================

def _toggle_like(user_id, resource_type, resource_id):
    existing = find_like(user_id, resource_type, resource_id)
    if existing:
        delete_like(existing['id'])
        _update_resource_count(resource_type, resource_id, 'likes_count', -1)
    else:
        insert_like(user_id, resource_type, resource_id)
        _update_resource_count(resource_type, resource_id, 'likes_count', 1)

    return _build_state_response(user_id, resource_type, resource_id)


def _add_coin(user_id, resource_type, resource_id):
    # 1. 砖块余额
    brick = _get_user_brick(user_id)
    if brick < 1:
        return jsonify({'code': 403, 'message': '砖块不足，请先签到获取砖块'}), 403

    # 2. 每日上限
    today = date.today()
    daily = find_daily_coins(user_id, today)
    used = daily['coins_used'] if daily else 0
    if used >= COIN_DAILY_LIMIT:
        return jsonify({'code': 403, 'message': f'今日投币已达上限（{COIN_DAILY_LIMIT}次）'}), 403

    # 3. 单资源上限
    coin_count = _get_user_resource_coin_count(user_id, resource_type, resource_id)
    if coin_count >= COIN_MAX_PER_RESOURCE:
        return jsonify({'code': 403, 'message': f'您对该资源最多只能投 {COIN_MAX_PER_RESOURCE} 次'}), 403

    # 4. 执行投币
    _update_user_brick(user_id, -1)
    insert_coin(user_id, resource_type, resource_id)
    _update_resource_count(resource_type, resource_id, 'coins_count', 1)

    if daily:
        increment_daily_coins(daily['id'])
    else:
        insert_daily_coins(user_id, today)

    # 5. 作者奖励：每个作者 +0.1 砖
    content_row = get_content(resource_type, resource_id)
    if content_row is not None:
        if content_row and content_row['content']:
            try:
                content = json.loads(content_row['content'])
                for author in content.get('authors', []):
                    if isinstance(author, str) and author.startswith('#id='):
                        try:
                            author_id = int(author[4:].strip())
                            _update_user_brick(author_id, 0.1)
                            log_action(
                                user_id=user_id,
                                action='coin_reward',
                                level='INFO',
                                target_type='user',
                                target_id=author_id,
                                request_data={
                                    'resource_type': resource_type,
                                    'resource_id':   resource_id,
                                    'amount':        0.1,
                                }
                            )
                        except (ValueError, TypeError):
                            continue
            except Exception as e:
                print(f"作者奖励解析失败: {e}")

    return _build_state_response(user_id, resource_type, resource_id)


def _toggle_favorite(user_id, resource_type, resource_id):
    existing = find_favorite(user_id, resource_type, resource_id)
    if existing:
        delete_favorite(existing['id'])
        _update_resource_count(resource_type, resource_id, 'favorites_count', -1)
    else:
        insert_favorite(user_id, resource_type, resource_id)
        _update_resource_count(resource_type, resource_id, 'favorites_count', 1)

    return _build_state_response(user_id, resource_type, resource_id)


def _build_state_response(user_id, resource_type, resource_id):
    """把三个动作统一返回完整状态，前端一处 updateUI 即可。"""
    counts = _get_resource_counts(resource_type, resource_id)
    liked, coined, favorited = _get_user_interaction_status(user_id, resource_type, resource_id)

    return jsonify({
        'code': 0,
        'data': {
            'likes_count':     counts['likes'],
            'coins_count':     counts['coins'],
            'favorites_count': counts['favorites'],
            'user_liked':      liked,
            'user_coined':     coined,
            'user_favorited':  favorited,
            'coins_remaining': _get_coins_remaining(user_id),
            'brick':           _get_user_brick(user_id),
            'user_coin_count': _get_user_resource_coin_count(user_id, resource_type, resource_id),
            'logged_in':       True,
        }
    })