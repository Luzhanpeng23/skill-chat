"""用户与会话数据访问层。"""
from __future__ import annotations

import sqlite3
from typing import Any

from .base import AppDatabase


def _normalize_user_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """将数据库行转换为标准化的用户字典。"""
    data = AppDatabase._row_to_dict(row)
    if data is None:
        return None
    data["is_admin"] = bool(data.get("is_admin"))
    data["isAdmin"] = data["is_admin"]
    return data


class UserStore:
    def __init__(self, db: AppDatabase) -> None:
        self.db = db

    def count_users(self) -> int:
        with self.db.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()
            return int(row["count"] if row else 0)

    def create_user(self, user: dict[str, Any]) -> dict[str, Any]:
        now = self.db.now_iso()
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO users (id, email, password_hash, is_admin, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    user["email"],
                    user["password_hash"],
                    1 if user.get("is_admin") else 0,
                    user.get("status", "active"),
                    now,
                    now,
                ),
            )
        return self.get_user_by_id(user["id"]) or {}

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
            ).fetchone()
        return _normalize_user_row(row)

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return _normalize_user_row(row)

    def update_user(
        self, user_id: str, *, status: str | None = None, is_admin: bool | None = None
    ) -> dict[str, Any] | None:
        updates: list[str] = []
        values: list[Any] = []
        if status is not None:
            updates.append("status = ?")
            values.append(status)
        if is_admin is not None:
            updates.append("is_admin = ?")
            values.append(1 if is_admin else 0)
        if not updates:
            return self.get_user_by_id(user_id)
        updates.append("updated_at = ?")
        values.append(self.db.now_iso())
        values.append(user_id)
        with self.db.connect() as connection:
            connection.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                values,
            )
        return self.get_user_by_id(user_id)

    # ── 会话管理 ──────────────────────────────────────────

    def create_session(self, session: dict[str, Any]) -> None:
        now = self.db.now_iso()
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, user_id, token_hash, created_at, expires_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session["id"],
                    session["user_id"],
                    session["token_hash"],
                    now,
                    session["expires_at"],
                    now,
                ),
            )

    def get_session_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
        return self.db._row_to_dict(row)

    def touch_session(self, session_id: str) -> None:
        with self.db.connect() as connection:
            connection.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE id = ?",
                (self.db.now_iso(), session_id),
            )

    def delete_session_by_token_hash(self, token_hash: str) -> None:
        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (token_hash,)
            )

    def delete_sessions_for_user(self, user_id: str) -> None:
        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE user_id = ?", (user_id,)
            )
