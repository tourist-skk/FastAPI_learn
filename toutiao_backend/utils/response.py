from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Any
    


def success_response(data: Any = None, message: str = "success"):
    # 目标:把任何的 FastAPI、Pydantic、ORM对象 都要正常响应 + code、 message、 data
    content = {
        "code": 0,
        "message": message,
        "data": jsonable_encoder(data)
    }
    return JSONResponse(content=jsonable_encoder(content))
