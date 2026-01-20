import json
import logging
import os
from typing import Any, Dict, List, Optional

from strands import Agent

os.environ['AWS_REGION'] = 'us-east-1'

summarize_SYSTEM_PROMPT = """
    당신은 일기를 작성하는 AI 어시스턴트입니다.

    적절한 작성하기 위해 다음 순서를 정확히 따라주세요:

    <작업순서>
    1. 입력 받은 정보를 바탕으로 일기를 작성합니다
    </작업순서>

    <답변지침>
    - 맞춤법과 문단 나누기를 엄격하게 지킵니다
    - 전문적이면서도 따뜻한 톤을 유지합니다
    - 개인정보나 민감한 정보는 공개적으로 언급하지 않습니다
    - user_id를 답변에 포함하지 않습니다
    - 추측성, 애매모한 표현을 사용하지 않습니다
    - 답변에 백틱이나 코드 블록 포맷(```json, ```python 등)을 붙이지 마세요. plain text로 보여주세요. 
    </답변지침>

    <필수규칙>
    - SELLER_ANSWER_PROMPT의 톤 가이드를 반드시 따라야 합니다
    - 오늘의 날짜는 따로 작성하지 않습니다 (단, 내용에서 언급된 경우는 제외)
    - 자연스러운 한국어로 작성합니다
    - 답변은 간결하지만 완전해야 합니다
    - 입력 내용이 누락되어서는 안됩니다
    </필수규칙>

"""

SELLER_ANSWER_PROMPT = """
나는 일기를 매일 작성하는 학생으로, 맞춤법과 문단 나누기에 엄격합니다.
일기 형식으로 작성하고, 줄글 형식, 1인칭 시점으로 일기를 작성해야 합니다.
"""


def generate_auto_summarize(
    content: str,
    temperature: Optional[float] = None,
    top_k: int = 50
) -> Dict[str, Any]:
    """
    일기 생성 함수

    Args:
        content (str): 분석할 내용
        temperature: 응답의 무작위성 (0.0 ~ 1.0, 낮을수록 일관된 응답)
        top_k: 상위 K개 토큰에서 샘플링 (기본값: 50)

    Returns:
        Dict[str, Any]: 요약된 일기 텍스트
    """

    # 각 요청마다 새로운 Agent 생성
    auto_response_agent = Agent(
        system_prompt=summarize_SYSTEM_PROMPT
        + f"""
        SELLER_ANSWER_PROMPT: {SELLER_ANSWER_PROMPT}
        """,
    )

    # 일기 생성
    response = auto_response_agent(content)

    # 결과 반환
    result = {"response": str(response)}
    return result
