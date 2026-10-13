# MCRES 主站功能总结

> 对象：**www.mcresource.cn**（主站，Flask + MySQL）。本文基于源码 `www.mcresource.cn/` 整理，不含 admin / sel / tea 子系统。
>
> 规模：106 个 Python 文件、60 个 Jinja2 模板、63 个 JS、58 个 CSS；17 个 Blueprint、128 条路由。

## 一、整体架构

- **应用工厂**：`create_app()`（`mcres/__init__.py`）负责会话配置、日志、IP 库初始化、APScheduler、请求钩子、上下文处理器、错误处理、Blueprint 注册与 CORS。
- **分层**：`mcres/views/*` 为路由层；`utils/*` 为业务工具层；`utils/data/*` 为数据访问层，SQL 全部收敛到 `utils/data/repositories/*`（视图层不写 SQL）。
- **三类核心资源**：资源包 `resourcepack`、光影包 `shaderpack`、地图 `map`；光影包另有子资源「预设」`shaderpack_preset`。类型与表名映射的唯一来源是 `utils/constants.py`。
- **跨站**：通过 `.mcresource.cn` 共享 Session Cookie，配置 CORS 子域白名单（www / admin / sel / tea / img / help + 本地端口）。
- **请求生命周期**：13 个 `before_request` / `after_request` 钩子（见「安全与风控」）。

## 二、账号与登录

- **本地注册**：图形验证码 `/captcha` → 邮箱验证码 `/send_email_code` / `/verify_email_code` → `/register`；限制邮箱域名白名单、密码长度、用户协议勾选。
- **本地登录**：`/login`（账号密码 + 图形验证码）。
- **忘记 / 重置密码**：`/forgot_password`、`/send_reset_code`、`/reset_password`。
- **QQ 登录**：`/login/qq`、`/login/qq/callback`，首次登录进入 `/login/qq/sync` 绑定或 `sync/skip` 跳过。
- **GitHub OAuth 登录**：`/login/github`、`/login/github/callback`、`/login/github/sync`、`sync/skip`。
- **扫码登录**：`/login/qrcode/generate` 生成、`/login/qrcode/scan` 扫码页、`/login/qrcode/status/<qr_id>` 轮询、`/login/qrcode/confirm` 确认、`/login/qrcode/scanned` 已扫通知、`/login/qrcode/login` 换取登录态（另有 `/api/user/<user_id>` 供端上展示）。
- **退出**：`/logout`；协议页 `/terms`、`/privacy`。
- **登录设备会话**：`user_sessions` 记录设备/IP/属地/UA，个人设置中可查看并踢下线（`DELETE /profile/settings/sessions/<id>`）；检测到异地或被踢会强制重新登录。
- **模拟登录（Impersonation）**：管理员可临时以某用户身份浏览，带到期时间，超时自动恢复原账号并提示。
- **账号封禁**：`role = 0` 视为封号；`ban.login` 到期判定走统一解析（兼容多种时间格式），封禁期间登录/评论/编辑分别拦截。

## 三、资源体系

### 3.1 首页与列表
- **首页** `/`：轮播图、热门资源（算法 `get_algorithm_hot` 或后台手动）、最新资源（算法或手动）、三类资源按分类分组并给出总数、活动动态流、公告、随机语录、访问者 IP 属地；按 UA 区分桌面 `index.html` 与移动端 `index_mobile.html`。
- **列表页**：`/resourcepacks`、`/shaderpacks`、`/maps`（资源包按 `category`、光影按 `style`、地图按 `map_type` 分组）。
- **详情页**：`/resourcepack/<id>`、`/shaderpack/<id>`、`/map/<id>`；含浏览量防刷计数、`/pv_trend` 趋势数据、互动区、评论区。

### 3.2 创建与编辑
- **新建**：`/resourcepack/new`、`/shaderpack/new`、`/map/new`。
- **编辑**：`/resourcepack/edit/<id>`、`/shaderpack/edit/<id>`、`/map/edit/<id>`。
- **表单能力**：富文本编辑器（`static/js/lib/editor`）、封面与文件上传、作者字段、HTML 白名单清洗（bleach）、违禁词检测、重复资源检测。
- **提交审核**：写入对应审核队列表，进入公共审核页 `/review?type=...`；支持按资源名/ID/操作类型/时间排序检索，本人可 `/review/recall` 撤回。

### 3.3 版本与差异
- **版本快照**：编辑时写入 `resource_versions`（含改动说明、操作者）。
- **差异对比**：`/<type>/<id>/diff` 版本列表、`/<type>/<id>/diff/compare` 版本对比（三种资源各一套路由）。

### 3.4 光影预设
- 预设列表 `/shaderpack/<id>/presets`、详情 `/shaderpack/<id>/preset/<pid>`、新建 `.../preset/new`、编辑 `.../preset/edit/<pid>`，以及预设的 `diff` 与 `diff/compare`；资源包预览 `/preview/resourcepack/<id>`。

## 四、互动系统

- **点赞 / 投币 / 收藏**：统一入口 `/interaction?type=&id=`，GET 读取计数与当前用户状态，POST 执行 `like` / `coin` / `favorite`。
- **投币规则**：每日上限 10 次、单资源最多 2 次、消耗 1 个「砖块」，作者每次获得 0.1 砖。
- **砖块与名誉**：`brick`（互动货币，可由成就/签到奖励获取）、`reputation`（名誉，满分 100，每日 +3 恢复）；名誉过低触发阶梯处罚。
- **收藏夹**：`/profile/favorites/data` 数据、`/favorites/add` / `/favorites/remove`，以及文件夹增删改 `/favorites/folder`、`/favorites/folder/<folder_id>`。
- **评论系统**：`/comments` 发表/拉取、`/comments/<id>` 删除、`/comments/reaction` 表态、`/comments/reactions` 表态列表、`/comments/emojis` 表情、`/comments/pin` 置顶、`/comments/report` 举报、`/comments/locate` 定位；支持分页、嵌套回复、软删除。
- **违禁词与处罚**：评论命中违禁词 → 扣名誉 → 按名誉区间执行禁言（小时/天）、登录封禁、永久封号，并写入处罚记录与站内通知。

## 五、用户中心（/profile）

- **个人主页** `/profile/<id>`：作品、点赞、收藏、成就、留言板五个标签页；`/profile/<id>/achievements` 重定向到成就页。
- **资料设置**：头像 `/settings/avatar`、昵称 `/settings/nickname`、签名 `/settings/signature`。
- **隐私设置** `/settings/privacy`、**通知设置** `/settings/notifications`。
- **密码修改**：`/settings/pwd`、`/settings/pwd/verify`、`/settings/pwd/reset`。
- **称号（Titles）**：`/settings/titles` 查看、`/settings/titles/select` 佩戴；评论与主页会展示佩戴称号。
- **成就系统**：
  - 规则注册表 `utils/achievements/registry.py`：`RouteTrigger`（按 method + path 正则匹配）与 `EventTrigger`（业务事件），支持聚合、过滤、隐藏。
  - 分类：每日 / 限时 / 永久；奖励类型：砖块、名誉、称号。
  - 隐藏成就：如「为爱发电」（`supporter`，爱发电赞助后授予）。
  - 自动评定：每个请求触发 `evaluate_user`（内部 10 秒防抖）；定时任务每日全量评定并清理过期周期。

## 六、站内消息与通知

- **消息中心** `/message`，分页接口 `/message/page`。
- **未读分类**：回复 `reply`（评论回复 + 评论表态）、系统 `system`、留言板 `board`（他人主页留言）。
- **通知设置过滤**：`reply` / `reaction` / `board` 开关生效，系统消息强制通知。
- **动态流**（`utils/messaging/feed.py`）：首页活动流，带用户隐私开关。
- **跨站未读**：茶室（tea）未读数独立统计。

## 七、搜索

- `/search`：跨三类资源的检索，Python 侧打分后分页。
- `/suggest`：搜索联想建议；`/clear_search_history`：清除搜索历史。

## 八、文件与下载服务

- **图片服务**：`/images/<path>`、`/background`（背景图，按 `sel` / `tea` 子目录）。
- **资源文件**：上传 `/file/upload/<type>/<id>/<filename>`、下载 `/file/download/...`、编辑 `PUT /file/edit/...`、重命名 `PUT /file/rename/...`、删除 `DELETE /file/delete/...`、清除授权 `/file/clear_auth/<type>/<id>`，均做资源归属与权限校验。
- **下载页与令牌**：`/download/<type>/<id>` 下载页（含游客下载配额）、`/download/.../checksum` 校验值、`/download/.../request_download` 申请下载；下载链接使用 HMAC-SHA256 签名令牌，5 分钟有效。
- **图片工具**：缩略图与图床远程上传（`utils/imaging`）、头像生成与着色。
- **后台域调用鉴权**：admin 通过 `X-API-Key` + `X-User-Id` 调用文件接口。

## 九、开放 API（/api）

- `/api/mcmod/<type>/<id>`：按 MCRES 类型+ID 反查 mcmod_id。
- `/api/resource_by_mcmod/<mcmod_id>`：按 mcmod_id 反查资源。
- `/api/bhl/lookup`、`/api/bhl/detail/<type>/<id>`：BHL 机器人查询。
- `/api/rules/list`、`/api/shader/styles`：规则与光影风格数据。
- `/api/shader/submit`、`/api/resourcepack/submit`：机器人提交/更新资源。
- `/api/check_duplicate`：资源重复检测。
- 接口密钥经环境变量读取（源码中硬编码兜底值已脱敏为占位符）。

## 十、站点、SEO 与外链安全

- **SEO / 站点文件**：`/robots.txt`、`/sitemap.xml`、`/feed.xml`、`/opensearch.xml`、`/.well-known/security.txt`（兼容 `/security.txt`）。
- **规则页**：`/rule/<rule_key>`，含版本列表 `/rule/<rule_key>/versions` 与单版本 `/rule/<rule_key>/version/<version>`。
- **外链安全中间页**：`/target/?h=<hash>`，先查库取原始域名，命中黑名单（支持子域匹配）则拦截，否则展示确认跳转页；正文外链会被自动加新窗口打开并把非白名单域名改写成中间页。
- **关于与更新日志**：`/about` 跳转帮助站；`/development` 展示更新日志。
- **公告**：`site_announcements` 表中生效期内公告在首页与维护页展示。
- **支持页**：`/support` 展示爱发电月度收支、支出分配、收入/支出明细与分页；`/webhook/afdian` 接收支付回调（验签 → 幂等 → API 二次校验 → 入库 → 授予隐藏成就 → 异步生成 AI 回复）。

## 十一、安全与风控

- **IP 归属地**：启动时初始化 ip2region / geoip2 库（30 天自动更新），页面展示省/市。
- **IP 黑白名单**：白名单直接放行；黑名单命中返回 403 封禁页并记录命中次数；图片等域按 `BAN_EXCLUDED_HOSTS` 豁免。
- **限流与入侵检测**：请求窗口限流（`RATE_WINDOW_SECONDS` / `RATE_MAX_REQUESTS`）、敏感路径扫描检测、恶意 User-Agent 拦截、4xx 洪水检测（`FOURXX_WINDOW_SECONDS` / `FOURXX_MAX_COUNT`），违规累计写入 IP 规则表。
- **浏览量防刷**：会话窗口 + 全局窗口两级节流（配置来自 `site_config`，60 秒缓存）。
- **维护模式**：`STOP` 环境变量开启后除静态/验证码/登录外全部 503 到维护页，`role = 4` 管理员仍可登录。
- **会话安全**：`session_token` 设备校验、模拟登录到期、封禁检查、根域 `mcresource.cn` 301 到 `www`。
- **内容安全**：HTML 白名单清洗、违禁词库、外链黑白名单与中间页。
- **审计**：`access_log`（访客哈希、属地、状态码、耗时）+ `action_log`（登录、投币奖励等关键动作，含等级与请求数据），控制台与轮转日志。
- **错误页**：403 / 404 / 500 与 IP 封禁页。

## 十二、定时任务（APScheduler）

调度器在应用工厂内启动，每天凌晨执行：

1. 归档全部资源的昨日数据；
2. 保存每日 PV（`resource_view_log` 聚合到 `resource_daily_pv`，保留 365 天）；
3. 名誉恢复 +3（上限 100）；
4. 成就全量评定与过期周期清理；
5. 清理 30 天前软删除评论及其表态（单次最多 2000 条）。

## 十三、前端

- **模板**：Jinja2 服务端渲染，公共组件（导航栏、页脚、评论、互动、搜索联想）与页面模板分层，含移动端首页与错误页。
- **JS**：原生模块化，按 `components / pages / lib` 组织；富文本编辑器、评论组件（抽屉、分页、渲染、事件、滚动）、搜索联想、互动、Toast、分享、Chart.js 图表、天气小组件。
- **CSS**：按页面/组件拆分，共 58 个样式文件。

## 十四、数据领域（按 repository 划分）

- **用户**：`user_info`、`user_sessions`、`user_system_message`、`user_edit_daily`、`user_edit_history`、成就定义与进度。
- **资源**：`resourcepacks` / `shaderpacks` / `maps`、`shaderpack_presets`、`resource_versions`、审核队列表族、`resource_view_log`、`resource_daily_pv`。
- **互动**：`comments`、`comment_reactions`、点赞 / 投币 / 收藏、砖块。
- **站点**：`site_config`、`site_announcements`、`site_rules`、`external_links`、爱发电订单与收支。
- **风控**：`access_log`、`action_log`、`forbidden_log`、IP 黑白名单与违规累计、处罚记录。

## 十五、路由清单（按 Blueprint）

| Blueprint | 前缀 | 主要路由 |
|---|---|---|
| index | / | /、/about、/development、/resourcepacks、/shaderpacks、/maps、/review、/review/recall、/support、/webhook/afdian |
| account | / | /captcha、/register、/login、/logout、/forgot_password、/reset_password、/send_email_code、/verify_email_code、/send_reset_code、/terms、/privacy、/login/qq（callback、sync、sync/skip）、/login/github（callback、sync、sync/skip）、/login/qrcode/generate、scan、status/<qr_id>、confirm、scanned、login、/api/user/<id> |
| api | /api | /mcmod/<type>/<id>、/resource_by_mcmod/<mcmod_id>、/bhl/lookup、/bhl/detail/<type>/<id>、/rules/list、/shader/styles、/shader/submit、/resourcepack/submit、/check_duplicate |
| comment | / | /comments（GET/POST）、/comments/<id>（DELETE）、/comments/reactions、/comments/emojis、/comments/reaction、/comments/pin、/comments/report、/comments/locate |
| detail | / | /resourcepack/<id>、/shaderpack/<id>、/map/<id>、/pv_trend |
| difference | / | /resourcepack/<id>/diff、/shaderpack/<id>/diff、/map/<id>/diff、/<type>/<id>/diff/compare |
| file | / | /images/<path>、/background、/file/upload、download、edit、rename、delete（含 type/id/filename）、/file/clear_auth/...、/download/<type>/<id>、/download/.../checksum、/download/.../request_download |
| interaction | /interaction | /interaction |
| message | / | /message、/message/page |
| preset | / | /preview/resourcepack/<id>、/shaderpack/<id>/preset/new、edit/<pid>、/<pid>、/shaderpack/<id>/presets、.../diff、.../diff/compare |
| resource_create | / | /resourcepack/new、/shaderpack/new、/map/new |
| resource_edit | / | /resourcepack/edit/<id>、/shaderpack/edit/<id>、/map/edit/<id> |
| rule | / | /rule/<rule_key>、/rule/<rule_key>/versions、/rule/<rule_key>/version/<version> |
| search | / | /search、/suggest、/clear_search_history |
| site | / | /robots.txt、/sitemap.xml、/feed.xml、/opensearch.xml、/.well-known/security.txt、/security.txt |
| target | /target | /target/ |
| profile | /profile | /<id>、/<id>/achievements、/favorites/data、add、remove、folder（/<id>）、/settings、notifications、privacy、avatar、nickname、signature、pwd（verify、reset）、titles（select）、sessions（/<id>） |
| （应用级） | / | /maintenance |

## 十六、说明

- 本文依据脱敏后的源码整理；所有密钥均为占位符，配置项通过环境变量注入，源码不含数据库结构，无法直接部署。
- 许可协议：Business Source License 1.1（见 LICENSE）。

