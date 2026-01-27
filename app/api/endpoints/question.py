"""
Question (Knowledge Base Search) Endpoint
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json

router = APIRouter()


@router.post("")
async def answer_question(request: Request):
    """
    질문 답변 엔드포인트 (Knowledge Base 검색)
    """
    try:
        from app.services.orchestrator.question.agent import generate_auto_response
        
        body = await request.json()
        
        print(f"[DEBUG] ========== Question 시작 ==========")
        print(f"[DEBUG] Request body: {json.dumps(body, ensure_ascii=False)[:200]}...")
        
        question = body.get('content') or body.get('question')
        user_id = body.get('user_id')
        current_date = body.get('current_date') or body.get('record_date')
        
        if not question:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "질문 내용이 필요합니다."
                }
            )
        
        # generate_auto_response에서 evaluation까지 처리
        result = generate_auto_response(
            question=question,
            user_id=user_id,
            current_date=current_date
        )
        
        print(f"[DEBUG] ========== Question 완료 ==========")
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"[ERROR] Question failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"질문 답변 중 오류가 발생했습니다: {str(e)}"
            }
        )
