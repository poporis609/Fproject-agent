# Diary Orchestrator Agent

Kubernetes 기반 일기 관리 AI Agent 시스템

## 주요 기능

### 1. 질문 답변 (Question Agent)
Knowledge Base를 검색하여 사용자 질문에 답변
- 예: "2026-01-13일에 나 무슨 영화봤어?"
- 엔드포인트: `POST /agent`

### 2. 일기 생성 (Summarize Agent)
사용자 데이터를 분석하여 일기 형식으로 작성
- 예: "오늘 영화 보고 파스타 먹었어" → 일기 형식 변환
- 엔드포인트: `POST /agent/summarize`

### 3. 이미지 생성 (Image Generator Agent)
일기 텍스트를 분석하여 이미지 생성
- Claude Sonnet 4.5로 프롬프트 변환
- Amazon Nova Canvas로 4:5 비율 이미지 생성
- S3 자동 업로드 및 URL 제공
- 엔드포인트: `POST /agent/image`

### 4. 주간 리포트 (Weekly Report Agent)
일정 기간의 일기를 분석하여 주간 리포트 생성
- 감정 점수 분석, 주요 테마 추출
- 엔드포인트: `POST /agent/report`

### 5. 데이터 저장
단순 데이터 입력은 처리 없이 저장
- 엔드포인트: `POST /agent`

## 아키텍처

```
FastAPI 엔드포인트
├── /agent (orchestrator)
│   ├── 질문 답변 (question_agent)
│   └── 데이터 저장 (no processing)
├── /agent/image (image_generator_agent)
├── /agent/report (weekly_report_agent)
└── /agent/summarize (summarize_agent)
```

**특징:**
- 각 기능이 독립적인 엔드포인트로 분리
- orchestrator는 질문/데이터 판단만 수행
- 각 agent는 내부적으로 복잡한 작업 자동 처리

자세한 내용은 [docs/API_EXAMPLES.md](./docs/API_EXAMPLES.md) 참고


## 빠른 시작

### 로컬 실행
```bash
python run.py
```

### API 호출 예시
```bash
# 질문 답변
curl -X POST http://localhost:8080/agent \
  -H "Content-Type: application/json" \
  -d '{"content":"오늘 뭐 먹었어?","user_id":"user123"}'

# 이미지 생성
curl -X POST http://localhost:8080/agent/image \
  -H "Content-Type: application/json" \
  -d '{"content":"이미지 생성해줘","text":"오늘 공원에서 산책했다"}'
```

## 배포

### GitHub Actions (자동)
```bash
git push origin main
```
→ Docker 빌드 → ECR 푸시 → K8s manifest 업데이트 → ArgoCD 배포

### 수동 배포
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/ingress.yaml
```

## 기술 스택

- **API**: FastAPI
- **AI**: Strands Agents + AWS Bedrock (Claude Sonnet 4.5, Nova Canvas)
- **Infrastructure**: Kubernetes (EKS) + ArgoCD
- **Storage**: S3, PostgreSQL (RDS)
- **CI/CD**: GitHub Actions + ECR

## 프로젝트 구조

```
app/
├── api/endpoints/     # API 엔드포인트
├── services/          # Agent 비즈니스 로직
│   └── orchestrator/  # 각 Agent 구현
├── core/              # 설정 및 초기화
└── schemas/           # 요청/응답 스키마

k8s/                   # Kubernetes 매니페스트
docs/                  # 문서
```

## 라이선스
MIT License


## 빠른 시작

### 로컬 실행
```bash
python run.py
```

### API 호출 예시
```bash
# 질문 답변
curl -X POST http://localhost:8080/agent \
  -H "Content-Type: application/json" \
  -d '{"content":"오늘 뭐 먹었어?","user_id":"user123"}'

# 이미지 생성
curl -X POST http://localhost:8080/agent/image \
  -H "Content-Type: application/json" \
  -d '{"content":"이미지 생성해줘","text":"오늘 공원에서 산책했다"}'

# 주간 리포트
curl -X POST http://localhost:8080/agent/report \
  -H "Content-Type: application/json" \
  -d '{"content":"이번 주 리포트","user_id":"user123"}'

# 일기 생성
curl -X POST http://localhost:8080/agent/summarize \
  -H "Content-Type: application/json" \
  -d '{"content":"오늘 영화 보고 파스타 먹었어"}'
```

## 배포

### GitHub Actions (자동)
```bash
git push origin main
```
→ Docker 빌드 → ECR 푸시 → K8s manifest 업데이트 → ArgoCD 배포

### 수동 배포
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/ingress.yaml
```

### 로그 확인
```bash
kubectl logs -f deployment/agent-api-deployment
```

## 기술 스택

- **API**: FastAPI
- **AI**: Strands Agents + AWS Bedrock (Claude Sonnet 4.5, Nova Canvas)
- **Infrastructure**: Kubernetes (EKS) + ArgoCD
- **Storage**: S3, PostgreSQL (RDS)
- **CI/CD**: GitHub Actions + ECR

## 프로젝트 구조

```
app/
├── api/endpoints/     # API 엔드포인트
│   ├── agent.py       # 질문 답변 + 데이터 저장
│   ├── image.py       # 이미지 생성
│   ├── report.py      # 주간 리포트
│   └── summarize.py   # 일기 생성
├── services/          # Agent 비즈니스 로직
│   └── orchestrator/  # 각 Agent 구현
├── core/              # 설정 및 초기화
└── schemas/           # 요청/응답 스키마

k8s/                   # Kubernetes 매니페스트
docs/                  # 문서
```

## 환경 변수

```yaml
AWS_REGION: us-east-1
KNOWLEDGE_BASE_ID: LOCNRTBMNB
KNOWLEDGE_BASE_BUCKET: knowledge-base-test-6575574
BEDROCK_CLAUDE_MODEL_ID: arn:aws:bedrock:...
BEDROCK_NOVA_CANVAS_MODEL_ID: amazon.nova-canvas-v1:0
```

## 라이선스
MIT License
