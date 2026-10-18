"""鉴权路由。

提供注册与登录接口。注册接口响应统一用 success() 包装；
登录接口使用 OAuth2PasswordRequestForm（表单提交 username/password），
成功后直接返回 OAuth2 标准格式 ``{"access_token": "...", "token_type": "bearer"}``，
不使用 success() 包裹——这是 Swagger UI OAuth2 密码流能正确读取 token 的前提。
"""

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from core.database import get_db
from core.exceptions import ConflictException, UnauthorizedException
from core.response import success
from core.security import create_access_token, verify_password
from crud.user import create_user, get_user_by_username
from schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["鉴权"])


@router.post("/register", response_model=None)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> dict:
    """用户注册。

    用户名唯一；若已存在则返回 40901 冲突。
    """
    if get_user_by_username(db, user_in.username) is not None:
        raise ConflictException(f"用户名 {user_in.username} 已存在")

    user = create_user(db, user_in)
    return success(data=UserOut.model_validate(user).model_dump(mode="json"), msg="注册成功")


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    """用户登录，返回 JWT 访问令牌。

    返回 OAuth2 标准格式：``{"access_token": "...", "token_type": "bearer"}``。
    故意不使用 success() 包装，以兼容 Swagger UI 的 OAuth2 密码流授权
    （Swagger 会从响应顶层读取 access_token 字段）。
    """
    user = get_user_by_username(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise UnauthorizedException("用户名或密码错误")
    if not user.is_active:
        raise UnauthorizedException("用户已被禁用")

    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}
