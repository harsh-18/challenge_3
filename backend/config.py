"""
Application configuration using pydantic-settings.
Reads environment variables automatically without redundant os.getenv wrapping.
"""
import os
import logging
from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator
from dotenv import load_dotenv

# Load env file strictly from local directory or parent project folder
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_env = os.path.join(current_dir, ".env")
project_env = os.path.join(os.path.dirname(current_dir), ".env")

if os.path.exists(backend_env):
    load_dotenv(backend_env)
elif os.path.exists(project_env):
    load_dotenv(project_env)


class Settings(BaseSettings):
    """Central application settings. Reads from environment variables automatically."""

    ENV: str = "development"
    PROJECT_ID: str = "mock-gcp-project"
    GEMINI_API_KEY: str = ""

    # Groq fallback LLM (used when Gemini API key is missing or fails)
    GROQ_API_KEY: str = ""

    # Firestore / Firebase
    FIRESTORE_DATABASE: str = "(default)"

    # Mock settings
    USE_MOCK_SERVICES: bool = True

    # Host and Port
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security settings
    CORS_ORIGINS: List[str] = [
        "https://genai-apac-2-497615.web.app",
        "https://ecosphere-ai-app.web.app",
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    MAX_UPLOAD_SIZE_MB: int = 8

    # Logging
    LOG_LEVEL: str = "INFO"

    @field_validator("USE_MOCK_SERVICES", mode="before")
    @classmethod
    def parse_mock_services(cls, v: object) -> bool:
        if isinstance(v, str):
            return v.lower() == "true"
        return bool(v)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


def setup_logging() -> None:
    """Configure structured logging for the application."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
