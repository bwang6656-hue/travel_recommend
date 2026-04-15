from passlib.context import CryptContext
from app.config.config import PASSWORD_SCHEMES

# 密码加密配置
pwd_context = CryptContext(schemes=PASSWORD_SCHEMES, deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码和加密密码是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成密码的加密哈希值"""
    return pwd_context.hash(password)
