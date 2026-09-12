# 07-SQLite命令行查询

本篇补充不通过 Python 检查 SQLite 数据库的方法。以下命令均在项目根目录 `fastApi-learn` 中执行，目标文件为 `sql/fastapi.db`。

可以使用 SQLite 自带的 `sqlite3` 命令行工具直接查询 `db` 文件。

先确认数据库文件是否存在：

```bash
ls -lh sql/fastapi.db
```

列出数据库中的所有表：

```bash
sqlite3 -readonly sql/fastapi.db ".tables"
```

检查指定的 `book` 表是否存在：

```bash
sqlite3 -readonly sql/fastapi.db "SELECT name FROM sqlite_master WHERE type='table' AND name='book';"
```

如果输出 `book`，说明表存在；没有输出则说明该数据库中没有这张表。

查看 `book` 表的完整建表结构：

```bash
sqlite3 -readonly sql/fastapi.db ".schema book"
```

也可以进入 SQLite 交互终端：

```bash
sqlite3 -readonly sql/fastapi.db
```

进入后依次执行：

```sql
.tables
.schema book
.quit
```

`-readonly` 表示以只读方式打开数据库。这样既不会修改数据库，也可以避免在路径错误或文件不存在时意外创建新的空数据库。
