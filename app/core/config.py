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
        "http://localhost:8443",
        "http://localhost:8444",
        "http://localhost:8445",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8443",
        "http://127.0.0.1:8444",
        "http://127.0.0.1:8445",
        "https://saturdays.co.in",
        "https://www.saturdays.co.in",
        "https://saturdays-lmx.web.app",
        "https://saturdays-admin.web.app",
        "https://saturdays-restaurant.web.app",
        "https://saturdays-lmx.firebaseapp.com",
        "https://saturdays-admin.firebaseapp.com",
        "https://saturdays-restaurant.firebaseapp.com",
    ]
    # Preview and production apps on Vercel and Firebase. Override to None to disable.
    CORS_ORIGIN_REGEX: str | None = (
        r"^https://.*(\.vercel\.app|\.web\.app|\.firebaseapp\.com|saturdays\.co\.in)$"
    )
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

    # WhatsApp order updates (Meta WhatsApp Business Cloud API). Off until switched on:
    # nothing is sent, and orders behave exactly as before. See WHATSAPP_SETUP.md.
    WHATSAPP_ENABLED: bool = False
    # "cloud" sends for real; "mock" only logs (local development, demos, tests).
    WHATSAPP_PROVIDER: str = "cloud"
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_API_VERSION: str = "v21.0"
    WHATSAPP_API_BASE_URL: str = "https://graph.facebook.com"
    # Secret for checking that delivery reports really come from Meta (the app secret).
    WHATSAPP_APP_SECRET: str = ""
    # A password you invent; Meta sends it back once when you register the webhook.
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_LANGUAGE: str = "en"
    # The approved template for each event. Leave one empty to switch that message off.
    WHATSAPP_TEMPLATE_ORDER_CONFIRMED: str = "order_confirmed"
    WHATSAPP_TEMPLATE_ORDER_READY: str = "order_ready"
    WHATSAPP_TEMPLATE_ORDER_CANCELLED: str = "order_cancelled"
    # While testing: comma-separated numbers (digits, with country code). When set, ONLY
    # these numbers are ever messaged, so nobody else receives a test message by mistake.
    WHATSAPP_TEST_ALLOWLIST: str = ""
    WHATSAPP_DEFAULT_COUNTRY_CODE: str = "91"
    # A slow WhatsApp must never hold up an order: give up after this many seconds.
    WHATSAPP_TIMEOUT_SECONDS: float = 3.5

    # An order waits for payment this long (minutes) before it is cancelled as abandoned. The
    # restaurant never sees an order until it is paid; the student's store credit is returned.
    ORDER_PAYMENT_WINDOW_MINUTES: int = 30

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
