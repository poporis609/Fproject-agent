"""
Image Generator Agent for Strands AI
일기 텍스트를 이미지로 변환하는 AI Agent

사용 모델:
- 프롬프트 생성: Claude Sonnet 4.5
- 이미지 생성: Amazon Nova Canvas (1024x1280, 4:5 비율)
"""

from .agent import (
    image_generator_agent,
    run_image_generator,
    generate_image_from_text,
    upload_image_to_s3,
    build_prompt_from_text,
    health_check
)

__version__ = "1.0.0"
__all__ = [
    "image_generator_agent",
    "run_image_generator",
    "generate_image_from_text",
    "upload_image_to_s3",
    "build_prompt_from_text",
    "health_check"
]
