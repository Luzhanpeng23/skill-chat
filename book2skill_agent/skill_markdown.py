from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import yaml


CODE_FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*$", re.IGNORECASE)
BODY_START_RE = re.compile(r"^(?:#{1,6}\s+\S|>\s*\S|-\s+\S|\d+\.\s+\S)")
REQUIRED_FRONTMATTER_FIELDS = ("name", "description")


@dataclass(slots=True)
class SkillMarkdownValidationResult:
    is_valid: bool
    normalized_content: str
    errors: list[str]
    frontmatter: dict[str, Any] | None = None
    body: str = ""
    repaired: bool = False


def unwrap_markdown_code_fence(text: str) -> str:
    value = text.strip()
    match = CODE_FENCE_RE.fullmatch(value)
    if match:
        return match.group(1).strip() + "\n"
    return text


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split_frontmatter_sections(text: str) -> tuple[str, str, bool]:
    normalized = _normalize_newlines(text).lstrip("﻿")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing opening frontmatter delimiter")

    closing_index: int | None = None
    implicit_body_index: int | None = None

    for index, line in enumerate(lines[1:], start=1):
        if closing_index is None and line.strip() == "---":
            closing_index = index
            continue

        if implicit_body_index is None and BODY_START_RE.match(line):
            implicit_body_index = index
            if closing_index is None or implicit_body_index < closing_index:
                break

    if implicit_body_index is not None and (
        closing_index is None or implicit_body_index < closing_index
    ):
        frontmatter_text = "\n".join(lines[1:implicit_body_index])
        body_text = "\n".join(lines[implicit_body_index:])
        return frontmatter_text, body_text, True

    if closing_index is not None:
        frontmatter_text = "\n".join(lines[1:closing_index])
        body_text = "\n".join(lines[closing_index + 1 :])
        return frontmatter_text, body_text, False

    raise ValueError("missing closing frontmatter delimiter")


def validate_and_normalize_skill_markdown(text: str) -> SkillMarkdownValidationResult:
    normalized = _normalize_newlines(unwrap_markdown_code_fence(text)).strip()
    errors: list[str] = []

    try:
        frontmatter_text, body_text, repaired = _split_frontmatter_sections(normalized)
    except ValueError as error:
        return SkillMarkdownValidationResult(
            is_valid=False,
            normalized_content=normalized + ("\n" if normalized else ""),
            errors=[str(error)],
        )

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as error:
        return SkillMarkdownValidationResult(
            is_valid=False,
            normalized_content=normalized + "\n",
            errors=[f"invalid frontmatter yaml: {error}"],
            repaired=repaired,
        )

    if not isinstance(frontmatter, dict):
        errors.append("frontmatter must be a mapping")
        frontmatter = None
    else:
        for field in REQUIRED_FRONTMATTER_FIELDS:
            value = frontmatter.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"missing required frontmatter field: {field}")

    body = body_text.strip("\n")
    if not body:
        errors.append("missing markdown body")

    normalized_content = f"---\n{frontmatter_text.strip()}\n---\n\n{body}\n"
    return SkillMarkdownValidationResult(
        is_valid=not errors,
        normalized_content=normalized_content,
        errors=errors,
        frontmatter=frontmatter if isinstance(frontmatter, dict) else None,
        body=body,
        repaired=repaired,
    )


def has_required_skill_frontmatter_text(text: str) -> bool:
    return validate_and_normalize_skill_markdown(text).is_valid
