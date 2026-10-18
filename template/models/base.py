"""公共字段 Mixin。

所有业务表共享：id、is_deleted、created_at。
注意：部分表无 updated_at，故 updated_at 不放入公共 Mixin，
由需要的表自行声明。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column


class CommonMixin:
    """业务表公共字段 Mixin。"""

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    is_deleted: Mapped[int] = mapped_column(
        TINYINT, nullable=False, server_default="0", comment="逻辑删除：0正常 1已删除"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
