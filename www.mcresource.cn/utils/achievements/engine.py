# utils/achievements/engine.py
import json
import random
import time
import logging

from utils.data.repositories import achievements as achievements_repo
from utils.data.repositories import interaction as interaction_repo
from utils.data.repositories import profiles as profiles_repo
from utils.time import datetime_fmt
from utils.text.titles import parse_titles
from . import checkers

logger = logging.getLogger(__name__)

_defs = []
_def_fingerprint = None
_last_eval = {}

EVAL_DEBOUNCE_SECONDS = 10


# ============================================================
# 定义加载
# ============================================================
def _fingerprint():
    try:
        row = achievements_repo.get_active_definitions_fingerprint()
        if not row:
            return (0, 0)
        return (int(row['n'] or 0), int(row['t'] or 0))
    except Exception as e:
        logger.error(f'[成就] 计算定义指纹失败: {e}')
        return (0, 0)


def _load_json(v):
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return None


def _load_definitions():
    rows = achievements_repo.list_active_definitions() or []

    defs = []
    for r in rows:
        defs.append({
            'key':            r['key'],
            'name':           r['name'],
            'desc':           r.get('description') or '',
            'category':       r.get('category') or 'permanent',
            'icon':           r.get('icon') or 'fa-trophy',
            'icon_url':       r.get('icon_url') or None,
            'rarity':         r.get('rarity') or 'common',
            'checker':        r['checker'],
            'checker_params': _load_json(r.get('checker_params')) or {},
            'target':         int(r.get('target') or 1),
            'reward':         _load_json(r.get('reward')) or [],
            'reward_text':    r.get('reward_text') or '',
            'window_start':   str(r['window_start']) if r.get('window_start') else None,
            'window_end':     str(r['window_end'])   if r.get('window_end')   else None,
            # ★ is_hidden: 0=公开  1=半隐藏(???)  2=完全隐藏
            'is_hidden':      int(r.get('is_hidden') or 0),
        })
    return defs


def ensure_definitions():
    global _defs, _def_fingerprint
    fp = _fingerprint()
    if fp == _def_fingerprint and _defs:
        return len(_defs)
    _defs = _load_definitions()
    _def_fingerprint = fp
    logger.info(f'[成就] 定义已刷新，共 {len(_defs)} 条')
    return len(_defs)


def reload_definitions():
    global _def_fingerprint
    _def_fingerprint = None
    return ensure_definitions()


# ============================================================
# 周期
# ============================================================
def _period_key(d):
    cat = d['category']
    if cat == 'daily':
        return 'daily:' + datetime_fmt.today()
    if cat == 'limited':
        end = d.get('window_end')
        if end:
            return 'limited:' + end
        return 'limited:unknown'
    return 'permanent'


def _in_window(d):
    if d['category'] != 'limited':
        return True
    today = datetime_fmt.today()
    if d.get('window_start') and today < d['window_start']:
        return False
    if d.get('window_end') and today > d['window_end']:
        return False
    return True


# ============================================================
# 评定
# ============================================================
def evaluate_user(user_id, force=False):
    ensure_definitions()

    if not user_id:
        return []

    now = time.time()
    if not force and now - _last_eval.get(user_id, 0) < EVAL_DEBOUNCE_SECONDS:
        return []
    _last_eval[user_id] = now

    if not _defs:
        return []

    newly = []
    for d in _defs:
        try:
            if not _in_window(d):
                continue

            period = _period_key(d)

            cur = achievements_repo.get_progress_state(user_id, d['key'], period)

            if cur and cur['completed_at']:
                continue

            fn = checkers.get(d['checker'])
            if not fn:
                logger.warning(f'[成就] 未知 checker: {d["checker"]} (key={d["key"]})')
                continue

            progress = int(fn(user_id, d['checker_params']) or 0)

            completed = progress >= d['target']
            completed_at = datetime_fmt.now() if completed else None

            achievements_repo.upsert_progress(
                user_id, d['key'], period, progress, d['target'],
                completed_at, datetime_fmt.now(),
            )

            if completed and (not cur or not cur['completed_at']):
                _grant_and_notify(user_id, d)
                newly.append(d['key'])

        except Exception as e:
            logger.exception(f'[成就] 评定失败 user={user_id} key={d["key"]}: {e}')
            continue

    return newly


def evaluate_all():
    ensure_definitions()
    rows = achievements_repo.list_evaluable_user_ids() or []
    total = len(rows)
    logger.info(f'[成就] 开始全量评定，共 {total} 个用户')

    done = 0
    for r in rows:
        try:
            evaluate_user(r['id'], force=True)
            done += 1
        except Exception as e:
            logger.exception(f'[成就] 全量评定异常 user={r["id"]}: {e}')

    logger.info(f'[成就] 全量评定完成 {done}/{total}')
    return done


# ============================================================
# 手动授予（供后台调用）
# ============================================================
def grant_achievement_manually(user_id, key):
    """
    人工授予成就（跳过 checker 判定）。
    使用场景：manual.only 类型的成就，需要管理员或业务代码手动标记完成。
    返回 (success: bool, message: str)
    """
    ensure_definitions()

    if not user_id or not key:
        return False, '参数不完整'

    d = next((x for x in _defs if x['key'] == key), None)
    if not d:
        return False, f'成就不存在或未启用: {key}'

    period = _period_key(d)

    cur = achievements_repo.get_completed_at(user_id, key, period)
    if cur and cur['completed_at']:
        return False, '该用户已达成此成就'

    achievements_repo.upsert_manual_completion(
        user_id, key, period, d['target'], d['target'], datetime_fmt.now(),
    )

    _grant_and_notify(user_id, d)
    logger.info(f'[成就] 手动授予 user={user_id} key={key}')
    return True, '已授予'


# ============================================================
# 奖励发放
# ============================================================
def _grant_and_notify(user_id, d):
    granted = _grant(user_id, d['reward'])
    try:
        from utils.messaging.msg import add_system_message, should_notify
        if should_notify(user_id, 'achievement'):
            reward_text = _format_reward(granted)
            add_system_message(
                user_id, 3,
                f'【成就达成】{d["name"]} —— {d["desc"]}{reward_text}'
            )
    except Exception as e:
        logger.exception(f'[成就] 通知失败 user={user_id} key={d["key"]}: {e}')


def _parse_brick_count(cnt):
    if cnt is None:
        return 0
    if isinstance(cnt, (list, tuple)) and len(cnt) == 2:
        try:
            lo = float(cnt[0])
            hi = float(cnt[1])
        except (TypeError, ValueError):
            return 0
        if lo > hi:
            lo, hi = hi, lo
        if lo == int(lo) and hi == int(hi):
            return random.randint(int(lo), int(hi))
        return round(random.uniform(lo, hi), 2)
    try:
        v = float(cnt)
    except (TypeError, ValueError):
        return 0
    if v == int(v):
        return int(v)
    return round(v, 2)


def _grant(user_id, rewards):
    out = []
    for r in rewards or []:
        rtype = r.get('type')

        if rtype == 'brick':
            cnt = _parse_brick_count(r.get('count', 0))
            if cnt:
                interaction_repo.add_brick(user_id, cnt)
            out.append({'type': 'brick', 'result': cnt})

        elif rtype == 'title':
            text = (r.get('text') or '').strip()
            color = (r.get('color') or '#55d88b').strip()
            if not text:
                continue

            row = profiles_repo.get_titles(user_id)
            data = parse_titles(row.get('titles') if row else None)

            if any(it.get('text') == text for it in data.get('list', [])):
                out.append({
                    'type': 'title',
                    'result': {'text': text, 'color': color, 'dup': True}
                })
                continue

            data.setdefault('list', []).append({'text': text, 'color': color})
            if data.get('selected', -1) == -1:
                data['selected'] = len(data['list']) - 1

            profiles_repo.set_titles(
                user_id, json.dumps(data, ensure_ascii=False))
            out.append({'type': 'title', 'result': {'text': text, 'color': color}})

    return out


def _format_reward(granted):
    parts = []
    for g in granted:
        t, r = g.get('type'), g.get('result')
        if t == 'brick' and r:
            if isinstance(r, float) and r == int(r):
                r = int(r)
            parts.append(f'砖块 +{r}')
        elif t == 'title' and isinstance(r, dict) and not r.get('dup'):
            parts.append(f'头衔「{r["text"]}」')
    return '，奖励：' + '、'.join(parts) if parts else ''


# ============================================================
# 展示数据
# ============================================================
def get_user_achievements(user_id):
    ensure_definitions()

    rows = achievements_repo.list_all_for_user(user_id) or []
    pmap = {(r['achievement_key'], r['period_key']): r for r in rows}

    result = []
    for d in _defs:
        period = _period_key(d)
        p = pmap.get((d['key'], period))

        item = {
            'key':          d['key'],
            'name':         d['name'],
            'desc':         d['desc'],
            'icon':         d['icon'],
            'icon_url':     d.get('icon_url'),
            'category':     d['category'],
            'rarity':       d['rarity'],
            'target':       d['target'],
            'progress':     int(p['progress']) if p else 0,
            'completed':    bool(p and p['completed_at']),
            'completed_at': (p['completed_at'].strftime('%Y-%m-%d %H:%M:%S')
                             if p and p['completed_at'] else None),
            'is_hidden':    d['is_hidden'],
            'reward_text':  d.get('reward_text') or '',
        }

        # ★ 三档处理：0=公开  1=半隐藏(???)  2=完全隐藏(不出现)
        hidden_level = int(d.get('is_hidden') or 0)

        if not item['completed']:
            if hidden_level == 2:
                # 完全隐藏：未完成时不返回给前端
                continue
            if hidden_level == 1:
                # 半隐藏：显示占位
                item['name'] = '???'
                item['desc'] = '完成特定条件后解锁'
                item['icon'] = 'fa-question'
                item['icon_url'] = None
                item['reward_text'] = ''

        result.append(item)

    cat_order = {'daily': 0, 'limited': 1, 'permanent': 2}
    result.sort(key=lambda x: (
        x['completed'],
        cat_order.get(x['category'], 9),
        x['key'],
    ))
    return result


def get_all_definitions():
    ensure_definitions()
    return list(_defs)


# ============================================================
# 定时清理
# ============================================================
def cleanup_old_periods(days=7):
    try:
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
        affected = achievements_repo.delete_old_periods('daily:' + cutoff)
        logger.info(f'[成就] 清理过期周期记录 {affected} 条')
        return affected
    except Exception as e:
        logger.exception(f'[成就] 清理过期记录失败: {e}')
        return 0