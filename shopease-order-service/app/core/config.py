"""Environment-backed settings for the ShopEase order service."""

from pathlib import Path
from decimal import Decimal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    app_name: str = "ShopEase Order Service"
    app_version: str = "1.0.0"
    api_prefix: str = "/api"
    debug: bool = False

    database_url: SecretStr = SecretStr("")
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "shopease_order_db"
    mysql_user: str = "shopease_order"
    mysql_password: SecretStr = SecretStr("")

    jwt_public_key_file: Path = Path("../shopease-auth-service/keys/jwt_public.pem")
    jwt_algorithm: str = "RS256"
    auth_service_url: str = "http://localhost:8002"
    user_service_url: str = "http://localhost:8004"
    product_service_url: str = "http://localhost:8005"
    catalog_service_api_key: SecretStr = SecretStr("")
    default_shipping_charge: Decimal = Decimal("10.00")
    tax_rate: Decimal = Decimal("0.10")

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

    @field_validator("default_shipping_charge")
    @classmethod
    def validate_shipping_charge(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0:
            raise ValueError("DEFAULT_SHIPPING_CHARGE must be non-negative.")
        return value

    @field_validator("tax_rate")
    @classmethod
    def validate_tax_rate(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0:
            raise ValueError("TAX_RATE must be non-negative.")
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
