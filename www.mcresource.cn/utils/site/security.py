# utils/security.py
import hashlib
import os
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
from utils.data.repositories import site as site_repo

# ---------- 黑白名单文件路径 ----------
WHITELIST_FILE = os.path.join(os.getcwd(), 'web_whitelist.txt')
BLACKLIST_FILE = os.path.join(os.getcwd(), 'web_blacklist.txt')

# ---------- 缓存（带文件修改时间） ----------
_whitelist_cache = {'data': set(), 'mtime': 0}
_blacklist_cache = {'data': set(), 'mtime': 0}


def _load_domain_list(filepath):
    """从文件加载域名列表（每行一个，跳过空行和#注释）"""
    domains = set()
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    domain = line.strip()
                    if domain and not domain.startswith('#'):
                        domains.add(domain)
        except Exception as e:
            print(f"⚠️ 读取域名文件失败 ({filepath}): {e}")
    return domains


def _get_cached_list(cache, filepath):
    """获取缓存列表，若文件修改时间变化则重新加载"""
    current_mtime = os.path.getmtime(filepath) if os.path.exists(filepath) else 0
    if current_mtime != cache['mtime']:
        cache['data'] = _load_domain_list(filepath)
        cache['mtime'] = current_mtime
    return cache['data']


def get_whitelist():
    """获取白名单集合"""
    return _get_cached_list(_whitelist_cache, WHITELIST_FILE)


def get_blacklist():
    """获取黑名单集合"""
    return _get_cached_list(_blacklist_cache, BLACKLIST_FILE)


# ---------- 新增：后缀匹配函数 ----------
def is_domain_match(target_domain: str, pattern_domain: str) -> bool:
    """
    检查 target_domain 是否匹配 pattern_domain（支持子域名）
    例如：target='www.github.com', pattern='github.com' → True
          target='evilgithub.com', pattern='github.com' → False
    """
    if target_domain == pattern_domain:
        return True
    # 检查是否以 .pattern_domain 结尾
    if target_domain.endswith('.' + pattern_domain):
        return True
    return False


# ---------- 链接哈希相关 ----------
def normalize_url(url):
    """规范化URL，确保相同资源对应同一哈希"""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    parsed = urlparse(url)
    # 去掉末尾斜杠，但保留根路径 '/'
    path = parsed.path.rstrip('/')
    if not path:
        path = '/'
    # 保留 query 和 fragment（可按需调整）
    normalized = urlunparse((parsed.scheme, parsed.netloc, path, '', parsed.query, parsed.fragment))
    return normalized


def get_or_create_link_hash(url):
    """获取或创建链接哈希，返回哈希值（SHA256）"""
    normalized = normalize_url(url)
    url_hash = hashlib.sha256(normalized.encode()).hexdigest()

    # 1. 尝试查询
    row = site_repo.external_link_exists(url_hash)
    if row:
        return url_hash

    # 2. 不存在则插入
    parsed = urlparse(normalized)
    domain = parsed.netloc.split(':')[0]  # 去掉端口
    site_repo.insert_external_link(url_hash, normalized, domain)
    return url_hash


def process_external_links(html):
    """
    处理 HTML 中的外部链接：
    - 强制添加 target="_blank"
    - 白名单域名（含子域名）-> 保持原链接
    - 非白名单域名 -> 替换为 /target?h={hash}
    """
    if not html:
        return html

    whitelist = get_whitelist()
    soup = BeautifulSoup(html, 'html.parser')

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if href.startswith(('http://', 'https://')):
            # 强制新窗口
            a_tag['target'] = '_blank'
            parsed = urlparse(href)
            domain = parsed.netloc.split(':')[0]

            # 白名单检查（支持子域名匹配）
            if any(is_domain_match(domain, w) for w in whitelist):
                continue  # 保持原链接

            # 非白名单 -> 走中间页 (利用哈希)
            link_hash = get_or_create_link_hash(href)
            new_href = f"/target?h={link_hash}"
            a_tag['href'] = new_href

    return str(soup)