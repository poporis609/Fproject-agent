"""
Phoenix Tracing Module

OpenTelemetry 기반 트레이싱을 Phoenix 서버로 전송합니다.
Strands Agent의 Bedrock LLM 호출을 자동으로 계측합니다.
"""
import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from .config import TracingConfig

logger = logging.getLogger(__name__)

# 전역 상태
_tracer_provider: Optional[TracerProvider] = None
_tracing_enabled: bool = False


# Bedrock Claude 모델 가격표 (USD per 1K tokens)
MODEL_PRICING = {
    "claude-sonnet-4-5": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "claude-sonnet-4-5-20250929": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "anthropic.claude-sonnet-4-5-20250929-v1:0": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "claude-haiku": {"input_per_1k": 0.00025, "output_per_1k": 0.00125},
    "amazon.nova-canvas-v1:0": {"input_per_1k": 0.0, "output_per_1k": 0.0},  # 이미지 모델
    "default": {"input_per_1k": 0.003, "output_per_1k": 0.015},
}


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """
    모델별 토큰 비용을 계산합니다.
    
    Args:
        model_name: 모델 이름 또는 ARN
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
    
    Returns:
        예상 비용 (USD)
    """
    # 모델 이름에서 가격 정보 찾기
    pricing = MODEL_PRICING.get("default")
    for key in MODEL_PRICING:
        if key in model_name.lower():
            pricing = MODEL_PRICING[key]
            break
    
    input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
    output_cost = (output_tokens / 1000) * pricing["output_per_1k"]
    
    return input_cost + output_cost


def init_tracing(config: TracingConfig) -> bool:
    """
    OpenTelemetry 트레이싱을 초기화합니다.
    
    Args:
        config: TracingConfig 설정
    
    Returns:
        초기화 성공 여부
    """
    global _tracer_provider, _tracing_enabled
    
    if not config.enabled:
        logger.info("트레이싱이 비활성화되어 있습니다 (TRACING_ENABLED=false)")
        _tracing_enabled = False
        return True
    
    try:
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        
        # 리소스 설정
        resource = Resource.create({
            SERVICE_NAME: config.project_name,
            "service.version": "1.0.0",
        })
        
        # TracerProvider 생성
        tracer_provider = TracerProvider(
            resource=resource,
            sampler=TraceIdRatioBased(config.sample_rate)
        )
        
        # Phoenix gRPC endpoint (4317 포트)
        grpc_endpoint = config.phoenix_endpoint.replace(":6006", ":4317")
        if ":4317" not in grpc_endpoint:
            grpc_endpoint = grpc_endpoint.rstrip("/") + ":4317" if ":" not in grpc_endpoint.split("/")[-1] else grpc_endpoint
        
        # gRPC exporter 설정
        otlp_exporter = OTLPSpanExporter(
            endpoint=grpc_endpoint.replace("http://", "").replace("https://", ""),
            insecure=True
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        # 전역 TracerProvider 설정
        trace.set_tracer_provider(tracer_provider)
        _tracer_provider = tracer_provider
        
        logger.info(f"✅ Phoenix gRPC endpoint: {grpc_endpoint}")
        
        # Bedrock Instrumentor 활성화
        try:
            from openinference.instrumentation.bedrock import BedrockInstrumentor
            BedrockInstrumentor().instrument(tracer_provider=tracer_provider)
            logger.info("✅ Bedrock Instrumentor 활성화됨")
        except ImportError:
            logger.warning("⚠️ openinference-instrumentation-bedrock 패키지가 설치되지 않았습니다")
        except Exception as e:
            logger.warning(f"⚠️ Bedrock Instrumentor 활성화 실패: {e}")
        
        _tracing_enabled = True
        logger.info(f"✅ Phoenix 트레이싱 초기화 완료")
        logger.info(f"   - Project: {config.project_name}")
        logger.info(f"   - Sample Rate: {config.sample_rate}")
        logger.info(f"   - Debug Mode: {config.debug_mode}")
        
        return True
        
    except ImportError as e:
        logger.warning(f"⚠️ Phoenix 라이브러리 누락, 트레이싱 비활성화: {e}")
        _tracing_enabled = False
        return False
    except ConnectionError as e:
        logger.warning(f"⚠️ Phoenix 연결 실패, 트레이싱 비활성화: {e}")
        _tracing_enabled = False
        return False
    except Exception as e:
        logger.error(f"❌ 트레이싱 초기화 실패: {e}")
        _tracing_enabled = False
        return False


def get_tracer(name: str = "diary-agent") -> trace.Tracer:
    """
    명명된 Tracer 인스턴스를 반환합니다.
    
    Args:
        name: Tracer 이름
    
    Returns:
        Tracer 인스턴스
    """
    return trace.get_tracer(name)


def shutdown_tracing() -> None:
    """트레이싱을 정상 종료하고 남은 스팬을 플러시합니다."""
    global _tracer_provider, _tracing_enabled
    
    if _tracer_provider is not None:
        try:
            _tracer_provider.shutdown()
            logger.info("✅ 트레이싱 종료 완료")
        except Exception as e:
            logger.error(f"❌ 트레이싱 종료 실패: {e}")
    
    _tracing_enabled = False


def is_tracing_enabled() -> bool:
    """트레이싱 활성화 여부를 반환합니다."""
    return _tracing_enabled
