"""
Tender Platform — Configuration
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://tp_user:tp_secret_2026@localhost:5432/tender_platform"
    
    # Redis (optional — empty string disables)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Meilisearch (optional — empty string disables)
    MEILI_URL: str = "http://localhost:7700"
    MEILI_KEY: str = "tp_meili_key_2026"
    
    # Auth
    SECRET_KEY: str = "change_me_in_production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ALGORITHM: str = "HS256"
    
    # App
    APP_NAME: str = "Tender Platform"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def async_database_url(self) -> str:
        """Convert Render's postgres:// to asyncpg format."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
