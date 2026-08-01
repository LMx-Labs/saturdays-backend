from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Saturdays Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database Settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/saturdays"
    
    # Security Settings
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Environment Flags
    EMERGENCY_MAINTENANCE_MODE: bool = False
    MAX_CAMPUS_ORDERS_PER_HOUR: int = 1000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
