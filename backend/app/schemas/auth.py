from __future__ import annotations

from pydantic import BaseModel


class AuthRegisterRequest(BaseModel):
    email: str
    password: str


class AuthRegisterResponse(BaseModel):
    user_id: str
    email: str
    is_active: bool
    created_at: str


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthMeResponse(BaseModel):
    user_id: str
    email: str
    is_active: bool
    created_at: str
