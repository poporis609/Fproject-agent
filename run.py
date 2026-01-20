"""
Application Runner
"""
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    print("=" * 80)
    print("🚀 Agent Core Runtime Server 시작")
    print("=" * 80)
    print(f"Host: {settings.HOST}")
    print(f"Port: {settings.PORT}")
    print("Endpoints:")
    print("  - GET  /health")
    print("  - POST /agent (질문 답변 또는 데이터 저장)")
    print("  - POST /agent/image (이미지 생성)")
    print("  - POST /agent/report (주간 리포트)")
    print("  - POST /agent/summarize (일기 생성)")
    print("=" * 80)
    
    try:
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            log_level="info",
            reload=False
        )
    except Exception as e:
        print(f"❌ 서버 시작 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
