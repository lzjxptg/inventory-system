"""客户门店表。

支持连锁客户多门店管理：一个客户下可有多个收货门店，
销售订单可指定具体送货门店（shop_id）。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

from .base import CommonMixin


class CustomerShop(Base, CommonMixin):
    """客户门店。"""

    __tablename__ = "customer_shops"

    customer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属客户ID",
    )
    shop_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="门店名称"
    )
    contact: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="联系人")
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="电话")
    address: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="收货地址")
    is_default: Mapped[int] = mapped_column(
        TINYINT, nullable=False, server_default="0", comment="是否默认门店：0否 1是"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    customer = relationship("Customer", lazy="select")

    __table_args__ = (
        UniqueConstraint(
            "customer_id", "shop_name", "is_deleted", name="uq_cs_customer_shop_name"
        ),
        Index("ix_customer_shops_customer_id", "customer_id"),
        {"comment": "客户门店表"},
    )
