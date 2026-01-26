import json
import logging
import os
import re
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

2. 데이터 그대로 반환 (no_processing) - **기본 선택**
   - 사용 조건: 
     * 단순 데이터 입력, 저장 요청
     * 명령형/의문형이 아닌 **모든 서술형 입력**
     * **길이와 관계없이** 특별한 처리 요청이 없는 경우
   - 예시: 
     * 짧은 입력: "오늘 영화 봤어", "점심에 파스타 먹었어"
     * 긴 입력: "오전 8시에 출근해서... (중략) ...5시에 퇴근했다" (장문의 일기 데이터)
   - ⚠️ 중요: **의심스러우면 무조건 이 옵션을 선택하세요!**
   - 이 경우 tool을 사용하지 않습니다
</처리 방법>

<작업순서>
1. 사용자의 요청 유형을 **신중하게** 판단합니다:
   - **의문형 질문**인가? (예: "~했어?", "~뭐야?", "~언제?") → generate_auto_response 호출
   - **위가 아니면 무조건** → tool 호출 없이 바로 JSON 응답

2. ⚠️ 중요한 판단 기준:
   - 서술형 문장 (예: "오늘 ~했다", "~를 먹었다") → **무조건 데이터 입력**
   - 긴 텍스트라고 해서 질문이 아님 → **무조건 데이터 입력**
   - 의심스러우면 → **무조건 데이터 입력**

3. 질문이면 generate_auto_response tool을 호출하고, tool 결과를 content에 담아 JSON 응답
4. 단순 데이터 입력이면 tool 호출 없이 바로 JSON 응답
</작업순서>

<필수규칙>
- 질문은 반드시 generate_auto_response tool을 사용해야 합니다
- generate_auto_response 호출 시 user_id와 current_date가 제공되면 반드시 함께 전달해야 합니다
- 단순 데이터 입력은 tool을 사용하지 않습니다
- tool 결과를 수정하거나 추가 설명을 붙이지 마세요
</필수규칙>

<응답 형식 - 매우 중요>
모든 작업이 끝난 후, 반드시 아래 JSON 형식으로만 최종 응답하세요.
다른 텍스트 없이 JSON만 출력하세요:

{"type": "data 또는 answer", "content": "생성된 내용 (data면 빈문자열)", "message": "응답 메시지"}

예시:
- 데이터 저장: {"type": "data", "content": "", "message": "메시지가 저장되었습니다."}
- 질문 답변: {"type": "answer", "content": "tool에서 받은 답변 내용", "message": "질문에 대한 답변입니다."}
</응답 형식>
"""


class OrchestratorResult(BaseModel):
    """Orchestrator result."""

    type: str = Field(description="응답 타입: data 또는 answer")
    content: str = Field(description="생성된 결과 내용")
    message: str = Field(description="응답 메시지")


def _parse_json_response(response_text: str) -> Dict[str, Any]:
    """
    LLM 응답에서 JSON을 추출하여 파싱
    
    Args:
        response_text: LLM의 응답 텍스트
        
    Returns:
        파싱된 딕셔너리
    """
    text = str(response_text).strip()
    
    # 1. 직접 JSON 파싱 시도
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 2. JSON 블록 추출 시도 (```json ... ``` 형태)
    json_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 3. 중괄호로 둘러싸인 JSON 추출
    json_match = re.search(r'\{[^{}]*"type"[^{}]*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # 4. 파싱 실패 시 기본값 반환
    print(f"[WARN] JSON 파싱 실패, 기본값 반환. 원본: {text[:200]}...")
    return {
        "type": "data",
        "content": "",
        "message": "메시지가 저장되었습니다."
    }


def _extract_tool_results(agent: Agent) -> tuple[list, Optional[str]]:
    """
    Agent의 메시지에서 tool 결과와 reference를 추출
    
    Returns:
        (tool_results 리스트, reference_text)
    """
    tool_results = []
    reference_text = None
    
    for m in agent.messages:
        for content in m.get("content", []):
            if "toolResult" in content:
                tool_result = content["toolResult"]
                print(f"[DEBUG] Tool result found: {str(tool_result)[:200]}...")
                tool_results.append(tool_result)
                
                # reference 추출
                if isinstance(tool_result, dict) and "content" in tool_result:
                    tool_content = tool_result["content"]
                    if isinstance(tool_content, list):
                        for item in tool_content:
                            if isinstance(item, dict) and "json" in item:
                                json_data = item["json"]
                                if isinstance(json_data, dict) and "reference" in json_data:
                                    reference_text = json_data["reference"]
                                    print(f"[DEBUG] Reference extracted: {len(reference_text)} chars")
    
    return tool_results, reference_text


def _is_likely_question(text: str) -> bool:
    """
    텍스트가 질문인지 빠르게 판단하는 사전 필터링 (LLM 호출 없이)
    """
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
        '뭘', '뭐를', '무엇', '무슨', '뭐했', '뭐 했',
    ]
    return any(pattern in text for pattern in question_patterns)


def orchestrate_request(
    user_input: str,
    user_id: Optional[str] = None,
    current_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    사용자 요청을 분석하여 적절한 처리 수행
    
    최적화: 키워드 필터링으로 orchestrator LLM 호출 완전 스킵 (~6초)

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
    
    # 키워드 기반 사전 필터링 (LLM 호출 없이 즉시 판단)
    if not _is_likely_question(user_input):
        print(f"[DEBUG] 사전 필터링: 질문 패턴 없음 → 데이터로 바로 반환 (LLM 스킵)")
        return {
            "type": "data",
            "content": "",
            "message": "메시지가 저장되었습니다."
        }
    
    print(f"[DEBUG] 사전 필터링: 질문 패턴 감지 → generate_auto_response 직접 호출")
    
    # 질문인 경우 generate_auto_response 직접 호출 (orchestrator LLM 완전 스킵)
    try:
        response = generate_auto_response(
            question=user_input,
            user_id=user_id,
            current_date=current_date
        )
        
        answer_content = response.get("response", "")
        reference_text = response.get("reference")
        
        # 평가 실행 (answer 타입인 경우에만)
        if answer_content:
            try:
                eval_result = run_evaluation(
                    input_text=user_input,
                    output_text=answer_content,
                    reference_text=reference_text
                )
                if eval_result.error:
                    print(f"[DEBUG] Evaluation skipped: {eval_result.error}")
                else:
                    print(f"[DEBUG] Evaluation started in background")
            except Exception as e:
                print(f"[DEBUG] Evaluation failed: {e}")
        
        print(f"[DEBUG] ========== orchestrate_request 완료 ==========")
        return {
            "type": "answer",
            "content": answer_content,
            "message": "질문에 대한 답변입니다."
        }
        
    except Exception as e:
        print(f"[ERROR] generate_auto_response 실패: {str(e)}")
        return {
            "type": "answer",
            "content": "",
            "message": f"답변 생성 중 오류가 발생했습니다: {str(e)}"
        }
