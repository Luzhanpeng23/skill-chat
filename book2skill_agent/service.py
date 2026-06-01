from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .agent import app
from .config import OUTPUT_DIR
from .skill_markdown import validate_and_normalize_skill_markdown
from .token_tracker import token_tracker


ProgressCallback = Callable[[dict[str, Any]], None]


def _append_rejected_publish_note(book_output_dir: Path, skill_name: str, errors: list[str]) -> None:
    rejected_dir = book_output_dir / 'rejected'
    rejected_dir.mkdir(parents=True, exist_ok=True)
    readme_path = rejected_dir / 'README.md'
    existing = readme_path.read_text(encoding='utf-8') if readme_path.exists() else '# 审计记录\n'
    note = f"\n### {skill_name}\n- 原因: 发布阶段发现非法 SKILL.md：{' ; '.join(errors)}\n"
    if f"### {skill_name}\n" not in existing:
        readme_path.write_text(existing.rstrip() + note, encoding='utf-8')


def _token_stats_snapshot() -> dict[str, int]:
    stats = token_tracker.get_stats()
    return {
        'input_tokens': int(stats.get('input_tokens', 0)),
        'output_tokens': int(stats.get('output_tokens', 0)),
        'total_tokens': int(stats.get('total_tokens', 0)),
        'successful_calls': int(stats.get('successful_calls', 0)),
    }


def _token_stats_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {
        'input_tokens': after['input_tokens'] - before['input_tokens'],
        'output_tokens': after['output_tokens'] - before['output_tokens'],
        'total_tokens': after['total_tokens'] - before['total_tokens'],
        'successful_calls': after['successful_calls'] - before['successful_calls'],
    }


def build_initial_state(book_path: str, progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    return {
        'book_path': book_path,
        'metadata': {},
        'full_text': '',
        'chapters': {},
        'overview': '',
        'candidates': [],
        'verified_units': [],
        'rejected_units': [],
        'relations': {},
        'final_skills': [],
        'errors': [],
        'stats': {},
        'progress_callback': progress_callback,
    }


def run_book_to_skill(
    book_path: str,
    progress_callback: ProgressCallback | None = None,
    recursion_limit: int = 50,
) -> dict[str, Any]:
    state = build_initial_state(book_path, progress_callback)
    final_state = state
    token_stats_before = _token_stats_snapshot()

    for output in app.stream(state, config={'recursion_limit': recursion_limit}):
        for _node_name, state_update in output.items():
            final_state = {**final_state, **state_update}

    token_stats_after = _token_stats_snapshot()
    stats = dict(final_state.get('stats', {}))
    stats['token_usage'] = _token_stats_delta(token_stats_before, token_stats_after)
    final_state['stats'] = stats

    return final_state


def get_book_output_dir(final_state: dict[str, Any]) -> Path:
    metadata = final_state.get('metadata', {})
    dir_name = metadata.get('dir_name')
    if not dir_name:
        raise ValueError('Book output directory is missing from metadata')

    return Path(OUTPUT_DIR) / dir_name


def create_skill_archive(book_output_dir: Path, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f'{book_output_dir.name}-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'
    archive_path = destination_dir / archive_name

    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in book_output_dir.rglob('*'):
            if file_path.is_file():
                zip_file.write(file_path, file_path.relative_to(book_output_dir))

    return archive_path


def publish_skill_pack(book_output_dir: Path, skills_root: Path, pack_id: str) -> list[str]:
    source_root = book_output_dir / 'skills'
    if not source_root.exists():
        return []

    published_paths: list[str] = []
    pack_root = skills_root / pack_id
    if pack_root.exists():
        shutil.rmtree(pack_root)

    pack_root.mkdir(parents=True, exist_ok=True)

    for skill_dir in sorted(source_root.iterdir()):
        if not skill_dir.is_dir():
            continue

        source_skill_file = skill_dir / 'SKILL.md'
        if not source_skill_file.exists():
            continue

        validation = validate_and_normalize_skill_markdown(
            source_skill_file.read_text(encoding='utf-8')
        )
        if not validation.is_valid:
            _append_rejected_publish_note(book_output_dir, skill_dir.name, validation.errors)
            continue

        target_dir = pack_root / skill_dir.name
        shutil.copytree(skill_dir, target_dir, dirs_exist_ok=True)

        skill_file = target_dir / 'SKILL.md'
        skill_file.write_text(validation.normalized_content, encoding='utf-8')

        published_paths.append(str(target_dir))

    return published_paths


def get_skill_pack_root(skills_root: Path, pack_id: str) -> Path:
    return skills_root / pack_id


def build_result_summary(
    task_id: str,
    final_state: dict[str, Any],
    archive_path: Path | None = None,
    published_paths: list[str] | None = None,
) -> dict[str, Any]:
    stats = final_state.get('stats', {})
    metadata = final_state.get('metadata', {})
    book_output_dir = get_book_output_dir(final_state)

    return {
        'taskId': task_id,
        'bookTitle': metadata.get('title') or Path(final_state.get('book_path', '')).stem,
        'bookAuthor': metadata.get('author') or 'Unknown',
        'bookDirName': metadata.get('dir_name'),
        'outputDir': str(book_output_dir),
        'archivePath': str(archive_path) if archive_path else None,
        'publishedPaths': published_paths or [],
        'finalSkills': final_state.get('final_skills', []),
        'verifiedCount': len(final_state.get('final_skills', [])),
        'rejectedCount': len(final_state.get('rejected_units', [])),
        'errors': final_state.get('errors', []),
        'stats': {
            'rawChars': stats.get('raw_chars', 0),
            'finalCount': stats.get('final_count', len(final_state.get('final_skills', []))),
            'ratio': stats.get('ratio'),
            'startTime': stats.get('start_time'),
            'endTime': stats.get('end_time'),
            'tokenUsage': stats.get('token_usage', _token_stats_snapshot()),
        },
    }


def build_index_snapshot(book_output_dir: Path) -> dict[str, Any]:
    snapshot: dict[str, Any] = {'files': []}
    for file_name in ['BOOK_OVERVIEW.md', 'INDEX.md', 'metadata.json']:
        file_path = book_output_dir / file_name
        if file_path.exists():
            snapshot['files'].append({'name': file_name, 'path': str(file_path)})

    skills_root = book_output_dir / 'skills'
    if skills_root.exists():
        snapshot['skills'] = []
        for skill_dir in sorted(skills_root.iterdir()):
            skill_file = skill_dir / 'SKILL.md'
            if skill_dir.is_dir() and skill_file.exists():
                snapshot['skills'].append(
                    {
                        'id': skill_dir.name,
                        'path': str(skill_file),
                        'testsPath': str(skill_dir / 'test-prompts.json'),
                    }
                )

    rejected_readme = book_output_dir / 'rejected' / 'README.md'
    if rejected_readme.exists():
        snapshot['rejectedReadme'] = str(rejected_readme)

    return snapshot


def serialize_result_summary(summary: dict[str, Any]) -> str:
    return json.dumps(summary, ensure_ascii=False)