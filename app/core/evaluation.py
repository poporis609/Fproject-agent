"""
Phoenix Evaluation Module

LLM 응답 품질을 평가합니다 (hallucination, relevance).
Phoenix evals의 run_evals + log_evaluations를 사용합니다.
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class EvaluationConfig:
    """평가 설정"""
    enabled: bool = field(default_factory=lambda: os.getenv("EVALUATION_ENABLED", "false").lower() == "true")
    hallucination_check: bool = True
    relevance_check: bool = True
    evaluator_model: str = field(default_factory=lambda: os.getenv("EVALUATOR_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"))
    project_name: str = field(default_factory=lambda: os.getenv("PHOENIX_PROJECT_NAME", "diary-agent"))
    phoenix_base_url: str = field(default_factory=lambda: os.getenv("PHOENIX_BASE_URL", "http://phoenix-service:6006"))


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
    Phoenix Client에서 최근 스팬을 가져와서 평가합니다.
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
        from phoenix.evals import (
            HallucinationEvaluator,
            RelevanceEvaluator,
            run_evals,
        )
        from phoenix.evals.models import BedrockModel
        from phoenix.trace import SpanEvaluations
        import phoenix as px
        
        # Phoenix Client 초기화 (환경변수 PHOENIX_BASE_URL 사용)
        # deployment.yaml에서 PHOENIX_BASE_URL=http://phoenix-service:6006 설정됨
        print(f"[DEBUG] Connecting to Phoenix (PHOENIX_BASE_URL env var)")
        phoenix_client = px.Client()
        
        # 최근 스팬 가져오기
        spans_df = phoenix_client.get_spans_dataframe(project_name=config.project_name)
        
        if spans_df is None or len(spans_df) == 0:
            result.error = "No spans found in Phoenix"
            print(f"[DEBUG] {result.error}")
            return result
        
        # 가장 최근 LLM 스팬 찾기
        recent_span = spans_df.iloc[0]
        span_id = recent_span.name  # index가 span_id
        result.span_id = str(span_id)
        
        print(f"[DEBUG] Found recent span: {span_id}")
        
        # Bedrock 모델 설정
        os.environ['AWS_DEFAULT_REGION'] = os.getenv("AWS_REGION", "ap-northeast-2")
        eval_model = BedrockModel(model_id=config.evaluator_model)
        
        # 평가용 DataFrame 준비
        eval_df = pd.DataFrame([{
            "input": input_text,
            "output": output_text,
            "reference": reference_text or ""
        }])
        
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
                print(f"[DEBUG] Relevance uploaded: {result.relevance_label}")
        
        # Hallucination 평가 (reference 없어도 실행 - 할루시네이션 테스트용)
        if config.hallucination_check:
            print("[DEBUG] Running Hallucination evaluation...")
            hallucination_eval = HallucinationEvaluator(eval_model)
            
            # reference가 없으면 빈 문자열 사용 (검색 결과 없음 = 모든 답변이 할루시네이션)
            eval_reference = reference_text if reference_text else "정보 없음"
            eval_df_hal = pd.DataFrame([{
                "input": input_text,
                "output": output_text,
                "reference": eval_reference
            }])
            
            hallucination_results = run_evals(
                dataframe=eval_df_hal,
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
                print(f"[DEBUG] Hallucination uploaded: {result.hallucination_label}")
        
        logger.info(f"✅ 평가 완료 - Relevance: {result.relevance_label}, Hallucination: {result.hallucination_label}")
        
    except ImportError as e:
        logger.warning(f"⚠️ Phoenix evals 라이브러리 누락: {e}")
        result.error = f"ImportError: {e}"
    except Exception as e:
        logger.error(f"❌ 평가 실패: {e}")
        print(f"[DEBUG] Evaluation error: {e}")
        result.error = str(e)
    
    return result
