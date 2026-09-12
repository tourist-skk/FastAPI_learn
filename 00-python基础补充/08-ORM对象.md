# 08-ORM对象

本文从第 18 节抽出，介绍 SQLAlchemy 模型实例在 Python 中是什么，以及它与字典、JSON 的区别。

示例沿用项目中的 `Book` 模型和 `AsyncSession` 会话 `db`。含 `await` 的片段放在异步函数内执行；假设数据库中存在 `id=1`、书名为 `Python for Beginners`、价格为 `30` 的记录。

## 一、模型类与模型实例

`Book` 是模型类，描述 `book` 表有哪些字段、字段如何映射。

**ORM 对象是这个模型类的实例**。查询得到的某个 `Book` 实例，在 Python 内存中表示数据库中的一条书籍记录：

```python
book = await db.get(Book, 1)

if book is not None:
    print(isinstance(book, Book))  # True
    print(book.id)                 # 1
    print(book.bookname)           # Python for Beginners
    print(book.price)              # 30.0
```

因此：

- `Book`：模型类，用于描述和构造查询。
- `Book.price`：构造 SQL 条件时使用的映射属性。
- `book`：某一本书的模型实例。
- `book.price`：这个实例当前保存的价格值。

例如 `Book.price >= 30` 用于构造数据库过滤条件；`book.price >= 30` 则是在 Python 中比较一个具体价格。

## 二、ORM 对象与字典、JSON 的区别

可以通过属性取得数据，再自己组织成字典：

```python
book = await db.get(Book, 1)

if book is not None:
    data = {"id": book.id, "bookname": book.bookname}
    print(data)
```

`book` 是 `Book` 实例，`data` 是 `dict`。接口返回的 JSON 则是 FastAPI 对返回值进行序列化之后的响应内容，不能把它们当作同一个东西。

SQLAlchemy 会管理查询加载的对象及其状态；对象本身也可以通过 `Book(...)` 在内存中创建，此时未必已经保存到数据库。创建一个实例并不等于已经插入一行。

查询得到对象之前，通常还会经过 `Result` 和 `Row`。这部分详见 [09-SQLAlchemy查询结果与取值](09-SQLAlchemy查询结果与取值.md)。

继续学习：[第 18 节：ORM 操作数据——查询](../18-FastAPI进阶-ORM操作数据-查询/18-FastAPI进阶-ORM操作数据-查询.md)。
