# utils/sanitize.py
"""资源描述的 HTML 清洗 —— 全站唯一的 bleach 配置。

背景
----
这套配置原先在 4 个视图里各存了一份，并且已经漂移：

    new.py / edit.py / preset.py   h2,h3,h4；表格属性只有 `*: style`；
                                   ALLOWED_ATTRIBUTES 声明了 img 却没有 img 标签
    api.py                         h1..h6（多 3 个）；表格有 border/colspan/...
                                   等属性；没有 img 条目

后果是**同一条资源描述走不同入口会得到不同结果**：经 api.py 提交的能保留
h1/h5/h6，经 new.py 提交的会被剥掉。这里合并为一份，取四者的并集作为
"最宽松也最一致"的策略，避免任何既有内容在迁移后突然被清洗掉。

安全说明
--------
新增或放宽任何标签/属性前请先想清楚：
· `data:` 协议是历史遗留（正文里内嵌 base64 图片），它同时也是
  `data:text/html` 的来源。bleach 只按协议白名单放行，不校验 MIME；
  若要收紧，应先确认存量正文不依赖 data URI。
· `style` 属性的取值由 CSSSanitizer 按 ALLOWED_STYLES 逐条过滤，
  不是整串放行。
· bulletproof 的正文重写（把 HTML 换成结构化 segment）属于更大的改动，
  不在本次规范化范围内。
"""
import bleach
from bleach.css_sanitizer import CSSSanitizer

# ============================================================
# 标签
# ============================================================
ALLOWED_TAGS = [
    # 文本
    'p', 'br', 'strong', 'b', 'i', 'em', 'u', 's',
    # 标题（h1/h5/h6 原仅 api.py 放行，这里统一）
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    # 结构
    'blockquote', 'ul', 'ol', 'li', 'hr',
    # 链接与代码
    'a', 'code', 'pre',
    # 容器与排版
    'div', 'span', 'font',
    # 表格
    'table', 'tbody', 'thead', 'tr', 'td', 'th',
    # 图片（原 new/edit/preset 声明了 img 属性却没放行 img 标签，等于摆设；
    # 详见下方 ALLOWED_ATTRIBUTES 里 img 的说明）
    'img',
]

# ============================================================
# 属性
# ============================================================
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'div': ['style', 'class'],
    'span': ['style', 'class'],
    'p': ['style', 'class'],
    'font': ['color', 'size', 'face'],
    'table': ['style', 'class', 'border', 'cellpadding', 'cellspacing',
              'align', 'width'],
    'td': ['style', 'class', 'colspan', 'rowspan', 'align', 'valign', 'width'],
    'th': ['style', 'class', 'colspan', 'rowspan', 'align', 'valign', 'width'],
    'tr': ['style', 'class', 'align', 'valign'],
    '*': ['style'],
}

# ============================================================
# CSS / 协议
# ============================================================
ALLOWED_STYLES = [
    'color', 'background-color', 'font-weight', 'font-style',
    'text-decoration', 'text-align', 'font-size', 'margin', 'padding',
]

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto', 'data']

# 模块级单例：CSSSanitizer 构造有一定开销，没必要每次调用重建
css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)


def sanitize_html(html_content):
    """清洗用户提交的 HTML，剥离白名单外的标签与属性。

    参数为假值（None / 空串）时返回空串，与原先 4 份实现的语义一致。
    """
    if not html_content:
        return ''
    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
        css_sanitizer=css_sanitizer,
    )
