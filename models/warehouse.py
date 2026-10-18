"""仓库表。"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

from .base import CommonMixin


class Warehouse(Base, CommonMixin):
    """仓库。"""

    __tablename__ = "warehouses"

    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="仓库编码"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="仓库名称")
    manager: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="负责人")

    __table_args__ = {"comment": "仓库表"}
