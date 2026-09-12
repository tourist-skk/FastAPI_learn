# 12 · FastAPI 异常响应处理

## 1. 定义

异常响应是接口无法正常完成请求时，返回给客户端的错误状态码和错误信息。

FastAPI 提供了 `HTTPException` 表示预期内的 HTTP 错误，例如资源不存在、没有权限或请求不符合业务规则。

```python
HTTPException(
    status_code=404,
    detail="商品不存在",
)
```

`HTTPException` 是异常对象，因此要使用 `raise` 抛出，不能使用 `return` 返回。[官方文档](https://fastapi.tiangolo.com/tutorial/handling-errors/)

## 2. 实现原理

当代码抛出异常时，当前请求后续的代码会停止执行。FastAPI 会寻找与该异常类型匹配的异常处理器，再由处理器生成 HTTP 响应。

FastAPI 已经为 `HTTPException` 和请求参数校验错误提供了默认处理器。没有被处理的其他异常通常会形成 500 服务器错误。

## 3. 方式一：抛出 `HTTPException`

```python
from fastapi import FastAPI, HTTPException, status

app = FastAPI()

products = {
    "1": {"id": "1", "name": "Keyboard"},
}


@app.get("/products/{product_id}")
def get_product(product_id: str):
    if product_id not in products:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "PRODUCT_NOT_FOUND",
                "message": "商品不存在",
            },
            headers={"X-Error-Code": "PRODUCT_NOT_FOUND"},
        )

    return products[product_id]
```

`HTTPException` 的常用参数：

- `status_code`：HTTP 错误状态码。
- `detail`：错误内容，可以是字符串、字典或列表等 JSON 兼容数据。
- `headers`：需要附加的响应头。

访问不存在的商品时，响应状态码为 404，响应体为：

```json
{
  "detail": {
    "code": "PRODUCT_NOT_FOUND",
    "message": "商品不存在"
  }
}
```

这种方式适合在某个接口、工具函数或依赖项中立即终止请求并返回明确错误。

## 4. 方式二：处理自定义业务异常

如果同一种业务错误可能在多个位置出现，可以先定义普通 Python 异常，再使用 `@app.exception_handler()` 统一生成响应：

```python
from fastapi import Request
from fastapi.responses import JSONResponse


class OutOfStockError(Exception):
    def __init__(self, product_id: str):
        self.product_id = product_id


@app.exception_handler(OutOfStockError)
async def out_of_stock_handler(
    _request: Request,
    exc: OutOfStockError,
):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "code": "OUT_OF_STOCK",
            "message": f"商品 {exc.product_id} 库存不足",
        },
    )


@app.post("/orders/{product_id}")
def create_order(product_id: str):
    if product_id == "2":
        raise OutOfStockError(product_id)

    return {"message": "订单创建成功"}
```

路由只负责抛出业务异常，异常处理器负责决定状态码和响应格式。这样可以让多个接口共用统一的错误结构。

## 5. 方式三：覆盖请求校验异常

当路径参数、查询参数或请求体不符合类型要求时，FastAPI 会抛出 `RequestValidationError`，默认返回 422 响应。可以覆盖其处理器，自定义错误结构：

```python
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
):
    errors = [
        {
            "location": ".".join(map(str, error["loc"])),
            "message": error["msg"],
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "code": "VALIDATION_ERROR",
            "message": "请求参数校验失败",
            "errors": errors,
        },
    )


class Order(BaseModel):
    product_id: int
    quantity: int


@app.post("/orders")
def submit_order(order: Order):
    return order
```

例如把 `quantity` 传成无法转换为整数的字符串时，请求会在进入 `submit_order()` 之前失败，然后由自定义校验异常处理器返回响应。

## 6. 如何选择

单个位置出现的预期错误，直接抛出 `HTTPException`。多个接口共用的业务错误，定义异常类并注册全局异常处理器。需要统一修改参数校验错误格式时，覆盖 `RequestValidationError` 的处理器。

**记忆：业务代码负责 `raise` 异常，异常处理器负责把异常转换成 HTTP 响应。**
