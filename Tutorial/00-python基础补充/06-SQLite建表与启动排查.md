# 06-SQLite建表与启动排查

本篇是 Python 基础知识在第 16 节中的应用，说明配置代码何时执行、建表何时触发以及数据库保存在哪里。

下面保留原补充文档的配置示例（只包含引擎和基类，模型及生命周期代码需另行定义）：

```python
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase


BASE_DIR = Path(__file__).resolve().parent
SQL_DIR = BASE_DIR / "sql"
SQL_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_FILE = SQL_DIR / "fastapi.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_FILE.as_posix()}"


class Base(DeclarativeBase):
    """所有 ORM 模型类的基类。"""

    pass


engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=True,
)
```

执行下面的命令时，FastAPI 会导入脚本并寻找其中的 `app`：

```bash
uv run fastapi dev database_sqlite.py
```

数据库的创建过程分为三个阶段。

## 1. 创建目录

下面的代码位于模块最外层，因此导入 `database_sqlite.py` 时就会执行：

```python
SQL_DIR.mkdir(parents=True, exist_ok=True)
```

它只创建 `sql` 目录，不会创建数据库文件。

## 2. 创建引擎对象

```python
engine = create_async_engine(DATABASE_URL)
```

`create_async_engine()` 只创建包含连接配置的引擎对象。SQLAlchemy 通常采用延迟连接，因此执行这一行时不会立即连接 SQLite，也不一定立即创建 `fastapi.db`。

## 3. 建立连接并创建数据表

真正触发数据库连接和建表的是：

```python
async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)
```

这段代码只有在 `create_db_tables()` 被调用时才会执行。仅仅定义函数不会执行函数体：

```python
async def create_db_tables():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
```

当前项目选择在 FastAPI 启动时调用它，因此必须把 `lifespan` 注册给应用：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_tables()
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
```

如果写成 `app = FastAPI()`，`lifespan()` 只是被定义，却没有交给 FastAPI。应用启动时不会执行 `create_db_tables()`，自然也不会创建数据库和表。

## 4. 确认数据库文件的位置

当前 `database_sqlite.py` 位于项目根目录，并且使用：

```python
BASE_DIR = Path(__file__).resolve().parent
SQL_DIR = BASE_DIR / "sql"
```

因此数据库的实际位置是：

```text
fastApi-learn/sql/fastapi.db
```

`BASE_DIR` 取决于 `database_sqlite.py` 所在的位置，与执行命令时终端所在的目录无关。如果希望数据库出现在 `16-FastAPI进阶-ORM建表/sql` 中，应将脚本放到该小节目录，或者明确修改 `SQL_DIR` 指向该目录。

参考资料：

- [FastAPI Lifespan 文档](https://fastapi.tiangolo.com/advanced/events/)
