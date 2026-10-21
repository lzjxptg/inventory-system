"""商品表。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

from .base import CommonMixin


class Product(Base, CommonMixin):
    """商品。"""

    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(50), nullable=False, comment="商品编码")
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="商品名称")
    category_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
        comment="分类ID",
    )
    unit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=False,
        comment="单位ID",
    )
    spec: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="规格型号")
    purchase_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0.00", comment="参考采购价"
    )
    sale_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0.00", comment="参考销售价"
    )
    min_stock: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0.000", comment="最低库存预警"
    )
    status: Mapped[int] = mapped_column(
        TINYINT, nullable=False, server_default="1", comment="状态：1上架 0下架"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    __table_args__ = (
        # 逻辑删除后旧记录仍占 sku，故唯一索引包含 is_deleted，使已删除记录不占用 sku
        Index("uq_products_sku", "sku", "is_deleted", unique=True),
        Index("ix_products_name_category", "name", "category_id"),
        Index("ix_products_category_id", "category_id"),
        {"comment": "商品表"},
    )
