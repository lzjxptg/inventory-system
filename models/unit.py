"""单位表。"""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

from .base import CommonMixin


class Unit(Base, CommonMixin):
    """计量单位。"""

    __tablename__ = "units"

    name: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="单位名称（个/箱/件/包）"
    )
    code: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="单位编码")
    sort: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", comment="排序"
    )

    __table_args__ = (
        UniqueConstraint("name", "is_deleted", name="uq_units_name"),
        {"comment": "单位表"},
    )
