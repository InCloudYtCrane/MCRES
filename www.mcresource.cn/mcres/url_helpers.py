# mcres/url_helpers.py
from .config import ASSET_DOMAIN, IMAGE_DOMAIN, ADMIN_DOMAIN, MAIN_DOMAIN


def asset_url(path):
    if not path:
        return ''
    path = path.lstrip('/')
    if ASSET_DOMAIN:
        return f"{ASSET_DOMAIN}/{path}"
    return f"/{path}"


def image_url(path):
    if not path:
        return ''
    path = path.lstrip('/')
    if IMAGE_DOMAIN:
        return f"{IMAGE_DOMAIN}/{path}"
    return f"/{path}"


def admin_url(path=''):
    if not path:
        return ADMIN_DOMAIN or '/admin'
    path = path.lstrip('/')
    if ADMIN_DOMAIN:
        return f"{ADMIN_DOMAIN}/{path}"
    return f"/admin/{path}"


def main_url(path=''):
    if not path:
        return MAIN_DOMAIN
    path = path.lstrip('/')
    return f"{MAIN_DOMAIN}/{path}"