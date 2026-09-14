# 新闻资讯项目后端设计与开发约定

本项目采用前后端分离的方式开发新闻浏览应用：`xwzx-news` 负责页面展示和用户交互，`toutiao_backend` 计划使用 FastAPI 提供接口、业务处理和数据库访问能力。

当前前端已有新闻列表、分类、详情、注册登录、个人资料、收藏、浏览历史和 AI 问答等页面，并包含相关接口调用。`toutiao_backend` 目前为空目录，本文中的后端结构、职责和开发步骤为后续建设约定，尚未实现。

## 技术栈

| 部分 | 技术与用途 |
| --- | --- |
| 前端 | Vue、Vite、Vue Router、Pinia、Vant、Axios |
| 后端 | Python 3.11+、FastAPI |
| 数据访问 | SQLAlchemy 异步 ORM |
| 数据库驱动 | 已声明 `aiosqlite`、`aiomysql`，分别用于 SQLite 和 MySQL；新闻业务数据库尚待配置 |
| 数据验证 | 计划使用 Pydantic 定义请求与响应结构 |
| Python 依赖管理 | 根目录 `pyproject.toml` 和 `uv.lock` |

## 项目结构

```text
fastApi-learn/
├── BACKEND_DESIGN.md         # 后端设计与开发约定
├── pyproject.toml            # Python 项目配置和依赖
├── uv.lock                   # Python 依赖锁定文件
├── xwzx-news/                # 新闻浏览前端
│   ├── src/
│   │   ├── components/       # 公共组件
│   │   ├── views/            # 业务页面
│   │   ├── router/           # 前端路由
│   │   ├── store/            # 状态管理及现有接口调用
│   │   ├── config/           # API 等前端配置
│   │   └── i18n/             # 国际化配置
│   ├── package.json          # 前端依赖和运行脚本
│   └── vite.config.js        # Vite 配置
├── toutiao_backend/          # 新闻业务后端，当前待搭建
├── Tutorial/                 # 现有学习示例
├── database_sqlite.py        # 现有数据库学习示例
├── sql/                      # SQL 相关文件
└── files/                    # 现有文件资源
```

### 后端目录规划

以下为待创建的目录和文件。沿用本项目约定的 `model`、`schemes` 命名。

```text
toutiao_backend/
├── __init__.py
├── main.py                   # FastAPI 入口：创建应用、注册路由和中间件
├── crud/                     # 数据库增、删、改、查
│   ├── __init__.py
│   ├── user.py               # 用户数据操作
│   ├── news.py               # 新闻和分类数据操作
│   ├── favorite.py           # 收藏数据操作
│   └── history.py            # 浏览历史数据操作
├── model/                    # SQLAlchemy 数据库模型
│   ├── __init__.py
│   ├── user.py               # 用户表模型
│   ├── news.py               # 新闻表、分类表模型
│   ├── favorite.py           # 用户与新闻的收藏关系
│   └── history.py            # 用户浏览记录模型
├── routers/                  # 按业务模块组织 HTTP 路由
│   ├── __init__.py
│   ├── user.py               # 注册、登录、个人资料接口
│   ├── news.py               # 新闻列表、分类、详情接口
│   ├── favorite.py           # 收藏相关接口
│   └── history.py            # 浏览历史相关接口
├── schemes/                  # Pydantic 数据验证与序列化
│   ├── __init__.py
│   ├── user.py               # 注册、登录、资料修改及用户响应结构
│   ├── news.py               # 新闻查询参数和响应结构
│   ├── favorite.py           # 收藏请求和响应结构
│   ├── history.py            # 浏览历史请求和响应结构
│   └── response.py           # 公共响应结构
├── utils/                    # 可复用工具和依赖函数
│   ├── __init__.py
│   ├── security.py           # 密码哈希、令牌生成与校验
│   └── dependencies.py       # 当前用户等接口依赖
└── config/                   # 应用配置与基础设施初始化
    ├── __init__.py
    ├── settings.py           # 环境变量、数据库地址、跨域来源等配置
    └── database.py           # ORM 基类、异步引擎、会话工厂和会话依赖
```

### 目录职责

| 目录 | 负责的内容 | 开发约定 |
| --- | --- | --- |
| `crud` | 封装数据库查询、新增、更新、删除操作 | 接收数据库会话和业务参数，返回数据或操作结果；不依赖 HTTP 请求对象 |
| `model` | 定义数据表字段、主外键、索引、唯一约束和关联关系 | 使用 SQLAlchemy 模型表达持久化结构 |
| `routers` | 定义接口路径、HTTP 方法、依赖注入及业务流程 | 调用 CRUD，处理鉴权和业务错误，声明响应结构 |
| `schemes` | 校验请求参数，定义响应字段和序列化规则 | 将新增、修改、查询响应结构按需拆分；用户响应不得包含密码哈希 |
| `utils` | 提供密码处理、令牌处理、当前用户解析等公共能力 | 提取确实可复用的逻辑，避免堆放具体业务接口 |
| `config` | 集中管理运行配置和数据库连接 | 从环境变量读取环境差异和敏感配置，统一提供数据库会话依赖 |

`model` 描述数据如何存储，`schemes` 描述接口如何接收和返回数据，两者分别维护。

## 请求处理流程

以查询新闻列表为例：

1. 前端通过 Axios 请求 `/api/news/list`，携带分类和分页参数。
2. `routers/news.py` 接收请求，通过 `schemes` 定义及 FastAPI 参数约束完成验证。
3. 路由通过依赖注入获取数据库会话，调用 `crud/news.py`。
4. CRUD 使用 `model/news.py` 中的模型执行数据库查询。
5. 路由按照响应结构返回 JSON，前端更新状态并渲染页面。

`main.py` 负责组装应用；数据库会话生命周期由 `config/database.py` 统一管理。事务的提交与回滚边界应保持一致，避免在路由和 CRUD 中重复提交。业务流程变复杂时，可新增 `services/` 承载跨模块业务逻辑。

## 前后端接口约定

前端 API 基础地址位于 `xwzx-news/src/config/api.js`，当前为 `http://127.0.0.1:8000`。

下表根据前端已有调用整理，是后端待实现的接口清单；请求路径和方法应在联调时保持一致。

| 模块 | 方法 | 路径 | 用途 |
| --- | --- | --- | --- |
| 用户 | POST | `/api/user/register` | 注册 |
| 用户 | POST | `/api/user/login` | 登录 |
| 用户 | GET | `/api/user/info` | 获取当前用户资料 |
| 用户 | PUT | `/api/user/update` | 更新个人资料 |
| 用户 | PUT | `/api/user/password` | 修改密码 |
| 新闻 | GET | `/api/news/categories` | 获取分类 |
| 新闻 | GET | `/api/news/list` | 分类、分页获取新闻 |
| 新闻 | GET | `/api/news/detail` | 根据查询参数 `id` 获取新闻详情 |
| 收藏 | GET | `/api/favorite/check` | 查询收藏状态 |
| 收藏 | POST | `/api/favorite/add` | 添加收藏 |
| 收藏 | DELETE | `/api/favorite/remove` | 取消收藏 |
| 收藏 | DELETE | `/api/favorite/clear` | 清空当前用户收藏 |
| 收藏 | GET | `/api/favorite/list` | 获取当前用户收藏列表 |
| 浏览历史 | POST | `/api/history/add` | 记录浏览历史 |
| 浏览历史 | DELETE | `/api/history/delete/{id}` | 删除单条历史记录 |
| 浏览历史 | DELETE | `/api/history/clear` | 清空当前用户浏览历史 |
| 浏览历史 | GET | `/api/history/list` | 获取当前用户浏览历史 |

前端以响应体的 `code === 200` 判断业务成功，后端成功响应应兼容以下结构：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

- 登录和注册成功时，前端读取 `data.token` 和 `data.userInfo`；注册流程目前期望注册后自动登录。
- 新闻、收藏、浏览历史列表读取 `data.list`；分类接口的 `data` 为数组。
- 新闻列表的查询参数使用 `categoryId`、`page`、`pageSize`。
- 当前前端直接将令牌放入 `Authorization` 请求头，没有添加 `Bearer ` 前缀。后端鉴权需要兼容现状；若改用 Bearer 格式，应同步修改前端。
- 数据验证失败、未登录、无权访问、资源不存在等场景应使用合适的 HTTP 状态码，并约定统一错误体。当前前端多处读取 `message`，后端需要在异常处理器中统一映射错误信息。
- 收藏、浏览历史和个人资料操作均须根据已验证的令牌确定当前用户，并按用户隔离数据。

AI 问答页面目前直接请求外部服务。后续可增加后端 AI 路由，将外部服务调用与密钥配置迁移至后端。

## 本地开发

### 安装后端依赖

准备 Python 3.11+ 和 `uv`，在项目根目录执行：

```bash
uv sync
```

后端依赖统一维护在根目录 `pyproject.toml` 中。

### 启动前端

准备与项目 Vite 版本兼容的 Node.js 和 npm，然后执行：

```bash
cd xwzx-news
npm install
npm run dev
```

前端访问地址以 Vite 终端输出为准。在 `xwzx-news` 目录执行 `npm run build` 可构建前端。

### 启动后端（完成基础代码后）

需先实现上述后端目录、数据库配置，以及 `toutiao_backend/main.py` 中的 `app = FastAPI(...)`。当前空目录无法直接启动。

完成后，在项目根目录执行：

```bash
uv run uvicorn toutiao_backend.main:app --reload --host 127.0.0.1 --port 8000
```

保持 FastAPI 默认文档配置时，可通过 `http://127.0.0.1:8000/docs` 查看和调试接口。

联调前，在后端配置允许访问的前端来源，并在 `main.py` 注册 CORS 中间件；来源中的协议、主机和端口应与实际前端地址一致。数据库连接、令牌密钥和外部服务密钥由后端配置读取，示例配置仅保留占位值。

## 建议开发顺序

1. 创建后端包结构，完成应用入口、配置读取、数据库会话管理和路由注册。
2. 定义用户、分类、新闻、收藏和浏览历史模型，确定表关系和建表方式。
3. 完成用户注册、登录、令牌校验和个人资料接口。
4. 完成分类、新闻分页列表和详情接口。
5. 完成收藏与浏览历史接口，验证数据隔离、重复收藏和重复浏览的处理。
6. 对照前端调用联调，检查分页边界、输入验证、错误响应及跨域配置。
7. 根据需要扩展数据库迁移、自动化测试、日志和后端 AI 问答能力。
