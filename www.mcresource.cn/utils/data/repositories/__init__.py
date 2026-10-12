# utils/data/repositories/__init__.py
"""按领域拆分的查询模块。

约定
----
1. **每个函数 = 一次意图明确的查询**，函数名描述业务意图，而不是 SQL 形状
   （`list_top_viewed` 而不是 `select_from_maps`）。
2. 视图里不出现 SQL，也不出现 `%s` 占位符。
3. 参数化一律用 `%s` 占位符；**表名/列名只能来自常量**，绝不拼接用户输入。
4. 返回值是普通 dict / list[dict]（DictCursor 的形状），便于逐步引入领域对象
   而不必一次性改完调用方。
5. 需要多条语句原子完成时，用 `utils.data.cursor()` 拿同一连接的多个游标 ——
   注意当前**尚未引入事务封装**，多写流程仍按原语义执行。

模块划分
--------
    system.py          系统级单例状态（归档状态、今日浏览滚动）
    scheduling.py      定时任务（PV 落表 / 历史补全 / 过期评论清理 / 名誉恢复）
    users.py           用户表 user_info 的读写（角色 / 封禁 / 名誉 / 昵称 / 计数）
    profiles.py        个人主页、收藏夹、编辑统计与历史、资源版本快照
    resources.py       资源主表（三张表按类型键路由）的查询
    resource_forms.py  资源表单（新建 / 编辑）与审核表读写
    presets.py         光影包预设与预设审核
    reviews.py         审核队列表家族
    comments.py        评论与表态
    messages.py        站内信 / 未读计数
    message_center.py  消息中心（回复、表态、茶室通知）
    interaction.py     点赞 / 投币 / 收藏 / 砖块
    achievements.py    成就定义、用户进度、checker 统计
    punishments.py     处罚执行器的落库（forbidden_log）
    ip_rules.py        IP 白 / 黑名单与违规累计
    sessions.py        登录会话
    logging.py         访问日志 / 操作日志
    impersonation.py   模拟登录
    site.py            站点级配置、规则、公告、外链、动态、收支

已达成：`mcres/` 与 `utils/`（除 `data/` 之外）**不再有裸 SQL**，
全部通过本包访问数据库。
"""
