"""安全工具：密码哈希与 JWT 令牌。

- 密码哈希直接使用 bcrypt 库（不经过 passlib，避免 passlib 1.7.4
  与 bcrypt>=4.1 的已知不兼容问题）。
- JWT 使用 python-jose 生成与验证，密钥与算法从 core.config.settings 读取。
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    """对明文密码进行 bcrypt 哈希，返回字符串。"""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """生成 JWT 访问令牌。

    Args:
        data: 写入令牌的载荷（通常包含 sub=username）。
        expires_delta: 过期时长增量，为 None 时使用 settings 中的默认值。

    Returns:
        编码后的 JWT 字符串。
    """
    to_encode = data.copy()
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    """解码并验证 JWT，返回载荷；无效或过期返回 None。"""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload
    except JWTError:
        return None
