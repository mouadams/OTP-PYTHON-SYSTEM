from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os


class Settings(BaseSettings):
    APP_NAME: str = "OTP System"
    DEBUG: bool = False

    # Database — defaults to the exact URL provided
    DATABASE_URL: str = "mysql+pymysql://root:@localhost/otp_system"

    # JWT
    SECRET_KEY: str = "super-secret-jwt-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # SMTP / Gmail
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "mouadtahiri1000@gmail.com"
    SMTP_PASSWORD: str = "oelq ckvq gfsr weqs"          # set in .env
    EMAIL_FROM_NAME: str = "OTP System"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
