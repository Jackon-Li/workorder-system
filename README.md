# 售后工单管理系统

> 面向**内网单机、10 人以内**售后团队的工单系统。把散落在 Excel 里的报修记录，收进一个有编号、有状态、有操作留痕、可多人同时录入的 Web 台账。
> Flask + SQLite + Bootstrap，**零公网依赖**，可在银河麒麟 V10（ARM64）上纯离线部署。

[**在线演示 →**](https://jackon-li.github.io/workorder-system/) ·
[部署说明书](部署说明书.md) ·
[变更记录](CHANGELOG.md)

![version](https://img.shields.io/badge/version-1.0.1-0891b2)
![python](https://img.shields.io/badge/python-3.8%2B-3776ab)
![flask](https://img.shields.io/badge/flask-2.3.3-000000)
![offline](https://img.shields.io/badge/deploy-100%25%20offline-059669)
![platform](https://img.shields.io/badge/arch-aarch64%20%7C%20x86__64-6b7280)
![license](https://img.shields.io/badge/license-MIT-f59e0b)

---

## 一、它解决什么问题

一个 5～10 人的售后小组，用 Excel 记工单，通常会遇到三件事：

| 痛点 | 具体表现 | 本系统的做法 |
|---|---|---|
| **台账会丢** | 文件在个人电脑上，覆盖保存、误删、换人接手就找不到；没人知道哪份是最新的 | 数据统一存在服务端 `db/workorder.db`，浏览器访问，只有一份权威数据 |
| **多人同步麻烦** | 靠发文件、手工合并，同一条工单被两个人改，最后不知道谁的版本对 | 多人同时在线录入，SQLite 开启 WAL，写入互不阻塞；工单编号服务端统一生成 |
| **历史查不到** | 改过什么、谁改的、什么时候完成的，Excel 里没有痕迹 | 每次创建、流转、删除都写操作日志，工单删了日志还在 |

它不追求做“大型 ITSM 平台”：**单机部署、不联网、不调接口、一个人半天能装完**，这是设计前提。

## 二、功能

- **工单管理**：新建 / 编辑 / 查看 / 删除 / 批量删除；工单编号按 `SG + 年月日 + 4 位序号` 自动生成，冲突自动重试
- **四态流转**：`待处理 → 处理中 → 已完成 → 已关闭`，每次流转记录操作人与时间
- **查询筛选**：状态 / 州市 / 优先级三重筛选 + 关键字模糊搜索（编号、单位、联系人、电话），翻页与导出保持同一组条件
- **云南区域联动**：16 个地州、129 个区县，州市与区县二级联动
- **批量导入**：CSV 模板下载、逐行校验、按行号报错；兼容 UTF-8 / GBK / GB18030（Excel 直接另存即可）
- **导出**：当前筛选结果导出 CSV，带 UTF-8 BOM，Excel 打开不乱码
- **数据大屏**：工单趋势、状态分布、故障类型占比、地州分布（ECharts，本地资源）
- **用户与权限**：管理员 / 普通用户两角色，支持新建、重置密码、启停用、删除
- **操作日志**：创建、流转、导入、删除全程留痕；已删工单的日志仍可追溯
- **纯离线**：前端 Bootstrap / jQuery / ECharts / FontAwesome 全部本地化，Python 依赖随包提供 `cp38 + aarch64` 轮子

## 三、在线预览

GitHub Pages 上有一份**纯静态的可交互演示**，用同一套业务规则与云南区域数据重写了前端，直接在浏览器里点：

**<https://jackon-li.github.io/workorder-system/>**

可以试：按状态 / 州市 / 优先级筛选、搜索、翻页、点开工单看详情并流转状态、新建工单（含区域联动）、看数据大屏、模拟批量导入、查操作日志。

> 演示页是**前端模拟**：数据存在浏览器内存里，刷新即还原，不连接任何后端。真实系统以仓库源码为准。
>
> **演示数据全部虚构且已脱敏**：单位名只保留机构类型并以「某」代替（如「某州教育局」），姓名统一用张三 / 李四 / 王五等测试用名，联系电话统一为 `138****0001`～`138****0068` 的掩码占位，**不包含任何真实可拨通号码，也不对应任何真实客户**。数据由固定种子的伪随机数在浏览器内生成，与任何生产库无关。

## 四、技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| Web 框架 | Flask 2.3.3 | 单文件路由，无蓝图分层，便于小团队维护 |
| ORM | Flask-SQLAlchemy 3.1.1 / SQLAlchemy 2.0.36 | 4 张表，无迁移框架 |
| 数据库 | SQLite 3（WAL 模式） | 单文件，无需安装服务，备份即拷贝 |
| 模板 | Jinja2 3.1.6 | 服务端渲染，无前端构建步骤 |
| 前端 | Bootstrap 4.6.2 / jQuery 3.6 / FontAwesome 5.15.4 | 全部存放于 `static/lib/`，不引用 CDN |
| 图表 | ECharts 5.5 | 数据大屏 4 张图 |
| 运行时 | Python 3.8+ | 目标环境为银河麒麟 V10 自带 Python 3.8 |
| 部署 | systemd + 内置 WSGI 服务器 | 内网低并发场景，不额外引入 gunicorn |

## 五、安装与运行

### 5.1 本地快速体验（Windows / macOS / Linux）

```bash
git clone https://github.com/Jackon-Li/workorder-system.git
cd workorder-system

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt     # 有网环境；离线环境见 5.2

python3 install.py                  # 建库 + 初始化管理员
python3 app.py                      # 默认 http://localhost:8000
```

默认账号：`admin / admin123`（首次登录后请立即修改，见「十三、安全边界」）。

> `requirements.txt` 锁定的是 `cp38 + aarch64` 组合。在 Windows / macOS 上安装时 pip 会回落到源码或本机轮子，正常可用；若要严格复现，请用 Python 3.8 + Linux ARM64。

### 5.2 离线部署（银河麒麟 V10 / ARM64）

```bash
# 1) 上传整个目录到服务器
scp -r workorder-system/ user@server:/opt/ticket_system

# 2) 一键安装（建虚拟环境、离线装依赖、建库、装 systemd）
cd /opt/ticket_system
sudo bash scripts/install.sh
```

脚本会依次完成：检查 Python 版本 → 从 `packages/` 离线安装 14 个轮子 → 校验 `import flask` → 初始化数据库 → 注册 `ticket-system.service`。

手动方式等价于：

```bash
cd /opt/ticket_system
python3 -m venv venv
venv/bin/pip install --no-index --find-links=./packages -r requirements.txt
venv/bin/python install.py
venv/bin/python app.py
```

完整的目录规划、防火墙、开机自启、反向代理与排错步骤见 **[部署说明书.md](部署说明书.md)**。

## 六、使用示例

### 6.1 录一张工单

1. 登录后进入「新建工单」，填写接收日期、州市（如 `昆明市`）→ 区县下拉自动变为该州市下辖区县；
2. 填用户单位、联系人、电话、问题现象，选择故障类型与优先级；
3. 是否需要上门选“是”时，补填上门人员与上门日期；
4. 提交后回到列表，编号形如 `SG202610180003`。

### 6.2 流转状态

在工单详情页：`开始处理` → 状态变为“处理中”；`完成工单` → 填写处理详情后变“已完成”；`关闭` → “已关闭”。每次动作都会写一条操作日志。

### 6.3 从 Excel 批量导入

在「批量导入」页下载模板，按表头填写后另存为 CSV（UTF-8 或 GBK 均可）：

```csv
工单编号,接收日期,接收人,省份,州市,区县,用户单位,联系人,联系电话,问题现象,处理详情,故障类型,自定义故障类型,是否需要上门处理,上门人员,上门日期,产品序列号,备注
,2026-10-17,李四,云南省,曲靖市,麒麟区,某某单位,王五,138****0000,打印机卡纸,已清理,硬件故障,,否,,,SN20260101,
```

- 工单编号留空则自动生成；与库中重复会**明确报错**，不会静默换号；
- 缺少必填项时提示“第 N 行：缺少 用户单位、联系人”；
- 导入结果按“成功 N 条 / 失败 M 条”汇总，失败明细逐行列出。

### 6.4 导出与大屏

列表页的「导出 CSV」会带上当前的筛选条件，导出的就是眼前看到的；「数据大屏」支持按日期区间与州市过滤，四张图联动刷新。

## 七、项目结构

```
workorder-system/
├── app.py                     # 全部路由与业务逻辑
├── models.py                  # 4 张表 + 建库与种子数据
├── config.py                  # 数据库路径、HOST/PORT、分页、导入模板字段
├── yunnan_regions.py          # 云南省 16 州 / 129 县
├── install.py                 # 建库、初始化管理员（命令行安装入口）
├── requirements.txt           # 锁定版本（cp38 / aarch64）
├── packages/                  # 14 个离线轮子，离线安装用
├── db/                        # SQLite 数据目录（首次运行生成 workorder.db）
├── templates/                 # 10 个 Jinja2 模板
│   ├── base.html              # 导航 / 侧边栏 / 全局样式
│   ├── login.html
│   ├── ticket_list.html       # 列表 + 筛选 + 分页
│   ├── ticket_create.html     # 新建（区域联动）
│   ├── ticket_detail.html     # 详情 + 状态流转 + 时间线
│   ├── ticket_edit.html
│   ├── dashboard.html         # 数据大屏
│   ├── import.html            # 批量导入
│   ├── histories.html         # 操作日志
│   └── user_list.html         # 用户管理
├── static/
│   └── lib/                   # bootstrap / jquery / echarts / fontawesome（本地）
├── scripts/
│   ├── install.sh             # 离线一键安装
│   └── download_packages.sh   # 在联网机器上重新拉取轮子
├── docs/                      # GitHub Pages 静态演示页
│   ├── index.html
│   └── .nojekyll
├── .github/workflows/pages.yml
├── 部署说明书.md               # 麒麟 V10 部署全流程
├── CHANGELOG.md
└── LICENSE
```

## 八、HTTP 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/login` `/logout` | 登录 / 退出 |
| GET | `/tickets` | 列表（`status` `city` `priority` `search` `page`） |
| GET/POST | `/tickets/create` | 新建工单 |
| GET | `/tickets/<id>` | 工单详情 |
| GET/POST | `/tickets/<id>/edit` | 编辑工单 |
| POST | `/tickets/<id>/start` | 待处理 → 处理中 |
| POST | `/tickets/<id>/complete` | → 已完成（可带处理详情） |
| POST | `/tickets/<id>/close` | → 已关闭 |
| POST | `/tickets/<id>/delete` | 删除工单（保留操作日志） |
| POST | `/tickets/batch_delete` | 批量删除 |
| GET | `/dashboard` | 数据大屏页面 |
| GET | `/api/dashboard/stats` | 大屏数据（`start` `end` `city`） |
| GET | `/export` | 导出 CSV（沿用列表筛选参数） |
| GET | `/export/template` | 下载导入模板 |
| GET/POST | `/import` | 批量导入 |
| GET | `/histories` | 操作日志 |
| GET | `/users` | 用户管理（仅管理员） |
| POST | `/users/create` `/users/<id>/reset_pwd` `/users/<id>/toggle_active` `/users/<id>/delete` | 用户维护 |
| GET | `/api/regions/prefectures` | 地州列表 |
| GET | `/api/regions/counties/<prefecture>` | 指定地州下区县 |
| GET | `/api/fault_types` | 故障类型列表 |

## 九、数据模型

| 表 | 关键字段 | 说明 |
|---|---|---|
| `ticket` | `serial_no` 唯一、`receive_date`、`city/county`、`user_unit`、`contact_person/phone`、`problem_desc`、`solution_detail`、`fault_type`、`need_onsite`、`priority`、`status`、`created_by` | 共 26 列，覆盖工单全字段 |
| `ticket_history` | `ticket_id`、`action`、`operator`、`detail`、`created_at` | 创建 / 流转 / 导入 / 删除记录，删单不清日志 |
| `auth_user` | `username` 唯一、`password_hash`、`display_name`、`is_admin`、`is_active` | 无盐 SHA-256（见安全边界） |
| `fault_type` | `name` 唯一 | 故障类型字典，导入时可自动扩充 |

## 十、配置项

`config.py`：

| 配置 | 默认值 | 说明 |
|---|---|---|
| `HOST` / `PORT` | `0.0.0.0` / `8000` | 启动时读取，改完需重启进程 |
| `SECRET_KEY` | 硬编码字符串 | **上线前务必替换**为随机值 |
| `DB_PATH` | `db/workorder.db` | SQLite 文件位置 |
| `TICKET_PREFIX` | `SG` | 工单编号前缀 |
| `PAGE_SIZE` | `10` | 列表每页条数 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / `admin123` | 仅 `install.py` 初始化时使用 |

运行期还读取环境变量 `TICKET_MAX_UPLOAD`（默认 10 MB）控制上传体积上限。

## 十一、运维

```bash
# 服务
sudo systemctl start|stop|restart|status ticket-system
sudo journalctl -u ticket-system -f

# 备份（WAL 模式下必须带 -wal / -shm，或先停服务）
sudo systemctl stop ticket-system
cp db/workorder.db* /backup/$(date +%Y%m%d)/
sudo systemctl start ticket-system

# 升级：覆盖程序文件，数据库无需迁移
```

## 十二、已知边界

- **并发**：SQLite + 单进程 WSGI，实测 10 线程 × 5 单并发写入全部成功、无 `database is locked`。适合 10 人以内；再往上建议换 PostgreSQL 并引入 gunicorn + 反向代理。
- **浏览器兼容**：面向 Chromium / Firefox / Edge 现代版本，未适配 IE。
- **演示页**：GitHub Pages 只能托管静态文件，因此 `docs/index.html` 是**前端模拟**，不是真实 Flask 服务。真实部署请按第五节操作。
- **平台验证**：依赖已按 `py3.8 + aarch64` 解析通过、轮子标签匹配，但未在麒麟 ARM64 真机跑过端到端；首次上线请按部署说明书 §3.2 做一次 `import flask` 校验。

## 十三、安全边界

本系统按“内网单机、可信用户”设计，**不适合直接暴露到公网**：

- 密码为无盐 SHA-256，无登录失败锁定；
- `SECRET_KEY` 硬编码在 `config.py`；
- 全站 POST 无 CSRF token；
- 默认口令 `admin / admin123`，首次登录不强制改密。

若要过等保或开放到办公网以外，请至少完成：改随机 `SECRET_KEY`、换 `pbkdf2/bcrypt` 哈希、加 CSRF 与失败限流、强制首登改密、前置 Nginx 并启用 HTTPS。

## 十四、发布与在线预览

仓库里有两套东西，各自独立部署：

| 内容 | 目录 | 部署方式 |
|---|---|---|
| Flask 应用 | 仓库根目录 | 拷到服务器上跑 `python3 app.py` |
| 静态演示页 | `docs/` | GitHub Pages（只托管静态文件） |

当前线上地址（已验证 200，且与仓库内 `docs/index.html` 的 sha256 一致）：

**<https://jackon-li.github.io/workorder-system/>**

### 14.1 前置：仓库必须先开一次 Pages（只需一次）

这一步**无法由工作流代劳**。`actions/configure-pages` 的 `enablement: true` 用的是 `GITHUB_TOKEN`，
它没有"创建 Pages 站点"的管理员权限，在全新仓库上会失败，日志里是：

```
Create Pages site failed. Error: Resource not accessible by integration
```

所以新克隆或新 fork 的仓库，第一次发布前要先手工开一次：

**Settings → Pages → Build and deployment → Source** 选 **GitHub Actions**，保存。

> ⚠️ 选完之后如果页面弹出 "Static HTML" 模板卡片并让你点 **Configure**，**不要点**。
> 那会生成 `.github/workflows/jekyll-gh-pages.yml`，它会用 Jekyll 渲染仓库根目录、把 README
> 发布成站点（约 31 KB 的静态页），与 `pages.yml` 争抢同一个部署目标，线上呈现的就不是交互演示页了。
> 本项目已删除该文件；若误点，`git rm .github/workflows/jekyll-gh-pages.yml` 删掉再推一次即可。

### 14.2 部署流程

`.github/workflows/pages.yml` 在 `docs/` 或工作流自身发生变化时触发，四步：

1. **PII 门禁** `python3 scripts/check_pii.py` —— 扫描 `docs/`、README 等公开文件，命中手机号 / 身份证 / 邮箱 / 真实姓名组合就直接失败，工件不会上传（本地可先跑一遍，退出码非 0 即阻断）；
2. `actions/configure-pages@v5` —— 读取（已开启则直接通过）Pages 配置；
3. `actions/upload-pages-artifact@v3` —— 把 `docs/` 打成 Pages 制品；
4. `actions/deploy-pages@v4` —— 发布到 `https://<用户名>.github.io/<仓库名>/`。

Pages 已开启后，日常只需改 `docs/` 并 push，无需再碰设置页。`docs/.nojekyll` 是空文件，
让 Pages 跳过 Jekyll 处理（否则下划线开头的文件会被静默忽略）。

若某次部署失败而代码没变，可在 **Actions → Deploy GitHub Pages → 最近一次运行 → Re-run all jobs** 重试，
不必额外提交。

### 14.3 备选：改为分支部署

不想用 Actions 时也可：**Settings → Pages → Source** 选 **Deploy from a branch**，
Branch 选 `main`、目录选 **`/docs`**，保存后 1～2 分钟出站。此模式下 `pages.yml` 会持续报错
（它仍尝试用 Actions 部署），建议同时把该工作流改为仅 `workflow_dispatch` 手动触发。

### 14.4 自定义域名

在 `docs/` 下新增 `CNAME` 文件，写一行域名（如 `ticket.example.com`），再到域名服务商添加 CNAME 记录指向 `<用户名>.github.io`，最后在 Settings → Pages 勾选 Enforce HTTPS。

> 注意：Pages 只能托管静态资源，**不能运行 Python**。所以演示页是用同一套业务规则重写的前端模拟，数据存在浏览器内存；真实系统必须按第五节部署。

## 十五、许可

[MIT](LICENSE) © 2026 Jackon-Li
