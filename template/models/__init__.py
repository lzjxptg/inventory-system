"""ORM 模型聚合入口。

集中导入全部模型类，确保 ``import models`` 时所有表注册到 ``Base.metadata``。
建表脚本（``Base.metadata.create_all``）只需 ``import models`` 即可覆盖全部表。

新增业务模型后，请在此处追加导入，保证 Alembic autogenerate 能识别。
"""

from .user import User

__all__ = ["User"]
