import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    PROJECT_NAME: str = "CV Management Service"
    BASE_DIR: str = str(Path(__file__).parent.parent.parent)  # project root
    CONTENT_DIR: str = os.path.join(BASE_DIR, "data", "categories")
    
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["*"]
    
    # External services
    HF_TOKEN: str
    HR_SMTP_GMAIL: str
    GPT_OSS_API: str
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    
    # Email settings
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    EMAIL_FROM: str = "hr@example.com"
    
    # Model settings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    LLM_MODEL: str = "openai/gpt-oss-120b"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()