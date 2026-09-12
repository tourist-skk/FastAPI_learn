# 09 · FastAPI 响应类型：HTML

## 1. 定义

HTML 响应是以 HTML 标记作为响应体，让浏览器按网页渲染。FastAPI 使用 `HTMLResponse` 返回 HTML，通常会设置响应头：

```http
Content-Type: text/html; charset=utf-8
```

FastAPI 默认返回 JSON，直接 `return "<h1>Hello</h1>"` 会得到 JSON 字符串；要返回网页，需要指定 HTML 响应类型。[官方文档](https://fastapi.tiangolo.com/advanced/custom-response/#html-response)

## 2. 两种设置方式

### 2.1 在装饰器中指定 `response_class`

在路由装饰器中传入 `response_class=HTMLResponse`，函数只需要返回 HTML 字符串：

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


@app.get("/html", response_class=HTMLResponse)
def get_html():
    return "<h1>你好，FastAPI！</h1><p>这是一个 HTML 页面。</p>"
```

**工作方式：** FastAPI 使用 `HTMLResponse` 包装函数的返回值，并把响应的 `Content-Type` 设置为 `text/html`。`HTMLResponse` 在这里传入的是类，所以不加括号。

**适用场景：** 返回类型固定的普通 HTML 页面，例如帮助页、简单展示页。

**优点：** 写法简洁；OpenAPI 和 `/docs` 能正确记录响应类型为 `text/html`。

**缺点：** 如果需要根据不同情况动态设置状态码或响应头，处理起来不够直接。

### 2.2 直接返回 `HTMLResponse` 对象

也可以在函数内部创建并返回响应对象：


```python
@app.get("/html-object")
def get_html_object(success: bool = True):
    return HTMLResponse(
        content="<h1>操作成功</h1>" if success else "<h1>操作失败</h1>",
        status_code=200 if success else 400,
        headers={"X-Result": "success" if success else "failed"},
    )
```

**工作方式：** 函数自己创建完整的响应对象，FastAPI 直接将该对象发送给客户端，不再自动转换返回内容。

**适用场景：** 需要根据执行结果动态修改 HTML 内容、状态码或响应头。

**优点：** 控制更加灵活，可以通过 `content`、`status_code` 和 `headers` 分别设置响应内容、状态码和响应头。

**缺点：** 代码稍多；仅返回响应对象时，OpenAPI 和 `/docs` 不会自动得知该接口返回 `text/html`。[直接返回响应对象](https://fastapi.tiangolo.com/advanced/custom-response/#return-a-response)

### 2.3 核心区别

装饰器方式是告诉 FastAPI：“请使用这个响应类处理我的返回值。”返回响应对象则是告诉 FastAPI：“响应已经创建好了，请直接发送。”

另外，`response_class=HTMLResponse` 只是默认响应类。如果函数直接返回一个 `Response` 对象，FastAPI 会优先发送该对象，并不会强制它必须是 `HTMLResponse`。

## 3. 两种方式可以结合

在上面的 `main.py` 中追加：

```python
@app.get("/html-both", response_class=HTMLResponse)
def get_html_both(success: bool = True):
    return HTMLResponse(
        content="<h1>成功</h1>" if success else "<h1>失败</h1>",
        status_code=200 if success else 400,
    )
```

这种组合通常最完整：装饰器让 `/docs` 正确显示 `text/html`，返回对象负责实际内容、状态码和响应头。[文档声明与实际响应](https://fastapi.tiangolo.com/advanced/custom-response/#document-in-openapi-and-override-response)

选择方法时可以简单记为：普通 HTML 页面优先使用装饰器；需要动态控制响应时返回响应对象；既要动态控制又要准确的接口文档，就把两种方式结合起来。

## 4. 运行查看

在 `main.py` 所在目录启动：

```bash
uv run fastapi dev main.py
```

浏览器访问 `http://127.0.0.1:8000/html` 或 `http://127.0.0.1:8000/html-object`，即可看到渲染后的页面。

**记忆：装饰器传“类”，`return` 可以返回“响应对象”；仅写 HTML 字符串不会自动切换响应类型。**
