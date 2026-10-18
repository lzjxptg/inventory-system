"""通用 FastAPI 依赖注入。

提供鉴权依赖 ``get_current_user``，从 Authorization: Bearer <token> 中
提取并校验 JWT，解析出用户名后查询数据库返回对应用户对象。
"""

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from core.database import get_db
from core.exceptions import UnauthorizedException
from core.security import decode_access_token
from models.user import User

# tokenUrl 指向登录接口（相对路径，由各 router 自带前缀）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从 JWT 解析当前登录用户。

    - token 缺失或解析失败 → 40101 未授权
    - token 有效但用户不存在/已删除/已禁用 → 40101 未授权
    """
    if not token:
        raise UnauthorizedException("未提供访问令牌")

    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedException("访问令牌无效或已过期")

    username: str | None = payload.get("sub")
    if not username:
        raise UnauthorizedException("访问令牌载荷无效")

    from crud.user import get_user_by_username

    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise UnauthorizedException("用户不存在或已被禁用")

    return user
