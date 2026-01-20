"""
Application Startup Handler
"""

config = None
orchestrate_request = None


async def startup_handler():
    """애플리케이션 시작 시 초기화"""
    global config, orchestrate_request
    
    print("=" * 80)
    print("🔧 Agent Core Runtime 초기화 중...")
    print("=" * 80)
    
    # 설정 로드
    try:
        from app.services.utils.secrets import get_config
        config = get_config()
        print(f"✅ 설정 로드 완료")
        print(f"   - AWS Region: {config.get('AWS_REGION')}")
        print(f"   - Knowledge Base ID: {config.get('KNOWLEDGE_BASE_ID', 'N/A')}")
        print(f"   - Claude Model: {config.get('BEDROCK_CLAUDE_MODEL_ID', 'N/A')[:50]}...")
        print(f"   - Nova Canvas Model: {config.get('BEDROCK_NOVA_CANVAS_MODEL_ID', 'N/A')}")
        print(f"   - S3 Bucket: {config.get('KNOWLEDGE_BASE_BUCKET', 'N/A')}")
    except Exception as e:
        print(f"⚠️  설정 로드 실패: {str(e)}")
        print(f"⚠️  일부 기능이 제한될 수 있습니다.")
        import traceback
        traceback.print_exc()
    
    # orchestrator 로드
    try:
        from app.services.orchestrator.orchestra_agent import orchestrate_request as orch
        orchestrate_request = orch
        print("✅ Orchestrator 로드 완료")
    except Exception as e:
        print(f"❌ CRITICAL: Orchestrator 로드 실패: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)
    print("🚀 초기화 완료")
    print("=" * 80)


def get_orchestrator():
    """orchestrator 함수 반환"""
    return orchestrate_request
