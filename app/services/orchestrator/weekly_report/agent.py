# weekly_report/agent.py
"""Weekly Report Agent - Strands 기반 Master Agent"""

import os
from typing import Dict, Any

from strands import Agent, tool
from strands.models import BedrockModel

from .prompts import REPORT_SYSTEM_PROMPT
from .tools import (
    get_user_info as _get_user_info,
    get_diary_entries as _get_diary_entries,
    get_report_list as _get_report_list,
    get_report_detail as _get_report_detail,
    create_report as _create_report,
    check_report_status as _check_report_status
)
from agent.utils.secrets import get_config

# 설정 로드
config = get_config()

# AWS 설정
AWS_REGION = config.get("AWS_REGION", os.environ.get("AWS_REGION", "us-east-1"))

# Claude 모델 (에이전트 추론용)
model = BedrockModel(
    model_id=config.get("BEDROCK_CLAUDE_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    region_name=AWS_REGION
)


# ============================================================================
# Strands Tools (기존 tools.py 래핑 - 이름 충돌 방지)
# ============================================================================

@tool
def get_user_info(user_id: str) -> Dict[str, Any]:
    """
    사용자 정보를 조회합니다.
    
    Args:
        user_id: 사용자 ID (Cognito sub)
    
    Returns:
        사용자 정보 (nickname, email 등)
    """
    return _get_user_info(user_id)


@tool
def get_diary_entries(user_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    지정된 기간의 일기 항목을 조회합니다.
    
    Args:
        user_id: 사용자 ID
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)
    
    Returns:
        일기 항목 목록
    """
    return _get_diary_entries(user_id, start_date, end_date)


@tool
def get_report_list(user_id: str, limit: int = 10) -> Dict[str, Any]:
    """
    사용자의 리포트 목록을 조회합니다.
    
    Args:
        user_id: 사용자 ID
        limit: 조회할 개수 (기본 10개)
    
    Returns:
        리포트 목록
    """
    return _get_report_list(user_id, limit)


@tool
def get_report_detail(report_id: int, user_id: str) -> Dict[str, Any]:
    """
    리포트 상세 정보를 조회합니다.
    
    Args:
        report_id: 리포트 ID
        user_id: 사용자 ID
    
    Returns:
        리포트 상세 정보
    """
    return _get_report_detail(report_id, user_id)


@tool
def create_report(user_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    주간 리포트 생성을 요청합니다.
    
    Args:
        user_id: 사용자 ID
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)
    
    Returns:
        생성된 리포트 정보 (report_id, status)
    """
    return _create_report(user_id, start_date, end_date)


@tool
def check_report_status(report_id: int, user_id: str) -> Dict[str, Any]:
    """
    리포트 생성 상태를 확인합니다.
    
    Args:
        report_id: 리포트 ID
        user_id: 사용자 ID
    
    Returns:
        리포트 상태 (processing, completed, failed)
    """
    return _check_report_status(report_id, user_id)


# ============================================================================
# Weekly Report Master Agent
# ============================================================================

weekly_report_agent = Agent(
    model=model,
    system_prompt=REPORT_SYSTEM_PROMPT,
    tools=[
        get_user_info,
        get_diary_entries,
        get_report_list,
        get_report_detail,
        create_report,
        check_report_status,
    ]
)


def run_weekly_report(
    request: str,
    user_id: str = None,
    start_date: str = None,
    end_date: str = None,
    report_id: int = None
) -> Dict[str, Any]:
    """
    Weekly Report Agent 실행 함수
    
    Args:
        request: 사용자 요청 (자연어)
        user_id: 사용자 ID
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)
        report_id: 리포트 ID (조회/상태확인 시)
    
    Returns:
        에이전트 실행 결과
    """
    # 컨텍스트 구성
    prompt = f"요청: {request}"
    if user_id:
        prompt += f"\n사용자 ID: {user_id}"
    if start_date:
        prompt += f"\n시작일: {start_date}"
    if end_date:
        prompt += f"\n종료일: {end_date}"
    if report_id:
        prompt += f"\n리포트 ID: {report_id}"
    
    try:
        response = weekly_report_agent(prompt)
        return {
            "success": True,
            "response": str(response)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
