# Bedrock 모델 ID 가이드

## 모델 ID 형식

Bedrock 모델 ID는 사용하는 API에 따라 다른 형식을 사용합니다:

### 1. Cross-Region Inference (Strands Agent, Converse API)
**형식:** `us.anthropic.claude-sonnet-4-20250514-v1:0`
- **Prefix 있음**: `us.`
- **사용처**: 
  - Strands Agent의 `BedrockModel`
  - Bedrock Converse API
  - Cross-region inference 기능

**예시:**
```python
from strands.models import BedrockModel

model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",  # ✅ us. prefix 필요
    region_name="us-east-1"
)
```

### 2. InvokeModel API (직접 boto3 호출)
**형식:** `anthropic.claude-sonnet-4-20250514-v1:0`
- **Prefix 없음**: `us.` 제거
- **사용처**:
  - `boto3.client('bedrock-runtime').invoke_model()`
  - 직접 Bedrock API 호출

**예시:**
```python
import boto3

client = boto3.client('bedrock-runtime', region_name='us-east-1')

response = client.invoke_model(
    modelId="anthropic.claude-sonnet-4-20250514-v1:0",  # ✅ us. prefix 제거
    body=json.dumps(request_body)
)
```

## 프로젝트에서의 사용

### Secrets Manager 설정
```json
{
  "BEDROCK_CLAUDE_MODEL_ID": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
  "BEDROCK_LLM_MODEL_ID": "us.anthropic.claude-sonnet-4-20250514-v1:0",
  "BEDROCK_NOVA_CANVAS_MODEL_ID": "amazon.nova-canvas-v1:0"
}
```

### 코드에서 자동 변환
```python
# Secrets Manager에서 가져온 값
CLAUDE_MODEL_ID_RAW = config.get("BEDROCK_LLM_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

# invoke_model API용으로 prefix 제거
CLAUDE_MODEL_ID = CLAUDE_MODEL_ID_RAW.replace("us.", "") if CLAUDE_MODEL_ID_RAW.startswith("us.") else CLAUDE_MODEL_ID_RAW
```

## 각 Agent별 사용

### 1. orchestrator (orchestra_agent.py)
- **API**: Strands Agent
- **모델 ID**: `BEDROCK_MODEL_ARN` (ARN 형식)
- **Prefix**: 필요 없음 (ARN 사용)

### 2. image_generator (image_generator/agent.py)
- **API**: Strands Agent의 `BedrockModel`
- **모델 ID**: `BEDROCK_CLAUDE_MODEL_ID`
- **Prefix**: `us.` 필요 ✅

### 3. image_generator/tools (image_generator/tools.py)
- **API**: `invoke_model` (직접 boto3 호출)
- **모델 ID**: `BEDROCK_LLM_MODEL_ID`
- **Prefix**: `us.` 제거 필요 ⚠️

### 4. weekly_report (weekly_report/agent.py)
- **API**: Strands Agent의 `BedrockModel`
- **모델 ID**: `BEDROCK_CLAUDE_MODEL_ID`
- **Prefix**: `us.` 필요 ✅

## 문제 해결

### 에러: "Could not resolve the foundation model"
```
ValidationException: Could not resolve the foundation model from the provided model identifier: us.anthropic.claude-sonnet-4-20250514-v1:0
```

**원인**: `invoke_model` API에 `us.` prefix가 포함된 모델 ID 사용

**해결**: prefix 제거
```python
# ❌ 잘못된 사용
modelId="us.anthropic.claude-sonnet-4-20250514-v1:0"

# ✅ 올바른 사용
modelId="anthropic.claude-sonnet-4-20250514-v1:0"
```

### 에러: "Model not found"
```
ResourceNotFoundException: Model not found
```

**원인**: Strands Agent에 prefix 없는 모델 ID 사용

**해결**: prefix 추가
```python
# ❌ 잘못된 사용
model_id="anthropic.claude-sonnet-4-20250514-v1:0"

# ✅ 올바른 사용
model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"
```

## 참고 자료

- [AWS Bedrock Model IDs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html)
- [Cross-Region Inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)
- [InvokeModel API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html)
