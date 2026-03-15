from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env from project root (talentlens/.env), regardless of CWD
_ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///./data/talentlens.db"
    GROQ_API_KEY: str = ""
    LLM_PROVIDER: str = "groq_free"
    UPLOAD_DIR: str = "./data/uploads"
    CHROMA_DIR: str = "./data/chroma"
    # Comma-separated allowed CORS origins. Use "*" for local dev.
    # Production example: "https://app.example.com,https://admin.example.com"
    CORS_ORIGINS: str = "*"


settings = Settings()
