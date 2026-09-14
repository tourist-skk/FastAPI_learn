# 16-FastAPI进阶-ORM建表（SQLite版）

本节使用 **FastAPI + SQLAlchemy 2.0 + SQLite** 完成建表。SQLite 不需要单独安装和启动数据库服务，程序首次连接数据库时会创建数据库文件。

项目结构如下：

```text
16-FastAPI进阶-ORM建表/
├── sql/
│   └── fastapi.db          # 首次启动应用后自动生成
├── database_sqlite.py      # 数据库路径、引擎和 Base
├── models_sqlite.py        # ORM 模型
└── main_sqlite.py          # FastAPI 应用和启动建表逻辑
```

## 一、安装依赖

SQLite 已经包含在 Python 标准库中，但异步访问 SQLite 还需要安装 `aiosqlite`：

```bash
uv add "sqlalchemy[asyncio]" aiosqlite
```

- `sqlalchemy[asyncio]`：提供 SQLAlchemy 的异步功能。
- `aiosqlite`：SQLAlchemy 异步操作 SQLite 时使用的驱动。

当前项目已经安装了这两个依赖，不需要重复安装。

## 二、建表前的处理

### 1. SQLite 不需要提前创建数据库

MySQL 通常需要先执行 `CREATE DATABASE` 创建数据库。SQLite 的数据库就是一个普通文件，只要连接地址指向目标文件，首次连接时就会自动创建它。

不过，SQLite 只负责创建数据库文件，不会自动创建它的上级目录。因此需要先建立 `sql` 目录。

### 2. 创建数据库目录并设置连接地址

新建 `database_sqlite.py`：

```python
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase


# 当前文件所在目录
BASE_DIR = Path(__file__).resolve().parent

# 数据库文件统一放在当前目录的 sql 文件夹中
SQL_DIR = BASE_DIR / "sql"
SQL_DIR.mkdir(parents=True, exist_ok=True)

# SQLite 数据库文件的完整路径
DATABASE_FILE = SQL_DIR / "fastapi.db"

# sqlite：数据库类型
# aiosqlite：异步驱动
# 三个斜杠后面跟数据库文件路径
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_FILE.as_posix()}"


class Base(DeclarativeBase):
    """所有 ORM 模型类的基类。"""

    pass


# 创建 SQLite 异步数据库引擎
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=True,
)
```

参数和变量说明：

- `Path(__file__).resolve().parent`：取得 `database_sqlite.py` 所在目录的绝对路径。
- `SQL_DIR.mkdir(parents=True, exist_ok=True)`：创建 `sql` 目录；目录已经存在时不会报错。
- `DATABASE_FILE`：最终数据库文件为 `sql/fastapi.db`。
- `sqlite+aiosqlite`：使用 SQLite 数据库和 `aiosqlite` 异步驱动。
- `DeclarativeBase`：SQLAlchemy 2.0 提供的声明式模型基类。

这里使用 `__file__` 计算绝对路径，因此无论从哪个目录启动应用，数据库文件都会放到本项目的 `sql` 目录中。

### 3. 创建 SQLite 数据库引擎

SQLite 也需要创建 SQLAlchemy 引擎。上面 `database_sqlite.py` 中的以下代码就是创建引擎的步骤：

```python
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=True,
)
```

- `create_async_engine()`：根据连接地址创建异步数据库引擎。
- `DATABASE_URL`：告诉引擎使用 SQLite、`aiosqlite` 驱动以及数据库文件的位置。
- `echo=True`：在终端输出引擎执行的 SQL，方便学习和调试；生产环境通常设置为 `False`。
- `engine`：后续创建连接、执行建表和创建数据库会话都要使用这个对象。

数据库引擎是 **SQLAlchemy 的统一概念**，MySQL、SQLite、PostgreSQL 等数据库都会使用。不同数据库主要是连接地址和驱动不同：

```python
# SQLite
sqlite_engine = create_async_engine(
    "sqlite+aiosqlite:///sql/fastapi.db"
)

# MySQL
mysql_engine = create_async_engine(
    "mysql+aiomysql://用户名:密码@主机:端口/数据库名"
)
```

如果只使用 Python 标准库中的 `sqlite3.connect()`，可以直接获得数据库连接，不会显式创建 SQLAlchemy 引擎。但是使用 SQLAlchemy ORM 时，引擎负责连接数据库、识别数据库类型并执行 ORM 生成的 SQL，因此仍然需要创建引擎。

### 4. 是否必须使用 `create_async_engine()`

使用 SQLAlchemy ORM 时，通常必须先创建 **SQLAlchemy 引擎**，但不一定非要使用 `create_async_engine()`。选择哪个函数取决于代码使用同步方式还是异步方式。

#### 同步 ORM

同步代码使用 `create_engine()` 和 `Session`：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


engine = create_engine(
    "sqlite:///sql/fastapi.db",
    echo=True,
)

with Session(engine) as session:
    # 在这里执行同步的 ORM 操作
    pass
```

#### 异步 ORM

异步代码使用 `create_async_engine()` 和 `AsyncSession`：

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


engine = create_async_engine(
    "sqlite+aiosqlite:///sql/fastapi.db",
    echo=True,
)

async with AsyncSession(engine) as session:
    # 在这里执行异步的 ORM 操作
    pass
```

本节使用 `aiosqlite`、异步引擎以及 FastAPI 的异步生命周期函数，因此需要 `create_async_engine()`。如果整个数据库操作都采用同步写法，则改用 `create_engine()`。

`sqlite3.connect()` 返回的是 Python SQLite 驱动的原生 `Connection`，不是 SQLAlchemy 的 `Engine`。它可以直接执行原生 SQL，但不能代替上面创建的 SQLAlchemy 引擎来完成常规 ORM 配置。

## 三、定义模型类

模型类一般包括:

1. 基类。继承 `DeclarativeBase`（包含通用属性和字段的映射）
2. 模型类。继承基类，定义数据库表名和字段。


新建 `models_sqlite.py`：

```python
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database_sqlite import Base


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

主要代码说明：

- `User(Base)`：继承 `Base` 后，该类才会成为 SQLAlchemy ORM 模型。
- `__tablename__ = "users"`：指定数据库中的表名。
- `Mapped[int]`、`Mapped[str]`：声明 Python 属性及其类型。
- `mapped_column()`：设置字段对应的数据库列。
- `primary_key=True`：将 `id` 设置为主键。
- `autoincrement=True`：新增数据时自动生成递增的 `id`。
- `unique=True`：该列的值不能重复。
- `index=True`：为该列建立索引。
- `nullable=False`：该列不允许保存空值。
- `server_default=func.now()`：插入数据时，由数据库填写当前时间。

## 四、应用启动时建表

新建 `main_sqlite.py`：

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

# 必须导入模型模块，使 User 模型注册到 Base.metadata
import models_sqlite
from database_sqlite import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时执行
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield

    # 应用关闭时释放数据库连接
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def read_root():
    return {"message": "SQLite tables are ready"}
```

### 1. `lifespan` 的执行时机

`lifespan` 是 FastAPI 管理应用启动和关闭逻辑的方式：

- `yield` 之前的代码在应用启动时执行。
- 应用正常接收和处理请求。
- `yield` 之后的代码在应用关闭时执行。

`FastAPI(lifespan=lifespan)` 表示将这个生命周期函数交给 FastAPI 管理。参数 `app` 是当前的 FastAPI 应用对象，本例没有使用它，但生命周期函数仍然需要接收该参数。

### 2. 建表代码的原理

`Base.metadata` 保存了所有已经导入的模型及其表结构信息。`Base.metadata.create_all` 会检查数据库，并创建尚不存在的表。

因为 `create_all()` 本身是同步方法，而当前使用的是异步连接，所以需要通过：

```python
await connection.run_sync(Base.metadata.create_all)
```

让 SQLAlchemy 在异步连接中安全地执行同步建表逻辑。

`import models_sqlite` 不能删除。只有导入模型模块后，`User` 表的信息才会注册到 `Base.metadata`；否则程序能够启动，但不会创建 `users` 表。

## 五、启动和检查结果

进入本节目录并启动应用：

```bash
cd 16-FastAPI进阶-ORM建表
uv run fastapi dev main_sqlite.py
```

应用第一次启动后，目录中会出现：

```text
sql/fastapi.db
```

可以使用 SQLite 命令行查看数据库：

```bash
sqlite3 sql/fastapi.db
```

进入 SQLite 后执行：

```sql
.tables
.schema users
.quit
```

`.tables` 用于查看所有表，`.schema users` 用于查看 `users` 表的建表结构。

## 六、完整建表流程

1. 安装 SQLAlchemy 和 `aiosqlite`。
2. 创建 `sql` 目录并设置 `sql/fastapi.db` 连接地址。
3. 通过 `create_async_engine()` 创建异步数据库引擎。
4. 创建 `Base`，再定义继承 `Base` 的 ORM 模型。
5. 在 FastAPI 的 `lifespan` 启动阶段执行 `Base.metadata.create_all`。
6. 首次连接时生成数据库文件，并创建尚不存在的数据表。

## 七、注意事项

`create_all()` 适合学习、测试和项目初始化。它只会创建不存在的表，不会自动修改已有表的字段。例如，之后给 `User` 增加一个字段，再次启动应用不会自动把这个字段加入旧表。正式项目通常使用 Alembic 管理数据库结构变更。

SQLite 使用单个文件保存数据，配置简单，适合学习、小型工具、原型和自动化测试。高并发写入或需要复杂数据库管理的项目，通常会使用 MySQL、PostgreSQL 等数据库。

参考资料：

- [SQLAlchemy SQLite 文档](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
- [SQLAlchemy 异步扩展文档](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Lifespan 文档](https://fastapi.tiangolo.com/advanced/events/)
