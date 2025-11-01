"""
Application Configuration
Manages environment variables and settings
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # Application
    APP_NAME: str = "DisruptIQ"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # API
    API_PREFIX: str = "/api"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:3003"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into list"""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return self.CORS_ORIGINS

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://disruptiq:disruptiq@postgres:5432/disruptiq"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_ENABLED: bool = True

    @property
    def redis_url(self) -> str:
        """Get Redis URL"""
        return self.REDIS_URL

    @property
    def redis_enabled(self) -> bool:
        """Check if Redis caching is enabled"""
        return self.REDIS_ENABLED

    # Qdrant Vector Database
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_COLLECTION_NAME: str = "disruptiq_documents"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Anthropic (Fallback)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-opus-20240229"

    # Gmail API
    GMAIL_CREDENTIALS_PATH: str = "./credentials/gmail_credentials.json"
    GMAIL_TOKEN_PATH: str = "./credentials/gmail_token.json"
    GMAIL_SCOPES: str = "https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.modify"

    @property
    def gmail_scopes_list(self) -> List[str]:
        """Parse GMAIL_SCOPES string into list"""
        if isinstance(self.GMAIL_SCOPES, str):
            return [scope.strip() for scope in self.GMAIL_SCOPES.split(",")]
        return self.GMAIL_SCOPES

    # N8N Webhooks
    N8N_WEBHOOK_BASE_URL: str = ""
    N8N_WEBHOOK_AUTH_TOKEN: str = ""
    N8N_TIMEOUT: int = 30
    N8N_MAX_RETRIES: int = 3

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Document Processing
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".docx", ".doc", ".txt"]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


settings = Settings()
