from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
        default="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
        description="Secret key for signing JWT tokens",
    )
    SECRET_KEY: str = Field(
        default="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
        description="Secret key for signing JWT tokens",
    )
    JWT_ALGORITHM: str = "HS256"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Operational Flags
    EMERGENCY_MAINTENANCE_MODE: bool = False
    MAX_CAMPUS_ORDERS_PER_HOUR: int = 1000

    # CORS: comma-separated (or JSON list) of allowed browser origins, e.g.
    # "https://app.saturdays.com,https://admin.saturdays.com".
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    # Preview and production apps on Vercel. Override to None to disable.
    CORS_ORIGIN_REGEX: str | None = r"https://.*\.vercel\.app"
    CORS_ALLOW_CREDENTIALS: bool = True

    # Razorpay (collections + RazorpayX payouts)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    RAZORPAYX_ACCOUNT_NUMBER: str = Field(
        default="", description="RazorpayX business account number payouts debit from"
    )
    RAZORPAY_BASE_URL: str = "https://api.razorpay.com/v1"
    # When true (default outside production) no real money moves: payment orders
    # and payouts are simulated locally. Production must set this to false.
    RAZORPAY_SIMULATE: bool = True

    # Refund policy: cancelled/unfulfilled orders get store credit, not cash back.
    # Keep false; true re-enables the legacy cash-refund endpoints.
    REFUNDS_ENABLED: bool = False

    # Payouts / store credit
    PAYOUT_MIN_AMOUNT: float = 1.0
    PAYOUT_SETTLEMENT_DELAY_HOURS: int = 0
    STORE_CREDIT_VALIDITY_DAYS: int = 90
    PAYOUT_SCHEDULER_ENABLED: bool = False
    PAYOUT_SCHEDULE_HOUR_UTC: int = 21  # 02:30 IST

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json

                return json.loads(v)
            return [o.strip().rstrip("/") for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod"}

    @property
    def cors_allow_credentials_effective(self) -> bool:
        # Browsers reject `Access-Control-Allow-Origin: *` together with credentials.
        return self.CORS_ALLOW_CREDENTIALS and "*" not in self.CORS_ORIGINS


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
