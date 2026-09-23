# FastAPI 学习与实践

本仓库包含两部分内容：一套系统的 **FastAPI 学习笔记**，以及一个前后端分离的 **新闻浏览实战项目**。

- **Tutorial/**：FastAPI 从零到进阶的知识点整理与示例代码。
- **实战项目**：仿今日头条的新闻浏览应用（前端 `xwzx-news` + 后端 `toutiao_backend`）。

---

## 实战项目：新闻浏览项目

一个前后端分离的新闻浏览应用，支持用户注册登录、新闻分类浏览、详情、收藏、浏览历史与 AI 问答等功能。

### 技术栈

| 部分 | 技术与用途 |
| --- | --- |
| 前端 | Vue 3、Vite、Vue Router、Pinia、Vant、Axios、Vue-i18n |
| 后端 | Python 3.11+、FastAPI |
| 数据访问 | SQLAlchemy（异步） |
| 数据库 | SQLite（`aiosqlite`，开发默认）/ MySQL（`aiomysql`，生产） |
| 缓存 | Redis（`redis` 异步客户端） |
| 后端依赖管理 | `uv`（`pyproject.toml` + `uv.lock`） |

### 目录结构

```text
fastApi-learn/
├── README.md                 # 本文件
├── BACKEND_DESIGN.md         # 后端设计与开发约定
├── pyproject.toml            # Python 项目配置与依赖
├── uv.lock                   # Python 依赖锁定文件
├── xwzx-news/                # 新闻浏览前端
├── toutiao_backend/          # 新闻业务后端（FastAPI）
├── files/项目物料/            # 项目物料：接口规范、数据库 SQL、后端设计说明
├── Tutorial/                 # FastAPI 学习笔记
├── database_sqlite.py        # SQLite/SQLAlchemy 学习示例
└── sql/                      # SQL 相关文件
```

后端目录结构：

```text
toutiao_backend/
├── main.py                    # FastAPI 入口：创建应用、注册路由、CORS、异常处理器
├── cache/                     # 缓存封装
│   └── news_cache.py          # 新闻分类、列表缓存的 key 与读写
├── config/                    # 应用配置与基础设施
│   ├── db_conf.py             # 异步引擎、会话工厂、get_db 依赖
│   └── cache_conf.py          # Redis 客户端与通用缓存读写/删除
├── crud/                      # 数据库增删改查
│   ├── users.py               # 用户数据操作
│   ├── news.py                # 新闻、分类数据操作
│   ├── news_cache.py          # 带缓存的数据查询
│   ├── favorite.py            # 收藏数据操作
│   └── history.py             # 浏览历史数据操作
├── models/                    # SQLAlchemy 模型
│   ├── Bases.py               # ORM 基类
│   ├── users.py               # 用户表模型
│   ├── news.py                # 新闻、分类表模型
│   ├── favorite.py            # 收藏关系模型
│   └── history.py             # 浏览记录模型
├── routers/                   # HTTP 路由（按业务模块）
│   ├── users.py               # 注册、登录、资料、密码接口
│   ├── news.py                # 新闻分类、列表、详情接口
│   ├── favorite.py            # 收藏接口
│   └── history.py             # 浏览历史接口
├── schemes/                   # Pydantic 请求与响应结构
│   ├── users.py
│   ├── news.py
│   ├── favorite.py
│   └── history.py
└── utils/                     # 公共工具
    ├── auth.py                # 当前用户解析（token 鉴权依赖）
    ├── security.py            # 密码哈希、令牌生成与校验
    ├── response.py            # 通用成功响应封装
    ├── exception.py           # 业务异常
    └── exception_handlers.py  # 全局异常处理器
```

### 功能模块

- **用户管理**：注册、登录、个人资料查询与更新、密码修改
- **新闻浏览**：分类获取、分页列表、详情、浏览量统计
- **收藏**：添加、取消、列表、清空、状态查询
- **浏览历史**：记录、列表、删除单条、清空
- **AI 问答**：目前前端直接请求外部服务（后续可迁移至后端）

### 本地开发

#### 前端

准备 Node.js 与 npm（版本需与 Vite 兼容）：

```bash
cd xwzx-news
npm install
npm run dev
```

前端 API 基础地址在 `xwzx-news/src/config/api.js` 中配置，当前为 `http://127.0.0.1:8000`。

#### 后端

准备 Python 3.11+ 与 `uv`，在项目根目录安装依赖：

```bash
uv sync
```

后端依赖 Redis 缓存，启动前需先运行 Redis 服务（后端默认连接 `localhost:6379`）：

```bash
redis-server
```

随后启动后端：

```bash
uv run uvicorn toutiao_backend.main:app --reload --host 127.0.0.1 --port 8000
```

启动后可通过 `http://127.0.0.1:8000/docs` 查看接口文档。

### 接口约定

后端统一返回如下结构，前端以 `code === 200` 判断业务成功：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

接口清单与开发约定详见 [BACKEND_DESIGN.md](BACKEND_DESIGN.md)。

---

## FastAPI 学习笔记

`Tutorial/` 目录按主题编号组织，覆盖从基础到进阶的 FastAPI 知识点：

| 范围 | 内容 |
| --- | --- |
| `00-python基础补充` | 类型注解、pathlib、同步与异步、上下文管理器、SQLite、ORM 等 |
| `01-12` | FastAPI 简介、安装、路由、路径/查询/请求体参数、响应类型、异常处理 |
| `13-27` | 中间件、依赖注入、ORM 建表与增删改查、多表查询等 |
| `28` | 实战项目（新闻浏览）项目物料 |

各目录内包含 `.md` 学习笔记与对应的 `main.py` / `database_sqlite.py` 示例代码。

---

## 相关文档

- [BACKEND_DESIGN.md](BACKEND_DESIGN.md)：后端结构、职责与开发约定
- `files/项目物料/01-接口规范文档/`：API 接口规范
- `files/项目物料/02-数据库sql文件/`：数据库 SQL
- `files/项目物料/项目后端设计说明文档.md`：后端设计说明
