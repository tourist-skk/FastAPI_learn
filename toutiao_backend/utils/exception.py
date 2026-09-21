import logging
import traceback
from fastapi import Request

from fastapi.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError,SQLAlchemyError
from fastapi.responses import JSONResponse
from fastapi import status


# 使用 Uvicorn 已配置的终端日志输出。
logger = logging.getLogger("uvicorn.error")

# 只控制响应中的错误详情，不控制终端日志。
# 开发模式: 返回详细的错误信息
# 生产模式: 返回简化的错误信息
DEBUG_MODE = True


async def http_exception_handler(request : Request, exc: HTTPException):
    """
    处理HTTP异常
    :param request: 请求对象
    :param exc: 异常对象
    :return: JSONResponse
    """

    # # HTTPException 通常是业务逻辑主动抛出的，data 保持 None
    return JSONResponse(
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "data": None
        }, 
        status_code=exc.status_code
    )

# 实际业务会枚举错误类型吗? 
async def integrity_error_handler(request : Request, exc: IntegrityError):
    """
    处理数据库完整性约束错误
    :param request: 请求对象
    :param exc: 异常对象
    :return: JSONResponse
    """
    logger.error(
        "数据库约束异常：%s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    error_msg = str(exc.orig)

    if "username_UNIQUE" in error_msg or "Duplicate entry" in error_msg:
        detail = "用户名已存在"
    elif "FOREIGN KEY" in error_msg:
        detail = "关联数据不存在"
    else:
        detail = "数据约束冲突，请检查输入"

    # 开发模式返回详细的错误信息
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type" : "IntegrityError",
            "error_detail" : error_msg,
            "path": str(request.url)
        }
    # HTTPException 自带状态码，因此直接读取；IntegrityError 不知道 HTTP 是什么，所以由应用决定
  # 返回 400、409 或其他状态
    return JSONResponse(
        content={
            "code": 400,
            "message": detail,
            "data": error_data
        }, 
        status_code=status.HTTP_400_BAD_REQUEST
    )

async def sqlalchemy_exception_handler(request : Request, exc: SQLAlchemyError):
    """
    处理SQLAlchemy异常
    :param request: 请求对象
    :param exc: 异常对象
    :return: JSONResponse
    """
    logger.error(
        "数据库操作异常：%s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type" : type(exc).__name__,
            "error_detail" : str(exc),
            "path": str(request.url),
            # 格式化异常信息为字符串，方便日志记录和调试
            "traceback": traceback.format_exc()
        }

    return JSONResponse(
        content={
            "code": 500,
            "message": "数据库操作失败，请稍后重试",
            "data": error_data
        }, # 这里是否可以直接写500? 为什么
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

async def generate_exception_handler(request : Request, exc: Exception):
    """
    处理所有未捕获的异常类型
    :param request: 请求对象
    :param exc: 异常对象
    :return: JSONResponse
    """
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type" : type(exc).__name__,
            "error_detail" : str(exc),
            "path": str(request.url),
            # 格式化异常信息为字符串，方便日志记录和调试
            "traceback": traceback.format_exc()
        }
    return JSONResponse(
        content={
            "code": 500,
            "message": "服务器内部错误，请稍后重试",
            "data": error_data
        }, 
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
