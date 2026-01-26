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
입력 분류기.

질문 → generate_auto_response(question, user_id, current_date) 호출
일기/메모 → type:"data", content:"", message:"저장완료"
"""


class OrchestratorResult(BaseModel):
    """Orchestrator result."""

    type: str = Field(description="응답 타입: data 또는 answer")
    content: str = Field(description="생성된 결과 내용")
    message: str = Field(description="응답 메시지")


def _is_likely_question(text: str) -> bool:
    """
    텍스트가 질문인지 빠르게 판단하는 사전 필터링
    
    Returns:
        True: 질문일 가능성이 높음 (Agent 호출 필요)
        False: 단순 데이터일 가능성이 높음 (바로 반환)
    """
    # 의문형 패턴
    question_patterns = [
        '?', '했어?', '뭐야', '뭐에요', '뭔가요',
        '언제', '어디', '누가', '누구', '왜', '어떻게', '어떤',
        '몇', '얼마', '알려줘', '알려주세요', '가르쳐',
        '있어?', '있나요', '있을까', '없어?', '없나요',
        '할까', '할까요', '해줘', '해주세요', '해줄래',
        '볼까', '볼래', '먹을까', '갈까',
        '맞아?', '맞나요', '아니야?', '아닌가요',
        '인가요', '인가', '일까', '일까요',
        '줄래', '줄까', '줄 수', '수 있어', '수 있나요',
        '뭘', '뭐를', '무엇', '무슨',
    ]
    
    return any(pattern in text for pattern in question_patterns)


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
    
    # 빠른 필터링: 의문형 패턴이 없으면 LLM 호출 없이 바로 데이터로 처리
    if not _is_likely_question(user_input):
        print(f"[DEBUG] 사전 필터링: 질문 패턴 없음 → 데이터로 바로 반환")
        return {
            "type": "data",
            "content": "",
            "message": "메시지가 저장되었습니다."
        }
    
    print(f"[DEBUG] 사전 필터링: 질문 패턴 감지 → Agent 호출")
    
    # 각 요청마다 새로운 Agent 생성
    orchestrator_agent = Agent(
        model=BEDROCK_MODEL_ARN,
        tools=[generate_auto_response],
        system_prompt=ORCHESTRATOR_PROMPT,
    )

    # orchestrator에게 요청 처리
    prompt = f"입력:{user_input}"
    if user_id:
        prompt += f"|user_id:{user_id}"
    if current_date:
        prompt += f"|date:{current_date}"
    
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
    reference_text = None
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
                                if isinstance(json_data, dict):
                                    if "response" in json_data:
                                        result_dict["content"] = json_data["response"]
                                        print(f"[DEBUG] Content extracted from tool result: {result_dict['content'][:100]}...")
                                    if "reference" in json_data:
                                        reference_text = json_data["reference"]
                                        print(f"[DEBUG] Reference extracted: {len(reference_text)} chars")
                                break
                    break
        else:
            # content가 있어도 reference는 추출
            for tool_result in tool_results:
                if isinstance(tool_result, dict) and "content" in tool_result:
                    tool_content = tool_result["content"]
                    if isinstance(tool_content, list):
                        for item in tool_content:
                            if isinstance(item, dict) and "json" in item:
                                json_data = item["json"]
                                if isinstance(json_data, dict) and "reference" in json_data:
                                    reference_text = json_data["reference"]
                                    print(f"[DEBUG] Reference extracted: {len(reference_text)} chars")
                                break
                    break

    # 평가 실행 (answer 타입인 경우에만)
    if result_dict.get("type") == "answer" and result_dict.get("content"):
        try:
            eval_result = run_evaluation(
                input_text=user_input,
                output_text=result_dict["content"],
                reference_text=reference_text  # RAG 검색 결과 전달
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
