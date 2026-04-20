"""Authentication schemas for the ytclfr pipeline."""

from typing import Literal

from pydantic import BaseModel


class AuthToken(BaseModel):
    """JWT access token response shape."""

    access_token: str
    token_type: Literal["bearer"]
    expires_in: int

    model_config = {
        "frozen": True,
    }


class JWTPayload(BaseModel):
    """Decoded JWT token payload claims."""

    sub: str
    exp: int
    iat: int
    jti: str

    model_config = {
        "frozen": True,
    }
