"""库存模块测试数据 seed 脚本。

幂等：已存在的记录会跳过，不重复插入。
所有操作在同一个事务中完成，出错自动回滚。

运行方式：
    .venv\\Scripts\\python.exe scripts/seed_inventory.py
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，便于直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from decimal import Decimal

from sqlalchemy import select

from core.database import SessionLocal
from models import Category, InventoryBalance, Product, StockMovement, Unit, User, Warehouse


def seed() -> None:
    """插入库存模块测试数据。"""
    session = SessionLocal()
    try:
        # a. 仓库：主仓库
        warehouse = session.execute(
            select(Warehouse).where(Warehouse.name == "主仓库", Warehouse.is_deleted == 0)
        ).scalars().first()
        if warehouse is None:
            warehouse = Warehouse(code="WH001", name="主仓库")
            session.add(warehouse)
            session.flush()
            print(f"[创建] 仓库: id={warehouse.id}, name={warehouse.name}")
        else:
            print(f"[跳过] 仓库已存在: id={warehouse.id}, name={warehouse.name}")

        # b. 单位：个
        unit = session.execute(
            select(Unit).where(Unit.name == "个", Unit.is_deleted == 0)
        ).scalars().first()
        if unit is None:
            unit = Unit(name="个")
            session.add(unit)
            session.flush()
            print(f"[创建] 单位: id={unit.id}, name={unit.name}")
        else:
            print(f"[跳过] 单位已存在: id={unit.id}, name={unit.name}")

        # c. 分类：测试分类（商品可选关联分类，此处创建以便商品完整）
        category = session.execute(
            select(Category).where(Category.name == "测试分类", Category.is_deleted == 0)
        ).scalars().first()
        if category is None:
            category = Category(name="测试分类")
            session.add(category)
            session.flush()
            print(f"[创建] 分类: id={category.id}, name={category.name}")
        else:
            print(f"[跳过] 分类已存在: id={category.id}, name={category.name}")

        # d. 商品：测试商品（编码字段为 sku）
        product = session.execute(
            select(Product).where(Product.sku == "P001", Product.is_deleted == 0)
        ).scalars().first()
        if product is None:
            product = Product(
                sku="P001",
                name="测试商品",
                category_id=category.id,
                unit_id=unit.id,
            )
            session.add(product)
            session.flush()
            print(f"[创建] 商品: id={product.id}, sku={product.sku}, name={product.name}")
        else:
            print(f"[跳过] 商品已存在: id={product.id}, sku={product.sku}, name={product.name}")

        # e. 操作人：取 admin 用户
        operator = session.execute(
            select(User).where(User.username == "admin", User.is_deleted == 0)
        ).scalars().first()
        if operator is None:
            raise RuntimeError("未找到 admin 用户，请先完成用户初始化")
        print(f"[使用] 操作人: id={operator.id}, username={operator.username}")

        # f. 库存余额：同一商品+仓库只一条，没有则插入 current_quantity=100
        balance = session.execute(
            select(InventoryBalance).where(
                InventoryBalance.product_id == product.id,
                InventoryBalance.warehouse_id == warehouse.id,
                InventoryBalance.is_deleted == 0,
            )
        ).scalars().first()
        if balance is None:
            balance = InventoryBalance(
                product_id=product.id,
                warehouse_id=warehouse.id,
                current_quantity=Decimal("100.00"),
            )
            session.add(balance)
            session.flush()
            print(
                f"[创建] 库存余额: product_id={product.id}, warehouse_id={warehouse.id}, "
                f"current_quantity={balance.current_quantity}"
            )
        else:
            print(
                f"[跳过] 库存余额已存在: product_id={product.id}, warehouse_id={warehouse.id}, "
                f"current_quantity={balance.current_quantity}"
            )

        # g. 入库流水：若该商品+仓库无 IN 流水则插入一条 quantity=100
        existing_in = session.execute(
            select(StockMovement).where(
                StockMovement.product_id == product.id,
                StockMovement.warehouse_id == warehouse.id,
                StockMovement.movement_type == "IN",
                StockMovement.is_deleted == 0,
            )
        ).scalars().first()
        if existing_in is None:
            movement = StockMovement(
                product_id=product.id,
                warehouse_id=warehouse.id,
                movement_type="IN",
                quantity=Decimal("100.00"),
                reference_type="ADJUST",
                operator_id=operator.id,
                remark="seed 初始入库",
            )
            session.add(movement)
            session.flush()
            print(
                f"[创建] 入库流水: id={movement.id}, product_id={product.id}, "
                f"warehouse_id={warehouse.id}, quantity={movement.quantity}"
            )
        else:
            print(
                f"[跳过] 入库流水已存在: id={existing_in.id}, product_id={product.id}, "
                f"warehouse_id={warehouse.id}, quantity={existing_in.quantity}"
            )

        session.commit()
        print("\n✅ Seed 完成，事务已提交。")
    except Exception as exc:
        session.rollback()
        print(f"\n❌ Seed 失败，事务已回滚: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
