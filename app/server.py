"""Web 入口：装配数据库、服务与 HTTP 路由。"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .auth import (
    AuthorizationError,
    AuthError,
    AuthService,
    SESSION_COOKIE_NAME,
    SESSION_DAYS,
)
from .chat import MODEL_OPTIONS
from .chat.agent import build_chat_agent, build_default_agent
from .config import (
    ARCHIVES_DIR,
    BOOK_OUTPUTS_ROOT,
    DATA_DIR,
    DEFAULT_HOST,
    DEFAULT_PORT,
    SKILLS_ROOT,
    UPLOADS_DIR,
    WEB_DIST,
    WEB_INDEX,
)
from .store import (
    AdminStore,
    AppDatabase,
    ConversationStore,
    SkillPackStore,
    TaskStore,
    UserStore,
)
from .task import SkillTaskManager

# ── 服务组装 ──────────────────────────────────────────────
database = AppDatabase(DATA_DIR / "app.db")
user_store = UserStore(database)
conversation_store = ConversationStore(database)
task_store = TaskStore(database)
skill_pack_store = SkillPackStore(database)
admin_store = AdminStore(database)

auth_service = AuthService(user_store)

task_manager = SkillTaskManager(
    task_store=task_store,
    skill_pack_store=skill_pack_store,
    uploads_dir=UPLOADS_DIR,
    archives_dir=ARCHIVES_DIR,
    skills_root=SKILLS_ROOT,
    book_outputs_root=BOOK_OUTPUTS_ROOT,
)


# ── 通用工具函数 ──────────────────────────────────────────
def error_response(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status_code)


def success_response(payload: dict[str, Any] | None = None) -> JSONResponse:
    data = {"ok": True}
    if payload:
        data.update(payload)
    return JSONResponse(data)


def build_auth_payload(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "isAdmin": bool(user.get("isAdmin")),
        "status": user.get("status", "active"),
    }


def apply_session_cookie(
    response: JSONResponse, token: str | None
) -> JSONResponse:
    if token:
        response.set_cookie(
            SESSION_COOKIE_NAME,
            token,
            httponly=True,
            samesite="lax",
            max_age=SESSION_DAYS * 24 * 60 * 60,
            path="/",
        )
    else:
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


def require_user(request: Request) -> dict[str, Any]:
    return auth_service.require_user(request)


def require_admin(request: Request) -> dict[str, Any]:
    return auth_service.require_admin(request)


def normalize_pack_visibility(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized not in {"private", "public"}:
        return None
    return normalized


def normalize_user_status(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized not in {"active", "disabled"}:
        return None
    return normalized


# ── 认证接口 ──────────────────────────────────────────────
async def register(request: Request) -> JSONResponse:
    payload = await request.json()
    try:
        user, token = auth_service.register(
            str(payload.get("email", "")),
            str(payload.get("password", "")),
            str(payload.get("confirmPassword", "")),
        )
    except AuthError as error:
        return error_response(str(error), 400)

    response = success_response({"user": build_auth_payload(user)})
    return apply_session_cookie(response, token)


async def login(request: Request) -> JSONResponse:
    payload = await request.json()
    try:
        user, token = auth_service.login(
            str(payload.get("email", "")),
            str(payload.get("password", "")),
        )
    except AuthError as error:
        return error_response(str(error), 400)
    except AuthorizationError as error:
        return error_response(str(error), 403)

    response = success_response({"user": build_auth_payload(user)})
    return apply_session_cookie(response, token)


async def logout(request: Request) -> JSONResponse:
    auth_service.logout(request.cookies.get(SESSION_COOKIE_NAME))
    return apply_session_cookie(success_response(), None)


async def me(request: Request) -> JSONResponse:
    user = auth_service.get_current_user(request)
    if not user:
        return error_response("未登录", 401)
    return success_response({"user": build_auth_payload(user)})


# ── 会话数据接口 ──────────────────────────────────────────
async def list_conversations(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    return JSONResponse(
        conversation_store.list_conversations(str(user["id"]))
    )


async def get_conversation_messages(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    conversation_id = request.path_params["conversation_id"]
    messages = conversation_store.get_messages(
        str(user["id"]), conversation_id
    )
    return JSONResponse({"messages": messages})


async def save_conversation_entry(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    payload = await request.json()
    conversation_store.save_conversation(str(user["id"]), payload)
    return success_response()


async def save_conversation_messages(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    conversation_id = request.path_params["conversation_id"]
    payload = await request.json()
    try:
        conversation_store.save_messages(
            str(user["id"]), conversation_id, payload.get("messages", [])
        )
    except ValueError as error:
        return error_response(str(error), 404)
    return success_response()


async def delete_conversation_entry(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    conversation_id = request.path_params["conversation_id"]
    conversation_store.delete_conversation(str(user["id"]), conversation_id)
    return success_response()


# ── Skill 任务接口 ────────────────────────────────────────
async def create_skill_task(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)

    form = await request.form()
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        return error_response("缺少 EPUB 文件", 400)

    file_name = (upload.filename or "").strip()
    if not file_name.lower().endswith(".epub"):
        return error_response("仅支持上传 .epub 文件", 400)

    file_bytes = await upload.read()
    task = task_manager.create_task(
        file_name=file_name,
        file_bytes=file_bytes,
        mime_type=upload.content_type or "application/epub+zip",
        owner_user_id=str(user["id"]),
    )
    return JSONResponse({"ok": True, "task": task})


async def list_skill_tasks(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    return JSONResponse({"tasks": task_manager.list_tasks(str(user["id"]))})


async def get_skill_task(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    task_id = request.path_params["task_id"]
    task = task_store.get_task(task_id, str(user["id"]))
    if not task:
        return error_response("任务不存在", 404)

    events = task_store.get_task_events(task_id, str(user["id"]))
    return JSONResponse(
        {
            "task": task_manager.normalize_task_display_title(task),
            "events": events,
        }
    )


async def get_skill_task_events(request: Request) -> Response:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    task_id = request.path_params["task_id"]
    task = task_store.get_task(task_id, str(user["id"]))
    if not task:
        return error_response("任务不存在", 404)

    return JSONResponse(
        {"events": task_store.get_task_events(task_id, str(user["id"]))}
    )


async def stream_skill_task_events(request: Request) -> Response:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    task_id = request.path_params["task_id"]
    task = task_store.get_task(task_id, str(user["id"]))
    if not task:
        return error_response("任务不存在", 404)

    last_index_param = request.query_params.get("lastEventIndex")
    start_index = (
        int(last_index_param)
        if last_index_param and last_index_param.isdigit()
        else 0
    )

    async def event_iterator():
        current_index = start_index
        idle_rounds = 0
        owner_user_id = str(user["id"])

        while True:
            current_task = task_store.get_task(task_id, owner_user_id)
            if not current_task:
                break

            events = task_store.get_task_events(task_id, owner_user_id)
            if current_index < len(events):
                while current_index < len(events):
                    event = events[current_index]
                    payload = {
                        "index": current_index,
                        "taskId": task_id,
                        **event,
                    }
                    yield b"data: " + task_manager.json_bytes(payload) + b"\n\n"
                    current_index += 1
                idle_rounds = 0
            else:
                idle_rounds += 1
                yield b": keep-alive\n\n"

            if (
                current_task.get("status") in {"completed", "failed"}
                and current_index >= len(events)
            ):
                break

            if idle_rounds > 300:
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_iterator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def download_skill_archive(request: Request) -> Response:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    task_id = request.path_params["task_id"]
    task = task_store.get_task(task_id, str(user["id"]))
    if not task:
        return error_response("任务不存在", 404)

    result = task.get("result") if isinstance(task, dict) else None
    archive_path = (
        Path(result.get("archivePath", ""))
        if isinstance(result, dict) and result.get("archivePath")
        else None
    )
    if not archive_path or not archive_path.exists():
        return error_response("压缩包不存在", 404)

    return FileResponse(
        archive_path,
        filename=archive_path.name,
        media_type="application/zip",
    )


async def delete_skill_task(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    task_id = request.path_params["task_id"]
    task = task_store.get_task(task_id, str(user["id"]))
    if not task:
        return error_response("任务不存在", 404)

    try:
        task_manager.delete_task(task_id)
    except RuntimeError as error:
        return error_response(str(error), 409)
    except Exception as error:
        return error_response(f"删除失败：{error}", 500)

    return success_response()


# ── 技能包接口 ────────────────────────────────────────────
async def list_skill_packs(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    return JSONResponse(
        {"packs": task_manager.list_packs(owner_user_id=str(user["id"]))}
    )


async def list_my_skill_packs(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    return JSONResponse(
        {"packs": task_manager.list_packs(owner_user_id=str(user["id"]))}
    )


async def list_public_skill_packs(request: Request) -> JSONResponse:
    try:
        require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)
    return JSONResponse({"packs": task_manager.list_packs(public_only=True)})


async def update_skill_pack_visibility(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)

    pack_id = request.path_params["pack_id"]
    payload = await request.json()
    visibility = normalize_pack_visibility(payload.get("visibility"))
    if not visibility:
        return error_response("visibility 仅支持 private 或 public", 400)

    pack = skill_pack_store.update_visibility(
        pack_id, str(user["id"]), visibility
    )
    if not pack:
        return error_response("技能包不存在", 404)
    return JSONResponse(
        {"ok": True, "pack": task_manager.normalize_pack_display_title(pack)}
    )


async def delete_skill_pack(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)

    pack_id = request.path_params["pack_id"]
    pack = skill_pack_store.get_pack(pack_id)
    if not pack:
        return error_response("技能包不存在", 404)

    if pack.get("ownerUserId") != user["id"]:
        return error_response("只能删除自己的技能包", 403)

    skill_pack_store.delete_pack(pack_id)
    return success_response()


async def copy_skill_pack_to_my_library(request: Request) -> JSONResponse:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)

    pack_id = request.path_params["pack_id"]
    source_pack = skill_pack_store.get_pack(pack_id)
    if not source_pack:
        return error_response("技能包不存在", 404)

    if source_pack.get("visibility") != "public":
        return error_response("只能复制公开的技能包", 403)

    if source_pack.get("ownerUserId") == user["id"]:
        return error_response("不能复制自己的技能包", 400)

    existing_packs = skill_pack_store.list_packs(owner_user_id=str(user["id"]))
    source_title = source_pack.get("title", "")
    for existing in existing_packs:
        if (
            existing.get("title") == source_title
            and existing.get("author") == source_pack.get("author")
        ):
            return error_response("你已经复制过这个技能包了", 409)

    new_pack_id = f"pack-{uuid4().hex}"
    new_pack = {
        **source_pack,
        "id": new_pack_id,
        "taskId": None,
    }

    skill_pack_store.save_pack(str(user["id"]), new_pack, visibility="private")

    return JSONResponse(
        {"ok": True, "pack": task_manager.normalize_pack_display_title(new_pack)}
    )


# ── 管理接口 ──────────────────────────────────────────────
async def admin_overview(request: Request) -> JSONResponse:
    try:
        require_admin(request)
    except AuthorizationError as error:
        return error_response(str(error), 403)
    return JSONResponse({"stats": admin_store.admin_stats()})


async def admin_list_users(request: Request) -> JSONResponse:
    try:
        require_admin(request)
    except AuthorizationError as error:
        return error_response(str(error), 403)
    users = [
        build_auth_payload(user)
        | {
            "conversationCount": user.get("conversationCount", 0),
            "taskCount": user.get("taskCount", 0),
            "skillPackCount": user.get("skillPackCount", 0),
        }
        for user in admin_store.list_users()
    ]
    return JSONResponse({"users": users})


async def admin_update_user(request: Request) -> JSONResponse:
    try:
        require_admin(request)
    except AuthorizationError as error:
        return error_response(str(error), 403)
    user_id = request.path_params["user_id"]
    payload = await request.json()
    status = (
        normalize_user_status(payload.get("status"))
        if "status" in payload
        else None
    )
    is_admin = payload.get("isAdmin") if "isAdmin" in payload else None
    if is_admin is not None:
        is_admin = bool(is_admin)
    updated = user_store.update_user(user_id, status=status, is_admin=is_admin)
    if not updated:
        return error_response("用户不存在", 404)
    if status == "disabled":
        user_store.delete_sessions_for_user(user_id)
    return JSONResponse({"ok": True, "user": build_auth_payload(updated)})


async def admin_list_tasks(request: Request) -> JSONResponse:
    try:
        require_admin(request)
    except AuthorizationError as error:
        return error_response(str(error), 403)
    tasks = [
        task_manager.normalize_task_display_title(task)
        for task in task_store.list_admin_tasks()
    ]
    return JSONResponse({"tasks": tasks})


async def admin_delete_task(request: Request) -> JSONResponse:
    try:
        require_admin(request)
    except AuthorizationError as error:
        return error_response(str(error), 403)
    task_id = request.path_params["task_id"]
    task = task_store.get_task(task_id)
    if not task:
        return error_response("任务不存在", 404)
    try:
        task_manager.delete_task(task_id)
    except RuntimeError as error:
        return error_response(str(error), 409)
    except Exception as error:
        return error_response(f"删除失败：{error}", 500)
    return success_response()


async def admin_list_skill_packs(request: Request) -> JSONResponse:
    try:
        require_admin(request)
    except AuthorizationError as error:
        return error_response(str(error), 403)
    packs = [
        task_manager.normalize_pack_display_title(pack)
        for pack in skill_pack_store.list_admin_skill_packs()
    ]
    return JSONResponse({"packs": packs})


async def admin_update_skill_pack_visibility(
    request: Request,
) -> JSONResponse:
    try:
        require_admin(request)
    except AuthorizationError as error:
        return error_response(str(error), 403)
    pack_id = request.path_params["pack_id"]
    payload = await request.json()
    visibility = normalize_pack_visibility(payload.get("visibility"))
    if not visibility:
        return error_response("visibility 仅支持 private 或 public", 400)
    pack = skill_pack_store.get_pack(pack_id)
    if not pack:
        return error_response("技能包不存在", 404)
    owner_user_id = str(pack.get("ownerUserId", ""))
    updated = skill_pack_store.update_visibility(
        pack_id, owner_user_id, visibility
    )
    if not updated:
        return error_response("技能包不存在", 404)
    return JSONResponse(
        {"ok": True, "pack": task_manager.normalize_pack_display_title(updated)}
    )


async def admin_list_conversations(request: Request) -> JSONResponse:
    try:
        require_admin(request)
    except AuthorizationError as error:
        return error_response(str(error), 403)
    return JSONResponse(
        {"conversations": admin_store.list_admin_conversations()}
    )


async def admin_delete_conversation(request: Request) -> JSONResponse:
    try:
        require_admin(request)
    except AuthorizationError as error:
        return error_response(str(error), 403)
    conversation_id = request.path_params["conversation_id"]
    admin_store.admin_delete_conversation(conversation_id)
    return success_response()


# ── 聊天接口 ──────────────────────────────────────────────
async def chat(request: Request) -> Response:
    try:
        user = require_user(request)
    except AuthorizationError as error:
        return error_response(str(error), 401)

    body = await request.body()
    payload = json.loads(body.decode("utf-8")) if body else {}
    model_id = payload.get("model") if isinstance(payload, dict) else None

    skill_pack_ids: list[str] | None = None
    if isinstance(payload, dict):
        raw_skill_pack_ids = payload.get("skillPackIds")
        if isinstance(raw_skill_pack_ids, list):
            skill_pack_ids = [
                item for item in raw_skill_pack_ids if isinstance(item, str)
            ]
        else:
            raw_skill_pack_id = payload.get("skillPackId")
            if isinstance(raw_skill_pack_id, str):
                skill_pack_ids = [raw_skill_pack_id]

    accessible_pack_ids = skill_pack_store.get_accessible_pack_ids(
        str(user["id"])
    )
    filtered_skill_pack_ids = [
        pack_id
        for pack_id in (skill_pack_ids or [])
        if pack_id in accessible_pack_ids
    ]

    def resolve_pack_dirs(pack_id: str) -> list[Path]:
        """当 pack 目录不存在时，从数据库中查找 pack 的实际发布路径。"""
        pack = skill_pack_store.get_pack(pack_id)
        if not pack:
            return []
        published_paths = pack.get("publishedPaths") or []
        # 从发布的 SKILL.md 路径中提取唯一的技能根目录
        skill_roots: set[Path] = set()
        for p in published_paths:
            try:
                path = Path(p)
                # publishedPaths 指向 SKILL.md 文件，取其父目录的父目录作为技能根
                # 例如: skills/skill-task-xxx/apply-xxx/SKILL.md → skills/skill-task-xxx
                if path.name == "SKILL.md" and path.parent.parent.exists():
                    skill_roots.add(path.parent.parent)
            except (ValueError, OSError):
                continue
        return list(skill_roots)

    try:
        chat_agent = build_chat_agent(
            SKILLS_ROOT, model_id, filtered_skill_pack_ids, resolve_pack_dirs
        )
    except Exception as error:
        return error_response(f"加载 skill 包失败：{error}", 500)

    from pydantic_ai.ui.vercel_ai import VercelAIAdapter

    return await VercelAIAdapter.dispatch_request(request, agent=chat_agent)


# ── 应用装配 ──────────────────────────────────────────────
agent = build_default_agent(SKILLS_ROOT)

if not WEB_INDEX.exists():
    raise FileNotFoundError(
        "未找到 ai-chat-ui 的构建产物，请在 ai-chat-ui 目录执行 pnpm install && pnpm run build"
    )

app = agent.to_web(models=MODEL_OPTIONS, html_source=str(WEB_INDEX))

# 路由注册（按功能分组）
_API_ROUTES: list[Route] = [
    # 认证
    Route("/api/auth/register", register, methods=["POST"]),
    Route("/api/auth/login", login, methods=["POST"]),
    Route("/api/auth/logout", logout, methods=["POST"]),
    Route("/api/auth/me", me, methods=["GET"]),
    # 聊天
    Route("/api/chat", chat, methods=["POST"]),
    # 会话
    Route("/api/conversations", list_conversations, methods=["GET"]),
    Route("/api/conversations", save_conversation_entry, methods=["POST"]),
    Route(
        "/api/conversations/{conversation_id:path}/messages",
        get_conversation_messages,
        methods=["GET"],
    ),
    Route(
        "/api/conversations/{conversation_id:path}/messages",
        save_conversation_messages,
        methods=["POST"],
    ),
    Route(
        "/api/conversations/{conversation_id:path}",
        delete_conversation_entry,
        methods=["DELETE"],
    ),
    # 技能包广场
    Route("/api/plaza/skill-packs", list_public_skill_packs, methods=["GET"]),
    Route(
        "/api/plaza/skill-packs/{pack_id:str}/copy",
        copy_skill_pack_to_my_library,
        methods=["POST"],
    ),
    # 技能包管理
    Route("/api/skill-packs", list_skill_packs, methods=["GET"]),
    Route("/api/skill-packs/mine", list_my_skill_packs, methods=["GET"]),
    Route(
        "/api/skill-packs/{pack_id:str}", delete_skill_pack, methods=["DELETE"]
    ),
    Route(
        "/api/skill-packs/{pack_id:str}/visibility",
        update_skill_pack_visibility,
        methods=["POST"],
    ),
    # Skill 任务
    Route("/api/skill-tasks", list_skill_tasks, methods=["GET"]),
    Route("/api/skill-tasks", create_skill_task, methods=["POST"]),
    Route(
        "/api/skill-tasks/{task_id:str}", get_skill_task, methods=["GET"]
    ),
    Route(
        "/api/skill-tasks/{task_id:str}", delete_skill_task, methods=["DELETE"]
    ),
    Route(
        "/api/skill-tasks/{task_id:str}/events",
        get_skill_task_events,
        methods=["GET"],
    ),
    Route(
        "/api/skill-tasks/{task_id:str}/events/stream",
        stream_skill_task_events,
        methods=["GET"],
    ),
    Route(
        "/api/skill-tasks/{task_id:str}/download",
        download_skill_archive,
        methods=["GET"],
    ),
    # 管理后台
    Route("/api/admin/overview", admin_overview, methods=["GET"]),
    Route("/api/admin/users", admin_list_users, methods=["GET"]),
    Route(
        "/api/admin/users/{user_id:str}",
        admin_update_user,
        methods=["POST"],
    ),
    Route("/api/admin/tasks", admin_list_tasks, methods=["GET"]),
    Route(
        "/api/admin/tasks/{task_id:str}",
        admin_delete_task,
        methods=["DELETE"],
    ),
    Route(
        "/api/admin/skill-packs", admin_list_skill_packs, methods=["GET"]
    ),
    Route(
        "/api/admin/skill-packs/{pack_id:str}/visibility",
        admin_update_skill_pack_visibility,
        methods=["POST"],
    ),
    Route(
        "/api/admin/conversations",
        admin_list_conversations,
        methods=["GET"],
    ),
    Route(
        "/api/admin/conversations/{conversation_id:path}",
        admin_delete_conversation,
        methods=["DELETE"],
    ),
]

for route in _API_ROUTES:
    app.router.routes.insert(0, route)

# 静态资源
assets_dir = WEB_DIST / "assets"
if assets_dir.exists():
    app.router.routes.insert(
        0, Mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    )

for filename in [
    "favicon.svg",
    "favicon.png",
    "favicon.ico",
    "apple-touch-icon.png",
]:
    file_path = WEB_DIST / filename
    if file_path.exists():
        app.router.routes.insert(
            0,
            Route(f"/{filename}", lambda _request, p=file_path: FileResponse(p)),
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)
