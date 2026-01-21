"""
Image Generator Agent - Strands 기반 Master Agent
일기 텍스트를 이미지로 변환하는 AI Agent
"""

import os
import asyncio
from typing import Dict, Any

from strands import Agent, tool
from strands.models import BedrockModel

from .tools import ImageGeneratorTools
from app.services.utils.secrets import get_config

# 설정 로드
config = get_config()

# AWS 설정
AWS_REGION = config.get("AWS_REGION", os.environ.get("AWS_REGION", "ap-northeast-2"))

# Claude 모델 (에이전트 추론용)
model = BedrockModel(
    model_id=config.get("BEDROCK_CLAUDE_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    region_name=AWS_REGION
)

# Tools 인스턴스
_tools = ImageGeneratorTools()


# ============================================================================
# Strands Tools
# ============================================================================

@tool
def generate_image_from_text(text: str) -> Dict[str, Any]:
    """
    일기 텍스트를 입력받아 이미지를 생성합니다 (미리보기용, S3 업로드 없음).
    Claude로 프롬프트 변환 후 Nova Canvas로 이미지 생성.
    
    Args:
        text: 일기 텍스트 (한글)
    
    Returns:
        image_base64: 생성된 이미지 (base64)
        prompt: 사용된 프롬프트
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_tools.generate_image_from_text(text))
    finally:
        loop.close()


@tool
def upload_image_to_s3(user_id: str, image_base64: str, record_date: str = None) -> Dict[str, Any]:
    """
    이미지를 S3에 업로드합니다 (히스토리에 추가 버튼용).
    
    Args:
        user_id: 사용자 ID (cognito_sub)
        image_base64: 업로드할 이미지 (base64)
        record_date: 기록 날짜 (선택, ISO format)
    
    Returns:
        s3_key: S3 키
        image_url: 이미지 URL
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_tools.upload_image_to_s3(user_id, image_base64, record_date))
    finally:
        loop.close()


@tool
def build_prompt_from_text(text: str) -> Dict[str, Any]:
    """
    일기 텍스트를 이미지 생성 프롬프트로 변환합니다 (이미지 생성 없음).
    
    Args:
        text: 일기 텍스트 (한글)
    
    Returns:
        positive_prompt: 생성된 프롬프트
        negative_prompt: 네거티브 프롬프트
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_tools.build_prompt_from_text(text))
    finally:
        loop.close()


@tool
def health_check() -> Dict[str, Any]:
    """
    이미지 생성 서비스의 상태를 확인합니다.
    
    Returns:
        서비스 상태 정보
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_tools.health_check())
    finally:
        loop.close()


# ============================================================================
# Image Generator Agent
# ============================================================================

AGENT_SYSTEM_PROMPT = """당신은 일기 텍스트를 이미지로 변환하는 AI Agent입니다.

**사용 가능한 도구:**
1. generate_image_from_text: 텍스트 → 이미지 생성 (미리보기용, S3 업로드 X)
   - 입력: text (일기 텍스트)
   - 출력: image_base64, prompt

2. upload_image_to_s3: 이미지를 S3에 업로드 (히스토리에 추가용)
   - 입력: user_id (cognito_sub), image_base64, record_date (선택)
   - 출력: s3_key, image_url

3. build_prompt_from_text: 프롬프트만 생성 (이미지 생성 없음)
   - 입력: text
   - 출력: positive_prompt, negative_prompt

4. health_check: 서비스 상태 확인

**작업 흐름:**
- "미리보기", "이미지 생성" 요청 + text 제공 → generate_image_from_text 사용
- "업로드", "저장", "히스토리에 추가" 요청 + user_id, image_base64 제공 → upload_image_to_s3 사용
- "프롬프트 생성" 요청 → build_prompt_from_text 사용

**중요:**
- 미리보기는 S3에 업로드하지 않고 base64 이미지만 반환
- 히스토리에 추가할 때만 S3에 업로드
"""

image_generator_agent = Agent(
    model=model,
    system_prompt=AGENT_SYSTEM_PROMPT,
    tools=[
        generate_image_from_text,
        upload_image_to_s3,
        build_prompt_from_text,
        health_check,
    ]
)


def run_image_generator(
    request: str, 
    user_id: str = None, 
    text: str = None, 
    image_base64: str = None,
    record_date: str = None
) -> Dict[str, Any]:
    """
    Image Generator Agent 실행 함수
    
    Args:
        request: 사용자 요청 (자연어)
        user_id: 사용자 ID - cognito_sub (S3 업로드 시 필요)
        text: 일기 텍스트 (이미지 생성 시 필요)
        image_base64: 업로드할 이미지 (S3 업로드 시 필요)
        record_date: 기록 날짜 (S3 업로드 시 선택)
    
    Returns:
        tool 실행 결과를 그대로 반환 (success, image_base64 등 포함)
    """
    prompt = f"요청: {request}"
    if user_id:
        prompt += f"\nuser_id: {user_id}"
    if text:
        prompt += f"\n일기 텍스트: {text}"
    if image_base64:
        prompt += f"\nimage_base64: {image_base64[:100]}... (총 {len(image_base64)} 문자)"
    if record_date:
        prompt += f"\nrecord_date: {record_date}"
    
    try:
        # Agent 실행
        response = image_generator_agent(prompt)
        
        # Agent의 tool_results에서 실제 결과 추출
        if hasattr(response, 'tool_results') and response.tool_results:
            # 마지막 tool 결과 반환
            last_result = response.tool_results[-1]
            if isinstance(last_result, dict):
                return last_result
            elif hasattr(last_result, 'model_dump'):
                return last_result.model_dump()
            elif hasattr(last_result, 'dict'):
                return last_result.dict()
        
        # tool_results가 없으면 응답 텍스트 반환
        return {
            "success": True,
            "response": str(response)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
