# utils/constants.py
"""全站共享的常量与映射 —— 单一真相源。

为什么需要这个模块
------------------
「资源类型 ↔ 数据库表名」这条映射原先在 11 个地方各写了一遍：

    mcres/views/file.py:20            TYPE_TO_TABLE
    mcres/views/api.py:25,152,471     table_map（模块内 3 份）
    mcres/views/detail.py:519
    mcres/views/difference.py:90,124
    mcres/views/profile/profile.py:79,130,364
    utils/interaction.py:13
    utils/hot.py:66
    utils/achievements/checkers.py:21

任何一处漏改都会造成"某个入口的行为和其它入口不一致"，而且这类不一致
不会报错、只会静默出错（例如新增一种资源类型后，只有部分页面能访问到）。
因此收敛到这里，其余位置一律引用。

注意：`RESOURCE_TABLE` 的**键顺序即展示顺序**，部分页面依赖它遍历渲染。
"""

# ============================================================
# 资源类型标识
# ============================================================
TYPE_RESOURCEPACK = 'resourcepack'
TYPE_SHADERPACK = 'shaderpack'
TYPE_MAP = 'map'

# ============================================================
# 数据库表名
# ============================================================
TABLE_RESOURCEPACKS = 'resourcepacks'
TABLE_SHADERPACKS = 'shaderpacks'
TABLE_MAPS = 'maps'

#: 类型 -> 表名（键顺序 = 展示顺序）
RESOURCE_TABLE = {
    TYPE_RESOURCEPACK: TABLE_RESOURCEPACKS,
    TYPE_SHADERPACK: TABLE_SHADERPACKS,
    TYPE_MAP: TABLE_MAPS,
}

#: 表名 -> 类型
TABLE_RESOURCE = {table: rtype for rtype, table in RESOURCE_TABLE.items()}

#: 合法类型集合（供入口校验，替代原先各自的 ALLOWED_TYPES）
RESOURCE_TYPES = frozenset(RESOURCE_TABLE)

#: 类型 -> 中文显示名
RESOURCE_LABEL = {
    TYPE_RESOURCEPACK: '资源包',
    TYPE_SHADERPACK: '光影包',
    TYPE_MAP: '地图',
}


def resource_table(resource_type):
    """类型 -> 表名；非法类型返回 None，由调用方决定回 400 还是 404。"""
    return RESOURCE_TABLE.get(resource_type)


def is_valid_resource_type(resource_type):
    """类型是否合法。"""
    return resource_type in RESOURCE_TABLE
