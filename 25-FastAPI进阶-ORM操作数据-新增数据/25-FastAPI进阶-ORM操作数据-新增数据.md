# 25-FastAPI进阶-ORM操作数据-新增数据

本节按 **创建 ORM 对象 → 加入会话 → 提交事务 → 获取生成的 ID → 接入路由 → 批量新增** 的顺序学习，并单独说明 SQLite 与 MySQL 的主键自增规则。

## 一、新增数据的基本原理

**ORM 新增数据，就是让 SQLAlchemy 根据模型对象或字段数据生成 `INSERT` 语句，再通过数据库事务保存记录。**

新增对象的基本流程是：

```text
Book(...) 创建对象
    ↓
db.add(对象) 加入会话，登记为待插入对象
    ↓
flush：执行 INSERT，数据库生成主键，ORM 将主键填回对象
    ↓
commit：提交事务，保存本次修改
```

`add()` 的准确含义是“加入会话”，它本身不会立即执行 `INSERT`。`commit()` 会先自动执行必要的 `flush()`，所以最基本的写法仍是：

```python
new_book = Book(
    bookname="Python新增数据练习",
    author="张三",
    price=39.0,
    publisher="学习出版社",
)
db.add(new_book)
await db.commit()
```

以上片段放在异步函数内执行。`Book(...)` 得到的是一个 **Book 类的实例，即 ORM 对象**；刚创建时，它只在 Python 内存中，还不代表数据库已经保存了一行。

下面沿用根目录 [database_sqlite.py](../database_sqlite.py) 中的 `Book`、`app` 和 `AsyncSessionLocal`。当前会话工厂已经设置 `expire_on_commit=False`，示例据此在提交后读取对象属性。需要的导入是：

```python
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import Integer, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
```

## 二、方式一：add() 新增一条记录

### 1. 完整代码

```python
async def insert_one_book(db: AsyncSession):
    new_book = Book(
        bookname="Python新增数据练习",
        author="张三",
        price=39.0,
        publisher="学习出版社",
    )

    db.add(new_book)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    print(new_book.id)  # 数据库自动生成的主键，不一定是 1
    return new_book
```

参数和执行过程：

1. `db: AsyncSession`：接收异步数据库会话，用来管理 ORM 对象和事务。
2. `Book(...)`：属性名对应模型字段；没有传入 `id`，由数据库生成。
3. `db.add(new_book)`：会话开始管理这个新对象，等待插入。
4. `await db.commit()`：先把待插入数据写入当前事务，再提交。
5. `await db.rollback()`：提交过程发生异常时回滚；`raise` 将异常继续抛给调用方。
6. `return new_book`：返回创建的 ORM 对象，包含生成的 ID。

本项目的 `create_time`、`update_time` 已在基类中配置插入默认值，所以通过上述 ORM 代码新增时也可以省略。这里的 SQLAlchemy 插入默认值，不等于数据库表一定定义了 `DEFAULT`；手动编写原生 SQL 时，仍要检查实际表结构。

**适用场景：**普通新增接口；后续还需要访问对象属性，或通过已配置的 ORM 关系一起保存关联对象。

**特点：**写法直观，会话会管理对象状态并回填主键；批量导入很多行时，逐个创建和管理对象会有额外开销。当前 `Book.author` 只是姓名字符串，新增一本书不会自动向作者表新增作者。

### 2. add() 和 commit() 返回什么

它们都不会返回新书或新书 ID：

```python
# 放在异步函数内，new_book 是一个尚未插入的 Book 实例
add_result = db.add(new_book)
print(add_result)  # None

commit_result = await db.commit()
print(commit_result)  # None

print(new_book.id)  # 从原对象读取生成的 ID
```

`add()` 是同步方法，不写 `await`。`commit()`、`flush()`、`refresh()`、`rollback()` 是异步方法，使用时写 `await`；这几个操作成功完成后也都返回 `None`。

不要写 `new_book = db.add(new_book)`，否则变量会被覆盖成 `None`。

## 三、区分 flush、commit、refresh 和 rollback

### 1. flush()：执行 SQL，但暂不提交

如果后续操作要用到新书 ID，又希望多个操作最后一起提交，可以先 `flush()`：

```python
async def demonstrate_flush(db: AsyncSession):
    new_book = Book(
        bookname="事务练习",
        author="李四",
        price=49.0,
        publisher="学习出版社",
    )
    db.add(new_book)
    print(new_book.id)  # None，此时没有传入 ID，也尚未执行插入

    try:
        await db.flush()
        print(new_book.id)  # 已获得数据库生成的整数 ID

        # 可以在这里用这个 ID 完成同一事务内的其他操作
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return new_book.id
```

`flush()` 会将会话中待处理的修改发送给数据库；**拿到 ID 只说明插入已执行，不说明事务已提交。** 在提交前回滚，这条新增记录就不会保留。

不需要提前获取 ID 时，直接 `commit()` 即可。默认设置下，执行某些 ORM 查询前也会自动 `flush`，因此不能认为“所有 INSERT 都只会在 commit 那一行执行”。[会话刷新与提交](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#flushing)

### 2. refresh()：从数据库重新读取对象属性

```python
# 放在异步函数内；new_book 已经通过 flush 或 commit 插入
await db.refresh(new_book)
print(new_book.id, new_book.create_time)
```

`refresh(new_book)` 根据对象的主键重新查询，并更新这个对象的属性。它会产生额外查询，**不是保存数据，也不是生成 ID 的步骤**。

常见用途是显式读取数据库生成或修改的字段。对于本节的自增主键，`flush()` 已经会将 ID 填回对象，不必为了获取 ID 再调用 `refresh()`。

`expire_on_commit=False` 表示“提交时不自动使已加载的对象属性过期”，方便异步代码在提交后继续读取；它不代表对象会自动跟踪数据库里后来发生的修改。[异步会话的属性访问](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession)

### 3. rollback()：撤销尚未提交的修改

例如重复插入已有主键，或缺少没有默认值的 `NOT NULL` 字段，通常会在 `flush()` 或 `commit()` 时触发数据库约束异常。失败后应回滚，再继续使用该会话。

`rollback()` 只能撤销当前事务尚未提交的修改，不能撤销之前已经成功提交的数据。批量新增如果要求“全部成功或全部失败”，应放在同一个事务中，最后统一提交，不要每插入一行就提交一次。

## 四、如何设置 ID 自增

### 1. 当前模型其实已经支持自动生成 ID

现在的定义是：

```python
# Book 类内部的字段定义
id: Mapped[int] = mapped_column(
    primary_key=True,
    index=True,
    comment="书籍ID",
)
```

`Mapped[int]` 让 SQLAlchemy 推导出整数列；对于本项目这种**单列、整数、非外键主键**，默认的 `autoincrement="auto"` 就会启用合适的主键生成行为。

也可以显式写出：

```python
# 替换 Book 类中的 id 定义
id: Mapped[int] = mapped_column(
    Integer,
    primary_key=True,
    autoincrement=True,
    comment="书籍ID",
)
```

- `Integer`：数据库整数类型。
- `primary_key=True`：主键，用来唯一标识一行。
- `autoincrement=True`：明确让 SQLAlchemy 按数据库的规则处理整数主键生成。

这不是 SQLAlchemy 在 Python 中计算“最大 ID 加一”。真正生成 ID 的是数据库，SQLAlchemy 负责建表适配以及获取生成值。不同数据库生成的建表语法可能不同。[autoincrement 参数](https://docs.sqlalchemy.org/en/20/core/metadata.html#sqlalchemy.schema.Column.params.autoincrement)

### 2. SQLite：INTEGER PRIMARY KEY 默认就能自动生成 ID

普通 SQLite 表内部通常有一个整数 `ROWID`。声明为 `INTEGER PRIMARY KEY` 的列是 `ROWID` 的别名；插入时省略该列，SQLite 就会自动分配值。字段叫 `id` 还是 `author_id` 不影响这条规则。

```sql
-- 独立的小表，用来观察 ID 分配
CREATE TABLE id_demo (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

INSERT INTO id_demo (name) VALUES ('甲'), ('乙'), ('丙');
SELECT id, name FROM id_demo ORDER BY id;
-- 1 | 甲
-- 2 | 乙
-- 3 | 丙

DELETE FROM id_demo WHERE id = 3;
INSERT INTO id_demo (name) VALUES ('丁');
SELECT id, name FROM id_demo ORDER BY id;
-- 1 | 甲
-- 2 | 乙
-- 3 | 丁：删除了原来的最大 ID 后，这次再次使用了它
```

普通情况下，新 ID 是**当前表内最大 ROWID 加一**，空表通常从 1 开始。因此它能自动生成 ID，但不保证永远不复用删除过的 ID。

当前书籍表的实际结构包含 `id INTEGER NOT NULL` 和 `PRIMARY KEY (id)`，也满足这里的整数主键规则，所以没有看到 `AUTOINCREMENT` 关键字仍然可以自动生成 ID。

这里要求类型名是 `INTEGER`；`INT PRIMARY KEY`、`BIGINT PRIMARY KEY` 不具有相同的 ROWID 别名行为。复合主键、`WITHOUT ROWID` 表也不能照搬这一规则。[SQLite 主键分配规则](https://www.sqlite.org/autoinc.html)

### 3. SQLite 的 AUTOINCREMENT 多解决了什么问题

如果希望自动生成的 ID 不再使用**历史上已经提交使用过**的值，可以额外使用 SQLite 的 `AUTOINCREMENT`：

```sql
CREATE TABLE id_demo_strict (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

INSERT INTO id_demo_strict (name) VALUES ('甲'), ('乙'), ('丙');
DELETE FROM id_demo_strict WHERE id = 3;
INSERT INTO id_demo_strict (name) VALUES ('丁');

SELECT id, name FROM id_demo_strict ORDER BY id;
-- 1 | 甲
-- 2 | 乙
-- 4 | 丁：不会再次自动分配历史上使用过的 3
```

对应 SQLAlchemy 设置是**表级参数**：

```python
# 放在 Book 类内部；其余字段沿用原定义
__table_args__ = {"sqlite_autoincrement": True}

id: Mapped[int] = mapped_column(Integer, primary_key=True)
```

**列上的 `autoincrement=True` 与表上的 `sqlite_autoincrement=True` 不是同一个配置。** 前者表示整数主键自动生成意图；后者才要求 SQLite 建表时显式写出 `AUTOINCREMENT`。[SQLAlchemy 的 SQLite 自增设置](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#using-the-autoincrement-keyword)

`AUTOINCREMENT` 需要通过 `sqlite_sequence` 维护历史记录，会有额外开销，通常不必为了“自动生成 ID”而启用。它也不保证编号连续；回滚事务中用过的 ID 仍可能被复用。

### 4. MySQL：使用 AUTO_INCREMENT

MySQL 仅设置 `INT PRIMARY KEY` 不会自动变成自增列，需要 `AUTO_INCREMENT`：

```sql
CREATE TABLE id_demo_mysql (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    PRIMARY KEY (id)
);

INSERT INTO id_demo_mysql (name) VALUES ('甲'), ('乙');
```

插入时省略 `id`，MySQL 自动分配 ID。常规设计是一张表有一个自增列，并将它设置为整数主键。

前面相同的 ORM 定义：

```python
id: Mapped[int] = mapped_column(
    Integer,
    primary_key=True,
    autoincrement=True,
)
```

使用 MySQL 引擎建表时，SQLAlchemy 会生成带 `AUTO_INCREMENT` 的列；使用 SQLite 引擎建表时，则通常使用 `INTEGER PRIMARY KEY` 的隐式规则。[MySQL 自增列](https://dev.mysql.com/doc/refman/8.4/en/example-auto-increment.html)

这些 MySQL 代码用于理解差异，本节继续使用 SQLite，不需要安装 MySQL。

### 5. 使用自增主键时的注意事项

- 请求体通常不接收 `id`，新增时交给数据库生成；手动指定重复主键会报错。
- 不要先查询 `max(id)` 再自己加一：两个并发请求可能算出相同的 ID。
- ID 用于唯一标识记录，不保证连续，也不等于当前记录数量。
- 修改模型后，`Base.metadata.create_all()` 不会自动修改已有表。已有 SQLite 表要增加 `AUTOINCREMENT`，需要迁移或重建表并保留数据；仅改模型再重启应用不会生效。本项目当前表已经能自动生成 ID，无须为此重建。

## 五、把新增操作接入 FastAPI

### 1. 请求模型与 ORM 模型负责不同的事情

沿用现有请求模型：

```python
class BookBase(BaseModel):
    bookname: str
    author: str
    price: float
    publisher: str
```

`BookBase` 是 Pydantic 模型，用于解析和校验请求体；`Book` 是 ORM 模型，用于映射数据库表。`db.add()` 应接收 `Book` 实例，不能直接接收 `BookBase` 实例。

```python
# book 是 FastAPI 解析请求体后得到的 BookBase 实例
data = book.model_dump()  # 转成字段字典
new_book = Book(**data)   # 展开字典，构造 ORM 对象
```

`**data` 是关键字参数解包。例如 `{"bookname": "Python入门", "author": "张三", ...}` 展开后，相当于 `Book(bookname="Python入门", author="张三", ...)`。

关于单星号、双星号，以及“调用时展开参数”和“定义时收集参数”的区别，见 [10-星号与参数解包](../00-python基础补充/10-星号与参数解包.md)。

原代码的 `book.__dict__` 在这个简单模型中也能取到字段，但 `model_dump()` 是 Pydantic 提供的序列化接口，支持字段包含、排除和嵌套模型转换，更适合表达“把请求模型转成字段数据”。[Pydantic model_dump](https://docs.pydantic.dev/latest/concepts/serialization/#python-mode)

### 2. 明确由谁提交事务

当前根目录的 `get_database()` 在 `yield` 后会 `commit()`，新增路由又调用了一次 `commit()`，存在重复负责提交的情况。

本节采用一个明确的分工：**路由提交事务，依赖负责提供会话、异常回滚和关闭会话。** 如果将下面示例用于项目，应成套替换原来的依赖与新增路由。

```python
async def get_database():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        # async with 退出时自动关闭会话，无须再次 close()
```

这里不在 `yield` 后自动提交。因此其他写入路由使用这个版本时，也要明确提交自己的事务。普通只读查询不需要提交。

### 3. 完整新增接口

```python
@app.post("/book/add_book", status_code=201)
async def add_book(
    book: BookBase,
    db: AsyncSession = Depends(get_database),
):
    new_book = Book(**book.model_dump())
    db.add(new_book)
    await db.commit()

    # 当前 expire_on_commit=False，可直接读取已加载的字段
    return {
        "id": new_book.id,
        "bookname": new_book.bookname,
        "author": new_book.author,
        "price": new_book.price,
        "publisher": new_book.publisher,
    }
```

- `book: BookBase`：将 JSON 请求体解析成 `BookBase` 实例。
- `Depends(get_database)`：获取该请求使用的异步数据库会话。
- `status_code=201`：表示资源创建成功。
- 返回普通字典：明确选择接口需要返回的字段。

请求示例：

```json
{
  "bookname": "FastAPI数据库实践",
  "author": "张三",
  "price": 59.0,
  "publisher": "学习出版社"
}
```

执行顺序是：

```text
解析、校验请求体，并获取数据库会话
    ↓
Book(**book.model_dump()) 创建 ORM 对象
    ↓
add() 登记待插入对象
    ↓
commit() 自动 flush，执行 INSERT、取得 ID、提交事务
    ↓
读取 new_book.id，组织成功响应
    ↓
依赖结束，关闭会话
```

如果 `commit()` 抛出异常，就不会继续执行成功返回；异常会交回依赖，执行 `rollback()` 并继续抛出。

## 六、方式二：add_all() 新增多个 ORM 对象

```python
async def insert_many_books(db: AsyncSession):
    books = [
        Book(bookname="批量练习一", author="张三", price=35.0, publisher="学习出版社"),
        Book(bookname="批量练习二", author="李四", price=45.0, publisher="学习出版社"),
    ]

    db.add_all(books)  # 参数是 ORM 对象组成的可迭代对象

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return [book.id for book in books]
```

`add_all()` 可以理解为一次把多个对象加入会话；它是同步方法，返回 `None`。最终统一提交，生成的主键会分别填回各个 `Book` 对象。

**适用场景：**一次新增多条记录，并且仍需要使用 ORM 对象及其属性。

**特点：**保留普通 ORM 对象管理能力，写法清楚；仍然需要创建每个对象。它不承诺“一定只执行一条 INSERT”，具体是否合并 SQL 由数据库和 SQLAlchemy 执行策略决定。

## 七、方式三：execute(insert(...)) 直接按字段插入

### 1. 新增单条数据

也可以构造 `INSERT` 语句，不先创建 `Book` 实例：

```python
async def insert_book_by_statement(db: AsyncSession):
    stmt = insert(Book).values(
        bookname="SQL表达式新增练习",
        author="张三",
        price=42.0,
        publisher="学习出版社",
    )

    try:
        await db.execute(stmt)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
```

`insert(Book)` 指定要插入的模型，`values(...)` 设置字段值；构造 `stmt` 时不访问数据库，`await db.execute(stmt)` 才执行插入。**execute() 不会自动提交事务**，因此后面仍需要 `commit()`。

### 2. 使用字典列表批量插入

SQLAlchemy 2.x 的常用批量方式是 `await db.execute(insert(Book), 数据字典列表)`：

```python
async def bulk_insert_books(db: AsyncSession, data: list[dict]):
    if not data:
        return 0

    try:
        await db.execute(insert(Book), data)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return len(data)  # 本例全部成功后，返回提交的数据条数
```

在异步函数内调用：

```python
count = await bulk_insert_books(
    db,
    [
        {"bookname": "导入练习一", "author": "张三", "price": 30.0, "publisher": "学习出版社"},
        {"bookname": "导入练习二", "author": "李四", "price": 40.0, "publisher": "学习出版社"},
    ],
)
print(count)  # 2
```

第二个参数中的每个字典代表一条数据，键使用 **ORM 属性名**。没有传入 `id`，仍由数据库生成。

**适用场景：**从文件、接口等来源批量导入字段数据，不需要逐个创建并管理对象。

**特点：**减少 Python 对象管理开销，便于批量执行；不会像 `add_all()` 一样自动遍历对象关系并级联保存，也不会把新 ID 自动写回输入字典。批量执行可能被拆成多条 SQL，不等于必须拼成一条很长的 `INSERT`。[ORM 批量插入](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#orm-bulk-insert-statements)

### 3. 插入后需要返回 ID：RETURNING

支持 `INSERT ... RETURNING` 的数据库，可以在插入时直接返回指定字段，减少单独查询：

```python
async def bulk_insert_books_returning(db: AsyncSession, data: list[dict]):
    if not data:
        return []

    stmt = insert(Book).returning(Book.id, Book.bookname)

    try:
        result = await db.execute(stmt, data)
        rows = [dict(row) for row in result.mappings().all()]
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return rows
```

`returning(Book.id, Book.bookname)` 决定返回哪些列。结果读取方式和前面的查询章节一样：先 `await execute()`，再同步调用 `mappings().all()`，得到各行的字段映射。

返回形状例如：

```python
# ID 仅为示意，实际取决于数据库
[
    {"id": 10, "bookname": "导入练习一"},
    {"id": 11, "bookname": "导入练习二"},
]
```

如果希望返回 ORM 对象，可将上述函数中的语句及取值两处一起改为：

```python
stmt = insert(Book).returning(Book)
result = await db.execute(stmt, data)
books = result.scalars().all()  # list[Book]
# 后续仍需提交事务，再 return books
```

注意：

- 本项目使用的 SQLite 3.50.4 支持 `RETURNING`，该语法从 SQLite 3.35.0 起提供；PostgreSQL 也支持。MySQL 不支持这里的 `INSERT ... RETURNING`，不能原样照搬。[SQLite RETURNING](https://www.sqlite.org/lang_returning.html)
- 批量 `RETURNING` 的结果顺序不保证与输入顺序相同；如果要逐项对应，可使用 `returning(Book.id, Book.bookname, sort_by_parameter_order=True)`，但可能降低批量效率。
- 普通 `INSERT` 未声明返回行时，不要把执行结果当作 `SELECT` 结果直接调用 `scalars().all()`。`execute()` 是否能返回数据行，取决于语句及数据库支持，不是每次都能取出 ORM 对象。

相关说明见 [INSERT RETURNING](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#getting-new-objects-with-returning)，也可复习 [SQLAlchemy 查询结果与取值](../00-python基础补充/09-SQLAlchemy查询结果与取值.md)。

## 八、如何选择

- 新增一本书、需要直接操作这个对象：`add()`。
- 新增多本书、需要各自的 ORM 对象及生成的 ID：`add_all()`。
- 直接构造插入语句：`execute(insert(Book).values(...))`。
- 批量导入字典数据：`execute(insert(Book), data)`；需要返回字段且数据库支持时，再加 `returning(...)`。

旧教程中的 `bulk_save_objects()`、`bulk_insert_mappings()` 属于旧式批量接口。学习当前 SQLAlchemy 2.x 时，优先掌握上面这些方式即可。
