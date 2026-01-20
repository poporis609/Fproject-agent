# API 호출 예시

## 엔드포인트 개요

모든 agent 관련 엔드포인트는 `/agent` 경로 아래에 있습니다:

- `GET /health` - 헬스체크
- `POST /agent` - 질문 답변 또는 데이터 저장 (orchestrator)
- `POST /agent/image` - 이미지 생성
- `POST /agent/report` - 주간 리포트
- `POST /agent/summarize` - 일기 생성

---

## 1. 질문 답변 또는 데이터 저장 (`POST /agent`)

orchestrator가 자동으로 질문인지 데이터인지 판단합니다.

### 1-1. 질문 답변 (Knowledge Base 검색)

**요청:**
```bash
curl -X POST https://api.aws11.shop/agent \
  -H "Content-Type: application/json" \
  -d '{
    "content": "2026-01-13일에 나 뭐 먹었어?",
    "user_id": "user123",
    "current_date": "2026-01-20"
  }'
```

**Python:**
```python
import httpx

response = httpx.post(
    "https://api.aws11.shop/agent",
    json={
        "content": "2026-01-13일에 나 뭐 먹었어?",
        "user_id": "user123",
        "current_date": "2026-01-20"
    }
)
result = response.json()
```

**응답:**
```json
{
  "type": "answer",
  "content": "2026-01-13일에는 파스타를 드셨습니다.",
  "message": "질문에 대한 답변입니다."
}
```

**판단 기준:**
- 의문형 문장 (예: "~했어?", "~뭐야?", "~언제?") → 질문으로 판단
- Knowledge Base에서 검색하여 답변 생성

### 1-2. 데이터 저장 (서술형 입력)

**요청:**
```bash
curl -X POST https://api.aws11.shop/agent \
  -H "Content-Type: application/json" \
  -d '{
    "content": "오늘 점심에 김치찌개 먹었어",
    "user_id": "user123",
    "current_date": "2026-01-20"
  }'
```

**응답:**
```json
{
  "type": "data",
  "content": "",
  "message": "메시지가 저장되었습니다."
}
```

**판단 기준:**
- 서술형 문장 (예: "~했다", "~먹었어") → 데이터로 판단
- 처리 없이 그대로 반환

### 파라미터

| 파라미터 | 필수 | 설명 |
|---------|------|------|
| `content` | ✅ | 사용자 입력 (질문 또는 데이터) |
| `user_id` | ⭐ | 사용자 ID (Knowledge Base 검색 필터용) |
| `current_date` | ⭐ | 현재 날짜 (검색 컨텍스트용) |

---

## 2. 이미지 생성 (`POST /agent/image`)

### 2-1. 미리보기 이미지 생성 (S3 업로드 없음)

일기 텍스트를 이미지로 변환하여 base64로 반환합니다.

**요청:**
```bash
curl -X POST https://api.aws11.shop/agent/image \
  -H "Content-Type: application/json" \
  -d '{
    "content": "이미지 미리보기 생성해줘",
    "text": "오늘 아침에 공원에서 산책했다. 날씨가 맑고 화창했다."
  }'
```

**Python:**
```python
import httpx

response = httpx.post(
    "https://api.aws11.shop/agent/image",
    json={
        "content": "이미지 미리보기 생성해줘",
        "text": "오늘 아침에 공원에서 산책했다. 날씨가 맑고 화창했다."
    }
)
result = response.json()
```

**응답:**
```json
{
  "success": true,
  "response": "이미지가 생성되었습니다. image_base64: iVBORw0KGgoAAAANS..."
}
```

### 2-2. 이미지 S3 업로드 (히스토리에 추가)

생성된 이미지를 S3에 업로드하고 URL을 반환합니다.

**요청:**
```bash
curl -X POST https://api.aws11.shop/agent/image \
  -H "Content-Type: application/json" \
  -d '{
    "content": "이 이미지를 히스토리에 추가해줘",
    "user_id": "user123",
    "image_base64": "iVBORw0KGgoAAAANS...",
    "record_date": "2026-01-20"
  }'
```

**응답:**
```json
{
  "success": true,
  "response": "이미지가 업로드되었습니다. URL: https://s3.amazonaws.com/..."
}
```

### 2-3. 프롬프트만 생성 (이미지 생성 없음)

일기 텍스트를 이미지 생성 프롬프트로만 변환합니다.

**요청:**
```bash
curl -X POST https://api.aws11.shop/agent/image \
  -H "Content-Type: application/json" \
  -d '{
    "content": "프롬프트만 생성해줘",
    "text": "오늘 친구들과 카페에서 수다를 떨었다."
  }'
```

**응답:**
```json
{
  "success": true,
  "response": "positive_prompt: A cozy cafe scene with friends chatting..."
}
```

### 파라미터

| 파라미터 | 필수 | 설명 |
|---------|------|------|
| `content` | ✅ | 사용자 요청 (자연어) |
| `text` | ⭐ | 일기 텍스트 (이미지 생성 시) |
| `user_id` | ⭐ | 사용자 ID (S3 업로드 시) |
| `image_base64` | ⭐ | 이미지 데이터 (S3 업로드 시) |
| `record_date` | ⭐ | 기록 날짜 (S3 업로드 시) |

---

## 3. 주간 리포트 (`POST /agent/report`)

### 3-1. 주간 리포트 생성

**요청:**
```bash
curl -X POST https://api.aws11.shop/agent/report \
  -H "Content-Type: application/json" \
  -d '{
    "content": "이번 주 리포트 생성해줘",
    "user_id": "user123",
    "start_date": "2026-01-13",
    "end_date": "2026-01-19"
  }'
```

**Python:**
```python
import httpx

response = httpx.post(
    "https://api.aws11.shop/agent/report",
    json={
        "content": "이번 주 리포트 생성해줘",
        "user_id": "user123",
        "start_date": "2026-01-13",
        "end_date": "2026-01-19"
    }
)
result = response.json()
```

**응답:**
```json
{
  "success": true,
  "response": "주간 리포트가 생성되었습니다. report_id: 123"
}
```

### 3-2. 리포트 목록 조회

**요청:**
```bash
curl -X POST https://api.aws11.shop/agent/report \
  -H "Content-Type: application/json" \
  -d '{
    "content": "내 리포트 목록 보여줘",
    "user_id": "user123"
  }'
```

**응답:**
```json
{
  "success": true,
  "response": "리포트 목록: [...]"
}
```

### 3-3. 특정 리포트 조회

**요청:**
```bash
curl -X POST https://api.aws11.shop/agent/report \
  -H "Content-Type: application/json" \
  -d '{
    "content": "리포트 상세 보기",
    "user_id": "user123",
    "report_id": 123
  }'
```

### 파라미터

| 파라미터 | 필수 | 설명 |
|---------|------|------|
| `content` | ✅ | 사용자 요청 (자연어) |
| `user_id` | ⭐ | 사용자 ID |
| `start_date` | ⭐ | 시작일 (YYYY-MM-DD) |
| `end_date` | ⭐ | 종료일 (YYYY-MM-DD) |
| `report_id` | ⭐ | 리포트 ID (조회 시) |

---

## 4. 일기 생성 (`POST /agent/summarize`)

사용자 입력을 일기 형식으로 변환합니다.

**요청:**
```bash
curl -X POST https://api.aws11.shop/agent/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "content": "오늘 영화 보고 파스타 먹었어",
    "temperature": 0.7
  }'
```

**Python:**
```python
import httpx

response = httpx.post(
    "https://api.aws11.shop/agent/summarize",
    json={
        "content": "오늘 영화 보고 파스타 먹었어",
        "temperature": 0.7
    }
)
result = response.json()
```

**응답:**
```json
{
  "response": "오늘은 영화를 관람하고 맛있는 파스타를 먹으며 즐거운 시간을 보냈다..."
}
```

### 파라미터

| 파라미터 | 필수 | 설명 |
|---------|------|------|
| `content` | ✅ | 일기로 변환할 텍스트 |
| `temperature` | ⭐ | 생성 온도 (0.0 ~ 1.0) |

---

## 5. 헬스체크 (`GET /health`)

**요청:**
```bash
curl https://api.aws11.shop/health
```

**응답:**
```json
{
  "status": "healthy"
}
```

---

## 요청 파라미터 정리

### 공통 파라미터
- `content` (필수): 사용자 요청 (자연어)
- `user_id` (선택): 사용자 ID

### `/agent` 전용
- `current_date` (선택): 현재 날짜

### `/agent/image` 전용
- `text` (선택): 일기 텍스트
- `image_base64` (선택): 이미지 데이터
- `record_date` (선택): 기록 날짜

### `/agent/report` 전용
- `start_date` (선택): 시작일
- `end_date` (선택): 종료일
- `report_id` (선택): 리포트 ID

### `/agent/summarize` 전용
- `temperature` (선택): 생성 온도

---

## 에러 응답

모든 엔드포인트는 에러 발생 시 다음 형식으로 응답합니다:

```json
{
  "type": "error",
  "content": "",
  "message": "에러 메시지"
}
```

또는

```json
{
  "success": false,
  "error": "에러 메시지"
}
```
