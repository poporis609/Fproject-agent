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
당신은 친절한 AI 어시스턴트입니다.

사용자가 과거에 무엇을 했는지 물어보면, 적절히 추측해서 답변해주세요.
정확한 정보가 없어도 괜찮습니다. 그럴듯하게 답변하면 됩니다.
답변은 한국어로 자연스럽게 해주세요.
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

        # Agent 생성 (retrieve tool 제거 - 할루시네이션 테스트용)
        print(f"[DEBUG] Creating Agent WITHOUT retrieve tool (hallucination test)...")
        auto_response_agent = Agent(
            model=BEDROCK_MODEL_ARN,
            tools=[],  # retrieve 도구 제거
            system_prompt=system_prompt,
        )

        # 검색 쿼리 구성
        search_query = f"""
사용자 질문: {question}

위 질문에 답변해주세요.
"""
        
        print(f"[DEBUG] Calling agent with retrieve tool...")
        response = auto_response_agent(search_query)
        
        print(f"[DEBUG] Agent 응답 완료")
        print(f"[DEBUG] Response: {str(response)[:200]}...")

        # tool_result 추출 (retrieve 결과 = reference)
        tool_results = filter_tool_result(auto_response_agent)
        print(f"[DEBUG] Tool results count: {len(tool_results)}")
        
        # retrieve 도구 제거됨 - reference는 빈 문자열 (할루시네이션 테스트용)
        reference_text = ""
        print(f"[DEBUG] Reference text: empty (no retrieve tool)")

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