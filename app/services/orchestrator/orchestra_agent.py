import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field
from strands import Agent

from .question.agent import generate_auto_response
from ...core.evaluation import run_evaluation, EvaluationConfig

# Secrets Manager에서 설정 가져오기
try:
    from ..utils.secrets import get_config
    config = get_config()
    # Claude 모델 ARN
    BEDROCK_MODEL_ARN = config.get('BEDROCK_MODEL_ARN')
    if not BEDROCK_MODEL_ARN:
        raise ValueError("BEDROCK_MODEL_ARN이 Secrets Manager에 설정되지 않았습니다.")
    print(f"✅ Orchestrator - Model ARN: {BEDROCK_MODEL_ARN}")
except Exception as e:
    print(f"❌ ERROR: Orchestrator 설정 로드 실패: {str(e)}")
    raise

# Configure the root strands logger
logging.getLogger("strands").setLevel(logging.INFO)

# Add a handler to see the logs
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


ORCHESTRATOR_PROMPT = """
당신은 AI 어시스턴트입니다.
사용자 입력을 처리해주세요.
"""


class OrchestratorResult(BaseModel):
    """Orchestrator result."""

    type: str = Field(description="응답 타입: data 또는 answer")
    content: str = Field(description="생성된 결과 내용")
    message: str = Field(description="응답 메시지")


def orchestrate_request(
    user_input: str,
    user_id: Optional[str] = None,
    current_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    사용자 요청을 분석하여 적절한 처리 수행

    Args:
        user_input (str): 사용자 입력 데이터
        user_id (Optional[str]): 사용자 ID (Knowledge Base 검색 필터용)
        current_date (Optional[str]): 현재 날짜 (검색 컨텍스트용)

    Returns:
        Dict[str, Any]: 처리 결과
            - type: "data" (데이터 저장) 또는 "answer" (질문 답변)
            - content: 생성된 내용 (data인 경우 빈 문자열)
            - message: 응답 메시지
    """
    
    print(f"[DEBUG] ========== orchestrate_request 시작 ==========")
    print(f"[DEBUG] user_input: {user_input[:100]}...")
    
    # 각 요청마다 새로운 Agent 생성
    orchestrator_agent = Agent(
        model=BEDROCK_MODEL_ARN,
        tools=[generate_auto_response],
        system_prompt=ORCHESTRATOR_PROMPT,
    )

    # orchestrator에게 요청 처리
    prompt = f"""
사용자 입력: {user_input}

답변해주세요.
"""
    
    orchestrator_agent(prompt)

    # Tool 결과 추출
    tool_results = []
    for m in orchestrator_agent.messages:
        for content in m.get("content", []):
            if "toolResult" in content:
                tool_result = content["toolResult"]
                print(f"[DEBUG] Tool result found: {str(tool_result)[:200]}...")
                tool_results.append(tool_result)

    result = orchestrator_agent.structured_output(
        OrchestratorResult, "사용자 요청에 대한 처리 결과를 구조화된 형태로 추출하시오"
    )

    # Pydantic 모델을 dict로 변환
    if hasattr(result, "model_dump"):
        result_dict = result.model_dump()
    elif hasattr(result, "dict"):
        result_dict = result.dict()
    else:
        result_dict = result

    # Tool 결과가 있고 type이 answer인 경우, content가 비어있으면 tool 결과로 채움
    if tool_results and result_dict.get("type") == "answer":
        if not result_dict.get("content") or result_dict.get("content") == "":
            # generate_auto_response의 결과에서 response 추출
            for tool_result in tool_results:
                if isinstance(tool_result, dict) and "content" in tool_result:
                    tool_content = tool_result["content"]
                    if isinstance(tool_content, list):
                        for item in tool_content:
                            if isinstance(item, dict) and "json" in item:
                                json_data = item["json"]
                                if isinstance(json_data, dict) and "response" in json_data:
                                    result_dict["content"] = json_data["response"]
                                    print(f"[DEBUG] Content extracted from tool result: {result_dict['content'][:100]}...")
                                    break
                    break

    # 평가 실행 (answer 타입인 경우에만)
    if result_dict.get("type") == "answer" and result_dict.get("content"):
        try:
            eval_result = run_evaluation(
                input_text=user_input,
                output_text=result_dict["content"],
                reference_text=None  # RAG 컨텍스트가 있으면 여기에 전달
            )
            if eval_result.error:
                print(f"[DEBUG] Evaluation skipped: {eval_result.error}")
            else:
                print(f"[DEBUG] Evaluation started in background")
        except Exception as e:
            print(f"[DEBUG] Evaluation failed: {e}")

    print(f"[DEBUG] Final result - type: {result_dict.get('type')}, content length: {len(str(result_dict.get('content', '')))} chars")
    print(f"[DEBUG] ========== orchestrate_request 완료 ==========")
    return result_dict
