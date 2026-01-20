"""
Weekly Report Endpoint
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json

router = APIRouter()


@router.post("")
async def create_report(request: Request):
    """
    주간 리포트 생성 엔드포인트
    """
    try:
        from app.services.orchestrator.weekly_report.agent import run_weekly_report
        
        body = await request.json()
        
        print(f"[DEBUG] ========== Weekly Report 시작 ==========")
        print(f"[DEBUG] Request body: {json.dumps(body, ensure_ascii=False)[:200]}...")
        
        user_input = body.get('content') or body.get('request')
        user_id = body.get('user_id')
        start_date = body.get('start_date')
        end_date = body.get('end_date')
        report_id = body.get('report_id')
        
        if not user_input:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "요청 내용이 필요합니다."
                }
            )
        
        result = run_weekly_report(
            request=user_input,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            report_id=report_id
        )
        
        print(f"[DEBUG] ========== Weekly Report 완료 ==========")
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"[ERROR] Weekly report failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"리포트 생성 중 오류가 발생했습니다: {str(e)}"
            }
        )
