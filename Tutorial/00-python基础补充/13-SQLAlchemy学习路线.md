# 13-SQLAlchemy学习路线

前面从第 15 节到第 40 节一直在用 SQLAlchemy，但基本是"照着写"：需要查询就抄 `select()`，需要更新就抄 `update()`。本篇不教具体 API，而是补上缺失的整体地图 —— **SQLAlchemy 由哪几块组成、每块各自负责什么、按什么顺序学**。

读完应当能回答这类问题：`db.execute()` 和 `db.add()` 为什么感觉不是一路的？`flush` 和 `commit` 到底差在哪？为什么配置里要写 `expire_on_commit=False`？

本篇的演示均在项目数据库副本上实际运行，输出原样贴出。当前项目使用的版本是 **SQLAlchemy 2.0.52**。

## 一、先建立一个总印象：SQLAlchemy 是两层

这是理解整个库的**第一关键**。SQLAlchemy 不是一个库，而是**两个库叠在一起**：

```mermaid
flowchart TD
    subgraph ORM["ORM 层：面向对象"]
        S[Session 会话<br/>身份映射 · 工作单元 · 对象状态]
        M[Declarative 模型<br/>User / News / UserToken]
    end
    subgraph CORE["Core 层：面向 SQL"]
        E[SQL 表达式语言<br/>select / insert / update / delete]
        T[MetaData 表结构定义]
        G[Engine 引擎<br/>连接池 · 方言 · 事务]
    end
    D[(数据库<br/>SQLite / MySQL / PostgreSQL)]
    S --> M
    M --> T
    S --> E
    E --> G
    T --> G
    G --> D
```

| | Core | ORM |
| --- | --- | --- |
| 关注什么 | 表、列、SQL 语句 | 类、对象、属性 |
| 核心概念 | Engine、MetaData、`select()` | Session、模型类、对象状态 |
| 能不能单独用 | **可以**，很多项目只用 Core | 不行，ORM 建在 Core 之上 |
| 项目里的例子 | `update(User).where(...)` | `user.password = x` |

**ORM 是建在 Core 之上的，不是替代关系。** 用 ORM 的时候，Core 一直在下面工作。

### 为什么这个区分很重要

回看我们踩过的坑，几乎每一个都源于"不知道自己此刻在哪一层"：

| 遇到的问题 | 实际上是哪一层的事 |
| --- | --- |
| `update(User).where(...)` 为什么不需要 `db.add()` | Core 语句，绕过了 ORM 的工作单元 |
| `db.add()` 对查出来的对象是空操作 | ORM 的 Session 状态管理 |
| `Result` / `ScalarResult` 一堆类型 | Core 的结果对象 |
| `PRAGMA foreign_keys` 要挂在 connect 事件上 | Core 的 Engine 连接层 |
| `onupdate=datetime.now` 两种写法都生效 | 定义在 Core 的列上，所以两层都吃得到 |

以后遇到不理解的行为，**先问自己：这是 Core 的行为还是 ORM 的行为？** 这个问题能解决一多半的困惑。

## 二、第一层：Engine —— 谁来连数据库

```python
engine = create_async_engine(
    "sqlite+aiosqlite:///path/to/news_app.db",
    echo=True, pool_size=10, max_overflow=20
)
```

Engine 是整个库的**底座**，一个程序通常只创建一个，全局复用。它管三件事：

### 1. 数据库 URL 怎么读

```text
sqlite  +  aiosqlite  ://  /path/to/news_app.db
  ↑           ↑                    ↑
方言        驱动                 数据库位置
```

换成 MySQL 就是 `mysql+aiomysql://user:pass@localhost:3306/news_app`。**方言决定生成什么 SQL，驱动决定怎么和数据库通信** —— 两者是分开的，同一个方言可以配不同驱动（`pymysql` / `aiomysql` / `asyncmy`）。

### 2. 连接池

`pool_size=10` 表示常驻 10 条连接，`max_overflow=20` 表示高峰期最多再临时开 20 条。建立数据库连接是很贵的操作，连接池让连接可以复用。

用完的连接会**还回池里而不是关闭**。这也是为什么 `PRAGMA foreign_keys` 要挂在 `connect` 事件上 —— 需要在每条**底层连接**建立时执行一次，而不是每次请求执行一次。

### 3. 方言：同一份代码，不同数据库

这是 SQLAlchemy 最核心的价值之一。同一条 Python 语句，编译到不同数据库会生成不同 SQL。实测：

```python
stmt = select(User.username).where(User.id > 1).order_by(User.id.desc()).limit(3)
```

```text
SQLite    : SELECT user.username FROM user WHERE user.id > ? ORDER BY user.id DESC LIMIT ? OFFSET ?
MySQL     : SELECT user.username FROM user WHERE user.id > %s ORDER BY user.id DESC LIMIT %s
PostgreSQL: SELECT "user".username FROM "user" WHERE "user".id > %(id_1)s ORDER BY "user".id DESC LIMIT %(param_1)s
```

注意三处差异：占位符写法不同（`?` / `%s` / `%(name)s`）、标识符引用不同、SQLite 还多补了个 `OFFSET`。这些差异 SQLAlchemy 都替我们处理了。

这意味着本项目如果哪天从 SQLite 换成 MySQL，业务代码基本不用改 —— 改的是 URL 和建表脚本。

### 4. 事件钩子

PRAGMA foreign_keys 是连接级别的设置，不是全局/永久设置。它默认 OFF，每条新建立的底层连接都要重新执行一次 PRAGMA foreign_keys=ON，否则那条连接的外键约束就不生效。

```python
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
```

Engine 暴露了一整套事件，可以在连接建立、语句执行前后插入自己的逻辑。项目里用它开启 SQLite 外键，其他常见用途还有打印慢查询、统计 SQL 次数。

## 三、第二层：SQL 表达式语言 —— 用 Python 写 SQL

### 1. select() 造出来的是对象，不是字符串

这一点很容易误解。实测：

```text
type(stmt) = Select
默认渲染   : SELECT "user".username FROM "user" WHERE "user".id > :id_1 ORDER BY "user".id DESC LIMIT :param_1
```

`select(...)` 返回的是一个 **`Select` 对象**，可以打印、可以继续加条件、可以传来传去。只有真正执行时才会编译成 SQL 字符串。

**调试技巧：任何时候都可以 `print(stmt)` 看它长什么样**，不需要真的连数据库。想看特定数据库的版本就用 `stmt.compile(dialect=sqlite.dialect())`。

### 2. 参数是绑定的，不是拼接的

```python
evil = "'; DROP TABLE user; --"
stmt = select(User).where(User.username == evil)
```

```text
SQL   : SELECT user.id, user.username, user.password, ... FROM user WHERE user.username = ?
参数  : {'username_1': "'; DROP TABLE user; --"}
```

恶意字符串老老实实待在**参数**里，没有进入 SQL 文本。这就是 SQL 注入防护的原理 —— 不是靠"过滤危险字符"，而是靠**语句和数据分离**。

**只要不手写 `text("SELECT ... WHERE name='" + x + "'")` 这种字符串拼接，就不会有注入问题。**

### 3. 语句是可以拆开组合的

```python
stmt = select(News)
if category_id:
    stmt = stmt.where(News.category_id == category_id)
if keyword:
    stmt = stmt.where(News.title.like(f"%{keyword}%"))
stmt = stmt.order_by(News.publish_time.desc()).limit(10)
```

每次 `.where()` 返回一个**新对象**（不修改原来那个），所以可以安全地按条件层层叠加。做动态筛选的接口时这个特性非常有用，比拼 SQL 字符串干净得多。

### 4. 查什么，决定拿回来的是什么形状

这是第 09 节讲结果类型时的核心问题，从"查询写法"角度再看一遍：

```text
select(News)                -> News    完整 ORM 对象，可 .title/.views
select(News.title, .views)  -> Row     行元组 (12504,)，没有 ORM 身份
select(func.count())        -> int     单个标量 403
```

**查整个模型类就拿到 ORM 对象，查具体列就拿到 Row 元组。** 后者不受 Session 管理，改它的值不会写回数据库。取值方法的完整规则见 [09-SQLAlchemy查询结果与取值](09-SQLAlchemy查询结果与取值.md)。

## 四、第三层：模型与元数据 —— 表长什么样

```python
class Base(ModelBase):
    __abstract__ = True
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
```

### 1. Base 背后是 MetaData

所有继承 `DeclarativeBase` 的模型类，会自动把表结构注册到 `Base.metadata` 里。这个 `MetaData` 对象是**所有表的目录**，`create_all()` 就是遍历它来建表的。

`__abstract__ = True` 表示这个类只提供共用字段，自己不对应任何表。

### 2. Mapped 与 mapped_column 分工不同

```python
username: Mapped[str] = mapped_column(String(50), unique=True)
#          ↑ Python 侧类型          ↑ 数据库侧类型和约束
```

- `Mapped[str]`：**类型注解**，告诉编辑器和类型检查器"这个属性在 Python 里是 str"
- `mapped_column(...)`：**列定义**，告诉 SQLAlchemy "数据库里这一列是 VARCHAR(50)、唯一"

`Mapped[Optional[str]]` 或 `Mapped[str | None]` 还会让 SQLAlchemy 自动推断 `nullable=True`。

### 3. default / server_default / onupdate 的区别

这三个很容易混，而且在我们项目里都出现过：

| 参数 | 谁来算 | 什么时候生效 |
| --- | --- | --- |
| `default=datetime.now` | **Python** 算好再发给数据库 | INSERT 时 |
| `server_default=func.now()` | **数据库** 自己算 | INSERT 时 |
| `onupdate=datetime.now` | **Python** 算好再发 | UPDATE 时 |
| `server_onupdate=...` | 数据库自己算 | UPDATE 时（多数库不支持） |

项目里 `Bases.py` 用的是 `default` + `onupdate`，都是 Python 侧计算。而建库 SQL 里写的 `DEFAULT CURRENT_TIMESTAMP` 是数据库侧的默认值 —— **两套机制同时存在**，谁先写上算谁的。

正因为两套机制并存，可能会出现「你以为数据库会刷新，其实没刷新」或反过来。比如纯靠数据库 DEFAULT CURRENT_TIMESTAMP 时，SQLAlchemy 内存里的对象不会自动知道数据库算出来的值（因为值不是 Python 给的），需要 refresh 才能拿到。而用 Python 的 default/onupdate 时，值在内存里就已经有了。这也是为什么项目里更倾向用 Python 侧的 default + onupdate。

这也解释了第 40 节的一个现象：`updated_at` 之所以在 Core 和 ORM 两条路径上都自动刷新，是因为 `onupdate` 定义在 Core 的列对象上，两层都能生效(不管你是用 Core 风格还是 ORM 风格去更新数据，updated_at 都会自动刷新)。所以「自动更新 updated_at」这个规则，被定义在了一个共享的地方（Core 列对象），于是无论哪条路走下来都会碰到它。

* Core 路径（现行 crud/users.py#L114 的写法）：
```python
update(User).where(...).values(password=user_new_password)
```
* ORM 路径（现行 crud/users.py#L120 的写法）：
```python
user.password = user_new_password
```


### 4. 还没用到的：relationship

目前项目里五张表之间的关联（`news.category_id`、`favorite.user_id` 等）都只声明了 `ForeignKey`，**没有声明 `relationship()`**。这意味着：

```python
# 现在只能这样：手动查两次
news = await db.get(News, 1)
category = await db.get(NewsCategory, news.category_id)

# 有了 relationship 之后：
news = await db.get(News, 1)
category = news.category      # 直接顺着对象取
```

这是目前最值得补的一块，详见第八节。

## 五、第四层：Session —— 对象与数据库之间的中间人

Session 是 ORM 的核心，也是最容易用错的地方。它做四件事：

### 1. 身份映射（Identity Map）

**同一个主键，在一个 Session 里只会有一个 Python 对象。** 实测：

```text
两次查询同一行 -> 是同一个对象吗? True   (id=4493316688 / 4493316688)
```

第二次查询不会创建新对象，而是返回缓存里已有的那个。好处是不会出现"同一行数据有两个对象、改了一个另一个还是旧的"这种混乱。

### 2. 工作单元（Unit of Work）与对象四状态

Session 追踪每个对象的状态（transient / pending / persistent / detached），并在 flush 时把所有变更一次性转成 SQL。

这部分在 [40 节](../40-FastAPI项目-修改用户密码/40-FastAPI项目-修改用户密码.md) 第六节已经详细展开过（包括 `db.add()` 到底做什么），这里不重复。

### 3. flush 和 commit 不是一回事

这是最常见的混淆点：

- **flush** = 把内存里的变更**翻译成 SQL 发出去**，但事务还没提交
- **commit** = **提交事务**，让变更对其他连接可见（commit 会自动先 flush）

实测，flush 之后另开一个会话去看：

```text
原始 nickname = '测试用户'
flush 后，另一个会话看到 = '测试用户'   ← 事务未提交，别人看不到
```

这就是为什么项目里 CRUD 层用 `flush()` 而不是 `commit()` —— **让整个请求保持在一个事务里**，由 `get_db()` 统一决定提交还是回滚。

配套的还有两个：

- **refresh** = 重新查库，把对象刷新成数据库里的最新值
- **expire** = 把对象标记为"过期"，下次访问属性时自动重新查

### 4. expire_on_commit 为什么设成 False

项目配置里有这么一行，之前可能没细想：

```python
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
```

`expire_on_commit` 默认是 `True`，意思是 commit 之后把所有对象标记为过期。同步代码下这没问题，下次访问属性会自动重新查。但**异步代码下会直接报错**。实测：

因为你在调用读取属性时，会有隐式IO

```text
expire_on_commit=True  -> commit 后读 u.username 报错: MissingGreenlet
                          （属性已过期，异步下不能隐式重新查库）
expire_on_commit=False -> commit 后读 u.username 成功: 'admin'
```

原因见下一节。在 FastAPI 这种异步项目里，`expire_on_commit=False` 基本是必须的。

## 六、异步版本特殊在哪

### 1. 三个 async 替身

| 同步 | 异步 |
| --- | --- |
| `create_engine` | `create_async_engine` |
| `Session` / `sessionmaker` | `AsyncSession` / `async_sessionmaker` |
| `session.execute()` | `await session.execute()` |

### 2. 核心规则：不能有隐式 IO

`MissingGreenlet` 这个报错，是异步 SQLAlchemy 最常见的坑，根源只有一条：

> **在异步模式下，凡是要访问数据库的操作，都必须显式 `await`。**

而 ORM 有很多地方会**偷偷**访问数据库：

- 访问一个已过期的属性 → 触发重新查询
- 访问一个未加载的 `relationship` → 触发懒加载

这些访问写出来长得像普通的属性读取（`u.username`、`news.category`），没有 `await`，所以异步引擎无法执行，直接抛 `MissingGreenlet`。

应对办法有三个：

1. `expire_on_commit=False` —— 避免 commit 后属性过期（项目已采用）
2. 用 `selectinload()` / `joinedload()` 提前把关联数据查出来 —— 避免懒加载
3. 需要时显式 `await db.refresh(obj)`

### 3. greenlet 是什么

SQLAlchemy 的绝大部分代码是同步写法，异步支持是靠 `greenlet` 库在同步调用栈和异步事件循环之间做桥接实现的。报错信息里的 "greenlet_spawn has not been called" 就是说：这次数据库访问发生在桥接之外，接不上事件循环。

日常使用不需要理解 greenlet 的细节，**只要记住"不能隐式 IO"这条规则即可**。

## 七、学习路线

按依赖顺序分成六个阶段。前三个阶段项目里基本已经涉及，后三个是缺口。

| 阶段 | 内容 | 本项目状态 |
| --- | --- | --- |
| 0 | 盘点已掌握的 | ✅ 见下 |
| 1 | 两层架构 · Engine · 方言 · 连接池 | 📖 **本篇** |
| 2 | 语句构造：select 的完整能力 | 🟡 会基础查询，缺 join / 子查询 |
| 3 | Session 生命周期与对象状态 | 🟡 40 节讲了状态，缺 expire/merge |
| 4 | **relationship 与关联加载** | ❌ 完全没用过，**优先补** |
| 5 | Alembic 数据库迁移 | ❌ 目前手写 SQL 建表 |
| 6 | 调试与性能：echo · N+1 · 索引 | ❌ |

### 阶段 0：盘点已经会的

统计项目里实际用到的 SQLAlchemy API：

```text
32 Mapped          12 select      7 commit    6 refresh      4 add
31 mapped_column    8 Index       6 update    6 scalars      4 ForeignKey
 5 DeclarativeBase  2 func        2 flush     2 create_async_engine
 4 scalar_one_or_none   1 rollback    1 listens_for
```

已经覆盖了：建模、基础查询、条件过滤、更新、事务、结果取值。**没出现过的**：`relationship`、`join`、`insert()`、`delete()`、`and_` / `or_`、`merge`、`expire`、`selectinload`。

### 阶段 2：语句构造要补什么

- `join()` / `outerjoin()` —— 目前多表数据都是分两次查
- `and_()` / `or_()` —— 复杂条件组合
- 子查询与 CTE
- `insert()` / `delete()` 的 Core 写法（现在只用 ORM 的 `add` 和 Core 的 `update`）
- 批量操作：一条语句插入多行

### 阶段 3：Session 要补什么

- `expire()` 和 `merge()` 的使用场景
- Session 的作用域：为什么是"一次请求一个 Session"
- 嵌套事务 / SAVEPOINT

### 阶段 5：Alembic 迁移

现在改表结构要手动改 SQL 文件再重建数据库，数据会丢。Alembic 能根据模型类的变化**自动生成迁移脚本**，支持升级和回滚。项目稳定后值得引入。

### 阶段 6：调试与性能

- `echo=True` 已经开着了，但可能没认真看过输出
- **N+1 查询问题** —— 学 relationship 时一定会遇到
- 索引是否被用上：`EXPLAIN QUERY PLAN`

## 八、下一步最值得补的：relationship

项目数据库里有五组外键关系，全部只声明了 `ForeignKey`，没有 `relationship`：

```text
news.category_id        -> news_category.id
user_token.user_id      -> user.id
favorite.user_id/news_id -> user.id / news.id
history.user_id/news_id  -> user.id / news.id
related_news.*          -> news.id
```

后面要做的"我的收藏列表"、"浏览历史"这些功能，都需要跨表取数据。现在的做法是查两次再手动拼；有了 `relationship` 就能直接顺着对象访问。

顺带会遇到一个绕不开的概念 —— **N+1 查询问题**：

```python
# 查 10 条新闻，然后逐条取分类名
news_list = (await db.execute(select(News).limit(10))).scalars().all()   # 1 次查询
for n in news_list:
    print(n.category.name)     # 每次循环再查 1 次 → 一共 11 次
```

解决办法是预加载：

```python
from sqlalchemy.orm import selectinload
stmt = select(News).options(selectinload(News.category)).limit(10)   # 一共 2 次
```

异步项目里这个问题更严重 —— 懒加载在异步下直接就是 `MissingGreenlet` 报错，**必须**预加载。

## 九、查文档的方法

### 1. 官方文档的结构对应本篇的分层

[docs.sqlalchemy.org](https://docs.sqlalchemy.org/) 的主要入口：

- **SQLAlchemy Unified Tutorial** —— 官方主教程，Core 和 ORM 混着讲，篇幅长但质量最高
- **ORM Querying Guide** —— 查询写法大全，查 join / 子查询看这里
- **Relationship Configuration** —— 学阶段 4 时的主要参考
- **Asyncio Support** —— 异步专章，`MissingGreenlet` 的官方说明在这里

### 2. 版本陷阱：1.x 和 2.0 语法差别很大

搜索时**一定要确认是不是 2.0 的写法**。同一个查询：

```python
# 1.x 旧写法（网上大量存在，异步下不能用）
user = session.query(User).filter(User.id == 1).first()

# 2.0 新写法（项目用的）
user = (await session.execute(select(User).where(User.id == 1))).scalar_one_or_none()
```

`session.query()` 在 2.0 里仍然能用（标记为 legacy），但**异步 Session 不支持**。搜到 `.query(` 开头的代码基本可以判定是旧文章。

另一个信号：旧代码用 `Column(...)` 声明字段，新代码用 `mapped_column(...)` 配 `Mapped[]` 注解。

### 3. 报错信息里带链接

SQLAlchemy 的报错通常附带一个短链接，例如 `MissingGreenlet` 后面跟着 `https://sqlalche.me/e/20/xd2s`。这些链接直达官方的错误说明页，**比搜索引擎准确得多**，遇到报错优先点它。

## 十、本篇核对了哪些实际行为？

演示均在项目数据库副本上真实运行（原库未改动）：

| 验证内容 | 结果 |
| --- | --- |
| `select()` 返回什么类型 | `Select` 对象，非字符串 |
| 同一语句编译到三种数据库 | 占位符、引号、OFFSET 均不同 |
| 恶意字符串是否进入 SQL 文本 | 否，留在绑定参数里 |
| 同一主键查两次是否同一对象 | 是，身份映射生效 |
| flush 后另一会话能否看到 | 不能，事务未提交 |
| `expire_on_commit=True` 下 commit 后读属性 | 抛 `MissingGreenlet` |
| `expire_on_commit=False` 下同样操作 | 正常读取 |
| 三种 select 写法的返回形状 | `News` / `Row` / `int` |
| 项目 API 使用统计 | 见阶段 0 |

相关笔记：[08-ORM对象](08-ORM对象.md)、[09-SQLAlchemy查询结果与取值](09-SQLAlchemy查询结果与取值.md)、[03-同步与异步](03-同步与异步.md)。

继续学习：[第 15 节：ORM 简介及安装](../15-FastAPI进阶-ORM简介及安装/15-ORM学习.md)。
