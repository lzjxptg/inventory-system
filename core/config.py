from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量读取。"""

    # 数据库连接串，格式：mysql+pymysql://user:password@host:port/dbname
    database_url: str = "mysql+pymysql://root:123456@localhost:3306/inventory"

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

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
