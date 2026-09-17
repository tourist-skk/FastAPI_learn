from fastapi import FastAPI
from utils.exception import generate_exception_handler
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from fastapi import HTTPException
from utils.exception import http_exception_handler,generate_exception_handler, sqlalchemy_exception_handler, integrity_error_handler

def register_exception_handlers(app: FastAPI):
    """
    注册异常处理函数: 子类在前，父类在后; 具体在前，通用在后; 其他异常在最后
    :param app: FastAPI实例
    """
    # 参数1: 异常类型
    # 参数2: 异常处理函数
    # 业务层面报错
    app.add_exception_handler(HTTPException, http_exception_handler)
    # 数据库层面报错
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    # 数据完整性报错
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    # 其他异常报错
    app.add_exception_handler(Exception, generate_exception_handler)