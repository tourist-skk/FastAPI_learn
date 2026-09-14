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
| 数据库 | SQLite（开发）/ MySQL（`aiomysql`，生产） |
| 后端依赖管理 | `uv`（`pyproject.toml` + `uv.lock`） |

### 目录结构

```text
fastApi-learn/
├── README.md                 # 本文件
├── BACKEND_DESIGN.md         # 后端设计与开发约定
├── pyproject.toml            # Python 项目配置与依赖
├── uv.lock                   # Python 依赖锁定文件
├── xwzx-news/                # 新闻浏览前端
├── toutiao_backend/          # 新闻业务后端（FastAPI，待搭建）
├── files/项目物料/            # 项目物料：接口规范、数据库 SQL、后端设计说明
├── Tutorial/                 # FastAPI 学习笔记
├── database_sqlite.py        # SQLite/SQLAlchemy 学习示例
└── sql/                      # SQL 相关文件
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

后端完成基础代码后（`toutiao_backend/main.py` 中创建 `app = FastAPI(...)`）启动：

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
