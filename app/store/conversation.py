"""对话数据访问层。"""
from __future__ import annotations

from typing import Any

from .base import AppDatabase


class ConversationStore:
    def __init__(self, db: AppDatabase) -> None:
        self.db = db

    def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT raw_json FROM conversations WHERE user_id = ? ORDER BY timestamp DESC",
                (user_id,),
            ).fetchall()
        return [
            self.db._loads(row["raw_json"], {})
            for row in rows
            if row["raw_json"]
        ]

    def get_conversation(
        self, user_id: str, conversation_id: str
    ) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT raw_json FROM conversations WHERE user_id = ? AND id = ?",
                (user_id, conversation_id),
            ).fetchone()
        if row is None:
            return None
        return self.db._loads(row["raw_json"], {})

    def save_conversation(self, user_id: str, conversation: dict[str, Any]) -> None:
        conversation_id = str(conversation.get("id", "")).strip()
        if not conversation_id:
            raise ValueError("Conversation id is required")
        now = self.db.now_iso()
        first_message = conversation.get("firstMessage")
        timestamp = int(conversation.get("timestamp", 0) or 0)
        fork_of_json = (
            self.db._dumps(conversation.get("forkOf"))
            if conversation.get("forkOf")
            else None
        )
        skill_pack_ids = conversation.get("skillPackIds")
        if skill_pack_ids is None and conversation.get("skillPackId"):
            skill_pack_ids = [conversation.get("skillPackId")]
        skill_pack_ids_json = self.db._dumps(skill_pack_ids or [])
        raw_json = self.db._dumps(conversation)
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (
                    id, user_id, first_message, timestamp, fork_of_json,
                    skill_pack_ids_json, raw_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    user_id = excluded.user_id,
                    first_message = excluded.first_message,
                    timestamp = excluded.timestamp,
                    fork_of_json = excluded.fork_of_json,
                    skill_pack_ids_json = excluded.skill_pack_ids_json,
                    raw_json = excluded.raw_json,
                    updated_at = excluded.updated_at
                """,
                (
                    conversation_id,
                    user_id,
                    first_message,
                    timestamp,
                    fork_of_json,
                    skill_pack_ids_json,
                    raw_json,
                    now,
                    now,
                ),
            )

    def get_messages(
        self, user_id: str, conversation_id: str
    ) -> list[dict[str, Any]] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                """
                SELECT conversation_messages.messages_json
                FROM conversation_messages
                JOIN conversations ON conversations.id = conversation_messages.conversation_id
                WHERE conversations.user_id = ? AND conversations.id = ?
                """,
                (user_id, conversation_id),
            ).fetchone()
        if row is None:
            return None
        return self.db._loads(row["messages_json"], [])

    def save_messages(
        self, user_id: str, conversation_id: str, messages: list[dict[str, Any]]
    ) -> None:
        with self.db.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM conversations WHERE user_id = ? AND id = ?",
                (user_id, conversation_id),
            ).fetchone()
            if not exists:
                raise ValueError(f"Conversation not found: {conversation_id}")
            connection.execute(
                """
                INSERT INTO conversation_messages (conversation_id, messages_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    messages_json = excluded.messages_json,
                    updated_at = excluded.updated_at
                """,
                (conversation_id, self.db._dumps(messages), self.db.now_iso()),
            )

    def delete_conversation(self, user_id: str, conversation_id: str) -> None:
        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM conversations WHERE user_id = ? AND id = ?",
                (user_id, conversation_id),
            )
