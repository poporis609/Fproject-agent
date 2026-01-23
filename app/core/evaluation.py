"""
Phoenix Evaluation Module

LLM 응답 품질을 평가합니다 (hallucination, relevance).
Phoenix evals의 run_evals + log_evaluations를 사용합니다.
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

import pandas as pd
from opentelemetry import trace

logger = logging.getLogger(__name__)


@dataclass
class EvaluationConfig:
    """평가 설정"""
    enabled: bool = field(default_factory=lambda: os.getenv("EVALUATION_ENABLED", "false").lower() == "true")
    hallucination_check: bool = True
    relevance_check: bool = True
    evaluator_model: str = field(default_factory=lambda: os.getenv("EVALUATOR_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"))


@dataclass
class EvaluationResult:
    """평가 결과"""
    span_id: Optional[str] = None
    relevance_label: Optional[str] = None
    hallucination_label: Optional[str] = None
    evaluated_at: Optional[datetime] = None
    error: Optional[str] = None


def run_evaluation(
    input_text: str,
    output_text: str,
    reference_text: Optional[str] = None,
    config: Optional[EvaluationConfig] = None
) -> EvaluationResult:
    """
    LLM 응답 품질을 평가하고 Phoenix에 업로드합니다.
    """
    if config is None:
        config = EvaluationConfig()
    
    if not config.enabled:
        return EvaluationResult(
            evaluated_at=datetime.now(),
            error="Evaluation disabled"
        )
    
    result = EvaluationResult(evaluated_at=datetime.now())
    
    # 현재 스팬 ID 가져오기
    current_span = trace.get_current_span()
    span_id = None
    if current_span and current_span.is_recording():
        span_id = format(current_span.get_span_context().span_id, '016x')
        result.span_id = span_id
    
    if not span_id:
        result.error = "No active span"
        return result
    
    try:
        from phoenix.evals import (
            HallucinationEvaluator,
            RelevanceEvaluator,
            run_evals,
        )
        from phoenix.evals.models import BedrockModel
        from phoenix.trace import SpanEvaluations
        import phoenix as px
        
        # Bedrock 모델 설정
        os.environ['AWS_DEFAULT_REGION'] = os.getenv("AWS_REGION", "ap-northeast-2")
        eval_model = BedrockModel(model_id=config.evaluator_model)
        
        # 평가용 DataFrame 준비
        eval_df = pd.DataFrame([{
            "input": input_text,
            "output": output_text,
            "reference": reference_text or ""
        }])
        
        phoenix_client = px.Client()
        
        # Relevance 평가
        if config.relevance_check:
            print("[DEBUG] Running Relevance evaluation...")
            relevance_eval = RelevanceEvaluator(eval_model)
            relevance_results = run_evals(
                dataframe=eval_df,
                evaluators=[relevance_eval],
                provide_explanation=True
            )
            
            if isinstance(relevance_results, list) and len(relevance_results) > 0:
                rel_df = relevance_results[0].copy()
                rel_df['context.span_id'] = [span_id]
                phoenix_client.log_evaluations(
                    SpanEvaluations(eval_name="relevance", dataframe=rel_df)
                )
                result.relevance_label = rel_df.iloc[0].get("label", "unknown")
                print(f"[DEBUG] Relevance: {result.relevance_label}")
        
        # Hallucination 평가 (reference가 있을 때만)
        if config.hallucination_check and reference_text:
            print("[DEBUG] Running Hallucination evaluation...")
            hallucination_eval = HallucinationEvaluator(eval_model)
            hallucination_results = run_evals(
                dataframe=eval_df,
                evaluators=[hallucination_eval],
                provide_explanation=True
            )
            
            if isinstance(hallucination_results, list) and len(hallucination_results) > 0:
                hal_df = hallucination_results[0].copy()
                hal_df['context.span_id'] = [span_id]
                phoenix_client.log_evaluations(
                    SpanEvaluations(eval_name="hallucination", dataframe=hal_df)
                )
                result.hallucination_label = hal_df.iloc[0].get("label", "unknown")
                print(f"[DEBUG] Hallucination: {result.hallucination_label}")
        
        logger.info(f"✅ 평가 완료 - Relevance: {result.relevance_label}, Hallucination: {result.hallucination_label}")
        
    except ImportError as e:
        logger.warning(f"⚠️ Phoenix evals 라이브러리 누락: {e}")
        result.error = f"ImportError: {e}"
    except Exception as e:
        logger.error(f"❌ 평가 실패: {e}")
        result.error = str(e)
    
    return result
