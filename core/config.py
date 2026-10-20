from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量读取。"""

    # 数据库连接串（直接指定时优先使用）
    database_url: str = "mysql+pymysql://root:123456@localhost:3306/inventory"

    # 支持通过单独的 DB_* 环境变量组装 database_url（Docker 部署用）
    db_host: str | None = None
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "123456"
    db_name: str = "inventory"

    # 应用名称
    app_name: str = "进销存管理系统"

    # API 路由前缀，统一在 main.py 注册路由时指定，这里置空避免双前缀
    api_prefix: str = ""

    # 是否开启调试模式
    debug: bool = True

    # JWT 鉴权配置
    secret_key: str = "your-super-secret-key-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @model_validator(mode="after")
    def _build_database_url(self) -> "Settings":
        """若设置了 DB_HOST，则用 DB_* 变量组装 database_url。"""
        if self.db_host:
            self.database_url = (
                f"mysql+pymysql://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
