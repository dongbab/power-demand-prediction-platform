# 보안 설정
from functools import wraps
from typing import Optional
import hashlib
import secrets
from datetime import datetime, timedelta


def generate_api_key() -> str:
    """API 키 생성"""
    return secrets.token_urlsafe(32)


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """비밀번호 해싱"""
    if salt is None:
        salt = secrets.token_hex(16)

    # PBKDF2를 사용한 안전한 해싱
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)  # 반복 횟수

    return key.hex(), salt


def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """비밀번호 검증"""
    key, _ = hash_password(password, salt)
    return secrets.compare_digest(key, hashed_password)


def sanitize_filename(filename: str) -> str:
    """파일명 안전화 - 경로 순회 공격 방지"""
    import re
    from pathlib import Path

    # 위험한 문자 제거
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # 경로 구분자 제거
    filename = Path(filename).name

    # 숨김 파일 방지
    if filename.startswith("."):
        filename = "_" + filename[1:]

    # 길이 제한
    if len(filename) > 255:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        filename = name[:250] + ("." + ext if ext else "")

    return filename


def validate_file_size(file_size: int, max_size_mb: int = 50) -> bool:
    """파일 크기 검증"""
    max_size_bytes = max_size_mb * 1024 * 1024
    return file_size <= max_size_bytes


def rate_limit_check(ip_address: str, endpoint: str, window_minutes: int = 5, max_requests: int = 100) -> bool:
    """간단한 속도 제한 체크 (실제로는 Redis나 데이터베이스 사용 권장)"""
    # 실제 구현에서는 외부 저장소 사용
    # 여기서는 예시만 제공
    return True


class SecurityHeaders:
    """보안 헤더 설정"""

    @staticmethod
    def get_security_headers() -> dict:
        """보안 헤더 반환"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }


def secure_headers(func):
    """보안 헤더 추가 데코레이터"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        response = await func(*args, **kwargs)

        # FastAPI Response 객체인 경우
        if hasattr(response, "headers"):
            headers = SecurityHeaders.get_security_headers()
            for key, value in headers.items():
                response.headers[key] = value

        return response

    return wrapper


def log_security_event(event_type: str, details: dict, ip_address: str = None):
    """보안 이벤트 로깅"""
    import logging

    security_logger = logging.getLogger("security")

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "details": details,
        "ip_address": ip_address,
    }

    # 실제 환경에서는 SIEM 시스템으로 전송
    security_logger.warning(f"Security event: {log_entry}")


def validate_input_data(data: dict, allowed_fields: list) -> dict:
    """입력 데이터 검증 및 필터링"""
    clean_data = {}

    for field in allowed_fields:
        if field in data:
            value = data[field]

            # 기본적인 XSS 방지
            if isinstance(value, str):
                value = value.replace("<", "&lt;").replace(">", "&gt;")
                value = value.replace('"', "&quot;").replace("'", "&#x27;")

            clean_data[field] = value

    return clean_data
