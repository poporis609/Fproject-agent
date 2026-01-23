"""
Application Configuration
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Diary Orchestrator Agent"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    AWS_REGION: str = "ap-northeast-2"
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


@dataclass
class TracingConfig:
    """Phoenix 트레이싱 설정"""
    phoenix_endpoint: str = field(default_factory=lambda: os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006"))
    project_name: str = field(default_factory=lambda: os.getenv("PHOENIX_PROJECT_NAME", "diary-agent"))
    enabled: bool = field(default_factory=lambda: os.getenv("TRACING_ENABLED", "true").lower() == "true")
    debug_mode: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    sample_rate: float = field(default_factory=lambda: float(os.getenv("TRACE_SAMPLE_RATE", "1.0")))
    jaeger_endpoint: Optional[str] = field(default_factory=lambda: os.getenv("JAEGER_ENDPOINT", None))
    batch_export: bool = True
    headers: Optional[dict] = None
    
    @classmethod
    def from_environment(cls) -> "TracingConfig":
        """환경변수에서 TracingConfig 생성"""
        return cls()
    
    def to_dict(self) -> dict:
        """설정을 딕셔너리로 변환"""
        return {
            "phoenix_endpoint": self.phoenix_endpoint,
            "project_name": self.project_name,
            "enabled": self.enabled,
            "debug_mode": self.debug_mode,
            "sample_rate": self.sample_rate,
            "jaeger_endpoint": self.jaeger_endpoint,
            "batch_export": self.batch_export,
        }
