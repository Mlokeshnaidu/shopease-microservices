"""Reusable application settings loaded from the environment or .env file."""

from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    """Configuration values shared across the authentication service."""

    app_name: str = "ShopEase Authentication Service"
    app_version: str = "1.0.0"
    debug: bool = False
    api_prefix: str = "/api"

    database_url: SecretStr = SecretStr("")
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str
    mysql_user: str
    mysql_password: SecretStr

    jwt_private_key_file: Path = Path("keys/jwt_private.pem")
    jwt_public_key_file: Path = Path("keys/jwt_public.pem")
    jwt_algorithm: str = "RS256"
    access_token_expire_minutes: int = 30

    @field_validator("jwt_algorithm")
    @classmethod
    def require_rs256(cls, value: str) -> str:
        if value != "RS256":
            raise ValueError("JWT_ALGORITHM must be RS256.")
        return value

    @model_validator(mode="after")
    def validate_jwt_configuration(self) -> "Settings":
        if self.access_token_expire_minutes <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer.")

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_database_url(self) -> URL:
        """Return the configured URL, or build one safely from MySQL settings."""
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
