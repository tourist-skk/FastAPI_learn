# 02 · FastAPI 安装与第一步使用

上一篇：[01 · FastAPI 框架简介](../01-FastAPI简介/01-FastAPI框架简介.md)

本篇从安装环境开始，完成第一个接口的编写、启动和访问，并说明 `fastapi[standard]` 与其他安装方式的区别。项目的 `pyproject.toml` 要求 Python 3.11 及以上，下面的练习也按这个要求进行。

## 1. 先理解安装命令中的方括号

你可能见过这两种写法：

```bash
python -m pip install fastapi
python -m pip install "fastapi[standard]"
```

**两者安装的是同一个 FastAPI 框架，区别是是否同时安装一组可选依赖。**

Python 包可以声明名为 extras 的可选依赖组。`fastapi[standard]` 的含义是“安装 FastAPI 本体、它的必需依赖，以及名为 `standard` 的可选依赖组”。`standard` 不是版本号，也不是需要付费解锁的版本。[Python 包的 extras 规范](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#extras)

例如，框架本身负责定义和处理接口；运行服务器、解析表单、校验邮箱等场景还会用到其他库。安装 `standard` 可以一次准备好常用工具。

命令中的引号需要保留：在 macOS 常用的 zsh 中，未加引号的方括号可能被当作文件匹配表达式，导致 `no matches found`。引号是终端语法，不是包名的一部分。[FastAPI 安装说明](https://fastapi.tiangolo.com/#installation)

## 2. 不同安装方式有什么区别？

下面比较的是**全新环境中**的安装结果；如果环境已经装有其他依赖，实际可用的功能还会受到已有包的影响。

| 安装目标 | 会安装什么 | 适用场景 |
| --- | --- | --- |
| `fastapi` | FastAPI 及其必需依赖，包括 Starlette、Pydantic 等 | 希望自己选择服务器和其他工具，控制依赖数量 |
| `fastapi[standard]` | 基础依赖加常用可选依赖，包含 Uvicorn、FastAPI CLI 等 | 初次学习、一般开发，安装后即可使用常见开发命令 |
| `fastapi[standard-no-fastapi-cloud-cli]` | 标准依赖方案，但不包含 `fastapi-cloud-cli` | 想使用本地 CLI 等常用功能，同时不安装云端部署 CLI |
| `fastapi[all]` | FastAPI 在该版本中声明的 `all` 可选依赖组 | 明确需要其中更多附加库时使用 |
| `fastapi` 加 `uvicorn[standard]` | FastAPI 基础依赖加 Uvicorn 的常用可选依赖 | 希望直接用 Uvicorn 启动，并按需求补充其他包 |

`standard` 和排除云端 CLI 的选项见[官方依赖说明](https://fastapi.tiangolo.com/#dependencies)；`all` 的具体定义可以在[FastAPI 包配置](https://github.com/fastapi/fastapi/blob/master/pyproject.toml)的 `project.optional-dependencies` 中查看。

### 2.1 `standard` 常见的附加依赖

以下列出官方文档介绍的常用组件，并非所有传递依赖的完整清单：

| 依赖 | 作用 | 什么时候会用到 |
| --- | --- | --- |
| `uvicorn[standard]` | 运行 ASGI 应用，并提供常用服务器附加组件 | 启动 FastAPI 服务 |
| `fastapi-cli[standard]` | 提供 `fastapi dev`、`fastapi run` 等命令 | 使用 FastAPI 的命令行工具 |
| `httpx` | HTTP 客户端，也是 `TestClient` 所需依赖 | 编写接口测试 |
| `jinja2` | 模板渲染 | 使用默认模板配置返回 HTML 页面 |
| `python-multipart` | 表单及文件上传数据解析 | 接收表单和上传文件 |
| `email-validator` | 邮箱地址校验 | 使用 Pydantic 的 `EmailStr` 等类型 |

当前官方说明中，`fastapi-cli[standard]` 还会引入 `fastapi-cloud-cli`。安装这个工具不等于部署应用；本篇使用的 `dev` 命令只启动本地服务。[标准依赖说明](https://fastapi.tiangolo.com/#standard-dependencies)

`uvicorn[standard]` 中的 `standard` 属于 **Uvicorn 包自己的依赖组**，与 FastAPI 的同名组不是一回事。它包括文件监控、协议支持及部分性能相关依赖；例如 `uvloop` 受平台限制，并非每个平台都会安装。[Uvicorn 安装说明](https://uvicorn.dev/installation/)

### 2.2 `all` 是否表示“所有功能都自动具备”？

`all` 只是维护者定义的依赖组名称，不是 Python 包管理器中的特殊关键字，也不会自动安装整个 FastAPI 生态。比如，数据库驱动、ORM 和业务需要的第三方 SDK 仍应单独选择。[extras 规范](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#extras)

在当前仓库配置中，`all` 包含 `itsdangerous`、`pyyaml` 等附加库。**不同版本的依赖组可能调整，不能仅凭名字认定 `all` 永远是 `standard` 的严格超集。** 网上旧教程列出的清单也可能与新版本不同。[FastAPI 包配置](https://github.com/fastapi/fastapi/blob/master/pyproject.toml)

本篇采用 `fastapi[standard]`：它能直接支持后面的 CLI 启动步骤。暂时不必为了“完整”而安装 `all`。

### 2.3 只安装 `fastapi` 会失去自动文档吗？

不会。路由、基于 Pydantic 的校验，以及 OpenAPI、Swagger UI、ReDoc 的集成都属于框架能力。基础安装缺少的是部分配套依赖，例如服务器和可用的 FastAPI CLI。补装 Uvicorn 并运行应用后，仍可访问 `/docs`。[自动文档](https://fastapi.tiangolo.com/tutorial/first-steps/)、[CLI 说明](https://fastapi.tiangolo.com/fastapi-cli/)

例如，下面是一种可行的手动组合（这是替代方案，不需要与后面的标准安装重复执行）：

```bash
python -m pip install fastapi "uvicorn[standard]"
python -m uvicorn main:app --reload
```

这里没有安装 `fastapi-cli`，因此应使用 Uvicorn 命令启动，不能假定 `fastapi dev` 已可用。

## 3. 安装环境：选择 pip 或 uv 中的一种

下面默认从项目根目录 `fastApi-learn/` 开始执行命令。两套方式都可以完成练习；选定一种后，后续使用对应的启动命令。

### 方式 A：使用 Python 自带的 venv 和 pip

适合希望先熟悉 Python 虚拟环境的同学。以下为 macOS / Linux 命令：

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "fastapi[standard]"
```

首先确认版本是 **3.11 或更高**。如果 `python3` 指向旧版本，需要先安装符合要求的 Python，并使用对应解释器创建环境。

这些命令分别用于查看版本、创建项目虚拟环境、激活环境、安装依赖。`.venv` 将本项目的包与其他项目隔离；`python -m pip` 使用当前 Python 对应的 pip，减少装错环境的情况。[FastAPI 虚拟环境教程](https://fastapi.tiangolo.com/virtual-environments/)

Windows PowerShell 对应命令为：

```powershell
py -3.11 --version
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install "fastapi[standard]"
```

这里假定已经安装 Python 3.11；如果使用其他符合要求的版本，替换相应版本参数。

安装后，在已激活环境的终端验证：

```bash
python -c "import sys, fastapi, pydantic; print(sys.executable); print('FastAPI:', fastapi.__version__); print('Pydantic:', pydantic.__version__)"
fastapi --help
```

第一条应输出 `.venv` 内的解释器路径和包版本，第二条应显示命令帮助。每次新开终端，都需要重新激活环境；使用完毕后执行 `deactivate` 退出环境。

### 方式 B：使用 uv 管理现有项目

项目根目录已经有 `pyproject.toml`，可以直接使用 uv 添加依赖，无需再次执行 `uv init`。先执行 `uv --version` 确认工具可用；尚未安装时，按 [uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)完成安装。

```bash
uv --version
uv add "fastapi[standard]"
uv run python -c "import sys, fastapi; print(sys.executable); print(fastapi.__version__)"
uv run fastapi --help
```

`uv add` 会把依赖写入 `pyproject.toml`，更新锁文件 `uv.lock` 并同步项目环境。`uv run` 使用项目环境执行命令，所以不需要先手动激活 `.venv`。[uv 项目指南](https://docs.astral.sh/uv/guides/projects/)

与之相比，前面的 `pip install` 只负责安装到当前环境，不会自动更新项目的 `pyproject.toml`。后续如果选择 uv 作为项目管理工具，应通过 `uv add` 记录依赖。

## 4. 编写第一个 FastAPI 应用

在 `02-FastAPI安装/` 子目录中新建 `main.py`。练习完成后，相关文件位置如下：

如果已经像当前项目一样，把 `main.py` 放在项目根目录，可以继续保留该位置，后面的启动命令也直接在根目录执行，无需另建一份文件或进入章节目录。

```text
fastApi-learn/
├── pyproject.toml
├── 01-FastAPI简介/
│   └── 01-FastAPI框架简介.md
└── 02-FastAPI安装/
    ├── 02-FastAPI安装与第一步使用.md
    └── main.py
```

将以下完整代码写入 `main.py`：

```python
from fastapi import FastAPI


app = FastAPI(title="FastAPI 入门练习")


@app.get("/")
def read_home():
    return {"message": "我的第一个 FastAPI 接口运行成功！"}


@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"你好，{name}！"}
```

先理解这几个部分：

| 代码 | 含义 |
| --- | --- |
| `from fastapi import FastAPI` | 导入用于创建应用的类 |
| `app = FastAPI(...)` | 创建应用对象，设置文档标题 |
| `@app.get("/")` | 把 `GET /` 请求关联到紧接着定义的函数 |
| `def read_home()` | 定义接收请求后执行的处理逻辑 |
| `return {"message": ...}` | 返回字典，由框架生成 JSON 响应 |
| `/hello/{name}` 与 `name: str` | 从路径读取名字，作为字符串传给函数 |

这些路由写法遵循官方入门示例；普通 `def` 可以直接使用，初次运行无需先学习异步编程。[第一步](https://fastapi.tiangolo.com/tutorial/first-steps/)

## 5. 启动服务

先从项目根目录进入本章目录：

```bash
cd 02-FastAPI安装
```

**使用 pip 安装且已激活环境时：**

```bash
fastapi dev main.py
```

**使用 uv 时：**

```bash
uv run fastapi dev main.py
# uv run XXXX 的意思是：「在我当前项目环境里运行 XXXX 这个命令」。它不要求你先手动激活虚拟环境（source .venv/bin/activate），uv run 会自动找到并激活项目环境，然后用这个环境去执行后面的命令。所以它后面的 fastapi 是用项目里安装的那个版本，而不是系统全局的。
# fastapi dev main.py 是真正的业务命令。FastAPI 自带的命令行工具（CLI）
# dev 子命令，表示「开发模式」，特点是代码改动后自动重启服务器（热重载）
# main.py — 告诉它去哪个文件找 FastAPI 应用实例
```

uv 会向上查找根目录的 `pyproject.toml` 并使用该项目环境。[uv 项目指南](https://docs.astral.sh/uv/guides/projects/)

正常启动后，终端会显示服务器地址 `http://127.0.0.1:8000`，并出现 `Application startup complete` 等日志。保持这个终端运行，再打开浏览器访问服务。[启动说明](https://fastapi.tiangolo.com/tutorial/first-steps/)

### `fastapi dev`、`fastapi run` 和 `uvicorn` 有什么区别？

| 命令 | 用途和默认行为 |
| --- | --- |
| `fastapi dev main.py` | 本地开发；默认自动重载，监听 `127.0.0.1` |
| `fastapi run main.py` | 面向生产运行；默认不自动重载，监听 `0.0.0.0` |
| `python -m uvicorn main:app --reload` | 直接调用 Uvicorn，并显式开启自动重载 |

FastAPI CLI 底层也使用 Uvicorn。`main:app` 中，`main` 是 Python 模块名（不带 `.py`），`app` 是模块中的应用对象；这条命令应在 `main.py` 所在目录执行。[FastAPI CLI](https://fastapi.tiangolo.com/fastapi-cli/)、[手动运行服务器](https://fastapi.tiangolo.com/deployment/manually/)

`127.0.0.1` 只监听本机回环地址，`0.0.0.0` 表示监听所有 IPv4 网络接口；它不是浏览器访问地址。`fastapi run` 也不等于自动部署到云端。本章使用 `dev` 即可。

直接执行 `python main.py` 只会定义应用和函数：示例中没有调用服务器启动代码，所以不会开始监听端口。

## 6. 访问接口与交互式文档

### 6.1 用浏览器访问

打开 `http://127.0.0.1:8000/`，预期返回：

```json
{"message": "我的第一个 FastAPI 接口运行成功！"}
```

再打开 `http://127.0.0.1:8000/hello/FastAPI`，预期返回：

```json
{"message": "你好，FastAPI！"}
```

浏览器地址栏在这里发起的是 GET 请求，因此能直接调用我们定义的两个 GET 接口。

### 6.2 在 Swagger UI 中调用

1. 打开 `http://127.0.0.1:8000/docs`。
2. 展开 `GET /hello/{name}`。
3. 点击 **Try it out**。
4. 在 `name` 输入框填写 `FastAPI`。
5. 点击 **Execute**，查看响应状态码 `200` 和返回的 JSON。

这是向应用发送的真实请求。你还可以访问 `/redoc` 阅读另一种样式的文档，或访问 `/openapi.json` 查看文档所依据的接口描述。[交互式文档](https://fastapi.tiangolo.com/tutorial/first-steps/#interactive-api-docs)

### 6.3 使用终端访问

保留运行服务的终端，再开一个终端执行：

```bash
curl -i "http://127.0.0.1:8000/hello/FastAPI"
```

`-i` 会同时显示响应头。你应看到 `200 OK`、JSON 类型的响应头和问候语响应体。

### 6.4 PyCharm 自动创建的 `test_main.http` 是什么？

**`.http` 是保存 HTTP 请求的纯文本文件，PyCharm 的 HTTP Client 可以读取它并发送请求。** PyCharm 创建 FastAPI 项目时，通常会同时生成 `main.py` 和 `test_main.http`：前者实现接口，后者提供调用接口的示例，方便创建项目后立即调试。[PyCharm 的 FastAPI 项目说明](https://www.jetbrains.com/help/pycharm/fastapi-project.html)

它由 IDE 项目模板提供，不是 FastAPI 运行必需的文件，也不是安装 `fastapi[standard]` 生成的。删除它不会影响接口运行；保留它则可以重复使用请求示例。文件名中的 `test_` 也不代表它会自动被 pytest 执行。

前面的步骤采用终端安装、手动创建应用，所以不会自动出现这个文件。对于使用 PyCharm 项目向导的同学，还需要了解这一配套工具。

#### 写入与本章接口对应的请求

可以在 `main.py` 旁边新建 `test_main.http`，或者编辑 PyCharm 已生成的文件：

```http
### 访问首页
GET http://127.0.0.1:8000/
Accept: application/json

### 使用名字打招呼
GET http://127.0.0.1:8000/hello/FastAPI
Accept: application/json
```

`###` 用来分隔请求并为请求命名；`GET` 是请求方法，后面是完整地址；`Accept: application/json` 表示客户端希望收到 JSON 响应，这两个接口即使省略该请求头也会返回 JSON。[HTTP 请求语法](https://www.jetbrains.com/help/pycharm/exploring-http-syntax.html)

使用步骤：

1. 先通过前面的终端命令，或 PyCharm 的 FastAPI 运行配置，启动应用。
2. 在 PyCharm 打开 `test_main.http`。
3. 点击目标请求左侧的运行按钮（▶）。
4. 在响应面板查看状态码、响应头和响应体；也可以运行文件中的全部请求。

点击 `.http` 请求的运行按钮是在调用服务，不会自动启动本章的 FastAPI 应用。服务未启动时通常会连接失败；修改服务端口后，也要修改请求中的端口。文件所在目录不决定请求目标，真正决定目标的是其中的 URL。[PyCharm 请求运行说明](https://www.jetbrains.com/help/pycharm/fastapi-project.html#http-client)

#### 它与 `/docs`、curl 有什么区别？

| 工具 | 在哪里使用 | 本章中适合做什么 |
| --- | --- | --- |
| Swagger UI（`/docs`） | 浏览器 | 查看自动生成的接口说明，填写参数后调用 |
| `.http` 文件 | PyCharm HTTP Client 等支持它的工具 | 保存请求地址、请求头和请求体，反复运行和分享示例 |
| curl | 终端 | 快速发送请求，便于写入命令或脚本 |

三者都可以调用同一个 FastAPI 接口，`.http` 也可以调用其他框架编写的 HTTP 服务。它还支持 POST 等方法、请求体、变量和响应断言；初学时先掌握上面的 GET 请求即可。[PyCharm HTTP Client](https://www.jetbrains.com/help/pycharm/http-client-in-product-code-editor.html)

## 7. 修改代码并停止服务

把 `read_home` 返回的文字改成其他内容，保存 `main.py`。开发模式会自动重载应用；等终端重新显示启动完成后，刷新浏览器即可看到新结果。文档页面也需要刷新才能显示路由变动。[开发模式说明](https://fastapi.tiangolo.com/fastapi-cli/#fastapi-dev)

结束练习时，在运行服务的终端按 `Ctrl+C`。停止后浏览器无法连接该地址，属于正常现象。若此前手动激活了虚拟环境，还可以执行 `deactivate`。

## 8. 常见问题

| 现象 | 排查和处理 |
| --- | --- |
| `zsh: no matches found: fastapi[standard]` | 将安装目标写成带引号的 `"fastapi[standard]"` |
| `No module named fastapi` | 检查执行代码的解释器是否为安装依赖的环境；pip 方式先激活，uv 方式使用 `uv run` |
| `fastapi: command not found`，或提示需要安装 CLI | 检查环境是否正确、是否只安装了基础包；在所选环境中安装 `fastapi[standard]` |
| 找不到 `main.py`，或无法导入 `main` | 确认已经进入 `02-FastAPI安装/`，并且文件已保存 |
| `Address already in use` | 检查是否已经启动过服务；也可执行 `fastapi dev main.py --port 8001`，并用新端口访问；uv 方式在命令前加 `uv run` |
| 浏览器无法连接 | 确认终端没有退出或报错，并检查访问地址、端口 |
| 返回 `404 Not Found` | 检查路径是否与代码一致，例如 `/hello/FastAPI` |
| `/docs` 空白，但接口和 `/openapi.json` 正常 | 默认文档页面依赖外部 CDN 的脚本和样式，检查网络或浏览器加载错误；需要离线使用时可配置本地资源 |

文档页面的资源加载机制参见[自托管文档静态资源](https://fastapi.tiangolo.com/how-to/custom-docs-ui-assets/)。

## 9. 查看自己实际安装了什么

如果使用 pip：

```bash
python -m pip show fastapi
python -m pip list
```

如果使用 uv，在项目内执行：

```bash
uv tree
```

`uv tree` 可以展示项目依赖树，帮助你观察 FastAPI 引入了哪些包。[uv 项目指南](https://docs.astral.sh/uv/guides/projects/)

依赖组会随版本变化。要查看**已安装版本**声明的 extras，可以在对应环境执行以下命令；uv 用户在命令前加 `uv run`：

```bash
python -c "from importlib.metadata import metadata; m = metadata('fastapi'); print('Version:', m['Version']); print('Extras:', m.get_all('Provides-Extra')); print('\n'.join(m.get_all('Requires-Dist') or []))"
```

输出中带 `extra == "standard"` 等条件的条目表示该可选依赖组的声明，并不意味着所有组都已安装；实际安装结果需要结合包列表或依赖树查看。

完成本篇时，你应该已经能在 `/` 看到响应，在 `/docs` 中调用接口，并解释：**`fastapi[standard]` 安装同一个框架，同时准备好常用配套依赖，让初次运行更方便。**
