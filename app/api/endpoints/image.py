"""
Image Generation Endpoint
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json

router = APIRouter()


@router.post("")
async def generate_image(request: Request):
    """
    이미지 생성 엔드포인트
    """
    try:
        from app.services.orchestrator.image_generator.agent import run_image_generator
        
        body = await request.json()
        
        print(f"[DEBUG] ========== Image Generation 시작 ==========")
        print(f"[DEBUG] Request body: {json.dumps(body, ensure_ascii=False)[:200]}...")
        
        user_input = body.get('content') or body.get('request')
        user_id = body.get('user_id')
        text = body.get('text')
        image_base64 = body.get('image_base64')
        record_date = body.get('record_date')
        
        if not user_input:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "요청 내용이 필요합니다."
                }
            )
        
        result = run_image_generator(
            request=user_input,
            user_id=user_id,
            text=text,
            image_base64=image_base64,
            record_date=record_date
        )
        
        print(f"[DEBUG] ========== Image Generation 완료 ==========")
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"[ERROR] Image generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"이미지 생성 중 오류가 발생했습니다: {str(e)}"
            }
        )
