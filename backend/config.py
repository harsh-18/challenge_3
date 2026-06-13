import os
from pydantic_settings import BaseSettings
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
    ENV: str = os.getenv("ENV", "development")
    PROJECT_ID: str = os.getenv("PROJECT_ID", "mock-gcp-project")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Firestore / Firebase
    FIRESTORE_DATABASE: str = os.getenv("FIRESTORE_DATABASE", "(default)")
    
    # Mock settings
    USE_MOCK_SERVICES: bool = os.getenv("USE_MOCK_SERVICES", "true").lower() == "true"
    
    # Host and Port
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
