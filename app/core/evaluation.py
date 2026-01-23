"""
Phoenix Evaluation Module

LLM 응답 품질을 평가합니다 (hallucination, relevance).
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

from opentelemetry import trace

logger = logging.getLogger(__name__)


@dataclass
class EvaluationConfig:
    """평가 설정"""
    enabled: bool = field(default_factory=lambda: os.getenv("EVALUATION_ENABLED", "false").lower() == "true")
    hallucination_check: bool = True
    relevance_check: bool = True
    evaluator_model: str = field(default_factory=lambda: os.getenv("EVALUATOR_MODEL", "claude-sonnet-4-5"))


@dataclass
class EvaluationResult:
    """평가 결과"""
    span_id: Optional[str] = None
    hallucination_score: Optional[float] = None
    relevance_score: Optional[float] = None
    custom_scores: Optional[Dict[str, float]] = None
    evaluated_at: Optional[datetime] = None
    error: Optional[str] = None


def run_evaluation(
    input_text: str,
    output_text: str,
    reference_text: Optional[str] = None,
    config: Optional[EvaluationConfig] = None
) -> EvaluationResult:
    """
    LLM 응답 품질을 평가합니다.
    
    Args:
        input_text: 입력 프롬프트
        output_text: LLM 응답
        reference_text: 참조 텍스트 (RAG 컨텍스트 등)
        config: 평가 설정
    
    Returns:
        EvaluationResult: 평가 결과
    """
    if config is None:
        config = EvaluationConfig()
    
    if not config.enabled:
        return EvaluationResult(
            evaluated_at=datetime.now(),
            error="Evaluation disabled"
        )
    
    result = EvaluationResult(evaluated_at=datetime.now())
    
    try:
        # Phoenix evals 라이브러리 사용
        from phoenix.evals import (
            HallucinationEvaluator,
            RelevanceEvaluator,
            llm_classify,
        )
        from phoenix.evals.models import BedrockModel
        
        # 평가용 모델 설정
        aws_region = os.getenv("AWS_REGION", "ap-northeast-2")
        eval_model = BedrockModel(model_id=config.evaluator_model, region_name=aws_region)
        
        # Hallucination 평가
        if config.hallucination_check and reference_text:
            hallucination_evaluator = HallucinationEvaluator(eval_model)
            hallucination_result = hallucination_evaluator.evaluate(
                input=input_text,
                output=output_text,
                reference=reference_text
            )
            result.hallucination_score = hallucination_result.score
        
        # Relevance 평가
        if config.relevance_check:
            relevance_evaluator = RelevanceEvaluator(eval_model)
            relevance_result = relevance_evaluator.evaluate(
                input=input_text,
                output=output_text
            )
            result.relevance_score = relevance_result.score
        
        # 현재 스팬에 평가 결과 추가
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            result.span_id = format(current_span.get_span_context().span_id, '016x')
            if result.hallucination_score is not None:
                current_span.set_attribute("evaluation.hallucination_score", result.hallucination_score)
            if result.relevance_score is not None:
                current_span.set_attribute("evaluation.relevance_score", result.relevance_score)
        
        logger.info(f"✅ 평가 완료 - Hallucination: {result.hallucination_score}, Relevance: {result.relevance_score}")
        
    except ImportError as e:
        logger.warning(f"⚠️ Phoenix evals 라이브러리 누락: {e}")
        result.error = f"ImportError: {e}"
    except Exception as e:
        logger.error(f"❌ 평가 실패: {e}")
        result.error = str(e)
    
    return result


def add_evaluation_to_span(
    span: trace.Span,
    hallucination_score: Optional[float] = None,
    relevance_score: Optional[float] = None,
    custom_scores: Optional[Dict[str, float]] = None
) -> None:
    """
    스팬에 평가 점수를 추가합니다.
    
    Args:
        span: OpenTelemetry 스팬
        hallucination_score: Hallucination 점수 (0.0 ~ 1.0)
        relevance_score: Relevance 점수 (0.0 ~ 1.0)
        custom_scores: 커스텀 평가 점수
    """
    if not span.is_recording():
        return
    
    if hallucination_score is not None:
        span.set_attribute("evaluation.hallucination_score", hallucination_score)
    
    if relevance_score is not None:
        span.set_attribute("evaluation.relevance_score", relevance_score)
    
    if custom_scores:
        for key, value in custom_scores.items():
            span.set_attribute(f"evaluation.{key}", value)
