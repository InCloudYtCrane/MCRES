# mcres/config.py
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
VISIT_SALT = os.getenv("VISIT_SALT")
RESET = os.getenv("RESET", 'false')

# ========== 二级域名配置 ==========
ASSET_DOMAIN = os.getenv("ASSET_DOMAIN", "").rstrip('/')
IMAGE_DOMAIN = os.getenv("IMAGE_DOMAIN", "").rstrip('/')
ADMIN_DOMAIN = os.getenv("ADMIN_DOMAIN", "").rstrip('/')
SELECT_DOMAIN = os.getenv("SELECT_DOMAIN", "").rstrip('/')
MAIN_DOMAIN = os.getenv("MAIN_DOMAIN", "https://www.mcresource.cn").rstrip('/')
USE_SUBDOMAIN = bool(ASSET_DOMAIN or IMAGE_DOMAIN or ADMIN_DOMAIN)

# ========== 跨子域 CORS 白名单 ==========
CORS_ALLOWED_ORIGINS = {
    'https://www.mcresource.cn',
    'https://admin.mcresource.cn',
    'https://sel.mcresource.cn',
    'https://tea.mcresource.cn',
    'https://img.mcresource.cn',
    'https://help.mcresource.cn',
    'http://localhost:5000',
    'http://localhost:5001',
    'http://localhost:5002',
    'http://localhost:5003',
    'http://localhost:5004',
    'http://127.0.0.1:5000',
    'http://127.0.0.1:5001',
    'http://127.0.0.1:5002',
    'http://127.0.0.1:5003',
    'http://127.0.0.1:5004',
}

# ========== IP 封禁豁免的子域名 ==========
# 这些子域不参与 IP 封禁检测（图片服务等需要接受公共请求的场景）。
# 多个用逗号分隔，可用环境变量 BAN_EXCLUDED_HOSTS 覆盖。
BAN_EXCLUDED_HOSTS = {
    h.strip().lower()
    for h in os.getenv('BAN_EXCLUDED_HOSTS', 'img.mcresource.cn').split(',')
    if h.strip()
}

# ---------- IP 属地数据库 ----------
IP_DB_DIR = os.path.join(os.getcwd(), 'mcres', 'data')
IP_DB_PATH = os.path.join(IP_DB_DIR, 'ip2region.xdb')
IP_DB_URL = os.environ.get('IP_DB_URL', 'https://ip.adysec.com/ip2region/ip2region.xdb')
IP_DB_MAX_AGE_DAYS = 30

# ---------- IP 黑名单文件 ----------
# 注意：旧版本用的 ip_blacklist.txt 已废弃，全部迁移到数据库。这里保留常量仅为兼容性。
IP_BLACKLIST_FILE = os.path.join(os.getcwd(), 'ip_blacklist.txt')