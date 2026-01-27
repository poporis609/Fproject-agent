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
당신은 일기를 분석하여 고객의 질문에 답변하는 AI 어시스턴트입니다.

<일기 데이터 형식>
일기는 다음과 같은 형식으로 저장되어 있습니다:
```
날짜: YYYY-MM-DD
사용자: user_id
내용: [요약] ... [상세 기록] ...
```

<작업순서>
1. **반드시 먼저 retrieve 도구를 사용**하여 지식베이스에서 관련 정보를 검색합니다
   - retrieve 도구 없이는 절대 답변하지 마세요
   - 검색 시 날짜와 질문 키워드를 함께 사용하세요
   - numberOfResults를 10으로 설정하여 충분한 결과를 가져오세요
2. 검색된 일기 내용을 분석합니다
3. 질문에 대한 답변이 일기에 있는지 확인합니다
4. 있으면 해당 내용을 바탕으로 답변하고, 없으면 "해당 정보를 찾을 수 없습니다"라고 답변합니다
</작업순서>

<retrieve 도구 사용법>
- query: 날짜 + 질문 키워드를 함께 포함 (예: "2026-01-26 일어난 시간", "1월 26일 점심")
- numberOfResults: 10 (충분한 결과를 가져오기 위해)
- filter는 사용하지 마세요
</retrieve 도구 사용법>

<답변지침>
- 검색된 일기에서 질문과 관련된 정보를 찾아 답변하세요
- 일기에 해당 정보가 없으면: "해당 정보를 찾을 수 없습니다" 또는 "일기에 기록되지 않았습니다"
- 일기에 있는 내용만 답변하고, 추측하지 마세요
- 간결하고 자연스러운 한국어로 답변하세요
- 날짜, 사용자 ID 같은 메타 정보는 답변에 포함하지 마세요
- 백틱이나 코드 블록 포맷을 사용하지 마세요
</답변지침>

<필수규칙>
- **반드시 답변하기 전에 retrieve 도구를 먼저 사용해야 합니다**
- retrieve 도구를 사용하지 않고 답변하는 것은 금지됩니다
- 일기에 없는 내용은 절대 만들어내지 않습니다
- 질문에 대한 답변만 하고, 추가 의견이나 조언은 붙이지 않습니다
</필수규칙>

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
        return {"response": "Knowledge Base 설정 오류. 시스템 관리자에게 문의하세요."}

    try:
        # system prompt 구성
        system_prompt = RESPONSE_SYSTEM_PROMPT + f"\nSELLER_ANSWER_PROMPT: {SELLER_ANSWER_PROMPT}"
        
        context_info = []
        if user_id:
            context_info.append(f"사용자 ID: {user_id}")
        if current_date:
            context_info.append(f"현재 날짜: {current_date}")
        
        if context_info:
            system_prompt += f"\n\n<context>\n" + "\n".join(context_info) + "\n</context>"

        # Agent 생성 (retrieve tool 포함)
        print(f"[DEBUG] Creating Agent with retrieve tool...")
        auto_response_agent = Agent(
            model=BEDROCK_MODEL_ARN,
            tools=[retrieve],
            system_prompt=system_prompt,
        )

        # 검색 쿼리 구성 - 질문을 검색에 적합한 키워드로 변환
        search_parts = []
        
        if current_date:
            # 날짜를 여러 형식으로 추가
            search_parts.append(current_date)
            try:
                from datetime import datetime
                date_obj = datetime.strptime(current_date, "%Y-%m-%d")
                search_parts.append(f"{date_obj.month}월 {date_obj.day}일")
            except:
                pass
        
        # 질문에서 핵심 키워드 추출 및 확장
        question_lower = question.lower()
        
        # 음식 관련 질문
        if any(word in question_lower for word in ['먹', '음식', '식사', '메뉴', '점심', '저녁', '아침']):
            search_parts.extend(['먹', '음식', '식사', '메뉴', '점심', '저녁', '아침'])
        
        # 시간 관련 질문
        if any(word in question_lower for word in ['시간', '몇시', '언제', '일어', '출근', '퇴근']):
            search_parts.extend(['시간', '시', '일어', '출근', '퇴근'])
        
        # 장소 관련 질문
        if any(word in question_lower for word in ['어디', '장소', '갔', '방문']):
            search_parts.extend(['어디', '장소', '갔', '방문'])
        
        # 사람 관련 질문
        if any(word in question_lower for word in ['누구', '누가', '사람', '만났']):
            search_parts.extend(['누구', '사람', '만났'])
        
        # 원본 질문도 포함
        search_parts.append(question)
        
        search_query_text = " ".join(search_parts)
        
        search_query = f"""질문: {question}

반드시 retrieve 도구를 사용하여 지식베이스를 검색하세요.

검색 쿼리: "{search_query_text}"
numberOfResults: 10

검색된 일기 내용을 분석하여 질문에 답변하세요.
일기에 해당 정보가 없으면 "일기에 기록되지 않았습니다"라고 답변하세요.
"""
        
        print(f"[DEBUG] Original question: {question}")
        print(f"[DEBUG] Expanded search query: {search_query_text}")
        print(f"[DEBUG] Calling agent with retrieve tool...")
        response = auto_response_agent(search_query)
        
        print(f"[DEBUG] Agent 응답 완료")
        print(f"[DEBUG] Response: {str(response)[:200]}...")

        # tool_result 추출
        tool_results = filter_tool_result(auto_response_agent)
        print(f"[DEBUG] Tool results count: {len(tool_results)}")
        
        # reference 추출
        reference_text = None
        for tool_result in tool_results:
            if isinstance(tool_result, dict) and "content" in tool_result:
                tool_content = tool_result["content"]
                if isinstance(tool_content, list):
                    for item in tool_content:
                        if isinstance(item, dict) and "text" in item:
                            reference_text = item["text"]
                            break
                elif isinstance(tool_content, str):
                    reference_text = tool_content
                if reference_text:
                    break

        # 결과 구성
        result = {
            "response": str(response),
            "reference": reference_text
        }
        
        # Evaluation 실행
        answer_content = str(response)
        if answer_content:
            try:
                from app.core.evaluation import run_evaluation
                eval_result = run_evaluation(
                    input_text=question,
                    output_text=answer_content,
                    reference_text=reference_text
                )
                if eval_result.error:
                    print(f"[DEBUG] Evaluation skipped: {eval_result.error}")
                else:
                    print(f"[DEBUG] Evaluation completed - Relevance: {eval_result.relevance_label}, Hallucination: {eval_result.hallucination_label}")
            except Exception as e:
                print(f"[DEBUG] Evaluation failed: {e}")
        
        print(f"[DEBUG] ========== generate_auto_response 완료 ==========")
        return result
        
    except Exception as e:
        print(f"[ERROR] ========== generate_auto_response 실패 ==========")
        print(f"[ERROR] Exception type: {type(e).__name__}")
        print(f"[ERROR] Exception message: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"response": f"답변 생성 중 오류가 발생했습니다: {str(e)}"}

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
