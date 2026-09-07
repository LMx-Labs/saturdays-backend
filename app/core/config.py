from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_SECRET = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Saturdays Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/saturdays",
        description="Async PostgreSQL Database URL",
    )

    # JWT Authentication
    JWT_SECRET_KEY: str = Field(
        default=DEVELOPMENT_SECRET,
        description="Secret key for signing JWT tokens",
    )
    SECRET_KEY: str = Field(
        default=DEVELOPMENT_SECRET,
        description="Secret key for signing JWT tokens",
    )
    INTERNAL_CLEANUP_KEY: str = "development-cleanup-key"
    JWT_ALGORITHM: str = "HS256"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    INVITATION_EXPIRE_DAYS: int = 7

    # Operational Flags
    EMERGENCY_MAINTENANCE_MODE: bool = False
    MAX_CAMPUS_ORDERS_PER_HOUR: int = 1000

    PAYMENT_PROVIDER: str = "mock"
    RAZORPAY_KEY_ID: str | None = None
    RAZORPAY_KEY_SECRET: str | None = None
    RAZORPAY_WEBHOOK_SECRET: str | None = None
    CHECKOUT_QUOTE_TTL_MINUTES: int = Field(default=10, ge=1, le=60)

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @model_validator(mode="after")
    def validate_runtime_security(self):
        provider = self.PAYMENT_PROVIDER.lower()
        if provider not in {"mock", "razorpay"}:
            raise ValueError("PAYMENT_PROVIDER must be 'mock' or 'razorpay'")
        if provider == "razorpay" and not (
            self.RAZORPAY_KEY_ID and self.RAZORPAY_KEY_SECRET and self.RAZORPAY_WEBHOOK_SECRET
        ):
            raise ValueError("Razorpay credentials and webhook secret are required")
        if self.ENVIRONMENT.lower() in {"production", "prod"}:
            if provider == "mock":
                raise ValueError("Production PAYMENT_PROVIDER must use a configured provider")
            if self.JWT_SECRET_KEY == DEVELOPMENT_SECRET or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("Production JWT_SECRET_KEY must be a unique secret of 32+ characters")
            if self.SECRET_KEY == DEVELOPMENT_SECRET or len(self.SECRET_KEY) < 32:
                raise ValueError("Production SECRET_KEY must be a unique secret of 32+ characters")
            if not self.CORS_ORIGINS or "*" in self.CORS_ORIGINS:
                raise ValueError("Production CORS_ORIGINS must list explicit trusted origins")
            if (
                self.INTERNAL_CLEANUP_KEY == "development-cleanup-key"
                or len(self.INTERNAL_CLEANUP_KEY) < 32
            ):
                raise ValueError("Production INTERNAL_CLEANUP_KEY must be a unique secret")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
