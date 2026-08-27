import typing

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from ytclfr.core.config import get_settings


class AuthErrorResponse(BaseModel):
    detail: str


CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing authentication token",
    headers={"WWW-Authenticate": "Bearer"},
)

FORBIDDEN_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Insufficient permissions",
)

security = HTTPBearer(auto_error=False)


def decode_supabase_jwt(token: str) -> typing.Any:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={
                "verify_aud": False,
            },
        )
        return payload
    except JWTError:
        raise CREDENTIALS_EXCEPTION


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> typing.Any:
    if not credentials:
        raise CREDENTIALS_EXCEPTION
    return decode_supabase_jwt(credentials.credentials)
