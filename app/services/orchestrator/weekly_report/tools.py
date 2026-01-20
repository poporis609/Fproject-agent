# weekly_report/tools.py
"""Weekly Report Agent Tools - FastAPI API 호출 방식"""

import os
import httpx
from strands import tool
from typing import Dict, Any

# FastAPI 서버 URL
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.aws11.shop")


@tool
def get_user_info(user_id: str) -> Dict[str, Any]:
    """
    사용자 정보를 조회합니다.
    
    Args:
        user_id: 사용자 ID (Cognito sub)
    
    Returns:
        사용자 정보 (nickname, email 등)
    """
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{API_BASE_URL}/user/{user_id}"
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"사용자 조회 실패: {response.status_code}"}
    except Exception as e:
        return {"error": f"API 호출 실패: {str(e)}"}


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
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{API_BASE_URL}/history",
                params={
                    "user_id": user_id,
                    "start_date": start_date,
                    "end_date": end_date
                }
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"일기 조회 실패: {response.status_code}"}
    except Exception as e:
        return {"error": f"API 호출 실패: {str(e)}"}


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
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{API_BASE_URL}/report",
                params={
                    "user_id": user_id,
                    "limit": limit
                }
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"리포트 목록 조회 실패: {response.status_code}"}
    except Exception as e:
        return {"error": f"API 호출 실패: {str(e)}"}


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
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{API_BASE_URL}/report/{report_id}",
                params={"user_id": user_id}
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"리포트 조회 실패: {response.status_code}"}
    except Exception as e:
        return {"error": f"API 호출 실패: {str(e)}"}


@tool
def create_report(
    user_id: str,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    주간 리포트 생성을 요청합니다.
    
    Args:
        user_id: 사용자 ID
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD)
    
    Returns:
        생성된 리포트 정보 (report_id, status)
    """
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{API_BASE_URL}/report/create",
                json={
                    "user_id": user_id,
                    "start_date": start_date,
                    "end_date": end_date
                }
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"리포트 생성 실패: {response.status_code}"}
    except Exception as e:
        return {"error": f"API 호출 실패: {str(e)}"}


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
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{API_BASE_URL}/report/status/{report_id}",
                params={"user_id": user_id}
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"상태 조회 실패: {response.status_code}"}
    except Exception as e:
        return {"error": f"API 호출 실패: {str(e)}"}
