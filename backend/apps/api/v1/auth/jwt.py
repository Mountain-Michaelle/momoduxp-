from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from apps.api.config import api_settings

ACCESS = "access"
REFRESH = "refresh"


def create_token(
    *,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra: dict | None = None,
) -> str:
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + expires_delta,
        "iss": api_settings.JWT_ISSUER,
        "aud": api_settings.JWT_AUDIENCE,
    }
    if extra:
        payload.update(extra)

    return jwt.encode(
        payload,
        api_settings.SECRET_KEY,
        algorithm=api_settings.ALGORITHM,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        api_settings.SECRET_KEY,
        algorithms=[api_settings.ALGORITHM],
        audience=api_settings.JWT_AUDIENCE,
        issuer=api_settings.JWT_ISSUER,
    )
