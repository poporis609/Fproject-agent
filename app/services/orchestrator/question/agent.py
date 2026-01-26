import json
import logging
import os
from typing import Any, Dict, List

from strands import Agent, tool
from strands_tools import retrieve

# Secrets Manager에서 설정 가져오기
try:
    from app.services.utils.secrets import get_config
    config = get_config()
    
    # KNOWLEDGE_BASE_ID는 필수값
    knowledge_base_id = config.get('KNOWLEDGE_BASE_ID')
    if not knowledge_base_id:
        raise ValueError("KNOWLEDGE_BASE_ID가 Secrets Manager에 설정되지 않았습니다.")
    
    # Claude 모델 ARN
    BEDROCK_MODEL_ARN = config.get('BEDROCK_MODEL_ARN')
    if not BEDROCK_MODEL_ARN:
        raise ValueError("BEDROCK_MODEL_ARN이 Secrets Manager에 설정되지 않았습니다.")
    
    # Knowledge Base Region (리소스가 있는 리전)
    KB_REGION = config.get('KB_REGION', 'ap-northeast-2')
    
    os.environ['KNOWLEDGE_BASE_ID'] = knowledge_base_id
    os.environ['AWS_REGION'] = KB_REGION
    
    print(f"✅ Question Agent - Knowledge Base ID: {knowledge_base_id}")
    print(f"✅ Question Agent - Model ARN: {BEDROCK_MODEL_ARN}")
    print(f"✅ Question Agent - KB Region: {KB_REGION}")
    
except Exception as e:
    print(f"❌ ERROR: Question Agent 설정 로드 실패: {str(e)}")
    raise
    os.environ['KNOWLEDGE_BASE_ID'] = os.environ.get('KNOWLEDGE_BASE_ID', 'MISSING')
    os.environ['AWS_REGION'] = os.environ.get('AWS_REGION', 'ap-northeast-2')

RESPONSE_SYSTEM_PROMPT = """
사용자 일기 기반 Q&A 어시스턴트.

규칙:
1. 반드시 retrieve 도구로 검색 먼저 실행
2. retrieve 결과에 "날짜:" 또는 "내용:"이 포함되어 있으면 검색 성공 → 해당 내용으로 답변
3. retrieve 결과가 비어있거나 관련 없는 경우에만 "기록이 없습니다"로 답변
4. 추측/지어내기 금지
5. 간결하게 답변 (1-2문장)

중요: retrieve 결과를 꼼꼼히 확인하세요. 검색 결과가 있는데 "없다"고 답변하면 안 됩니다.
"""

SELLER_ANSWER_PROMPT = """
나는 40대 셀러로, 우리 제품은 주로 30대 사용자들이므로, 이를 감안한 답변을 해야 합니다.
고객에게 오해의 여지가 없도록 깔끔하고 차분하게 정보에 기반한 답변을 제공해주세요.
단, 공손한 톤이어야 합니다. 
"""

@tool
def generate_auto_response(question: str, user_id: str = None, current_date: str = None) -> Dict[str, Any]:
    """
    질문에 대한 답변을 생성하는 함수

    Args:
        question (str): 사용자의 질문
        user_id (str): 사용자 ID (Knowledge Base 검색 필터용)
        current_date (str): 현재 날짜 (검색 컨텍스트용)

    Returns:
        Dict[str, Any]: 생성한 답변
    """
    
    print(f"[DEBUG] ========== generate_auto_response 호출 ==========")
    print(f"[DEBUG] question: {question}")
    print(f"[DEBUG] user_id: {user_id}")
    print(f"[DEBUG] current_date: {current_date}")
    
    # 환경변수 확인 (이미 모듈 로드 시 검증되었지만 재확인)
    kb_id = os.environ.get('KNOWLEDGE_BASE_ID', '')
    aws_region = os.environ.get('AWS_REGION', '')
    print(f"[DEBUG] KNOWLEDGE_BASE_ID from env: {kb_id}")
    print(f"[DEBUG] AWS_REGION from env: {aws_region}")
    
    # 이 시점에서는 이미 모듈 로드 시 검증되었으므로 비어있을 수 없음
    if not kb_id:
        print(f"[ERROR] CRITICAL: KNOWLEDGE_BASE_ID가 런타임에 비어있습니다!")
        return {"response": "Knowledge Base 설정 오류. 시스템 관리자에게 문의하세요.", "reference": ""}

    try:
        # system prompt 구성
        system_prompt = RESPONSE_SYSTEM_PROMPT + f"\nSELLER_ANSWER_PROMPT: {SELLER_ANSWER_PROMPT}"
        
        if user_id:
            system_prompt += f"\n\n<context>\n사용자 ID: {user_id}\n"
        if current_date:
            system_prompt += f"현재 날짜: {current_date}\n</context>"

        # Agent 생성 (retrieve tool 포함)
        print(f"[DEBUG] Creating Agent with retrieve tool...")
        auto_response_agent = Agent(
            model=BEDROCK_MODEL_ARN,
            tools=[retrieve],
            system_prompt=system_prompt,
        )

        # 검색 쿼리 구성 - user_id를 쿼리에 포함시켜 검색 정확도 향상
        search_query = f"""
retrieve 도구를 사용하여 다음 조건으로 검색하세요:

검색어: "{question} 사용자:{user_id if user_id else ''}"

검색 후 반드시 검색 결과를 확인하고, 결과가 있으면 그 내용을 바탕으로 답변하세요.
검색 결과가 비어있는 경우에만 "기록이 없습니다"라고 답변하세요.
"""
        
        print(f"[DEBUG] Calling agent with retrieve tool...")
        response = auto_response_agent(search_query)
        
        print(f"[DEBUG] Agent 응답 완료")
        print(f"[DEBUG] Response: {str(response)[:200]}...")

        # tool_result 추출 (retrieve 결과 = reference)
        tool_results = filter_tool_result(auto_response_agent)
        print(f"[DEBUG] Tool results count: {len(tool_results)}")
        
        # retrieve 결과에서 reference 텍스트 추출
        reference_text = extract_reference_from_tool_results(tool_results)
        print(f"[DEBUG] Reference text length: {len(reference_text)} chars")

        # 결과 반환 (reference 포함)
        result = {
            "response": str(response),
            "reference": reference_text
        }
        print(f"[DEBUG] ========== generate_auto_response 완료 ==========")
        return result
        
    except Exception as e:
        print(f"[ERROR] ========== generate_auto_response 실패 ==========")
        print(f"[ERROR] Exception type: {type(e).__name__}")
        print(f"[ERROR] Exception message: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"response": f"답변 생성 중 오류가 발생했습니다: {str(e)}", "reference": ""}

def filter_tool_result(agent: Agent) -> List:
    """
    Agent의 실행 결과에서 tool_result만을 추출하는 함수

    Args:
        agent (Agent): Agent 인스턴스

    Returns:
        Dict[str, Any]: tool_result만을 포함하는 딕셔너리
    """
    tool_results = []
    for m in agent.messages:
        for content in m["content"]:
            if "toolResult" in content:
                tool_results.append(m["content"][0]["toolResult"])
    return tool_results


def extract_reference_from_tool_results(tool_results: List) -> str:
    """
    retrieve tool 결과에서 reference 텍스트를 추출하는 함수
    
    Args:
        tool_results: tool result 리스트
        
    Returns:
        str: 검색된 문서 내용 (reference)
    """
    reference_parts = []
    
    for tool_result in tool_results:
        try:
            if isinstance(tool_result, dict):
                content = tool_result.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            # text 형태
                            if "text" in item:
                                reference_parts.append(item["text"])
                            # json 형태
                            elif "json" in item:
                                json_data = item["json"]
                                if isinstance(json_data, dict):
                                    # retrieve 결과 구조에 따라 추출
                                    if "text" in json_data:
                                        reference_parts.append(json_data["text"])
                                    elif "content" in json_data:
                                        reference_parts.append(str(json_data["content"]))
                                else:
                                    reference_parts.append(str(json_data))
                elif isinstance(content, str):
                    reference_parts.append(content)
        except Exception as e:
            print(f"[DEBUG] Error extracting reference: {e}")
            continue
    
    return "\n\n".join(reference_parts)