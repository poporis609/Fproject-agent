"""
Agent Endpoint
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json
from app.core.startup import get_orchestrator
from app.schemas.response import AgentResponse, ErrorResponse

router = APIRouter()


@router.post("", response_model=AgentResponse)
async def process_agent_request(request: Request):
    """
    Agent 요청 처리 엔드포인트 (질문 답변 또는 데이터 저장)
    """
    orchestrate_request = get_orchestrator()
    
    if orchestrate_request is None:
        return JSONResponse(
            status_code=500,
            content={
                "type": "error",
                "content": "",
                "message": "Orchestrator 초기화 실패. 로그를 확인하세요."
            }
        )
    
    try:
        body = await request.json()
        
        print(f"[DEBUG] ========== Agent Request 시작 ==========")
        print(f"[DEBUG] Request body: {json.dumps(body, ensure_ascii=False)[:200]}...")
        
        # 파라미터 추출
        user_input = body.get('content') or body.get('inputText') or body.get('input') or body.get('user_input')
        user_id = body.get('user_id')
        current_date = body.get('record_date') or body.get('current_date')
        
        if not user_input:
            return JSONResponse(
                status_code=400,
                content={
                    "type": "error",
                    "content": "",
                    "message": "입력 데이터가 필요합니다."
                }
            )
        
        print(f"[DEBUG] Extracted parameters:")
        print(f"[DEBUG]   user_input: {user_input[:100]}..." if len(str(user_input)) > 100 else f"[DEBUG]   user_input: {user_input}")
        print(f"[DEBUG]   user_id: {user_id}")
        print(f"[DEBUG]   current_date: {current_date}")
        
        # orchestrator 실행
        result = orchestrate_request(
            user_input=user_input,
            user_id=user_id,
            current_date=current_date
        )
        
        print(f"[DEBUG] Result type: {result.get('type', 'unknown')}")
        print(f"[DEBUG] ========== Agent Request 완료 ==========")
        
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"[ERROR] ========== Agent Request 실패 ==========")
        print(f"[ERROR] Exception type: {type(e).__name__}")
        print(f"[ERROR] Exception message: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "type": "error",
                "content": "",
                "message": f"요청 처리 중 오류가 발생했습니다: {str(e)}"
            }
        )
