"""任务数据访问层。"""
from __future__ import annotations

from typing import Any

from .base import AppDatabase


class TaskStore:
    def __init__(self, db: AppDatabase) -> None:
        self.db = db

    def list_tasks(
        self, owner_user_id: str | None = None
    ) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            if owner_user_id:
                rows = connection.execute(
                    "SELECT raw_json FROM tasks WHERE owner_user_id = ? ORDER BY created_at DESC",
                    (owner_user_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT raw_json FROM tasks ORDER BY created_at DESC"
                ).fetchall()
        return [
            self.db._loads(row["raw_json"], {})
            for row in rows
            if row["raw_json"]
        ]

    def get_task(
        self, task_id: str, owner_user_id: str | None = None
    ) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            if owner_user_id:
                row = connection.execute(
                    "SELECT raw_json FROM tasks WHERE id = ? AND owner_user_id = ?",
                    (task_id, owner_user_id),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT raw_json FROM tasks WHERE id = ?",
                    (task_id,),
                ).fetchone()
        if row is None:
            return None
        return self.db._loads(row["raw_json"], {})

    def create_task(self, owner_user_id: str, task: dict[str, Any]) -> None:
        task_id = str(task.get("id", "")).strip()
        if not task_id:
            raise ValueError("Task id is required")
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (id, owner_user_id, status, phase, file_name, created_at, updated_at, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    owner_user_id,
                    task.get("status", "pending"),
                    task.get("phase"),
                    task.get("fileName"),
                    task.get("createdAt") or self.db.now_iso(),
                    task.get("updatedAt") or self.db.now_iso(),
                    self.db._dumps(task),
                ),
            )

    def update_task(
        self, task_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT raw_json, owner_user_id FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Task not found: {task_id}")
            task = self.db._loads(row["raw_json"], {})
            task.update(updates)
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, phase = ?, file_name = ?, updated_at = ?, raw_json = ?
                WHERE id = ?
                """,
                (
                    task.get("status", "pending"),
                    task.get("phase"),
                    task.get("fileName"),
                    task.get("updatedAt") or self.db.now_iso(),
                    self.db._dumps(task),
                    task_id,
                ),
            )
        return task

    def append_task_event(
        self, task_id: str, event: dict[str, Any]
    ) -> dict[str, Any]:
        with self.db.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if exists is None:
                raise ValueError(f"Task not found: {task_id}")
            connection.execute(
                "INSERT INTO task_events (task_id, event_json, created_at) VALUES (?, ?, ?)",
                (task_id, self.db._dumps(event), event.get("timestamp") or self.db.now_iso()),
            )
        return event

    def replace_task_events(
        self, task_id: str, events: list[dict[str, Any]]
    ) -> None:
        with self.db.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if exists is None:
                raise ValueError(f"Task not found: {task_id}")
            connection.execute(
                "DELETE FROM task_events WHERE task_id = ?", (task_id,)
            )
            for event in events:
                connection.execute(
                    "INSERT INTO task_events (task_id, event_json, created_at) VALUES (?, ?, ?)",
                    (task_id, self.db._dumps(event), event.get("timestamp") or self.db.now_iso()),
                )

    def get_task_events(
        self, task_id: str, owner_user_id: str | None = None
    ) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            if owner_user_id:
                exists = connection.execute(
                    "SELECT 1 FROM tasks WHERE id = ? AND owner_user_id = ?",
                    (task_id, owner_user_id),
                ).fetchone()
            else:
                exists = connection.execute(
                    "SELECT 1 FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
            if exists is None:
                return []
            rows = connection.execute(
                "SELECT event_json FROM task_events WHERE task_id = ? ORDER BY id ASC",
                (task_id,),
            ).fetchall()
        return [
            self.db._loads(row["event_json"], {})
            for row in rows
            if row["event_json"]
        ]

    def delete_task(self, task_id: str) -> None:
        with self.db.connect() as connection:
            connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def list_admin_tasks(self) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT tasks.raw_json, users.email AS owner_email
                FROM tasks
                JOIN users ON users.id = tasks.owner_user_id
                ORDER BY tasks.created_at DESC
                """
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = self.db._loads(row["raw_json"], {})
            item["ownerEmail"] = row["owner_email"]
            items.append(item)
        return items
