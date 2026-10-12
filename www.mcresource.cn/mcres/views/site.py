# mcres/views/site.py
from flask import Blueprint, send_from_directory, Response

from utils.data.repositories.resources import (
    SEARCH_TABLES,
    list_ids_and_dates,
    list_recent_for_feed,
)


import os
import time
import traceback
import json
from datetime import datetime

site_bp = Blueprint('site', __name__)

# 站点根 URL（供 sitemap / feed 使用）
BASE_URL = "https://www.mcresource.cn"


# ==================== 通用工具 ====================

def _xml_escape(s):
    """XML 文本转义（用于 <title>、<loc> 等）"""
    if s is None:
        return ''
    return (str(s)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))


def _cdata_safe(s):
    """CDATA 里如果含 ]]> 要拆开，避免破坏 XML"""
    if s is None:
        return ''
    return str(s).replace(']]>', ']]]]><![CDATA[>')


def format_date_iso(date_val):
    """
    将 date_added 转为 YYYY-MM-DD 字符串
    ★ 若值为空，返回 None（调用方应跳过 lastmod 输出）
    """
    if not date_val:
        return None
    if hasattr(date_val, 'strftime'):
        return date_val.strftime('%Y-%m-%d')
    s = str(date_val).split(' ')[0]
    # 简单校验格式
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        return s
    return None


def parse_datetime(date_val):
    """将 date_added 转为 datetime 对象（用于 RSS 排序）"""
    if not date_val:
        return datetime.now()
    if isinstance(date_val, datetime):
        return date_val
    try:
        return datetime.fromisoformat(str(date_val).replace(' ', 'T'))
    except Exception:
        return datetime.now()


def format_rfc822(dt):
    """将 datetime 转为 RSS RFC 822 格式"""
    return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')


# ==================== robots.txt ====================

@site_bp.route('/robots.txt')
def robots_txt():
    """
    优先返回项目根目录下的 robots.txt 静态文件；
    不存在则返回默认内容。
    """
    try:
        return send_from_directory(os.getcwd(), 'robots.txt')
    except FileNotFoundError:
        default_content = f"""User-agent: *
Disallow: /admin/
Disallow: /resourcepack/new
Disallow: /resourcepack/edit/
Disallow: /resourcepack/*/diff
Disallow: /shaderpack/new
Disallow: /shaderpack/edit/
Disallow: /shaderpack/*/diff
Disallow: /shaderpack/*/preset/edit/
Disallow: /map/new
Disallow: /map/edit/
Disallow: /map/*/diff
Disallow: /review
Disallow: /profile/settings
Disallow: /message
Disallow: /login
Disallow: /register
Disallow: /forgot_password
Disallow: /logout
Disallow: /api/
Disallow: /file/upload/
Disallow: /file/edit/
Disallow: /file/delete/
Disallow: /comments
Disallow: /target
Disallow: /captcha
Disallow: /background
Disallow: /suggest
Disallow: /clear_search_history

Allow: /

Sitemap: {BASE_URL}/sitemap.xml
"""
        return Response(default_content, mimetype='text/plain; charset=utf-8')


# ==================== sitemap.xml ====================

@site_bp.route('/sitemap.xml')
def sitemap():
    """动态生成 sitemap.xml（从数据库读取资源）"""
    try:
        static_pages = [
            {'loc': '/',              'priority': '1.0'},
            {'loc': '/resourcepacks', 'priority': '0.9'},
            {'loc': '/shaderpacks',   'priority': '0.9'},
            {'loc': '/maps',          'priority': '0.9'},
            {'loc': '/about',         'priority': '0.7'},
            {'loc': '/development',   'priority': '0.7'},
        ]

        urls = []
        now = time.strftime('%Y-%m-%d')

        # ---------- 静态页面 ----------
        for page in static_pages:
            urls.append({
                'loc': page['loc'],
                'lastmod': now,
                'changefreq': 'weekly',
                'priority': page['priority'],
            })

        # ---------- 三类资源 ----------
        for table, type_prefix in SEARCH_TABLES:
            try:
                rows = list_ids_and_dates(table)
                for row in rows:
                    lastmod = format_date_iso(row.get('date_added'))
                    item = {
                        'loc': f'/{type_prefix}/{row["id"]}',
                        'changefreq': 'monthly',
                        'priority': '0.8',
                    }
                    # ★ 只有真实有日期时才输出 lastmod
                    if lastmod:
                        item['lastmod'] = lastmod
                    urls.append(item)
            except Exception as e:
                print(f"[sitemap] 查询 {table} 失败: {e}")

        # ---------- 生成 XML ----------
        xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        for url in urls:
            xml_parts.append('  <url>')
            # ★ loc 做 XML 转义
            xml_parts.append(f'    <loc>{_xml_escape(BASE_URL + url["loc"])}</loc>')
            if url.get('lastmod'):
                xml_parts.append(f'    <lastmod>{url["lastmod"]}</lastmod>')
            if url.get('changefreq'):
                xml_parts.append(f'    <changefreq>{url["changefreq"]}</changefreq>')
            if url.get('priority'):
                xml_parts.append(f'    <priority>{url["priority"]}</priority>')
            xml_parts.append('  </url>')
        xml_parts.append('</urlset>')

        return Response(
            ''.join(xml_parts),
            mimetype='application/xml; charset=utf-8'
        )

    except Exception as e:
        traceback.print_exc()
        return f"生成 sitemap.xml 时出错：{str(e)}", 500


# ==================== RSS 订阅源 ====================

@site_bp.route('/feed.xml')
def rss_feed():
    """生成 RSS 2.0 订阅源（最新 20 条资源）"""
    try:
        all_items = []

        for table, type_prefix in SEARCH_TABLES:
            rows = list_recent_for_feed(table)
            for row in rows:
                try:
                    content = json.loads(row['content']) if row.get('content') else {}
                    title = content.get('main_name') or f'未命名{type_prefix}'
                    summary = content.get('summary') or ''

                    dt = parse_datetime(row.get('date_added'))
                    pub_date = format_rfc822(dt)

                    all_items.append({
                        'title': title,
                        'link': f'/{type_prefix}/{row["id"]}',
                        'description': summary or title,
                        'pubDate': pub_date,
                        'guid': f'{type_prefix}-{row["id"]}',
                        'dt': dt,
                    })
                except Exception as e:
                    print(f"RSS 处理 {table} id={row['id']} 失败: {e}")
                    continue

        # 按时间倒序，取最新 20 条
        all_items.sort(key=lambda x: x['dt'], reverse=True)
        all_items = all_items[:20]

        now_rfc = format_rfc822(datetime.now())

        xml_parts = []
        xml_parts.append('<?xml version="1.0" encoding="UTF-8" ?>')
        xml_parts.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">')
        xml_parts.append('<channel>')
        xml_parts.append('  <title>MCRES 方块工坊 - 最新资源</title>')
        xml_parts.append(f'  <link>{_xml_escape(BASE_URL)}</link>')
        xml_parts.append('  <description>MCRES 最新发布的资源包、光影包和地图</description>')
        xml_parts.append('  <language>zh-cn</language>')
        xml_parts.append(f'  <lastBuildDate>{now_rfc}</lastBuildDate>')
        xml_parts.append(
            f'  <atom:link href="{_xml_escape(BASE_URL)}/feed.xml" '
            f'rel="self" type="application/rss+xml"/>'
        )

        for item in all_items:
            # ★ title 做 XML 转义
            xml_parts.append('  <item>')
            xml_parts.append(f'    <title>{_xml_escape(item["title"])}</title>')
            xml_parts.append(f'    <link>{_xml_escape(BASE_URL + item["link"])}</link>')
            # ★ description 走 CDATA，先处理 ]]>
            xml_parts.append(
                f'    <description><![CDATA[{_cdata_safe(item["description"])}]]></description>'
            )
            xml_parts.append(f'    <pubDate>{item["pubDate"]}</pubDate>')
            xml_parts.append(
                f'    <guid isPermaLink="true">{_xml_escape(BASE_URL + item["link"])}</guid>'
            )
            xml_parts.append('  </item>')

        xml_parts.append('</channel>')
        xml_parts.append('</rss>')

        return Response(
            ''.join(xml_parts),
            mimetype='application/rss+xml; charset=utf-8'
        )

    except Exception as e:
        traceback.print_exc()
        return f"生成 RSS 失败: {str(e)}", 500


# ==================== security.txt ====================

@site_bp.route('/.well-known/security.txt')
@site_bp.route('/security.txt')          # ★ 兼容旧路径
def security_txt():
    content = """Contact: mailto:1399885823@qq.com
Expires: 2027-12-31T23:59:00Z
Acknowledgments: https://www.mcresource.cn/thanks
Preferred-Languages: zh-CN, en
Canonical: https://www.mcresource.cn/.well-known/security.txt
"""
    return Response(content, mimetype='text/plain; charset=utf-8')


# ==================== OpenSearch ====================

@site_bp.route('/opensearch.xml')
def opensearch():
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>MCRES</ShortName>
  <Description>搜索 MCRES 资源包、光影包、地图</Description>
  <InputEncoding>UTF-8</InputEncoding>
  <Url type="text/html" template="{BASE_URL}/search?q={{searchTerms}}"/>
  <Image height="16" width="16" type="image/png">https://img.mcresource.cn/icon/logo/logo.png</Image>
</OpenSearchDescription>"""
    return Response(
        xml,
        mimetype='application/opensearchdescription+xml; charset=utf-8'
    )