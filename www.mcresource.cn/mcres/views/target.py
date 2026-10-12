# target.py
from flask import Blueprint, request, abort, render_template

from utils.data.repositories.site import find_external_link
from utils.site.security import get_blacklist, is_domain_match


redirect_bp = Blueprint('redirect', __name__, url_prefix='/target')


@redirect_bp.route('/')
def target():
    h = request.args.get('h')
    if not h:
        abort(400, "Missing hash parameter")

    # 从数据库查询原始链接
    row = find_external_link(h)
    if not row:
        abort(404, "Link not found")

    url = row['url']
    domain = row['domain']

    # 黑名单拦截（支持子域名匹配）
    blacklist = get_blacklist()
    if any(is_domain_match(domain, b) for b in blacklist):
        return render_template('target/blocked.html', domain=domain, url=url), 403

    # 非黑名单：显示确认跳转页
    return render_template('target/redirect_confirm.html', domain=domain, url=url)