"""认证服务：注册、登录与会话管理。"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from starlette.requests import Request

from ..store.user import UserStore
from .crypto import (
    EMAIL_RE,
    PASSWORD_MIN_LENGTH,
    SESSION_COOKIE_NAME,
    SESSION_DAYS,
    AuthError,
    AuthorizationError,
    hash_password,
    hash_session_token,
    verify_password,
)


class AuthService:
    def __init__(self, user_store: UserStore) -> None:
        self.user_store = user_store

    def register(
        self, email: str, password: str, confirm_password: str
    ) -> tuple[dict[str, Any], str]:
        normalized_email = email.strip().lower()
        if not EMAIL_RE.match(normalized_email):
            raise AuthError("邮箱格式不正确")
        if len(password) < PASSWORD_MIN_LENGTH:
            raise AuthError("密码至少需要 8 位")
        if password != confirm_password:
            raise AuthError("两次输入的密码不一致")
        if self.user_store.get_user_by_email(normalized_email):
            raise AuthError("该邮箱已注册")

        is_first_user = self.user_store.count_users() == 0
        user = self.user_store.create_user(
            {
                "id": f"user-{uuid4().hex}",
                "email": normalized_email,
                "password_hash": hash_password(password),
                "is_admin": is_first_user,
                "status": "active",
            }
        )
        token = self.create_session(user["id"])
        return user, token

    def login(self, email: str, password: str) -> tuple[dict[str, Any], str]:
        normalized_email = email.strip().lower()
        user = self.user_store.get_user_by_email(normalized_email)
        if not user or not verify_password(
            password, str(user.get("password_hash", ""))
        ):
            raise AuthError("邮箱或密码错误")
        if user.get("status") != "active":
            raise AuthorizationError("当前账户不可用")
        token = self.create_session(user["id"])
        return user, token

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = (
            datetime.now() + timedelta(days=SESSION_DAYS)
        ).isoformat(timespec="seconds")
        self.user_store.create_session(
            {
                "id": f"session-{uuid4().hex}",
                "user_id": user_id,
                "token_hash": hash_session_token(token),
                "expires_at": expires_at,
            }
        )
        return token

    def logout(self, token: str | None) -> None:
        if not token:
            return
        self.user_store.delete_session_by_token_hash(hash_session_token(token))

    def get_current_user(self, request: Request) -> dict[str, Any] | None:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            return None
        session = self.user_store.get_session_by_token_hash(
            hash_session_token(token)
        )
        if not session:
            return None
        expires_at = str(session.get("expires_at", "")).strip()
        if not expires_at:
            self.user_store.delete_session_by_token_hash(hash_session_token(token))
            return None
        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except ValueError:
            self.user_store.delete_session_by_token_hash(hash_session_token(token))
            return None
        if expires_dt <= datetime.now():
            self.user_store.delete_session_by_token_hash(hash_session_token(token))
            return None

        user = self.user_store.get_user_by_id(str(session.get("user_id", "")))
        if not user or user.get("status") != "active":
            self.user_store.delete_session_by_token_hash(hash_session_token(token))
            return None
        self.user_store.touch_session(str(session.get("id", "")))
        return user

    def require_user(self, request: Request) -> dict[str, Any]:
        user = self.get_current_user(request)
        if not user:
            raise AuthorizationError("请先登录")
        return user

    def require_admin(self, request: Request) -> dict[str, Any]:
        user = self.require_user(request)
        if not user.get("isAdmin"):
            raise AuthorizationError("需要管理员权限")
        return user
