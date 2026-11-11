"""Environment-backed settings for the User Management Service."""

from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

class Settings(BaseSettings):
    app_name: str = "ShopEase User Management Service"
    app_version: str = "1.0.0"
    api_prefix: str = "/api"

    database_url: SecretStr = SecretStr("")
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "shopease_user_db"
    mysql_user: str = "shopease_user"
    mysql_password: SecretStr = SecretStr("")

    jwt_public_key_file: Path = Path("keys/jwt_public.pem")
    jwt_algorithm: str = "RS256"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("jwt_algorithm")
    @classmethod
    def require_rs256(cls, value: str) -> str:
        if value != "RS256":
            raise ValueError("JWT_ALGORITHM must be RS256.")
        return value

    @property
    def sqlalchemy_database_url(self) -> URL:
        configured_url = self.database_url.get_secret_value()
        if configured_url:
            return make_url(configured_url)
        return URL.create(
            drivername="mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password.get_secret_value(),
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
        )


settings = Settings()
