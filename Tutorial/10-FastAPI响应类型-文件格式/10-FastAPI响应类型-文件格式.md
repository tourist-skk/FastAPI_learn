# 10 · FastAPI 响应类型：文件

## 1. 定义

文件响应是将 PDF、图片、压缩包、音视频等内容发送给客户端。浏览器可以根据响应头决定直接预览文件，还是将文件下载到本地。

FastAPI 中常用的实现方式有：

- `FileResponse`：返回磁盘中已经存在的文件。
- `StreamingResponse`：分批读取并发送文件。
- `Response`：直接返回内存中的少量二进制数据。

## 2. 使用 `FileResponse`

`FileResponse` 适合返回路径已知、已经保存在磁盘中的文件。它会异步发送文件，并自动添加 `Content-Length`、`Last-Modified` 和 `ETag` 等响应头。[官方文档](https://fastapi.tiangolo.com/advanced/custom-response/#fileresponse)

### 2.1 直接返回 `FileResponse` 对象

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI()

FILE_PATH = Path("files/report.pdf")


@app.get("/download")
def download_file():
    return FileResponse(
        path=FILE_PATH,
        media_type="application/pdf",
        filename="report.pdf",
    )
```

常用参数：

- `path`：服务器上的文件路径。
- `media_type`：文件的 MIME 类型；省略时会根据文件名推断。
- `filename`：客户端保存文件时显示的名称，同时会设置 `Content-Disposition` 响应头。
- `headers`：需要额外添加的响应头。

这种写法可以直接控制下载文件名、响应头和状态码，适合普通的文件下载接口。

### 2.2 在装饰器中指定 `FileResponse`

```python
@app.get("/download-by-path", response_class=FileResponse)
def download_by_path():
    return str(FILE_PATH)
```

此时函数只需要返回文件路径，FastAPI 会使用 `FileResponse` 创建响应。写法更加简洁，并且接口文档能够记录响应类型；需要设置 `filename` 等参数时，直接返回 `FileResponse` 对象更方便。

## 3. 使用 `StreamingResponse`

`StreamingResponse` 会把文件分块发送，不需要先将整个文件读入内存，适合大文件、动态生成的文件以及连续的音视频数据。[流式响应文档](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)

```python
from collections.abc import Iterator

from fastapi.responses import StreamingResponse


def read_file() -> Iterator[bytes]:
    with open(FILE_PATH, "rb") as file:
        while chunk := file.read(1024 * 1024):
            yield chunk


@app.get("/stream")
def stream_file():
    return StreamingResponse(
        read_file(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="report.pdf"'
        },
    )
```

`yield` 每次返回一块数据。这里每次读取 1 MB，文件用完后，`with` 会自动关闭它。

这种方式节省内存，也能边生成边发送；缺点是需要自己管理文件读取、MIME 类型和下载响应头。

## 4. 使用普通 `Response` 返回二进制数据

如果文件内容很小，或者内容已经在内存中，可以直接返回字节数据：

```python
from fastapi import Response


@app.get("/small-file")
def get_small_file():
    content = b"Hello, FastAPI!"

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="hello.txt"'
        },
    )
```

`application/octet-stream` 表示通用二进制数据。这种方式简单，但响应内容会一次性保存在内存中，因此不适合大文件。

## 5. 如何选择

磁盘中已经存在的普通文件，优先使用 `FileResponse`。大文件或需要边生成边发送的内容，使用 `StreamingResponse`。已经存在于内存中的少量二进制内容，可以使用普通 `Response`。

无论使用哪种方式，都不要直接使用未经检查的用户输入拼接文件路径，否则可能让用户访问到不应该公开的服务器文件。

## 6. 运行查看

先在项目下创建 `files/report.pdf`，然后启动服务：

```bash
uv run fastapi dev main.py
```

访问 `http://127.0.0.1:8000/download`，即可下载文件。

**记忆：普通磁盘文件用 `FileResponse`，大文件或动态内容用 `StreamingResponse`，少量内存数据用 `Response`。**
