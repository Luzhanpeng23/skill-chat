"""Agent 构建：Skill 发现与聊天 Agent 组装。"""
from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from book2skill_agent.service import get_skill_pack_root
from book2skill_agent.skill_markdown import has_required_skill_frontmatter_text
from pydantic_ai import Agent
from pydantic_ai_skills import SkillsCapability

from tools import register_tools

from .models import DEFAULT_MODEL, DEFAULT_SYSTEM_PROMPT, get_model_by_id


def _has_required_skill_frontmatter(skill_file: Path) -> bool:
    try:
        content = skill_file.read_text(encoding="utf-8")
    except OSError:
        return False
    return has_required_skill_frontmatter_text(content)


def _is_managed_skill_pack_file(skill_root: Path, skill_file: Path) -> bool:
    try:
        relative_parts = skill_file.relative_to(skill_root).parts
    except ValueError:
        return False
    if not relative_parts:
        return False
    return bool(
        re.fullmatch(r"skill-task-[a-z0-9]+", relative_parts[0], re.IGNORECASE)
    )


def discover_skill_directories(
    skill_root: Path, *, include_managed_packs: bool = True
) -> list[str]:
    """只加载 frontmatter 校验通过的 skills，避免脏数据进入运行时。"""
    if not skill_root.exists():
        return []

    valid_directories: list[str] = []
    for skill_file in sorted(skill_root.rglob("SKILL.md")):
        if not include_managed_packs and _is_managed_skill_pack_file(
            skill_root, skill_file
        ):
            continue
        if _has_required_skill_frontmatter(skill_file):
            valid_directories.append(str(skill_file.parent))
        else:
            print(f"Skipping invalid skill file: {skill_file}")

    return valid_directories


def get_skill_directories_for_packs(
    skills_root: Path,
    skill_pack_ids: list[str] | None,
    pack_dir_resolver: Callable[[str], list[Path]] | None = None,
) -> list[str]:
    """根据 skill_pack_ids 发现技能目录。

    Args:
        skills_root: 技能根目录。
        skill_pack_ids: 用户选择的技能包 ID 列表。
        pack_dir_resolver: 可选的 pack 目录解析函数，当 pack 目录不存在时
            调用此函数获取实际的技能根目录列表。
    """
    # 如果没有指定 skill_pack_ids，不加载任何 skills
    if not skill_pack_ids:
        return []
    
    # 否则，先加载非 managed 的 skills，再加载指定 packs 的 skills
    directories = discover_skill_directories(
        skills_root, include_managed_packs=False
    )
    seen = set(directories)
    for skill_pack_id in skill_pack_ids:
        pack_root = get_skill_pack_root(skills_root, skill_pack_id)
        if not pack_root.exists():
            # 目录不存在时，尝试使用解析函数获取实际目录
            if pack_dir_resolver is not None:
                for resolved_root in pack_dir_resolver(skill_pack_id):
                    if not resolved_root.exists():
                        continue
                    for directory in discover_skill_directories(resolved_root):
                        if directory in seen:
                            continue
                        seen.add(directory)
                        directories.append(directory)
            continue
        for directory in discover_skill_directories(pack_root):
            if directory in seen:
                continue
            seen.add(directory)
            directories.append(directory)

    return directories


def build_chat_agent(
    skills_root: Path,
    model_id: str | None,
    skill_pack_ids: list[str] | None,
    pack_dir_resolver: Callable[[str], list[Path]] | None = None,
) -> Agent:
    """按当前会话选择的模型与 skill packs 动态构建聊天 Agent。"""
    chat_agent = Agent(
        get_model_by_id(model_id),
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        tools=[],
        tool_retries=6,
        capabilities=[
            SkillsCapability(
                directories=get_skill_directories_for_packs(
                    skills_root, skill_pack_ids, pack_dir_resolver
                ),
                auto_reload=True,
            )
        ],
    )
    register_tools(chat_agent)
    return chat_agent


def build_default_agent(skills_root: Path) -> Agent:
    """页面启动时的默认 Agent，仅加载系统级 skills。"""
    default_agent = Agent(
        DEFAULT_MODEL,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        tools=[],
        tool_retries=6,
        capabilities=[
            SkillsCapability(
                directories=discover_skill_directories(
                    skills_root, include_managed_packs=False
                ),
                auto_reload=True,
            )
        ],
    )
    register_tools(default_agent)
    return default_agent
