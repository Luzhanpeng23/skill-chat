"""统一管理 book2skill 任务的创建、执行、展示与清理。"""
from __future__ import annotations

import json
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from book2skill_agent.service import (
    build_index_snapshot,
    build_result_summary,
    create_skill_archive,
    get_skill_pack_root,
    publish_skill_pack,
    run_book_to_skill,
)

from ..store.skill_pack import SkillPackStore
from ..store.task import TaskStore


class SkillTaskManager:
    def __init__(
        self,
        task_store: TaskStore,
        skill_pack_store: SkillPackStore,
        uploads_dir: Path,
        archives_dir: Path,
        skills_root: Path,
        book_outputs_root: Path,
    ) -> None:
        self.task_store = task_store
        self.skill_pack_store = skill_pack_store
        self.uploads_dir = uploads_dir
        self.archives_dir = archives_dir
        self.skills_root = skills_root
        self.book_outputs_root = book_outputs_root.resolve()

        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.archives_dir.mkdir(parents=True, exist_ok=True)

        self.task_threads: dict[str, threading.Thread] = {}
        self.task_lock = threading.Lock()
        self.allowed_delete_roots = [
            self.uploads_dir.resolve(),
            self.archives_dir.resolve(),
            self.skills_root.resolve(),
            self.book_outputs_root,
        ]

    @staticmethod
    def now_iso() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def json_bytes(data: dict[str, object]) -> bytes:
        return json.dumps(data, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def is_generated_task_label(value: object) -> bool:
        if not isinstance(value, str):
            return False
        return bool(
            re.fullmatch(r"skill-task-[a-z0-9]+", value.strip(), re.IGNORECASE)
        )

    @staticmethod
    def derive_book_title_from_file_name(file_name: object) -> str | None:
        if not isinstance(file_name, str):
            return None

        value = Path(file_name.strip()).stem.strip()
        if not value:
            return None

        noisy_suffix_re = re.compile(
            r"\s*\((?:z-library|1lib|z-lib|annas-archive|libgen)[^)]*\)\s*$",
            re.IGNORECASE,
        )
        while noisy_suffix_re.search(value):
            value = noisy_suffix_re.sub("", value).strip()

        return value or None

    def normalize_task_display_title(
        self, task: dict[str, object]
    ) -> dict[str, object]:
        normalized = dict(task)
        result = normalized.get("result")
        file_name = normalized.get("fileName")
        fallback_title = (
            self.derive_book_title_from_file_name(file_name) or normalized.get("id")
        )

        if isinstance(result, dict):
            next_result = dict(result)
            book_title = next_result.get("bookTitle")
            if (
                not isinstance(book_title, str)
                or not book_title.strip()
                or self.is_generated_task_label(book_title)
            ):
                next_result["bookTitle"] = fallback_title
            normalized["result"] = next_result

        return normalized

    def normalize_pack_display_title(
        self, pack: dict[str, object]
    ) -> dict[str, object]:
        normalized = dict(pack)
        title = normalized.get("title")
        if (
            isinstance(title, str)
            and title.strip()
            and not self.is_generated_task_label(title)
        ):
            return normalized

        task_id = normalized.get("taskId")
        task = (
            self.task_store.get_task(task_id) if isinstance(task_id, str) else None
        )
        fallback_title = None
        if isinstance(task, dict):
            fallback_title = self.derive_book_title_from_file_name(
                task.get("fileName")
            )

        normalized["title"] = (
            fallback_title or normalized.get("title") or normalized.get("id")
        )
        return normalized

    def list_tasks(
        self, owner_user_id: str | None = None
    ) -> list[dict[str, object]]:
        return [
            self.normalize_task_display_title(task)
            for task in self.task_store.list_tasks(owner_user_id)
        ]

    def list_packs(
        self,
        owner_user_id: str | None = None,
        *,
        accessible_user_id: str | None = None,
        public_only: bool = False,
    ) -> list[dict[str, object]]:
        if public_only:
            packs = self.skill_pack_store.list_packs(visibility="public")
        elif accessible_user_id:
            packs = self.skill_pack_store.list_accessible_packs(accessible_user_id)
        else:
            packs = self.skill_pack_store.list_packs(owner_user_id)
        return [self.normalize_pack_display_title(pack) for pack in packs]

    def build_task_event(
        self, event: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        return {
            "event": event,
            "timestamp": self.now_iso(),
            "payload": payload or {},
        }

    def update_task_progress(
        self, task_id: str, event: dict[str, object]
    ) -> None:
        self.task_store.append_task_event(task_id, event)

        payload = event.get("payload", {})
        event_name = event.get("event")
        progress_phase = payload.get("phase") if isinstance(payload, dict) else None

        updates: dict[str, object] = {"updatedAt": event["timestamp"]}
        if progress_phase:
            updates["phase"] = progress_phase
        if event_name == "task_started":
            updates["status"] = "running"
            updates["startedAt"] = event["timestamp"]
        elif event_name == "task_completed":
            updates["status"] = "completed"
            updates["completedAt"] = event["timestamp"]
        elif event_name == "task_failed":
            updates["status"] = "failed"
            updates["completedAt"] = event["timestamp"]
            updates["error"] = (
                payload.get("message")
                if isinstance(payload, dict)
                else "Unknown error"
            )

        self.task_store.update_task(task_id, updates)

    def run_book_task(self, task_id: str, book_path: Path) -> None:
        """后台线程入口：执行拆书、发布 skill 包并回写任务结果。"""
        try:
            self.update_task_progress(
                task_id,
                self.build_task_event("task_started", {"phase": "queued"}),
            )

            def progress_callback(event: dict[str, object]) -> None:
                payload = dict(event)
                event_name = str(payload.pop("event", "progress"))
                self.update_task_progress(
                    task_id, self.build_task_event(event_name, payload)
                )

            final_state = run_book_to_skill(
                str(book_path), progress_callback=progress_callback
            )
            dir_name = final_state.get("metadata", {}).get("dir_name", "")
            if not dir_name:
                raise ValueError("Book2Skill 未返回输出目录信息")

            source_output_dir = Path(dir_name)
            if not source_output_dir.is_absolute():
                source_output_dir = self.book_outputs_root / source_output_dir

            archive_path = create_skill_archive(
                source_output_dir, self.archives_dir
            )
            pack_id = task_id
            published_paths = publish_skill_pack(
                source_output_dir, self.skills_root, pack_id
            )

            summary = build_result_summary(
                task_id, final_state, archive_path, published_paths
            )
            summary["snapshot"] = build_index_snapshot(source_output_dir)
            summary["packId"] = pack_id

            task_record = self.task_store.get_task(task_id)
            fallback_title = None
            if isinstance(task_record, dict):
                fallback_title = self.derive_book_title_from_file_name(
                    task_record.get("fileName")
                )
            if self.is_generated_task_label(summary.get("bookTitle")) and fallback_title:
                summary["bookTitle"] = fallback_title

            owner_user_id = (
                str(task_record.get("ownerUserId", ""))
                if isinstance(task_record, dict)
                else ""
            )
            self.skill_pack_store.save_pack(
                owner_user_id,
                {
                    "id": pack_id,
                    "taskId": task_id,
                    "title": summary["bookTitle"],
                    "author": summary["bookAuthor"],
                    "createdAt": self.now_iso(),
                    "archivePath": summary["archivePath"],
                    "outputDir": summary["outputDir"],
                    "publishedPaths": summary["publishedPaths"],
                    "snapshot": summary["snapshot"],
                    "verifiedCount": summary["verifiedCount"],
                },
                visibility="private",
            )

            self.task_store.update_task(
                task_id,
                {
                    "status": "completed",
                    "phase": "completed",
                    "updatedAt": self.now_iso(),
                    "completedAt": self.now_iso(),
                    "result": summary,
                    "packId": pack_id,
                },
            )
            self.task_store.append_task_event(
                task_id, self.build_task_event("task_completed", summary)
            )
        except Exception as error:
            self.task_store.update_task(
                task_id,
                {
                    "status": "failed",
                    "phase": "failed",
                    "updatedAt": self.now_iso(),
                    "completedAt": self.now_iso(),
                    "error": str(error),
                },
            )
            self.task_store.append_task_event(
                task_id,
                self.build_task_event("task_failed", {"message": str(error)}),
            )
        finally:
            with self.task_lock:
                self.task_threads.pop(task_id, None)

    def create_task(
        self,
        file_name: str,
        file_bytes: bytes,
        mime_type: str,
        owner_user_id: str,
    ) -> dict[str, object]:
        """创建任务记录并立即启动后台处理。"""
        task_id = f"skill-task-{uuid4().hex[:12]}"
        saved_path = self.uploads_dir / f"{task_id}.epub"
        saved_path.write_bytes(file_bytes)

        task = {
            "id": task_id,
            "type": "book2skill",
            "status": "pending",
            "phase": "uploaded",
            "createdAt": self.now_iso(),
            "updatedAt": self.now_iso(),
            "fileName": file_name,
            "filePath": str(saved_path),
            "fileSize": len(file_bytes),
            "mimeType": mime_type or "application/epub+zip",
            "ownerUserId": owner_user_id,
        }
        self.task_store.create_task(owner_user_id, task)
        self.task_store.append_task_event(
            task_id,
            self.build_task_event("task_created", {"fileName": file_name}),
        )
        self.start_task(task_id, saved_path)
        return task

    def start_task(self, task_id: str, saved_path: Path) -> None:
        thread = threading.Thread(
            target=self.run_book_task, args=(task_id, saved_path), daemon=True
        )
        with self.task_lock:
            self.task_threads[task_id] = thread
        thread.start()

    def is_task_running(self, task_id: str) -> bool:
        thread = self.task_threads.get(task_id)
        if thread and thread.is_alive():
            return True

        task = self.task_store.get_task(task_id)
        if isinstance(task, dict) and task.get("status") in {"pending", "running"}:
            return True

        return False

    def delete_task(self, task_id: str) -> None:
        """删除任务时同步清理上传文件、发布目录和归档产物。"""
        task = self.task_store.get_task(task_id)
        if not task:
            raise FileNotFoundError("任务不存在")

        if self.is_task_running(task_id):
            raise RuntimeError("任务仍在运行中，暂不支持删除")

        pack = self.skill_pack_store.get_pack(task_id)
        cleanup_paths = self.collect_task_cleanup_paths(task_id, task, pack)

        for path in cleanup_paths:
            self.delete_path_if_allowed(path)
        self.skill_pack_store.delete_pack(task_id)
        self.task_store.delete_task(task_id)

    def collect_task_cleanup_paths(
        self,
        task_id: str,
        task: dict[str, object],
        pack: dict[str, object] | None,
    ) -> list[Path]:
        values: list[str | Path | None] = [
            task.get("filePath"),
            get_skill_pack_root(self.skills_root, task_id),
        ]

        result = task.get("result")
        if isinstance(result, dict):
            values.extend([result.get("archivePath"), result.get("outputDir")])
            published_paths = result.get("publishedPaths")
            if isinstance(published_paths, list):
                values.extend(
                    item
                    for item in published_paths
                    if isinstance(item, (str, Path))
                )

        if isinstance(pack, dict):
            values.extend([pack.get("archivePath"), pack.get("outputDir")])
            published_paths = pack.get("publishedPaths")
            if isinstance(published_paths, list):
                values.extend(
                    item
                    for item in published_paths
                    if isinstance(item, (str, Path))
                )

        unique_paths: list[Path] = []
        seen: set[str] = set()
        for value in values:
            if not value:
                continue
            normalized = str(Path(value).resolve())
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_paths.append(Path(normalized))

        unique_paths.sort(key=lambda item: len(item.parts), reverse=True)
        return unique_paths

    def delete_path_if_allowed(self, path_value: str | Path | None) -> None:
        if not path_value:
            return

        path = Path(path_value).resolve()
        if not any(
            self.is_path_within(path, root) for root in self.allowed_delete_roots
        ):
            raise ValueError(f"不允许删除目录范围外的路径: {path}")

        if not path.exists():
            return

        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    @staticmethod
    def is_path_within(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False
