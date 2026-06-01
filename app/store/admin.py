"""管理后台数据查询：跨表聚合操作。"""
from __future__ import annotations

from typing import Any

from .base import AppDatabase
from .user import _normalize_user_row


class AdminStore:
    def __init__(self, db: AppDatabase) -> None:
        self.db = db

    def list_users(self) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    users.*,
                    COUNT(DISTINCT conversations.id) AS conversation_count,
                    COUNT(DISTINCT tasks.id) AS task_count,
                    COUNT(DISTINCT skill_packs.id) AS skill_pack_count
                FROM users
                LEFT JOIN conversations ON conversations.user_id = users.id
                LEFT JOIN tasks ON tasks.owner_user_id = users.id
                LEFT JOIN skill_packs ON skill_packs.owner_user_id = users.id
                GROUP BY users.id
                ORDER BY users.created_at DESC
                """
            ).fetchall()
        users: list[dict[str, Any]] = []
        for row in rows:
            item = _normalize_user_row(row) or {}
            item["conversationCount"] = int(row["conversation_count"] or 0)
            item["taskCount"] = int(row["task_count"] or 0)
            item["skillPackCount"] = int(row["skill_pack_count"] or 0)
            users.append(item)
        return users

    def list_admin_conversations(self) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT conversations.raw_json, users.email AS owner_email
                FROM conversations
                JOIN users ON users.id = conversations.user_id
                ORDER BY conversations.timestamp DESC
                """
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = self.db._loads(row["raw_json"], {})
            item["ownerEmail"] = row["owner_email"]
            items.append(item)
        return items

    def admin_delete_conversation(self, conversation_id: str) -> None:
        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )

    def admin_stats(self) -> dict[str, int]:
        with self.db.connect() as connection:
            users_count = connection.execute(
                "SELECT COUNT(*) AS count FROM users"
            ).fetchone()
            conversations_count = connection.execute(
                "SELECT COUNT(*) AS count FROM conversations"
            ).fetchone()
            tasks_count = connection.execute(
                "SELECT COUNT(*) AS count FROM tasks"
            ).fetchone()
            packs_count = connection.execute(
                "SELECT COUNT(*) AS count FROM skill_packs"
            ).fetchone()
            public_packs_count = connection.execute(
                "SELECT COUNT(*) AS count FROM skill_packs WHERE visibility = 'public'"
            ).fetchone()
            active_users_count = connection.execute(
                "SELECT COUNT(*) AS count FROM users WHERE status = 'active'"
            ).fetchone()
        return {
            "users": int(users_count["count"] if users_count else 0),
            "conversations": int(
                conversations_count["count"] if conversations_count else 0
            ),
            "tasks": int(tasks_count["count"] if tasks_count else 0),
            "skillPacks": int(packs_count["count"] if packs_count else 0),
            "publicSkillPacks": int(
                public_packs_count["count"] if public_packs_count else 0
            ),
            "activeUsers": int(
                active_users_count["count"] if active_users_count else 0
            ),
        }
