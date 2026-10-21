"""供应商表。"""

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

from .base import CommonMixin


class Supplier(Base, CommonMixin):
    """供应商。"""

    __tablename__ = "suppliers"

    code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="供应商编码"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="供应商名称")
    contact: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="联系人")
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="联系电话")
    address: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="地址")

    __table_args__ = (
        UniqueConstraint("code", "is_deleted", name="uq_suppliers_code"),
        {"comment": "供应商表"},
    )
