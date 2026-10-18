"""Pydantic Schema 聚合入口。

``_BaseSchema`` 为内部基类，仅提供 ``from_attributes`` 配置，
供各模块 Schema 继承。新增业务 Schema 请在各模块文件中定义。
"""

from pydantic import BaseModel, ConfigDict


class _BaseSchema(BaseModel):
    """内部基类：开启 ORM 对象属性读取。"""

    model_config = ConfigDict(from_attributes=True)
