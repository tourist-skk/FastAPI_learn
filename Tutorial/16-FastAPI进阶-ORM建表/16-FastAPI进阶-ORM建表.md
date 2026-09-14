# 16 · FastAPI 进阶：ORM 建表

## 1. 本节目标

使用异步 SQLAlchemy 和 MySQL 完成下面的建表流程：

```text
安装并启动 MySQL
→ 创建数据库和数据库用户
→ 创建 SQLAlchemy 异步 Engine
→ 定义 ORM 模型类
→ FastAPI 启动时创建表
```

SQLAlchemy 可以根据模型创建表，但不能通过 `Base.metadata.create_all()` 自动创建 MySQL 数据库。因此连接前必须保证 MySQL 服务、数据库和用户已经存在。

## 2. 建表前的准备

当前项目已经安装：

```bash
uv add "sqlalchemy[asyncio]" aiomysql
```

`SQLAlchemy` 提供 ORM 和数据库操作接口，`aiomysql` 是 Python 连接 MySQL 的异步驱动。安装 `aiomysql` 并不等于安装了 MySQL 数据库服务。

### 2.1 安装并启动 MySQL

本地尚未安装 MySQL 时，可以使用 Homebrew 安装 MySQL 8.4 LTS：

```bash
brew install mysql@8.4
brew services start mysql@8.4
```

首次安装后，可以执行安全初始化：

```bash
"$(brew --prefix mysql@8.4)/bin/mysql_secure_installation"
```

进入 MySQL：

```bash
"$(brew --prefix mysql@8.4)/bin/mysql" -u root -p
```

Homebrew 的 `mysql@8.4` 是独立版本，因此这里使用 `brew --prefix` 得到它的实际安装路径。[Homebrew MySQL 8.4](https://formulae.brew.sh/formula/mysql@8.4)

### 2.2 创建数据库和用户

进入 MySQL 后执行：

```sql
CREATE DATABASE fastapi_learn
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

CREATE USER 'fastapi_user'@'127.0.0.1'
    IDENTIFIED BY 'change_me_123';

GRANT ALL PRIVILEGES
    ON fastapi_learn.*
    TO 'fastapi_user'@'127.0.0.1';
```

`CREATE DATABASE` 创建数据库，`CREATE USER` 创建应用专用用户，`GRANT` 只授予该用户访问 `fastapi_learn` 数据库的权限。[MySQL 创建数据库](https://dev.mysql.com/doc/refman/8.4/en/create-database.html)

不要在正式项目中使用示例密码。创建完成后，可以在终端测试连接：

```bash
"$(brew --prefix mysql@8.4)/bin/mysql" \
    -h 127.0.0.1 \
    -u fastapi_user \
    -p fastapi_learn
```

## 3. 代码文件结构

本节将数据库配置、模型和 FastAPI 应用分开：

```text
16-FastAPI进阶-ORM建表/
├── database.py
├── models.py
└── main.py
```

## 4. 第一步：创建数据库引擎

创建 `database.py`：

```python
import os

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    (
        "mysql+aiomysql://fastapi_user:"
        "change_me_123@127.0.0.1:3306/"
        "fastapi_learn?charset=utf8mb4"
    ),
)


class Base(DeclarativeBase):
    pass


engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
)
```

### 4.1 引擎代码解释

连接地址的基本结构是：

```text
数据库类型+驱动://用户名:密码@主机:端口/数据库名
```

本例中的 `mysql+aiomysql` 表示使用 MySQL 方言和 `aiomysql` 异步驱动。

`create_async_engine()` 创建异步 Engine。Engine 保存连接配置并管理连接池，创建 Engine 时通常不会立即连接数据库，第一次执行数据库操作时才会取得连接。

`echo=True` 会在终端显示 SQL，适合学习；正式环境通常关闭。`pool_pre_ping=True` 会在复用连接前检查连接是否仍然有效。

`Base` 是所有 ORM 模型的共同父类，也保存模型对应的表结构信息。

正式项目应通过环境变量提供 `DATABASE_URL`，不要把真实账号和密码提交到代码仓库。

## 5. 第二步：定义模型类

创建 `models.py`：

```python
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
```

### 5.1 模型代码解释

`User(Base)` 表示 `User` 是一个 ORM 模型。`__tablename__ = "users"` 指定数据库表名。

`Mapped[int]` 和 `Mapped[str]` 描述 Python 属性及对应字段的类型。`mapped_column()` 设置字段的数据库规则。

`primary_key=True` 表示主键，`autoincrement=True` 表示自动递增。`unique=True` 添加唯一约束，`index=True` 创建索引，`nullable=False` 表示不允许空值。

`server_default=func.now()` 表示由数据库在新增记录时生成创建时间。

定义模型类时，SQLAlchemy 会把 `users` 表的信息登记到 `Base.metadata` 中，但此时还没有真正向 MySQL 发送建表语句。

## 6. 第三步：应用启动时建表

创建 `main.py`：

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

import models
from database import Base, engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )

    yield

    await engine.dispose()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def read_root():
    return {"message": "tables are ready"}
```

### 6.1 启动代码解释

`import models` 虽然没有直接使用，但不能删除。导入模型后，`User` 对应的表才会登记到 `Base.metadata`；否则 `create_all()` 不知道需要创建哪些表。

`lifespan()` 管理 FastAPI 的启动和关闭过程。`yield` 之前的代码在应用接收请求前执行一次，`yield` 之后的代码在应用关闭时执行一次。

`engine.begin()` 从连接池取得异步连接并开启事务。`connection.run_sync()` 允许异步连接调用同步风格的 `Base.metadata.create_all()`。

`create_all()` 会检查表是否已经存在，只创建缺少的表。建表失败时，应用启动会失败，不会在数据库不可用的情况下继续接收请求。

`engine.dispose()` 在应用关闭时释放连接池中的连接。

FastAPI 当前推荐使用 `lifespan` 管理启动和关闭逻辑；`@app.on_event("startup")` 已经弃用。[FastAPI Lifespan](https://fastapi.tiangolo.com/advanced/events/)

## 7. 启动并检查结果

进入代码所在目录，设置连接地址并启动：

```bash
export DATABASE_URL='mysql+aiomysql://fastapi_user:change_me_123@127.0.0.1:3306/fastapi_learn?charset=utf8mb4'

uv run fastapi dev main.py
```

启动日志中会显示 `CREATE TABLE users`。再次启动时，因为表已经存在，`create_all()` 不会重复创建。

进入 MySQL 后检查表：

```sql
USE fastapi_learn;
SHOW TABLES;
DESCRIBE users;
```

## 8. 建表流程回顾

### 8.1 MySQL 数据库

先启动 MySQL，并创建 `fastapi_learn` 数据库和有权限的应用用户。SQLAlchemy 建表的前提是能够连接这个数据库。

### 8.2 Engine

Engine 确定数据库类型、驱动、地址和连接池配置，是应用访问数据库的入口。

### 8.3 模型

模型类描述表名、字段、类型和约束。导入模型后，表结构会进入 `Base.metadata`。

### 8.4 应用启动

FastAPI 启动时通过异步连接执行 `Base.metadata.create_all`，将 `Base.metadata` 中还不存在的表创建到数据库。

## 9. `create_all()` 的限制

`create_all()` 适合学习、测试和首次建表，但不会自动修改已经存在的表。例如给模型增加一个字段后，再次执行 `create_all()` 不会自动为旧表添加字段。

正式项目应使用 Alembic 管理数据库结构变更。

**记忆：先创建数据库，再创建 Engine；先导入模型，再调用 `create_all()`；FastAPI 使用 `lifespan` 在启动时完成建表。**
