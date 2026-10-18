"""商品分类表（支持树形结构）。"""

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

from .base import CommonMixin


class Category(Base, CommonMixin):
    """商品分类。"""

    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="分类名称")
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
        comment="父分类ID，NULL为顶级",
    )
    sort: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", comment="排序"
    )

    parent: Mapped["Category | None"] = relationship(
        "Category", remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list["Category"]] = relationship(
        "Category", back_populates="parent"
    )

    __table_args__ = (
        Index("ix_categories_parent_id", "parent_id"),
        {"comment": "商品分类表"},
    )
