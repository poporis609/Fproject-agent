"""
Image Generator Tools - boto3 기반 직접 AWS 호출
TypeScript 서비스 없이 독립 실행
"""

import os
import json
import base64
import random
import time
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime

import boto3

from agent.utils.secrets import get_config

logger = logging.getLogger(__name__)

# ============================================================================
# 설정
# ============================================================================

# 설정 로드
config = get_config()

# Nova Canvas 설정
NOVA_CANVAS_MODEL_ID = config.get("BEDROCK_NOVA_CANVAS_MODEL_ID", "amazon.nova-canvas-v1:0")
# Claude 모델 ID - cross-region inference prefix 제거
CLAUDE_MODEL_ID_RAW = config.get("BEDROCK_LLM_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
# invoke_model API는 prefix 없이 사용
CLAUDE_MODEL_ID = CLAUDE_MODEL_ID_RAW.replace("us.", "") if CLAUDE_MODEL_ID_RAW.startswith("us.") else CLAUDE_MODEL_ID_RAW

AWS_REGION = config.get("AWS_REGION", os.getenv("AWS_REGION", "us-east-1"))
S3_BUCKET = config.get("KNOWLEDGE_BASE_BUCKET", os.getenv("KNOWLEDGE_BASE_BUCKET", "knowledge-base-test-6575574"))

print(f"[ImageGenerator] Using Claude Model: {CLAUDE_MODEL_ID}")
print(f"[ImageGenerator] Using Nova Canvas Model: {NOVA_CANVAS_MODEL_ID}")

# 이미지 생성 설정
IMAGE_CONFIG = {
    "width": 1024,
    "height": 1280,
    "cfg_scale": 6.5,
    "number_of_images": 1
}

# Negative Prompt
NEGATIVE_PROMPT = """anime, cartoon, illustration, painting, sketch, drawing, 3d render, cgi, unreal engine, fantasy, surreal, low quality, low resolution, blurry, out of focus, noise, overexposed, underexposed, jpeg artifacts, deformed body, distorted face, bad anatomy, extra fingers, missing fingers, fused fingers, extra limbs, missing limbs, overly posed, studio lighting, text, caption, subtitle, watermark, logo, wrong food, wrong animal, substituted items, inaccurate details"""

# Claude 시스템 프롬프트
SYSTEM_PROMPT = """You are an expert at converting Korean diary entries into detailed English image generation prompts for realistic photography.

CRITICAL RULES:
1. Read the Korean diary CAREFULLY and extract ALL visual elements
2. Your output must be ONLY the English prompt - no explanations, no Korean text
3. The prompt must accurately reflect what is described in the diary

MUST INCLUDE if mentioned in diary:
- WEATHER: rainy, sunny, cloudy, snowy, foggy, etc.
- TIME OF DAY: morning light, afternoon, sunset, evening, night
- LOCATION: indoor/outdoor, home, cafe, park, street, window view
- ANIMALS: dog, cat, etc. with specific actions they're doing
- MOOD: cozy, peaceful, melancholic, warm, lonely, happy

CRITICAL - TOGETHERNESS:
- If the diary mentions doing something WITH a pet, the image MUST show BOTH the person AND the animal TOGETHER
- Use phrases like "a person walking together with their dog", "owner and dog side by side"

CRITICAL - ETHNICITY:
- ALL people in the image MUST be Asian/East Asian
- Always include "Asian" or "East Asian" when describing people

PROMPT STRUCTURE:
"A realistic photo of [Asian person and animal together doing activity], [weather conditions], [lighting], [specific details], [mood/atmosphere], natural photography style, high quality"

Keep prompt under 500 characters."""


# ============================================================================
# AWS 클라이언트
# ============================================================================

_bedrock_client = None
_s3_client = None


def get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    return _bedrock_client


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=AWS_REGION)
    return _s3_client


# ============================================================================
# 핵심 기능
# ============================================================================

def generate_prompt_with_claude(journal_text: str) -> Dict[str, str]:
    """Claude를 사용하여 한글 일기를 영어 프롬프트로 변환"""
    client = get_bedrock_client()
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"Convert this Korean diary entry into an English image generation prompt:\n\n{journal_text}"
            }
        ]
    }
    
    try:
        response = client.invoke_model(
            modelId=CLAUDE_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response["body"].read())
        generated_prompt = response_body.get("content", [{}])[0].get("text", "").strip()
        
        if len(generated_prompt) > 1024:
            generated_prompt = generated_prompt[:1021] + "..."
        
        logger.info(f"[PromptBuilder] Generated prompt: {generated_prompt[:100]}...")
        
        return {
            "positive_prompt": generated_prompt,
            "negative_prompt": NEGATIVE_PROMPT
        }
    except Exception as e:
        logger.error(f"[PromptBuilder] Claude error: {e}")
        return {
            "positive_prompt": f"A realistic documentary-style photo representing: {journal_text[:200]}",
            "negative_prompt": NEGATIVE_PROMPT
        }


def generate_image_with_nova(positive_prompt: str, negative_prompt: str = None) -> Dict[str, Any]:
    """Nova Canvas로 이미지 생성"""
    client = get_bedrock_client()
    
    seed = random.randint(0, 2147483647)
    
    request_body = {
        "taskType": "TEXT_IMAGE",
        "textToImageParams": {
            "text": positive_prompt,
            "negativeText": negative_prompt or NEGATIVE_PROMPT
        },
        "imageGenerationConfig": {
            "cfgScale": IMAGE_CONFIG["cfg_scale"],
            "seed": seed,
            "width": IMAGE_CONFIG["width"],
            "height": IMAGE_CONFIG["height"],
            "numberOfImages": IMAGE_CONFIG["number_of_images"]
        }
    }
    
    try:
        logger.info(f"[ImageGenerator] Generating image with Nova Canvas (seed: {seed})...")
        
        response = client.invoke_model(
            modelId=NOVA_CANVAS_MODEL_ID,
            contentType="application/json",
            accept="*/*",
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response["body"].read())
        
        if not response_body.get("images"):
            return {"success": False, "error": "No images returned from Nova Canvas"}
        
        image_base64 = response_body["images"][0]
        logger.info("[ImageGenerator] Image generated successfully")
        
        return {
            "success": True,
            "image_base64": image_base64
        }
    except Exception as e:
        logger.error(f"[ImageGenerator] Nova Canvas error: {e}")
        return {"success": False, "error": str(e)}


def upload_to_s3(user_id: str, image_base64: str, record_date: str = None) -> Dict[str, str]:
    """
    S3에 이미지 업로드
    경로: {user_id}/history/{년}/{월}/{일}/image_{timestamp}.png
    """
    client = get_s3_client()
    
    # record_date가 있으면 그 날짜 사용, 없으면 현재 시간
    if record_date:
        try:
            dt = datetime.fromisoformat(record_date.replace('Z', '+00:00'))
        except:
            dt = datetime.utcnow()
    else:
        dt = datetime.utcnow()
    
    year = dt.strftime("%Y")
    month = dt.strftime("%m")
    day = dt.strftime("%d")
    timestamp = int(time.time() * 1000)
    
    s3_key = f"{user_id}/history/{year}/{month}/{day}/image_{timestamp}.png"
    
    try:
        image_bytes = base64.b64decode(image_base64)
        
        client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=image_bytes,
            ContentType="image/png"
        )
        
        image_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        logger.info(f"[S3] Uploaded: {s3_key}")
        
        return {
            "s3_key": s3_key,
            "image_url": image_url
        }
    except Exception as e:
        logger.error(f"[S3] Upload error: {e}")
        raise


# ============================================================================
# Tools 클래스 (DB 의존성 없음)
# ============================================================================

class ImageGeneratorTools:
    """Image Generator Agent의 도구 모음 - DB 없이 동작"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    async def generate_image_from_text(self, text: str) -> Dict[str, Any]:
        """
        텍스트에서 이미지 생성 (미리보기용, S3 업로드 X)
        
        Args:
            text: 일기 텍스트 (한글)
        
        Returns:
            image_base64: 생성된 이미지 (base64)
            prompt: 사용된 프롬프트
        """
        try:
            # 1. Claude로 프롬프트 생성
            prompt_result = generate_prompt_with_claude(text)
            
            # 2. Nova Canvas로 이미지 생성
            image_result = generate_image_with_nova(
                prompt_result["positive_prompt"],
                prompt_result["negative_prompt"]
            )
            
            if not image_result["success"]:
                return {"success": False, "error": image_result["error"]}
            
            return {
                "success": True,
                "image_base64": image_result["image_base64"],
                "prompt": {
                    "positive": prompt_result["positive_prompt"],
                    "negative": prompt_result["negative_prompt"]
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def upload_image_to_s3(self, user_id: str, image_base64: str, record_date: str = None) -> Dict[str, Any]:
        """
        이미지를 S3에 업로드 (히스토리에 추가 버튼용)
        
        Args:
            user_id: 사용자 ID (cognito_sub)
            image_base64: 업로드할 이미지 (base64)
            record_date: 기록 날짜 (선택, ISO format)
        
        Returns:
            s3_key: S3 키
            image_url: 이미지 URL
        """
        try:
            if not user_id:
                return {"success": False, "error": "user_id is required"}
            
            if not image_base64:
                return {"success": False, "error": "image_base64 is required"}
            
            s3_result = upload_to_s3(user_id, image_base64, record_date)
            
            return {
                "success": True,
                "user_id": user_id,
                "s3_key": s3_result["s3_key"],
                "image_url": s3_result["image_url"]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def build_prompt_from_text(self, text: str) -> Dict[str, Any]:
        """프롬프트만 생성 (이미지 생성 없음)"""
        try:
            prompt_result = generate_prompt_with_claude(text)
            
            return {
                "success": True,
                "positive_prompt": prompt_result["positive_prompt"],
                "negative_prompt": prompt_result["negative_prompt"]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """서비스 상태 확인"""
        return {
            "success": True,
            "status": "ok",
            "service": "image-generator-agent",
            "s3_bucket": S3_BUCKET,
            "timestamp": datetime.utcnow().isoformat()
        }
