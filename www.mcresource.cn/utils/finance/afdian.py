# utils/afdian.py
"""爱发电工具：验签、API 签名、订单查询、留言解析"""
import os
import json
import time
import base64
import hashlib
import logging

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from utils.data.repositories import site as site_repo

logger = logging.getLogger(__name__)

AFDIAN_USER_ID = os.getenv('AFDIAN_USER_ID', '')
AFDIAN_API_TOKEN = os.getenv('AFDIAN_API_TOKEN', '')
API_BASE = 'https://ifdian.net/api/open'

# 爱发电官方公钥（用于验证 Webhook 签名）
AFDIAN_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwwdaCg1Bt+UKZKs0R54y
lYnuANma49IpgoOwNmk3a0rhg/PQuhUJ0EOZSowIC44l0K3+fqGns3Ygi4AfmEfS
4EKbdk1ahSxu7Zkp2rHMt+R9GarQFQkwSS/5x1dYiHNVMiR8oIXDgjmvxuNes2Cr
8fw9dEF0xNBKdkKgG2qAawcN1nZrdyaKWtPVT9m2Hl0ddOO9thZmVLFOb9NVzgYf
jEgI+KWX6aY19Ka/ghv/L4t1IXmz9pctablN5S0CRWpJW3Cn0k6zSXgjVdKm4uN7
jRlgSRaf/Ind46vMCm3N2sgwxu/g3bnooW+db0iLo13zzuvyn727Q3UDQ0MmZcEW
MQIDAQAB
-----END PUBLIC KEY-----"""


# ============================================================
# Webhook 验签
# ============================================================
def verify_webhook_sign(order, sign_b64):
    """
    验证爱发电 Webhook 推送的 sign。
    sign_str = out_trade_no + user_id + plan_id + total_amount 依次拼接
    """
    if not sign_b64:
        return False
    sign_str = (
        str(order.get('out_trade_no', '')) +
        str(order.get('user_id', '')) +
        str(order.get('plan_id', '')) +
        str(order.get('total_amount', ''))
    )
    try:
        public_key = serialization.load_pem_public_key(
            AFDIAN_PUBLIC_KEY.encode()
        )
        signature = base64.b64decode(sign_b64)
        public_key.verify(
            signature,
            sign_str.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception as e:
        logger.warning(f'[afdian] Webhook 验签失败: {e}')
        return False


# ============================================================
# API 签名（主动调用）
# ============================================================
def _make_api_sign(params_json, ts):
    """
    sign = md5(token + params + ts + user_id)
    params_json 是 JSON 字符串本身
    """
    raw = f'{AFDIAN_API_TOKEN}params{params_json}ts{ts}user_id{AFDIAN_USER_ID}'
    return hashlib.md5(raw.encode()).hexdigest()


def _call_api(endpoint, params_dict):
    """通用 API 调用"""
    if not AFDIAN_USER_ID or not AFDIAN_API_TOKEN:
        raise RuntimeError('爱发电 API 未配置')

    params_json = json.dumps(params_dict, ensure_ascii=False, separators=(',', ':'))
    ts = int(time.time())
    sign = _make_api_sign(params_json, ts)

    payload = {
        'user_id': AFDIAN_USER_ID,
        'params': params_json,
        'ts': ts,
        'sign': sign,
    }
    resp = requests.post(f'{API_BASE}/{endpoint}', json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def query_order(out_trade_no):
    """按订单号查询（用于 Webhook 二次验证）"""
    data = _call_api('query-order', {'out_trade_no': out_trade_no})
    if data.get('ec') != 200:
        return None
    orders = data.get('data', {}).get('list', [])
    return orders[0] if orders else None


# ============================================================
# 留言解析
# ============================================================
import re

_RE_ID = re.compile(r'#([A-Za-z0-9_\u4e00-\u9fa5-]{1,30})')
_RE_MSG = re.compile(r'\*([^\n]*)')


def parse_remark(remark):
    """
    解析留言，返回 (site_id, message)
    格式：#站内ID 换行 *捎话
    """
    if not remark:
        return None, None
    m_id = _RE_ID.search(remark)
    m_msg = _RE_MSG.search(remark)
    site_id = m_id.group(1) if m_id else None
    message = m_msg.group(1).strip() if m_msg else None
    return site_id, message


def resolve_nickname(site_id):
    """
    根据站内 ID 查昵称和头像。
    site_id 可能是数字 ID，也可能是昵称。
    查不到就返回 ('爱心人士', None)。
    """
    if not site_id:
        return '爱心人士', None

    row = None
    if site_id.isdigit():
        row = site_repo.find_user_by_site_id(site_id)
    if not row:
        row = site_repo.find_user_by_nickname(site_id)

    if row:
        return row['nickname'], row.get('avatar')
    return '爱心人士', None


# ============================================================
# 月度统计
# ============================================================
def get_month_income(month_str):
    """month_str 格式：'2026-10'"""
    row = site_repo.month_income(month_str)
    return float(row['total']) if row else 0.0


def get_month_expense(month_str):
    row = site_repo.month_expense(month_str)
    return float(row['total']) if row else 0.0


def get_expense_by_category(month_str):
    """返回 [{'category', 'item_name', 'amount'}, ...]"""
    return site_repo.expense_by_category(month_str) or []


def list_income(page=1, per_page=20):
    """收入列表（分页）"""
    offset = (page - 1) * per_page
    rows = site_repo.income_rows('WHERE status = 2', [], per_page, offset)
    total_row = site_repo.income_count('WHERE status = 2', [])
    total = int(total_row['cnt']) if total_row else 0
    total_pages = max(1, (total + per_page - 1) // per_page)
    return rows, total, total_pages


def list_expense(page=1, per_page=20, month=None):
    """支出列表（分页，可按月筛选）"""
    offset = (page - 1) * per_page
    where = 'WHERE 1=1'
    args = []
    if month:
        where += ' AND expense_month = %s'
        args.append(month)
    rows = site_repo.expense_rows(where, args, per_page, offset)
    total_row = site_repo.expense_count(where, args)
    total = int(total_row['cnt']) if total_row else 0
    total_pages = max(1, (total + per_page - 1) // per_page)
    return rows, total, total_pages