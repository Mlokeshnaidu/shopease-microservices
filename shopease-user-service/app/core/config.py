"""Environment-backed settings for the User Management Service."""

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


_JWT_MINIMUM_KEY_BYTES = {"HS256": 32, "HS384": 48, "HS512": 64}


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

    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    auth_service_url: str = "http://localhost:8002"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_jwt_configuration(self) -> "Settings":
        minimum_key_bytes = _JWT_MINIMUM_KEY_BYTES.get(self.jwt_algorithm)
        if minimum_key_bytes is None:
            raise ValueError("JWT_ALGORITHM must be HS256, HS384, or HS512.")
        if len(self.jwt_secret_key.get_secret_value().encode("utf-8")) < minimum_key_bytes:
            raise ValueError(
                f"JWT_SECRET_KEY must contain at least {minimum_key_bytes} UTF-8 bytes "
                f"for {self.jwt_algorithm}."
            )
        return self

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
