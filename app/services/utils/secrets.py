"""
AWS Secrets Manager에서 민감 정보를 가져오는 유틸리티
"""
import json
import os
import boto3
from botocore.exceptions import ClientError


def get_secret(secret_name: str, region_name: str = None) -> dict:
    """
    AWS Secrets Manager에서 시크릿을 가져옵니다.
    
    Args:
        secret_name: Secrets Manager의 시크릿 이름
        region_name: AWS 리전 (기본값: 환경변수 또는 us-east-1)
    
    Returns:
        시크릿 값을 담은 딕셔너리
    """
    if region_name is None:
        region_name = os.environ.get('AWS_REGION', 'us-east-1')
    
    # Secrets Manager 클라이언트 생성
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    
    try:
        print(f"[Secrets] Fetching secret: {secret_name} from region: {region_name}")
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
        print(f"[Secrets] Secret fetched successfully")
    except ClientError as e:
        # 에러 처리
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceNotFoundException':
            print(f"❌ Secret을 찾을 수 없습니다: {secret_name}")
        elif error_code == 'InvalidRequestException':
            print(f"❌ 잘못된 요청입니다: {error_code}")
        elif error_code == 'InvalidParameterException':
            print(f"❌ 잘못된 파라미터입니다: {error_code}")
        elif error_code == 'DecryptionFailure':
            print(f"❌ 복호화 실패: {error_code}")
        elif error_code == 'InternalServiceError':
            print(f"❌ 내부 서비스 오류: {error_code}")
        else:
            print(f"❌ 알 수 없는 오류: {error_code}")
        raise e
    
    # 시크릿 값 파싱
    if 'SecretString' in get_secret_value_response:
        secret_string = get_secret_value_response['SecretString']
        print(f"[Secrets] Secret string length: {len(secret_string)}")
        print(f"[Secrets] Secret string preview: {secret_string[:100]}...")
        
        # 작은따옴표로 감싸진 경우 제거 (AWS CLI 출력 형식)
        if secret_string.startswith("'") and secret_string.endswith("'"):
            print(f"[Secrets] Removing surrounding single quotes from secret string")
            secret_string = secret_string[1:-1]
        
        try:
            secret_dict = json.loads(secret_string)
            print(f"[Secrets] Successfully parsed JSON with {len(secret_dict)} keys")
            return secret_dict
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 실패: {str(e)}")
            print(f"❌ Secret string: {secret_string}")
            print(f"❌ First 50 chars: {repr(secret_string[:50])}")
            print(f"❌ Last 50 chars: {repr(secret_string[-50:])}")
            raise ValueError(f"Secret '{secret_name}'의 JSON 파싱 실패: {str(e)}")
    else:
        # 바이너리 시크릿의 경우
        import base64
        decoded_binary_secret = base64.b64decode(get_secret_value_response['SecretBinary'])
        return json.loads(decoded_binary_secret)


def get_config() -> dict:
    """
    애플리케이션 설정을 가져옵니다.
    Secrets Manager에서 가져옵니다.
    
    Returns:
        설정 딕셔너리
    """
    # Secret 이름 (환경변수 또는 기본값)
    secret_name = os.environ.get('SECRET_NAME', 'agent-core-secret')
    region_name = os.environ.get('AWS_REGION', 'us-east-1')
    
    try:
        config = get_secret(secret_name, region_name)
        print(f"✅ Secrets Manager에서 설정을 가져왔습니다: {secret_name}")
        
        # 필수 키 검증
        required_keys = ['KNOWLEDGE_BASE_ID', 'AWS_REGION']
        missing_keys = [key for key in required_keys if not config.get(key)]
        
        if missing_keys:
            print(f"⚠️  경고: 다음 필수 키가 누락되었습니다: {', '.join(missing_keys)}")
        
        # AWS_REGION은 환경변수 우선
        if 'AWS_REGION' not in config or not config['AWS_REGION']:
            config['AWS_REGION'] = region_name
        
        return config
    except Exception as e:
        print(f"❌ CRITICAL: Secrets Manager에서 설정을 가져올 수 없습니다: {str(e)}")
        print(f"❌ Secret 이름: {secret_name}")
        print(f"❌ Region: {region_name}")
        
        # 런타임 오류 방지를 위해 기본값 반환 (최소한의 동작 보장)
        print(f"⚠️  WARNING: 기본값으로 fallback합니다. 일부 기능이 제한될 수 있습니다.")
        return {
            'AWS_REGION': region_name,
            'KNOWLEDGE_BASE_ID': os.environ.get('KNOWLEDGE_BASE_ID', ''),
            'KNOWLEDGE_BASE_BUCKET': os.environ.get('KNOWLEDGE_BASE_BUCKET', ''),
            'BEDROCK_MODEL_ARN': os.environ.get('BEDROCK_MODEL_ARN', ''),
            'IAM_ROLE_ARN': os.environ.get('IAM_ROLE_ARN', ''),
            'BEDROCK_CLAUDE_MODEL_ID': os.environ.get('BEDROCK_CLAUDE_MODEL_ID', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'),
            'BEDROCK_NOVA_CANVAS_MODEL_ID': os.environ.get('BEDROCK_NOVA_CANVAS_MODEL_ID', 'amazon.nova-canvas-v1:0'),
            'BEDROCK_LLM_MODEL_ID': os.environ.get('BEDROCK_LLM_MODEL_ID', 'us.anthropic.claude-sonnet-4-20250514-v1:0'),
        }
