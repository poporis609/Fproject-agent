"""
Summarize (Diary Generation) Endpoint
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json

router = APIRouter()


@router.post("")
async def summarize_content(request: Request):
    """
    일기 생성 엔드포인트
    """
    try:
        from app.services.orchestrator.summarize.agent import generate_auto_summarize
        
        body = await request.json()
        
        print(f"[DEBUG] ========== Summarize 시작 ==========")
        print(f"[DEBUG] Request body: {json.dumps(body, ensure_ascii=False)[:200]}...")
        
        content = body.get('content')
        temperature = body.get('temperature')
        
        if not content:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "내용이 필요합니다."
                }
            )
        
        result = generate_auto_summarize(
            content=content,
            temperature=temperature
        )
        
        print(f"[DEBUG] ========== Summarize 완료 ==========")
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"[ERROR] Summarize failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"일기 생성 중 오류가 발생했습니다: {str(e)}"
            }
        )
