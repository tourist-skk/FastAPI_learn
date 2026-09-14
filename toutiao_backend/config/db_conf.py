from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent

# 数据库文件统一放在当前目录的 sql 文件夹中
SQL_DIR = BASE_DIR / "sql"
SQL_DIR.mkdir(parents=True, exist_ok=True)
# SQLite 数据库文件的完整路径
DATABASE_FILE = SQL_DIR / "news_app.db"
# 数据库URL
ASYNC_DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_FILE.as_posix()}"
# 数据库连接池大小
MAX_POOL_SIZE = 10
# 数据库连接超时时间
POOL_TIMEOUT = 30

# 1. 创建数据库引擎
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
engine: AsyncEngine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,       # 可选: 输出SQL日志
    pool_size=10,    # 设置连接池中保持的持久连接数
    max_overflow=20  # 设置连接池允许创建的额外连接数
)

# 2.创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,# 绑定数据库引擎
    expire_on_commit=False, # 禁用会话过期
    # 可选: 可以根据需要调整其他参数
    class_=AsyncSession
)


# 3. 依赖项
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

from sqlalchemy import event

# SQLite 默认不强制外键，需在「每个底层连接」建立时开启
# 装饰器：监听数据库引擎的 connect 事件，当连接建立时触发
# 这个函数在每次新底层连接创建时都会执行，所以连接池里的每个连接都被正确配置，不需要手动在每个请求里再开。
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()