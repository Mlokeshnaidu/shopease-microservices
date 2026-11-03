from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """Application configuration settings."""
    APP_NAME: str = Field(default="ShopEase Product Service", description="Application Name")
    APP_VERSION: str = Field(default="1.0.0", description="Application Version")
    DEBUG: bool = Field(default=False, description="Debug mode flag")
    HOST: str = Field(default="0.0.0.0", description="Server Host")
    PORT: int = Field(default=8003, description="Server Port")
    API_PREFIX: str = Field(default="/api", description="API Prefix")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

