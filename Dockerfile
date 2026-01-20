# Dockerfile for Agent Core Runtime - Multi-stage Build
# Stage 1: Builder - 의존성 설치
FROM public.ecr.aws/docker/library/python:3.11-slim as builder

WORKDIR /app

# pip 업그레이드
RUN pip install --upgrade pip

# requirements 복사 및 의존성 설치 (user 디렉토리에 설치)
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime - 최종 실행 이미지
FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# 시스템 패키지 최소화 (런타임에 필요한 것만)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Builder stage에서 설치된 Python 패키지 복사
COPY --from=builder /root/.local /root/.local

# 애플리케이션 코드 복사
COPY app/ /app/app/
COPY run.py /app/

# PATH에 로컬 bin 추가
ENV PATH=/root/.local/bin:$PATH

# Python 최적화 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 포트 8080 노출 (Agent Core Runtime 필수)
EXPOSE 8080

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

# FastAPI 서버 실행
CMD ["python", "run.py"]
