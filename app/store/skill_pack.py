"""技能包数据访问层。"""
from __future__ import annotations

from typing import Any

from .base import AppDatabase


class SkillPackStore:
    def __init__(self, db: AppDatabase) -> None:
        self.db = db

    @staticmethod
    def _normalize_pack_payload(
        pack: dict[str, Any], *, owner_user_id: str, visibility: str
    ) -> dict[str, Any]:
        payload = dict(pack)
        payload["ownerUserId"] = owner_user_id
        payload["visibility"] = visibility
        return payload

    def list_packs(
        self,
        owner_user_id: str | None = None,
        *,
        visibility: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT raw_json, visibility, owner_user_id FROM skill_packs"
        values: list[Any] = []
        clauses: list[str] = []
        if owner_user_id is not None:
            clauses.append("owner_user_id = ?")
            values.append(owner_user_id)
        if visibility is not None:
            clauses.append("visibility = ?")
            values.append(visibility)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        with self.db.connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [
            self._normalize_pack_payload(
                self.db._loads(row["raw_json"], {}),
                owner_user_id=row["owner_user_id"],
                visibility=row["visibility"],
            )
            for row in rows
            if row["raw_json"]
        ]

    def list_accessible_packs(self, user_id: str) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT raw_json, visibility, owner_user_id
                FROM skill_packs
                WHERE owner_user_id = ? OR visibility = 'public'
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        items: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        # 记录用户已拥有的技能包的 title+author，用于去重公开包
        owned_keys: set[str] = set()
        for row in rows:
            item = self._normalize_pack_payload(
                self.db._loads(row["raw_json"], {}),
                owner_user_id=row["owner_user_id"],
                visibility=row["visibility"],
            )
            pack_id = str(item.get("id", ""))
            if not pack_id or pack_id in seen_ids:
                continue
            # 如果是用户自己的包，记录其 title+author
            if row["owner_user_id"] == user_id:
                key = f"{item.get('title', '')}|{item.get('author', '')}".lower()
                if key:
                    owned_keys.add(key)
            seen_ids.add(pack_id)
            items.append(item)
        # 过滤：排除用户已复制的公开包（title+author 相同但不属于自己的公开包）
        if owned_keys:
            items = [
                item
                for item in items
                if item.get("ownerUserId") == user_id
                or f"{item.get('title', '')}|{item.get('author', '')}".lower()
                not in owned_keys
            ]
        return items

    def get_pack(self, pack_id: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT raw_json, visibility, owner_user_id FROM skill_packs WHERE id = ?",
                (pack_id,),
            ).fetchone()
        if row is None:
            return None
        return self._normalize_pack_payload(
            self.db._loads(row["raw_json"], {}),
            owner_user_id=row["owner_user_id"],
            visibility=row["visibility"],
        )

    def save_pack(
        self, owner_user_id: str, pack: dict[str, Any], visibility: str = "private"
    ) -> None:
        pack_id = str(pack.get("id", "")).strip()
        if not pack_id:
            raise ValueError("Skill pack id is required")
        payload = self._normalize_pack_payload(
            pack, owner_user_id=owner_user_id, visibility=visibility
        )
        now = self.db.now_iso()
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO skill_packs (id, owner_user_id, visibility, title, author, created_at, updated_at, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    owner_user_id = excluded.owner_user_id,
                    visibility = excluded.visibility,
                    title = excluded.title,
                    author = excluded.author,
                    updated_at = excluded.updated_at,
                    raw_json = excluded.raw_json
                """,
                (
                    pack_id,
                    owner_user_id,
                    visibility,
                    payload.get("title"),
                    payload.get("author"),
                    payload.get("createdAt") or now,
                    now,
                    self.db._dumps(payload),
                ),
            )

    def update_visibility(
        self, pack_id: str, owner_user_id: str, visibility: str
    ) -> dict[str, Any] | None:
        pack = self.get_pack(pack_id)
        if not pack or pack.get("ownerUserId") != owner_user_id:
            return None
        self.save_pack(owner_user_id, pack, visibility=visibility)
        return self.get_pack(pack_id)

    def delete_pack(self, pack_id: str) -> None:
        with self.db.connect() as connection:
            connection.execute("DELETE FROM skill_packs WHERE id = ?", (pack_id,))

    def get_accessible_pack_ids(self, user_id: str) -> set[str]:
        return {
            str(item.get("id"))
            for item in self.list_accessible_packs(user_id)
            if item.get("id")
        }

    def list_admin_skill_packs(self) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT skill_packs.raw_json, skill_packs.visibility,
                       skill_packs.owner_user_id, users.email AS owner_email
                FROM skill_packs
                JOIN users ON users.id = skill_packs.owner_user_id
                ORDER BY skill_packs.created_at DESC
                """
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = self._normalize_pack_payload(
                self.db._loads(row["raw_json"], {}),
                owner_user_id=row["owner_user_id"],
                visibility=row["visibility"],
            )
            item["ownerEmail"] = row["owner_email"]
            items.append(item)
        return items
