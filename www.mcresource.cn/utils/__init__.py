# utils/__init__.py
"""主站共享工具层。

本包原先**没有 `__init__.py`**（靠命名空间包工作），也没有任何地方集中说明
模块职责；30 个模块平铺在根目录，且大量使用两三个字母的缩写名。现已按职责
归入子包。

目录结构
--------
    utils/
        constants.py          全站常量与映射（资源类型 ↔ 表名等）的单一真相源
        db.py                 数据访问的对外别名（实现见 utils/data/）
        hot.py                资源热度评分（纯计算）
        interaction.py        点赞 / 投币 / 收藏
        reset.py              全量重置

        data/                 数据访问层
            pool.py               连接池 + cursor() 上下文管理器
            queries.py            通用 SQL 封装
            repositories/         按领域拆分的查询
                system.py             系统级单例状态（归档）
                resources.py          资源三表
                messages.py           站内信 / 未读计数 / 通知设置
                sessions.py           登录设备会话
        achievements/         成就系统（registry / checkers / engine / rewards …）

        time/                 datetime_fmt（时间格式化）、time_utils（相对时间）
        scheduling/           scheduler（定时任务）、scheduler_manager（调度器）
        imaging/              image_store（图片存取/缩略图）、remote_upload（图床）、
                              avatar（头像生成与着色）
        text/                 emo（表情与正文渲染）、forbidden_words（违禁词）、
                              titles（称号）、sanitize（HTML 清洗，全站唯一配置）
        users/                permissions（登录/角色校验）、sessions（登录设备）、
                              punishment（处罚执行）
        messaging/            msg（站内信/未读）、feed（动态流 + 隐私开关）
        reviews/              review（审核状态与时间线）
        finance/              afdian、afdian_reply（爱发电对接）
        site/                 site_data（站点静态数据）、announce（公告）、
                              anti_fraud（防刷配置）、security（域名黑白名单/外链中间页）

命名变更对照（原文件名缩写不可读）
----------------------------------
    fd.py       -> messaging/feed.py            动态流（feed）
    fbd.py      -> text/forbidden_words.py      违禁词检测
                                                原与 fd.py 仅差一字母，极易看错
    ic.py       -> (已移除，无引用)             data URI 图片压缩
    sts.py      -> site/site_data.py            站点静态数据
                                                原名无实义；edit() 并非"编辑"而是站点配置
    ct_tm.py    -> time/datetime_fmt.py         时间格式化
    op.py       -> users/permissions.py         登录与角色校验、编辑历史
    pnsm.py     -> users/punishment.py          处罚执行器
    helper.py   -> (已移除，与 text/titles.py 重复)
    sv_img.py   -> imaging/image_store.py       图片存取与缩略图 URL

已移除的无引用模块（存档在备份区，非删除）
------------------------------------------
    titles_util.py   与 text/titles.py 的 parse_titles 完全重复
    tasks.py         依赖不存在的 achievements.json，无任何引用
    ban.py           check_ban 已被各视图内联实现取代
    image_compress.py  compress_data_uri 无任何引用

导入约定
--------
· 数据访问一律走 `utils.data.repositories.*`，不要在视图里写 SQL。
· 新增工具模块请放进对应子包，不要直接堆在 utils/ 根目录。
"""
