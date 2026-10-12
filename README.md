# MCRES

MCRES（mcresource.cn）主站的前后端源代码：一个用 Flask 编写的 Minecraft 资源站，包含资源发布、审核、评论、消息、用户中心、搜索、文件服务等模块。

> 仓库当前只包含**主站 `www.mcresource.cn`** 的前后端代码；`admin` / `sel` / `tea` 等子系统暂未包含。

## ⚠️ 重要声明

- 本仓库**仅用于学习与交流**，是脱敏后的源码快照，**不能直接部署运行**。
- 上传内容被限制为 `.py` / `.js` / `.css` / `.html` 四类文件；数据库结构（`db_mysql.sql`）、依赖清单（`requirements.txt`）、站点配置（`.env`）、运行时数据（`.json` / `.txt`）与日志均未包含。
- 所有密钥均已脱敏：`mcres/views/api.py`、`mcres/views/file.py` 中硬编码的机器人接口密钥与下载签名密钥已替换为 `CHANGE_ME_*` 占位符，请勿使用。
- 请勿将本项目用于任何生产环境或商业用途，许可条款见下文。

## 目录结构

```
.
├── LICENSE
└── www.mcresource.cn/          # 主站
    ├── app_serve.py            # waitress 生产启动入口
    ├── app_debug.py            # 开发调试入口
    ├── mcres/                  # 应用主体
    │   ├── __init__.py         # create_app() 应用工厂
    │   ├── config.py           # 配置
    │   ├── middleware.py       # 请求钩子 / 会话 / 审计
    │   ├── ip_service.py       # IP 库、黑名单、限流
    │   ├── audit.py            # 行为审计
    │   ├── templating.py       # 模板上下文
    │   ├── views/              # 路由层（按业务拆分 Blueprint）
    │   │   ├── index.py  detail.py  search.py  account.py
    │   │   ├── resource_create.py  resource_edit.py  resource_lists.py
    │   │   ├── comment.py  interaction.py  message.py  preset.py
    │   │   ├── file.py  api.py  rule.py  site.py  target.py  difference.py  image.py
    │   │   └── profile/
    │   ├── static/             # css / js
    │   └── templates/          # 页面模板
    └── utils/                  # 工具与数据访问层
        ├── data/               # 连接池 + 各领域 repository
        ├── users/  reviews/  messaging/  achievements/
        ├── finance/  imaging/  scheduling/  site/  text/  time/
        └── resource_forms/
```

## 技术栈

- Web 框架：Flask 3 + Blueprint
- 数据库：MySQL（PyMySQL + DBUtils 连接池）
- WSGI：waitress
- 调度：APScheduler
- 其他：Pillow（验证码 / 图片）、bleach + BeautifulSoup4（HTML 清洗）、requests、python-dotenv、py-ip2region / geoip2（IP 归属地）

## 代码组织

代码按 `create_app()` 应用工厂组织：`views/` 为路由层，`utils/` 为工具与数据访问层，SQL 收敛在 `utils/data/repositories/*`。由于缺少数据库结构与运行时配置，本仓库中的代码无法直接启动。

## 许可协议

采用 [Business Source License 1.1](LICENSE)：

- **Licensor**：InCloudYtCrane
- **Additional Use Grant**：None（不授予任何生产用途）
- **Change Date**：2030-10-13
- **Change License**：GNU General Public License v2.0 or later

在 Change Date 之前，你可以在**非生产环境**下复制、修改、二次分发本作品用于学习研究；任何生产或商业用途都需要另行获得授权。

## 免责声明

本项目仅供技术学习参考，作者不对因使用本代码产生的任何后果负责。
