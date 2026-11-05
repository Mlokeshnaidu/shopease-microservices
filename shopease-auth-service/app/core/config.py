"""Reusable application settings loaded from the environment or .env file."""

from pydantic import SecretStr
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


_JWT_MINIMUM_KEY_BYTES = {
    "HS256": 32,
    "HS384": 48,
    "HS512": 64,
}


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

    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @model_validator(mode="after")
    def validate_jwt_configuration(self) -> "Settings":
        minimum_key_bytes = _JWT_MINIMUM_KEY_BYTES.get(self.jwt_algorithm)
        if minimum_key_bytes is None:
            raise ValueError("JWT_ALGORITHM must be HS256, HS384, or HS512.")

        key_bytes = self.jwt_secret_key.get_secret_value().encode("utf-8")
        if len(key_bytes) < minimum_key_bytes:
            raise ValueError(
                f"JWT_SECRET_KEY must contain at least {minimum_key_bytes} UTF-8 bytes "
                f"for {self.jwt_algorithm}."
            )

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
