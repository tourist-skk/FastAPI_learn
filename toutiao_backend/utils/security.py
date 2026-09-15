from passlib.context import CryptContext
import bcrypt
# 创建密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    pwd = password.encode("utf-8")
    return bcrypt.hashpw(pwd, bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd = plain_password.encode("utf-8")
    return bcrypt.verifypw(pwd, hashed_password.encode("utf-8"))
