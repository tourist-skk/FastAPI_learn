from contextlib import asynccontextmanager

from sqlalchemy import func
import datetime
from pathlib import Path
from fastapi import Depends, FastAPI, Path as FastAPIPath
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, func, Float
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column


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
# as_posix 把 Path 对象转换成用正斜杠 / 分隔的路径字符串。
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_FILE.as_posix()}"





# 1. 创建 SQLite 异步数据库引擎
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=True,       # 可选: 输出SQL日志
    pool_size=10,    # 设置连接池中保持的持久连接数
    max_overflow=20  # 设置连接池允许创建的额外连接数
)

# 2. 定义模型类: 基类 + 表对应的模型类
# 基类： 创建时间、更新时间。
# 书籍类: id、书名、作者、价格、出版社
class Base(DeclarativeBase):
    """所有 ORM 模型类的基类。"""
    # Mapped[datetime] 类型注解：这一列在 Python 里对应 datetime 对象
    # mapped_column(...) 生成一个"列定义"，并告诉 SQLAlchemy 这列的各种规则
    # DateTime: 数据库列的类型是日期时间
    # insert_default=func.now(): 插入新行时，如果没传这个字段，就默认填当前时间
    # default=func.now() 更通用的默认值（插入、更新都适用的兜底）
    # onupdate=func.now(): 只要这行被 UPDATE，就自动把这个字段刷新为当前时间
    create_time:Mapped[datetime] = mapped_column(DateTime,insert_default=func.now(),default=func.now(),comment="创建时间")
    # onupdate: 只要这行被 UPDATE，就自动把这个字段刷新为当前时间
    update_time:Mapped[datetime] = mapped_column(DateTime,insert_default=func.now(),default=func.now(),onupdate=func.now(),comment="更新时间")
    
class Book(Base):
    """书籍类。"""
    __tablename__ = "book"
    # 主键
    # Python 类型和数据库类型不是一回事，也不能直接用。
    # str、float、int、datetime 是 Python 内存里的表示。
    # VARCHAR、FLOAT、INTEGER、DATETIME 是数据库里的存储表示。
    # String、Float、DateTime 这些 SQLAlchemy 类型对象，扮演的是翻译层 / 适配层的角色：
    # 它们把 Python 类型转换为数据库类型，把数据库类型转换为 Python 类型。
    # 例如，String(255) 表示数据库里的 VARCHAR(255) 类型，Float 表示数据库里的 FLOAT 类型。
    # 你只写一次 String(255)，SQLAlchemy 帮你适配不同数据库的语法差异。这就是它和普通 Python 类型最大的区别——它知道怎么"落地"到具体数据库。
    # 这些类型对象还支持索引、默认值、约束等。
    # 例如，index=True 表示创建索引，default=0 表示默认值为 0。
    id: Mapped[int] = mapped_column(primary_key=True, index=True,comment="书籍ID")
    # ython 的 str 没有"长度"概念，但数据库的字符串列通常需要长度、是否可空、索引等约束。这些只能通过 SQLAlchemy 类型对象（String(255)）和 mapped_column 的参数来表达，Python 类型本身表达不了。
    bookname: Mapped[str] = mapped_column(String(255),index=True,comment="书名")
    author: Mapped[str] = mapped_column(String(255),index=True,comment="作者")
    price: Mapped[float] = mapped_column(Float,index=True,comment="价格")
    publisher: Mapped[str] = mapped_column(String(255),index=True,comment="出版社")

# 在FastAPI启动时，创建数据库表
# 3. 从连接池获取异步连接，开启事务，执行ORM操作
# 4. FastAPI启动时，创建数据库表
async def create_db_tables():
    # 从异步引擎获取异步连接，开启事务，执行ORM操作
    # engine.begin() —— 拿连接、开事务
    # engine 是之前创建的异步引擎。engine.begin() 是一个异步上下文管理器：
        # 进入 async with 时：从连接池借一个连接，并开启一个事务，得到 connection（异步连接对象）
        # 退出 async with 时：提交事务、归还连接
    # connection.run_sync(...) —— 在异步连接上跑同步代码
        # Base.metadata.create_all 本身是同步方法，而 connection 是异步连接，不能直接调用同步方法。run_sync() 就是"在异步连接上安全地执行一个同步函数"的桥，它内部在线程池里跑那个同步函数，并把结果用 await 返回。
    # Base.metadata.create_all —— 真正的建表动作
        # 这是最关键的一点。Base.metadata 是一个 MetaData 对象，相当于一张表结构的登记册。
        # 定义 Book 类的那一刻，SQLAlchemy 就自动把 book 这张表的信息——表名、每一列的名字/类型/主键/索引/注释——全部登记进了 Base.metadata
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

# on_event现在属于废弃，建议使用lifespan参数
# asynccontextmanager是 Python 标准库 contextlib 里的装饰器，作用是把一个异步生成器函数（含 yield 的 async def）转换成一个异步上下文管理器，从而可以配合 async with 使用。
# 原理等价于
# async with lifespan(app):
#     # 进入时：执行到 yield 之前
#     # 应用运行中……
#     # 退出时：执行 yield 之后
@asynccontextmanager
# 这里 lifespan 函数接收一个 FastAPI 实例作为参数，返回一个异步上下文管理器。
async def lifespan(app: FastAPI):
    # FastAPI 的 lifespan 参数接收一个异步上下文管理器。它用 yield 把生命周期分成两段：
    # yield 之前 → 应用启动时执行（这里建表）
    # yield 之后 → 应用关闭时执行（这里释放连接）
    # 应用启动时执行
    await create_db_tables()
    yield
    # 应用关闭时释放数据库连接
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def read_root():
    return {"message": "SQLite tables are ready"}
# @app.on_event("startup")
# async def on_startup():
#     await create_db_tables()


# 异步会话工厂
# AsyncSession 已经实现异步上下文管理协议，所以可以直接在 async with 中使用 AsyncSessionLocal() 来获取异步会话
AsyncSessionLocal = async_sessionmaker(
    bind=engine,# 绑定异步引擎
    class_=AsyncSession,# 异步会话类
    expire_on_commit=False,# 提交会话不过期，不会重新查询数据库
)
# 依赖项: 函数
# yield下面的代码的处理时间线
# 你在地址栏访问 /books、刷新页面、点击按钮调用接口 → 每做一次，浏览器就发出一个请求。
# "关闭页面"这个动作本身 → 不会发出任何请求，服务器无从感知。
# ① 客户端发起请求 GET /books
# ② FastAPI 进入 get_db，创建 session
# ③ 执行到 yield，把 session 交给 list_books
# ④ list_books 函数体执行完，生成响应
# ⑤ FastAPI 把响应返回给客户端   ← 这时页面还没"关闭"，但响应已经发完
# ⑥ FastAPI 回到 get_db，执行 yield 之后的代码（关闭 session）
# ⑦ 这次请求彻底结束
async def get_database():
    async with AsyncSessionLocal() as session:
        try:
            yield session  # 返回数据库会话给路由处理函数
            await session.commit()  # 无异常，提交事务
        except Exception:
            await session.rollback()  # 有异常则回滚
            raise
        finally:
            await session.close()  # 关闭会话


# 需求: 查询功能的接口 -> 依赖注入的方式: 创建依赖项获取数据库的会话 + Depends 注入路由处理函数
@app.get("/book/books")
async def get_book_list(
    db: AsyncSession = Depends(get_database)
):
    # 查询所有书籍
    # select(模型类) 是一个 ORM 查询语句。
    # execute() 真正把 SQL 发给数据库执行，返回一个 Result 对象。
    result = await db.execute(select(Book))  # Book 模型类
    # Result 的特点：它按行组织，每一行是一个 Row 对象。即使你只查了一个实体（Book），每一行也被包在 Row 里，形如：
    # Row(1, "Python for Beginners", "John Doe", 2023, "Python for beginners")
    # Row(2, "Python for Advanced Users", "Jane Doe", 2024, "Python for advanced users")
    # ...
    # scalars() 是 Result 的方法，返回一个 ScalarResult。ScalarResult 是一个异步迭代器，每次迭代返回一个值。
    # 当每行只有一个返回值时，把每行从 (Book,) 这种"包了一层"的形式，拆开成直接的 Book 对象。
    # all() 方法把所有值都取出来，返回一个列表。
    books = result.scalars().all()
    return books

@app.get("/book/Onebooks")
async def get_one_book(
    db: AsyncSession = Depends(get_database),
):
    # 查询单条书籍
    # select(模型类) 是一个 ORM 查询语句。
    # execute() 真正把 SQL 发给数据库执行，返回一个 Result 对象。
    result = await db.execute(select(Book))
    book = result.scalars().first()
    return book

@app.get("/book/books/{book_id}")
async def get_book_by_id(
    db: AsyncSession = Depends(get_database),
    book_id: int = FastAPIPath(..., description="书籍ID")
):
    # 查询单条书籍
    # select(模型类) 是一个 ORM 查询语句。
    # execute() 真正把 SQL 发给数据库执行，返回一个 Result 对象。
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalars().first()
    return book