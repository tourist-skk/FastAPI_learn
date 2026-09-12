# 02 · 问题记录：uv 运行 FastAPI 提示缺少 standard 依赖

## 报错现象

在项目根目录执行：

```bash
uv run fastapi dev main.py
```

出现以下提示，并抛出 `RuntimeError`：

```text
To use the fastapi command, please install "fastapi[standard]":

        pip install "fastapi[standard]"
```

当时项目只声明了 `fastapi>=0.141.1`，实际环境中缺少 `fastapi-cli` 和 `uvicorn`。

## 原因与解决方法

**`uv run` 默认会自动同步项目声明的依赖，但不会根据你运行的命令推测需要哪些可选依赖。** 如果配置里只有 `"fastapi>=0.141.1"`，uv 安装基础包就已经满足声明；这并不包含运行 FastAPI CLI 所需的全部组件。[uv 自动同步说明](https://docs.astral.sh/uv/concepts/projects/sync/#automatic-lock-and-sync)

基础包可以提供一个名为 `fastapi` 的命令入口，但入口在执行时仍需导入 `fastapi-cli`。因此，“终端找到了 fastapi 命令”和“CLI 的依赖已经装齐”是两件事。缺少 CLI 时，就会提示安装 `fastapi[standard]`。[FastAPI CLI 说明](https://fastapi.tiangolo.com/fastapi-cli/)

在项目根目录执行下面的命令，补充依赖声明并安装：

```bash
uv add "fastapi[standard]"
```

例如，本项目对应的声明为：

```toml
dependencies = [
    "fastapi[standard]>=0.141.1",
]
```

其中 `0.141.1` 是本项目已有的版本下限，不是所有项目必须使用的版本号。`uv add` 会同时更新 `uv.lock` 和 `.venv`，随后再运行 `uv run fastapi dev main.py` 即可。

仅重复执行 `uv run` 或 `uv sync`，不会把配置里的 `fastapi` 自动改成 `fastapi[standard]`。错误提示中的 pip 命令是通用安装提示；使用 uv 管理项目时，应优先使用 `uv add`，让项目配置也记录这项需求。

