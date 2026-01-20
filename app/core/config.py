"""
Application Configuration
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Diary Orchestrator Agent"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
