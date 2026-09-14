# 02-pathlib路径处理

本篇使用 `pathlib.Path` 拼接路径、创建目录并生成路径字符串。以下片段以 Python 脚本所在目录为起点，先准备：

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
```

`__file__` 表示当前脚本文件路径，`resolve()` 取得绝对路径，`.parent` 取得所在目录。完整应用示例见[SQLite 建表与启动排查](06-SQLite建表与启动排查.md)。

## 1. 使用 `/` 拼接路径

```python
SQL_DIR = BASE_DIR / "sql"
DATABASE_FILE = SQL_DIR / "fastapi.db"
```

这里的 `/` 不是数学除法。`Path` 对象对该运算符进行了定义，使它可以用来拼接路径。

假设 `BASE_DIR` 是：

```text
/project/16-FastAPI进阶-ORM建表
```

拼接结果就是：

```text
/project/16-FastAPI进阶-ORM建表/sql/fastapi.db
```

## 2. 创建目录

```python
SQL_DIR.mkdir(parents=True, exist_ok=True)
```

- `mkdir()`：创建目录。
- `parents=True`：上级目录不存在时一起创建。
- `exist_ok=True`：目标目录已经存在时不报错。

如果 `sql` 已经存在，但它是一个普通文件而不是目录，`mkdir()` 仍然会报错。

## 3. 将路径转换为字符串

```python
DATABASE_FILE.as_posix()
```

`as_posix()` 将 `Path` 对象转换为使用正斜杠的字符串，适合拼接数据库 URL：

```python
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_FILE.as_posix()}"
```

参考资料：

- [Python pathlib 文档](https://docs.python.org/3.11/library/pathlib.html)
