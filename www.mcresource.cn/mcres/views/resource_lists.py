# mcres/views/resource_lists.py
"""资源列表页的泛型实现。

背景
----
`/resourcepacks`、`/shaderpacks`、`/maps` 三条路由原先各自写了一遍约 103 行、
结构完全平行的代码（列表过滤、排序、分页、筛选项装配）。三者的差异**只有 5 处**：

    ┌────────────────┬──────────┬────────────────────────┬──────────────┬──────────────┐
    │ 类型           │ 筛选键   │ content 里额外拷出的键 │ settings 键  │ 选项变量名   │
    ├────────────────┼──────────┼────────────────────────┼──────────────┼──────────────┤
    │ resourcepack   │ category │ category               │ resourcepack │ categories   │
    │ shaderpack     │ style    │ style, performance     │ shaderpack   │ styles       │
    │ map            │ map_type │ map_type, player_count │ map          │ map_types    │
    └────────────────┴──────────┴────────────────────────┴──────────────┴──────────────┘

其余（platform/version/status/q 的过滤方式、sort 语义、分页数学、current_filters
与 query_params 的构造）逐字相同。这里把公共部分收敛成一份，差异用描述符表达。

后续
----
本模块目前仍保留原 SQL 原文（`SELECT ... FROM <表> ORDER BY id DESC`），以便
"先去重、再迁数据访问层"分两步独立验证。SQL 迁入
`utils/data/repositories/` 后，本模块将不再出现查询语句。
"""
import json

from flask import render_template, request


from utils.data.repositories.resources import list_for_cards_by_table
from utils.site import site_data

from utils.constants import RESOURCE_TABLE

# 两个硬编码的下拉选项（三条路由原本各写一遍，取值一致）
PLATFORM_OPTIONS = ['java', 'bedrock']
STATUS_OPTIONS = ['active', 'semi', 'inactive', 'unknown']

PER_PAGE = 20


def _content_fields_resourcepack(content):
    return {
        'category': content.get('category', '未分类'),
    }


def _content_fields_shaderpack(content):
    return {
        'style': content.get('style', '未分类'),
        'performance': content.get('performance', ''),
    }


def _content_fields_map(content):
    return {
        'map_type': content.get('map_type', '未分类'),
        'player_count': content.get('player_count', ''),
    }


#: 类型 -> 列表页描述符
LIST_SPECS = {
    'resourcepack': {
        'table': RESOURCE_TABLE['resourcepack'],
        'template': 'resource/list/resourcepacks.html',
        'filter_key': 'category',
        'content_fields': _content_fields_resourcepack,
        'settings_key': 'resourcepack',
        'options_from_settings': 'categories',
        'options_var': 'categories',
    },
    'shaderpack': {
        'table': RESOURCE_TABLE['shaderpack'],
        'template': 'resource/list/shaderpacks.html',
        'filter_key': 'style',
        'content_fields': _content_fields_shaderpack,
        'settings_key': 'shaderpack',
        'options_from_settings': 'styles',
        'options_var': 'styles',
    },
    'map': {
        'table': RESOURCE_TABLE['map'],
        'template': 'resource/list/maps.html',
        'filter_key': 'map_type',
        'content_fields': _content_fields_map,
        'settings_key': 'map',
        'options_from_settings': 'map_types',
        'options_var': 'map_types',
    },
}


# ============================================================
# 纯函数（可独立测试，不依赖请求上下文）
# ============================================================
def parse_filters(filter_key):
    """从当前请求解析筛选条件。"""
    return {
        'primary': request.args.getlist(filter_key),
        'platforms': request.args.getlist('platform'),
        'versions': request.args.getlist('version'),
        'statuses': request.args.getlist('status'),
        'q': request.args.get('q', '').strip(),
        'sort': request.args.get('sort', 'latest'),
    }


def paginate(items, page, per_page):
    """分页数学。

    返回 (page, total_pages, page_items)。`page` 会被夹到合法范围，
    与原实现一致（上一页越界时回落到最后一页）。
    """
    total = len(items)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    return page, total_pages, items[start:start + per_page]


def filter_rows(rows, filters, filter_key, content_fields):
    """按筛选条件过滤数据库行，并转成模板需要的数据结构。

    逐字对应原实现的三段 `for row in rows:` 循环。
    """
    primary = filters['primary']
    platforms = filters['platforms']
    versions = filters['versions']
    statuses = filters['statuses']
    q = filters['q']

    out = []
    for row in rows:
        try:
            content = json.loads(row['content'])
        except Exception:
            continue

        if primary and content.get(filter_key) not in primary:
            continue
        if platforms and not any(p in content.get('platforms', []) for p in platforms):
            continue
        if versions and not any(v in content.get('versions', []) for v in versions):
            continue
        if statuses and content.get('status') not in statuses:
            continue
        if q:
            search_text = (
                content.get('main_name', '') + ' ' +
                content.get('sub_name', '') + ' ' +
                content.get('summary', '') + ' ' +
                content.get('keywords', '')
            ).lower()
            if q.lower() not in search_text:
                continue

        item = {
            'id': row['id'],
            'main_name': content.get('main_name', '未命名'),
            'sub_name': content.get('sub_name', ''),
            'summary': content.get('summary', ''),
            'cover': content.get('cover', ''),
            'authors': content.get('authors', []),
            'platforms': content.get('platforms', []),
            'versions': content.get('versions', []),
            'status': content.get('status', 'unknown'),
            'view_count': row.get('view_count', 0),
            'yesterday_view_count': row.get('yesterday_view_count', 0),
        }
        item.update(content_fields(content))
        out.append(item)

    return out


def sort_items(items, sort):
    """就地排序，与原实现的 sort 语义一致。"""
    if sort == 'hot':
        items.sort(key=lambda x: x['yesterday_view_count'], reverse=True)
    elif sort == 'name':
        items.sort(key=lambda x: x['main_name'])
    return items


def build_filter_context(filters, filter_key):
    """构造 current_filters（键名做了单复数归一，与原实现一致）。"""
    return {
        filter_key: filters['primary'],
        'platform': filters['platforms'],
        'version': filters['versions'],
        'status': filters['statuses'],
        'q': filters['q'],
        'sort': filters['sort'],
    }


# ============================================================
# 视图入口
# ============================================================
def render_resource_list(resource_type='resourcepack'):
    """三条列表路由共用的渲染流程。"""
    spec = LIST_SPECS[resource_type]
    page = request.args.get('page', 1, type=int)

    filters = parse_filters(spec['filter_key'])

    query_params = request.args.copy()
    query_params.pop('page', None)

    sort_params = request.args.copy()
    sort_params.pop('page', None)
    sort_params.pop('sort', None)

    rows = list_for_cards_by_table(spec['table'])
    items = filter_rows(rows, filters, spec['filter_key'], spec['content_fields'])
    sort_items(items, filters['sort'])
    page, total_pages, page_items = paginate(items, page, PER_PAGE)

    settings = site_data.edit()[spec['settings_key']]
    options = settings.get(spec['options_from_settings'], [])

    context = {
        'resource_packs': page_items,
        'total_count': len(items),
        'versions': settings.get('versions', []),
        'platforms': PLATFORM_OPTIONS,
        'statuses': STATUS_OPTIONS,
        'current_filters': build_filter_context(filters, spec['filter_key']),
        'query_params': query_params,
        'sort_params': sort_params,
        'page': page,
        'total_pages': total_pages,
        'per_page': PER_PAGE,
    }
    context[spec['options_var']] = options
    return render_template(spec['template'], **context)
