"""客户表。"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

from .base import CommonMixin


class Customer(Base, CommonMixin):
    """客户。"""

    __tablename__ = "customers"

    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="客户编码"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="客户名称")
    contact: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="联系人")
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="联系电话")
    address: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="地址")

    __table_args__ = {"comment": "客户表"}
