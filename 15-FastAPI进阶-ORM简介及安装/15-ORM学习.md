# 15 · ORM 简介与安装

## 1. ORM 的定义

ORM（Object-Relational Mapping，对象关系映射）是一种在 Python 对象和关系型数据库之间建立映射的编程技术。

常见的映射关系如下：

- Python 类对应数据库表。
- 类的对象对应表中的一行记录。
- 对象属性对应表中的字段。
- 对象之间的关系对应表的外键关系。

使用 ORM 后，可以通过创建对象、修改属性和调用查询 API 操作数据库。ORM 会根据这些操作生成并执行 SQL。

ORM 减少了直接编写 SQL 的数量，但不能代替 SQL 和数据库基础知识。复杂查询和性能排查时，仍然需要理解最终执行的 SQL。

## 2. ORM 的优势

### 2.1 减少重复代码

ORM 负责把查询结果转换为 Python 对象，也负责把对象变化转换为 `INSERT`、`UPDATE`、`DELETE` 等语句，从而减少重复的 SQL 和数据转换代码。

### 2.2 集中管理数据结构

表名、字段类型、约束和表关系都可以集中写在模型类中。业务代码围绕模型对象工作，结构更清晰。

### 2.3 降低 SQL 注入风险

ORM 查询通常使用参数化语句，不会直接把用户输入拼接进 SQL，因此能降低 SQL 注入风险。但如果使用原始 SQL 并手动拼接字符串，仍然可能产生安全问题。

### 2.4 管理对象状态和事务

SQLAlchemy 的 `Session` 会跟踪对象的新增、修改和删除，并在 `commit()` 时提交事务。出现错误时仍需要正确执行回滚和资源关闭。

### 2.5 提供一定的数据库可移植性

相同的 ORM 模型和查询通常可以配合 SQLite、PostgreSQL、MySQL 等数据库使用。不过数据库特有的数据类型和功能仍然存在差异。

## 3. ORM 的两种常见设计方式

### 3.1 Active Record 风格

数据对象本身提供保存、删除和查询等数据库操作，使用方式通常接近：

```python
user = User(name="Alice")
user.save()

users = User.objects.filter(name="Alice")
```

Django ORM 的使用方式接近 Active Record。它约定较多、上手快，适合以 Django 为主体的后台管理、内容网站和常规 CRUD 项目。

### 3.2 Data Mapper 风格

模型主要描述数据结构，持久化操作交给独立的会话或数据访问层：

```python
user = User(name="Alice")
session.add(user)
session.commit()
```

SQLAlchemy ORM 采用这种方式，并结合 Unit of Work 管理对象变化。它的概念更多，但模型和数据库操作的职责更容易分离，适合 FastAPI、复杂数据关系和长期维护的项目。

## 4. 常见的 Python ORM

### 4.1 Django ORM

Django ORM 是 Django 框架的一部分。通常一个模型对应一张数据库表，并配套提供 QuerySet、数据迁移和 Django Admin。

它最适合已经使用 Django 的项目。若项目以 FastAPI 为主体，仅为了 ORM 引入完整的 Django 配置通常不够自然。[Django 模型文档](https://docs.djangoproject.com/en/5.2/topics/db/)

### 4.2 SQLAlchemy ORM

SQLAlchemy 与具体 Web 框架无关，同时提供底层的 SQL Expression Language（Core）和上层 ORM。它支持同步、异步以及多种数据库方言，既能快速完成 CRUD，也允许细致控制 SQL。

它适合 FastAPI 服务、复杂查询、多数据库项目以及需要长期扩展的数据访问层。

### 4.3 SQLModel

SQLModel 构建在 SQLAlchemy 和 Pydantic 之上，由 FastAPI 作者创建。一个模型可以同时参与数据库映射和数据校验，代码量较少。

它适合希望快速开发 FastAPI 数据库接口的项目。遇到复杂映射和查询时，仍然需要理解底层 SQLAlchemy。[SQLModel 官方介绍](https://sqlmodel.tiangolo.com/)

### 4.4 Tortoise ORM

Tortoise ORM 是异步优先、受 Django 启发的 ORM，API 风格与 Django ORM 相似。

它适合偏好 Django 查询风格、并且数据库操作全部采用 `asyncio` 的项目。[Tortoise ORM 官方文档](https://tortoise.github.io/)

## 5. 最泛用的 ORM

在 Python Web 项目中，如果重点是框架无关、数据库支持广泛和复杂场景下的控制能力，SQLAlchemy 通常是最泛用的选择。

FastAPI 不强制使用任何 ORM，而 SQLAlchemy 可以独立使用，也能与 FastAPI 的依赖注入结合。因此本节使用 SQLAlchemy 继续学习。

## 6. 安装 SQLAlchemy

当前项目使用 `uv` 管理依赖，安装命令为：

```bash
uv add sqlalchemy
```

查看安装版本：

```bash
uv run python -c "import sqlalchemy; print(sqlalchemy.__version__)"
```

当前项目安装的是 SQLAlchemy `2.0.52`。[SQLAlchemy 2.0 安装文档](https://docs.sqlalchemy.org/en/20/intro.html#installation-guide)

SQLite 驱动包含在 Python 标准库中，不需要额外安装。连接 PostgreSQL、MySQL 等数据库时，还需要安装对应的数据库驱动。

## 7. SQLAlchemy ORM 简单使用

下面使用 SQLite 内存数据库演示定义模型、创建表、插入数据和查询数据。程序结束后，内存数据库中的数据会自动消失。

```python
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    age: Mapped[int | None]

    def __repr__(self) -> str:
        return (
            f"User(id={self.id}, "
            f"name={self.name!r}, age={self.age})"
        )


engine = create_engine(
    "sqlite:///:memory:",
    echo=True,
)

Base.metadata.create_all(engine)


# 新增数据
with Session(engine) as session:
    user = User(name="Alice", age=20)

    session.add(user)
    session.commit()
    session.refresh(user)

    print("新增用户：", user)


# 查询数据
with Session(engine) as session:
    statement = select(User).where(User.age >= 18)
    users = session.scalars(statement).all()

    print("成年用户：", users)
```

### 7.1 模型相关代码

`DeclarativeBase` 是所有 ORM 模型的基础类。继承 `Base` 的类会被 SQLAlchemy 识别为映射模型。

`__tablename__` 指定数据库表名。`Mapped[int]`、`Mapped[str]` 等声明属性对应的 Python 类型和数据库字段类型。

`mapped_column(primary_key=True)` 把 `id` 设置为主键。`String(50)` 把 `name` 映射为最大长度为 50 的字符串字段。

### 7.2 Engine 和建表

`create_engine()` 创建 Engine，它负责保存数据库连接配置并与数据库驱动协作。

`sqlite:///:memory:` 表示使用 SQLite 内存数据库。改为 `sqlite:///orm_demo.db` 后，数据会保存在当前目录的 `orm_demo.db` 文件中。

`echo=True` 会在终端输出 SQL，适合学习和调试。`Base.metadata.create_all(engine)` 根据模型创建尚不存在的表。

### 7.3 Session 和新增数据

`Session(engine)` 创建一次数据库会话。`session.add(user)` 把对象加入会话，`commit()` 提交事务，`refresh(user)` 从数据库刷新对象并取得自动生成的主键。

使用 `with` 后，代码块结束时会关闭 Session。关闭 Session 不等于自动提交，因此需要显式调用 `commit()`。

### 7.4 查询数据

`select(User)` 创建查询语句，`where(User.age >= 18)` 添加查询条件。

`session.scalars(statement)` 取得查询结果中的 `User` 对象，`all()` 将所有结果组成列表。这是 SQLAlchemy 2.x 推荐的查询方式。[SQLAlchemy ORM 快速入门](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)

## 8. 初学时需要注意

`Base.metadata.create_all()` 适合学习和简单建表。正式项目修改表结构时通常使用 Alembic 数据迁移。

在 FastAPI 项目中，不应让所有请求共用同一个 `Session`。后续可以使用依赖注入，为每个请求创建并关闭独立的 Session。

**记忆：模型类负责描述表结构，Engine 负责连接配置，Session 负责一次数据库操作和事务，`select()` 负责构造查询。**
