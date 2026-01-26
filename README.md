# Diary Orchestrator Agent

Strands AI 기반 Multi-Agent 일기 관리 시스템

## 주요 기능

- **질문 답변**: Knowledge Base 검색 기반 질의응답
- **일기 생성**: 사용자 입력을 일기 형식으로 변환
- **이미지 생성**: 일기 내용 기반 이미지 자동 생성 (Nova Canvas)
- **주간 리포트**: 감정 분석 및 주간 요약 리포트

## 아키텍처

```
FastAPI
├── /agent           - Orchestrator (질문/데이터 분류)
├── /agent/image     - 이미지 생성
├── /agent/report    - 주간 리포트
└── /agent/summarize - 일기 생성
```

## 빠른 시작

```bash
# 로컬 실행
python run.py

# API 호출
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"content":"오늘 뭐 먹었어?","user_id":"user123"}'
```

## 기술 스택

- FastAPI
- Strands Agents + AWS Bedrock (Claude Sonnet 4.5, Nova Canvas)
- Kubernetes (EKS) + ArgoCD
- Arize Phoenix (AI 모니터링)

## 프로젝트 구조

```
app/
├── api/endpoints/     # API 엔드포인트
├── services/          # Agent 구현
│   └── orchestrator/
│       ├── question/        # 질문 답변
│       ├── summarize/       # 일기 생성
│       ├── image_generator/ # 이미지 생성
│       └── weekly_report/   # 주간 리포트
├── core/              # 설정, 트레이싱
└── schemas/           # 요청/응답 스키마
k8s/                   # Kubernetes 매니페스트
```

## 배포

```bash
# GitHub Actions 자동 배포
git push origin main

# 수동 배포
kubectl apply -f k8s/
```

## 라이선스

MIT License
