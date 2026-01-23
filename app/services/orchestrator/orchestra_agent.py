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
당신은 AI의 워크플로우를 관리하는 오케스트레이터입니다.
사용자가 입력하는 데이터를 기반으로 다음 중 가장 적절한 처리 방법을 선택해주세요.

<처리 방법>
1. generate_auto_response: 사용자의 질문에 답변을 생성
   - 사용 조건: 질문, 조회, 검색, "~했어?", "~뭐야?", "~언제?" 등 **의문형 질문**
   - ⚠️ 중요: 서술형 문장은 질문이 아닙니다!
   - **반드시 전달해야 할 파라미터:**
     * question: 질문 내용 전체를 문자열로 전달
     * user_id: 사용자 ID (제공된 경우 반드시 전달)
     * current_date: 현재 날짜 (제공된 경우 반드시 전달)
   - 응답 형식: {"type": "answer", "content": "답변 내용", "message": "질문에 대한 답변입니다."}

2. 데이터 그대로 반환 (no_processing) - **기본 선택**
   - 사용 조건: 
     * 단순 데이터 입력, 저장 요청
     * 명령형/의문형이 아닌 **모든 서술형 입력**
     * **길이와 관계없이** 특별한 처리 요청이 없는 경우
   - 예시: 
     * 짧은 입력: "오늘 영화 봤어", "점심에 파스타 먹었어"
     * 긴 입력: "오전 8시에 출근해서... (중략) ...5시에 퇴근했다" (장문의 일기 데이터)
   - ⚠️ 중요: **의심스러우면 무조건 이 옵션을 선택하세요!**
   - 응답 형식: {"type": "data", "content": "", "message": "메시지가 저장되었습니다."}
   - 이 경우 tool을 사용하지 않고 입력 데이터를 그대로 반환합니다
</처리 방법>

<작업순서>
1. 사용자의 요청 유형을 **신중하게** 판단합니다:
   - **의문형 질문**인가? (예: "~했어?", "~뭐야?", "~언제?") → generate_auto_response → type: "answer"
   - **위가 아니면 무조건** → no_processing → type: "data"

2. ⚠️ 중요한 판단 기준:
   - 서술형 문장 (예: "오늘 ~했다", "~를 먹었다") → **무조건 데이터 입력**
   - 긴 텍스트라고 해서 질문이 아님 → **무조건 데이터 입력**
   - 의심스러우면 → **무조건 데이터 입력**

3. 질문이면 generate_auto_response tool을 호출합니다
   - question 파라미터: user_input 전체를 전달
   - user_id, current_date: 제공된 경우 반드시 전달

4. 단순 데이터 입력이면 tool을 사용하지 않습니다
   - type: "data", content: "", message: "메시지가 저장되었습니다."

5. tool 결과 처리:
   - generate_auto_response를 호출한 경우: tool이 반환한 response 값을 content에 그대로 담습니다
   - no_processing인 경우 content는 빈 문자열("")입니다
   - ⚠️ 중요: tool 결과의 "response" 필드 값을 content에 넣어야 합니다
</작업순서>

<응답 형식>
반드시 다음 형식으로 응답하세요:
- type: "data" 또는 "answer"
- content: 생성된 내용 (data인 경우 빈 문자열)
- message: 적절한 응답 메시지
</응답 형식>

<필수규칙>
- 질문은 반드시 generate_auto_response tool을 사용해야 합니다
- generate_auto_response 호출 시 user_id와 current_date가 제공되면 반드시 함께 전달해야 합니다
- 단순 데이터 입력은 tool을 사용하지 않고 type: "data"로 반환합니다
- generate_auto_response tool의 결과에서 "response" 필드 값을 content에 그대로 넣어야 합니다
- tool 결과를 수정하거나 추가 설명을 붙이지 마세요
- 응답은 반드시 type, content, message 세 필드를 포함해야 합니다
- content에는 실제 답변 내용이 들어가야 하며, "호출했습니다" 같은 메타 정보가 아닙니다
</필수규칙>

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
사용자 요청을 분석하고 적절한 tool을 호출하세요.

<user_input>{user_input}</user_input>
"""
    
    # user_id 추가 (중요: tool 호출 시 반드시 전달)
    if user_id:
        prompt += f"\n<user_id>{user_id}</user_id>\n⚠️ 중요: generate_auto_response 호출 시 이 user_id를 반드시 전달하세요!"
    
    # current_date 추가 (중요: tool 호출 시 반드시 전달)
    if current_date:
        prompt += f"\n<current_date>{current_date}</current_date>\n⚠️ 중요: generate_auto_response 호출 시 이 current_date를 반드시 전달하세요!"
    
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
