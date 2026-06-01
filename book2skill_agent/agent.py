import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from .config import API_KEY, BASE_URL, MODEL_NAME, OUTPUT_DIR, PROMPTS_DIR, TEMPLATES_DIR
from .parser import (
    get_book_metadata,
    parse_file_to_markdown,
    split_markdown_by_chapters,
)
from .skill_markdown import validate_and_normalize_skill_markdown
from .token_tracker import token_tracker


# 定义状态
class AgentState(TypedDict):
    book_path: str
    metadata: Dict
    full_text: str
    chapters: Dict[str, str]
    overview: str
    candidates: List[Dict]
    verified_units: List[Dict]
    rejected_units: List[Dict]
    relations: Dict[str, List[Dict]]
    final_skills: List[str]
    errors: List[str]
    stats: Dict
    progress_callback: Any


# 初始化模型
llm = ChatOpenAI(
    api_key=API_KEY, base_url=BASE_URL, model=MODEL_NAME, temperature=0.1, timeout=120
)

# --- 辅助函数 ---


def safe_invoke(messages, max_retries=5):
    """带指数退避重试机制的 LLM 调用，专门应对 429 限流"""
    for i in range(max_retries):
        try:
            response = llm.invoke(messages)
            token_tracker.add_usage(response)
            return response
        except Exception as e:
            if (
                "429" in str(e)
                or "rate_limit" in str(e).lower()
                or "quota" in str(e).lower()
            ):
                wait_time = (i + 1) * 10  # 递增等待 10s, 20s, 30s...
                print(
                    f"  [Retry] 触发限流或 API 错误，等待 {wait_time} 秒后重试... ({i + 1}/{max_retries})"
                )
                time.sleep(wait_time)
            else:
                raise e
    raise Exception("LLM 调用超过最大重试次数")


def sanitize_path(text: str) -> str:
    s = str(text).lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "untitled-book"


def sanitize_slug(text: str) -> str:
    s = str(text).lower().strip()
    s = re.sub(r"-[a-f0-9]{6}$", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "skill"


def get_content_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:6]


def load_prompt(extractor_name: str) -> str:
    path = os.path.join(PROMPTS_DIR, f"{extractor_name}-extractor.md")
    if not os.path.exists(path):
        print(f"  [Warn] 提取器提示词不存在: {path}", flush=True)
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def report_progress(state: AgentState, event: str, **payload: Any) -> None:
    callback = state.get("progress_callback")
    if not callable(callback):
        return

    try:
        callback({"event": event, **payload})
    except Exception:
        pass


def build_chapter_context(
    chapters: Dict[str, str],
    *,
    total_budget: int,
    per_chapter_cap: int,
    min_per_chapter: int,
) -> str:
    items = list(chapters.items())
    if not items:
        return ""

    parts: list[str] = []
    used_chars = 0
    total_items = len(items)

    for index, (title, content) in enumerate(items):
        remaining_items = max(1, total_items - index)
        remaining_budget = max(0, total_budget - used_chars)
        current_limit = min(
            per_chapter_cap,
            max(min_per_chapter, remaining_budget // remaining_items if remaining_budget else 0),
        )
        snippet = content[:current_limit].strip()
        used_chars += len(snippet)
        parts.append(f"\n## {title}\n{snippet}\n")

    return "".join(parts)


def extract_fenced_block(text: str) -> str | None:
    match = re.search(r"```(?:json|yaml|yml)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def extract_balanced_structure(text: str, opening: str) -> str | None:
    closing = "]" if opening == "[" else "}"
    start = text.find(opening)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def escape_json_control_chars(text: str) -> str:
    escaped: list[str] = []
    in_string = False
    escape = False

    for char in text:
        if in_string:
            if escape:
                escaped.append(char)
                escape = False
                continue
            if char == "\\":
                escaped.append(char)
                escape = True
                continue
            if char == '"':
                escaped.append(char)
                in_string = False
                continue
            if char == "\n":
                escaped.append("\\n")
                continue
            if char == "\r":
                escaped.append("\\r")
                continue
            if char == "\t":
                escaped.append("\\t")
                continue
            if ord(char) < 32:
                escaped.append(f"\\u{ord(char):04x}")
                continue
            escaped.append(char)
            continue

        escaped.append(char)
        if char == '"':
            in_string = True

    return "".join(escaped)


def parse_llm_structure(text: str, expected_type: type[list] | type[dict]):
    candidates: list[str] = []
    fenced = extract_fenced_block(text)
    if fenced:
        candidates.append(fenced)

    opening = "[" if expected_type is list else "{"
    balanced = extract_balanced_structure(text, opening)
    if balanced:
        candidates.append(balanced)

    candidates.append(text.strip())

    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)

        for attempt in (candidate, escape_json_control_chars(candidate)):
            try:
                parsed = json.loads(attempt)
                if isinstance(parsed, expected_type):
                    return parsed
            except Exception:
                pass

        try:
            parsed = yaml.safe_load(candidate)
            if isinstance(parsed, expected_type):
                return parsed
        except Exception:
            pass

    raise ValueError("无法从模型输出中解析出合法结构化结果")


# --- 节点定义 ---


def parser_node(state: AgentState) -> AgentState:
    report_progress(state, "phase_started", phase="parser")
    print(f"--- [Node: Parser] 正在解析: {state['book_path']} ---", flush=True)
    try:
        book_path = state["book_path"]
        metadata = get_book_metadata(book_path)
        metadata["dir_name"] = sanitize_path(metadata["title"])

        full_text = parse_file_to_markdown(book_path)
        chapters = split_markdown_by_chapters(full_text)

        book_dir = Path(OUTPUT_DIR) / metadata["dir_name"]
        book_dir.mkdir(parents=True, exist_ok=True)
        (book_dir / "skills").mkdir(exist_ok=True)
        (book_dir / "rejected").mkdir(exist_ok=True)

        return {
            **state,
            "metadata": metadata,
            "full_text": full_text,
            "chapters": chapters,
            "stats": {
                "raw_chars": len(full_text),
                "start_time": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        print(f"Parser failed: {e}")
        return {
            **state,
            "errors": state.get("errors", []) + [f"Parser error: {str(e)}"],
        }


def overview_node(state: AgentState) -> AgentState:
    report_progress(state, "phase_started", phase="overview")
    print("--- [Node: Overview] Adler 战略分析 ---", flush=True)
    sample_text = build_chapter_context(
        state["chapters"],
        total_budget=90000,
        per_chapter_cap=5000,
        min_per_chapter=1200,
    )

    prompt = """你是一个专业的知识工程专家。请对文本进行 Adler 分析阅读，产出 BOOK_OVERVIEW。
核心目标：识别出书中真正具有“方法论价值”的核心模型、底层逻辑、章节结构与作者盲点。
重要要求：
1. 优先覆盖全书，而不是只抓少数高频主题。
2. 如果原书存在编号条目、计策清单、法则清单、章节级离散方法，请逐一识别其差异，不要因为表面相似就提前合并。
3. 优先保证后续 skill 提取质量，不要为了节省上下文而过度压缩。
请使用 Markdown 格式详细输出。"""

    try:
        response = safe_invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=f"书名: {state['metadata']['title']}\n内容采样:\n{sample_text}"
                ),
            ]
        )
        overview = response.content
        book_dir = Path(OUTPUT_DIR) / state["metadata"]["dir_name"]
        (book_dir / "BOOK_OVERVIEW.md").write_text(overview, encoding="utf-8")
        return {**state, "overview": overview}
    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"Overview error: {str(e)}"],
        }


def extract_node(state: AgentState) -> AgentState:
    report_progress(state, "phase_started", phase="extract")
    print("--- [Node: Extract] 全书深度采矿 ---", flush=True)
    extractors = ["principle", "framework", "case", "glossary", "counter-example"]
    all_candidates = []
    chapter_context = build_chapter_context(
        state["chapters"],
        total_budget=160000,
        per_chapter_cap=8000,
        min_per_chapter=1500,
    )

    for ext in extractors:
        print(f"  [Miner] 启动 {ext} 提取器...", flush=True)
        prompt_tmpl = load_prompt(ext)
        if not prompt_tmpl:
            continue

        ctx = f"BOOK_OVERVIEW:\n{state['overview']}\n\nTEXT:\n{chapter_context}"

        try:
            res = safe_invoke(
                [SystemMessage(content=prompt_tmpl), HumanMessage(content=ctx)]
            )
            items = parse_llm_structure(res.content, list)
            if items:
                all_candidates.extend(items)
        except Exception as e:
            print(f"    {ext} 提取失败: {e}", flush=True)

    report_progress(state, "candidates_extracted", count=len(all_candidates))
    return {**state, "candidates": all_candidates}


def _normalize_candidate(c) -> Dict:
    """将字符串候选标准化为 {title, summary} 字典。"""
    if isinstance(c, dict):
        return c
    text = str(c).strip()
    lines = text.split("\n", 1)
    title = lines[0].strip().lstrip("#").strip()[:120] or "未命名条目"
    summary = lines[1].strip() if len(lines) > 1 else text[:300]
    return {"title": title, "summary": summary, "raw": text}


def verify_node(state: AgentState) -> AgentState:
    report_progress(state, "phase_started", phase="verify")
    # 标准化：确保所有候选都是 dict
    normalized = [_normalize_candidate(c) for c in state["candidates"]]
    print(
        f"--- [Node: Verify] Two-Stage 语义去重与深度审计 (待处理: {len(normalized)} 个) ---",
        flush=True,
    )
    rejected = []
    stage1_survivors = []

    # ==========================================
    # Stage 1 (Map): 本地绝对质量审计 (不进行去重)
    # ==========================================
    print("  [Stage 1] 质量清洗 (剔除常识与纯描述性内容)...", flush=True)
    map_prompt = f"""你是一个审慎但不过度保守的知识架构师。请参考以下 BOOK_OVERVIEW，对候选单元进行纯粹的质量过滤。

BOOK_OVERVIEW:
{state["overview"]}

核心任务：
只做一件事：判断该单元是否具有独立作为“方法论（Skill）”的资格。
- 淘汰条件（is_passed=false）：纯剧情描述、常识废话、毫无操作性的陈述。
- 保留条件（is_passed=true）：具有可执行的操作步骤、诊断标准、适用情境或思维框架。
- 对于编号条目、计策、战术、法则、口诀这类原生离散内容，只要它具备清晰意图、适用场景或决策价值，即使篇幅短也应保留。

【重要规则：不许去重！】
即使你看到两个内容几乎一模一样的候选点，只要它们各自质量过关，都必须标记为 is_passed: true！去重工作将在下一阶段进行。

请严格返回 JSON 列表，格式如下：
[{{"title": "原标题", "is_passed": true_or_false, "reason": "淘汰理由（如果通过则填空）"}}]"""

    try:
        # 加大 batch size，只做简单的 true/false 判断
        batch_size = 40
        for i in range(0, len(normalized), batch_size):
            batch = normalized[i : i + batch_size]
            # 为了减少 token 和提升注意力，只传关键字段
            minimal_batch = [
                {"title": c.get("title"), "summary": c.get("summary")} for c in batch
            ]

            res = safe_invoke(
                [
                    SystemMessage(content=map_prompt),
                    HumanMessage(content=json.dumps(minimal_batch, ensure_ascii=False)),
                ]
            )
            try:
                results = parse_llm_structure(res.content, list)
            except Exception as parse_error:
                print(f"  [Stage 1 Warn] 批次解析失败，默认保留该批候选点: {parse_error}", flush=True)
                stage1_survivors.extend(batch)
                continue

            for r in results:
                original_title = r.get("title")
                if not original_title:
                    continue

                original_match = next(
                    (c for c in batch if c.get("title") == original_title), None
                )
                if not original_match:
                    continue

                if not r.get("is_passed", True):
                    rejected.append(
                        {
                            "title": original_title,
                            "reason": r.get("reason", "未通过阶段一质量审查"),
                        }
                    )
                else:
                    stage1_survivors.append(original_match)

    except Exception as e:
        print(f"Stage 1 failed: {e}")
        return {
            **state,
            "errors": state.get("errors", []) + [f"Verify Stage 1 error: {str(e)}"],
        }

    print(
        f"  [Stage 1 完成] 保留了 {len(stage1_survivors)} 个高质量单元，进入全局融合。"
    )

    # ==========================================
    # Stage 2 (Reduce): 全局聚类与优中选优融合
    # ==========================================
    print("  [Stage 2] 全局视野下的聚类与融合...", flush=True)
    verified = []
    seen_hashes = set()

    if not stage1_survivors:
        print("  [警告] 阶段一没有幸存的候选点！")
        return {**state, "verified_units": [], "rejected_units": rejected}

    reduce_prompt = f"""你是一个顶级的知识架构师。以下列表中的知识点都已经通过了初步的质量审核。你的任务是站在【全局视角】对它们进行聚类和完美融合。

BOOK_OVERVIEW:
{state["overview"]}

任务目标：
1. 聚类融合：只合并语义高度重合、几乎互为改写、或明显属于同一上位技能且拆开会重复解释的候选点。
2. 优中选优：在融合时，提取各个重复单元中最精彩的细节（如：A的案例+B的操作步骤），不要因为某个单元“出现得早”就忽略“出现得晚但质量更高”的内容。
3. 优先保留原书粒度：对于编号条目、计策、战术、法则清单中的独立项，默认分别保留；除非它们本质上只是同一技能的不同说法。
4. 动作化标题：为最终 Skill 赋予动作化标题（如：识别...、建立...、应用...）。
5. 动词化 Slug：生成简练的英文 slug，必须以动词开头（如：identify-..., establish-...）。
6. 最终数量：不要预设硬上限，宁可多保留也不要过度折叠；如果原书天然包含 20/36/48 个离散方法，输出数量应尽量贴近原书结构。
7. 如果某个候选点本身已经足够独立、无需与其他项融合，`source_titles` 可以只包含 1 项。

请严格返回 JSON 列表，格式如下：
[{{"merged_title": "最终的动作化标题", "slug": "verb-started-slug", "source_titles": ["被融合的原始标题1", "被融合的原始标题2"]}}]"""

    try:
        res = safe_invoke(
            [
                SystemMessage(content=reduce_prompt),
                HumanMessage(content=json.dumps(stage1_survivors, ensure_ascii=False)),
            ]
        )
        results = parse_llm_structure(res.content, list)

        for r in results:
            title = r.get("merged_title")
            if not title or str(title).lower() == "none":
                continue

            source_titles = r.get("source_titles", [])
            if not source_titles:
                continue

            fused_sources = [
                c for c in stage1_survivors if c.get("title") in source_titles
            ]
            if not fused_sources:
                continue

            base_item = fused_sources[0].copy()
            base_item["title"] = title

            merged_summary = "\n\n---\n\n".join(
                [f"[{c.get('title')}]: {c.get('summary', '')}" for c in fused_sources]
            )
            base_item["summary"] = merged_summary

            base_slug = sanitize_slug(r.get("slug") or title)
            if base_slug == "none" or not base_slug:
                base_slug = "analyze-method"

            c_hash = get_content_hash(title + merged_summary)
            if c_hash in seen_hashes:
                continue
            seen_hashes.add(c_hash)

            base_item["slug"] = f"{base_slug}-{c_hash}"
            verified.append(base_item)

    except Exception as e:
        print(f"Stage 2 failed, fallback to keep survivors as-is: {e}")
        for item in stage1_survivors:
            title = str(item.get("title") or "Unknown")
            summary = str(item.get("summary") or "")
            base_slug = sanitize_slug(item.get("slug") or title)
            c_hash = get_content_hash(title + summary)
            if c_hash in seen_hashes:
                continue
            seen_hashes.add(c_hash)

            next_item = item.copy()
            next_item["slug"] = f"{base_slug}-{c_hash}"
            verified.append(next_item)

    if not verified:
        for item in stage1_survivors:
            title = str(item.get("title") or "Unknown")
            summary = str(item.get("summary") or "")
            base_slug = sanitize_slug(item.get("slug") or title)
            c_hash = get_content_hash(title + summary)
            if c_hash in seen_hashes:
                continue
            seen_hashes.add(c_hash)

            next_item = item.copy()
            next_item["slug"] = f"{base_slug}-{c_hash}"
            verified.append(next_item)

    book_dir = Path(OUTPUT_DIR) / state["metadata"]["dir_name"]
    (book_dir / "rejected").mkdir(parents=True, exist_ok=True)
    (book_dir / "rejected" / "README.md").write_text(
        "# 审计记录\n\n"
        + "\n".join([f"### {r['title']}\n- 原因: {r['reason']}" for r in rejected]),
        encoding="utf-8",
    )

    report_progress(
        state,
        "skills_initialized",
        items=[
            {"slug": item.get("slug"), "title": item.get("title")}
            for item in verified
        ],
        verified_count=len(verified),
        rejected_count=len(rejected),
    )

    return {**state, "verified_units": verified, "rejected_units": rejected}


def relate_node(state: AgentState) -> AgentState:
    report_progress(state, "phase_started", phase="relate")
    print(f"--- [Node: Relate] 建立拓扑网 ---", flush=True)
    units = [{"title": u["title"], "slug": u["slug"]} for u in state["verified_units"]]
    if not units:
        return {**state, "relations": {}}

    prompt = '分析以下技能列表，生成逻辑连接关系。只返回 JSON: {"relations": [{"from": "slug-a", "to": "slug-b", "type": "composes-with"}]}'
    try:
        res = safe_invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=json.dumps(units, ensure_ascii=False)),
            ]
        )
        relations = parse_llm_structure(res.content, dict)

        rel_map = {}
        for r in relations.get("relations", []):
            f, t, typ = r.get("from"), r.get("to"), r.get("type")
            if f and t:
                if f not in rel_map:
                    rel_map[f] = []
                rel_map[f].append({"slug": t, "type": typ})
        return {**state, "relations": rel_map}
    except:
        return {**state, "relations": {}}


def ria_node(state: AgentState) -> AgentState:
    report_progress(state, "phase_started", phase="ria")
    units = state.get("verified_units", [])
    print(f"--- [Node: RIA] 并发封装 (目标: {len(units)} 个) ---", flush=True)

    template_path = Path(TEMPLATES_DIR) / "SKILL.md.template"
    template = (
        template_path.read_text(encoding="utf-8") if template_path.exists() else ""
    )

    final_skills = []
    book_dir_name = state["metadata"]["dir_name"]
    today = datetime.now().strftime("%Y-%m-%d")

    def append_rejected_skill_note(skill_title: str, reason: str) -> None:
        rejected_dir = Path(OUTPUT_DIR) / book_dir_name / "rejected"
        rejected_dir.mkdir(parents=True, exist_ok=True)
        readme_path = rejected_dir / "README.md"
        existing = readme_path.read_text(encoding="utf-8") if readme_path.exists() else "# 审计记录\n"
        note = f"\n### {skill_title}\n- 原因: {reason}\n"
        if f"### {skill_title}\n" not in existing:
            readme_path.write_text(existing.rstrip() + note, encoding="utf-8")

    def process_unit(index, unit):
        slug, title = unit.get("slug"), unit.get("title", "Unknown")
        unit_rels = state.get("relations", {}).get(slug, [])

        # 第一阶段：高质量生成 SKILL.md
        ria_prompt = f"""你是一个专业的知识架构师。今天的日期是 {today}。请将此单元封装为符合 RIA+ 结构的 SKILL.md。确保内容充实、逻辑严密。

输出铁律：
1. 只输出最终的原始 Markdown 文本，不要解释，不要额外前言，不要使用 ```markdown 或任何代码块包裹整个文档。
2. 文档必须以 YAML frontmatter 开头：第一行是 ---，frontmatter 在正文开始前必须用第二个 --- 明确结束。
3. description 字段只包含描述文本本身；任何正文内容，包括标题行 (#)、引用行 (>), 列表行 (-, 1.)，都必须出现在第二个 --- 之后，绝不能落在 frontmatter 内。
4. 如果 R 段以引用块 > 开头，也必须先写完并关闭 frontmatter，再开始引用。
5. 严格遵守模板字段名，不要新增 frontmatter 字段，不要删除必填字段。

正确示例：
---
name: sample-skill
description: |
  这里是描述。
source_book: 《示例》 作者
source_chapter: 第一章
tags: [tag1, tag2]
related_skills: []
---

# 标题

> 这里才是正文引用

错误示例：
---
name: sample-skill
description: |
  这里是描述。
source_book: 《示例》 作者
related_skills: []

> 这里是错误写法，因为第二个 --- 丢了，引用被吞进 frontmatter

输出前自检：
- 是否没有外层代码块
- 是否存在第二个 --- 结束 frontmatter
- 是否所有 #、>、-、1. 正文都出现在第二个 --- 之后

模板：
{template}"""
        ctx = f"单元数据: {yaml.dump(unit, allow_unicode=True)}\n关系网: {json.dumps(unit_rels)}\n整书背景: {state.get('overview', '')}"

        try:
            report_progress(
                state,
                "skill_started",
                slug=slug,
                title=title,
                index=index + 1,
                total=len(units),
                step="生成 SKILL.md",
            )
            print(f"  [Task] 正在封装 SKILL: {title}...", flush=True)
            res_md = safe_invoke(
                [SystemMessage(content=ria_prompt), HumanMessage(content=ctx)]
            )
            validation = validate_and_normalize_skill_markdown(res_md.content)
            if not validation.is_valid:
                reason = "生成的 SKILL.md 校验失败: " + "; ".join(validation.errors)
                append_rejected_skill_note(title, reason)
                raise ValueError(reason)
            content_md = validation.normalized_content

            # 第二阶段：基于生成的 SKILL.md，独立生成高质量测试用例
            test_prompt = """你是一个高级测试工程师。请为提供的 SKILL 生成 Darwin 兼容的测试用例。
必须包含：
- 3条 should_trigger (正面场景)
- 2条 should_not_trigger (反面场景)
- 1条 edge_case (边界场景)
必须只返回合法的 JSON 列表。格式如下：
[
  {
    "category": "should_trigger",
    "input": "用户可能说的话...",
    "expected_trigger": true,
    "reason": "为什么触发"
  }
]"""
            report_progress(
                state,
                "skill_step",
                slug=slug,
                title=title,
                index=index + 1,
                total=len(units),
                step="生成测试用例",
            )
            print(f"  [Task] 正在生成 Tests: {title}...", flush=True)
            res_test = safe_invoke(
                [SystemMessage(content=test_prompt), HumanMessage(content=content_md)]
            )
            try:
                test_items = parse_llm_structure(res_test.content, list)
                test_json = json.dumps(test_items, ensure_ascii=False, indent=2)
            except Exception:
                test_json = "[]"

            # 写入文件
            skill_dir = Path(OUTPUT_DIR) / book_dir_name / "skills" / slug
            skill_dir.mkdir(parents=True, exist_ok=True)

            (skill_dir / "SKILL.md").write_text(content_md, encoding="utf-8")
            (skill_dir / "test-prompts.json").write_text(test_json, encoding="utf-8")

            print(f"  [OK] 完成: {title}", flush=True)
            result_path = str(skill_dir / "SKILL.md")
            report_progress(
                state,
                "skill_completed",
                slug=slug,
                title=title,
                index=index + 1,
                total=len(units),
                path=result_path,
            )
            return result_path

        except Exception as e:
            append_rejected_skill_note(title, str(e))
            report_progress(
                state,
                "skill_failed",
                slug=slug,
                title=title,
                index=index + 1,
                total=len(units),
                error=str(e),
            )
            print(f"  [Fail] {title}: {e}", flush=True)
            return None

    # 控制并发以避免触发大量 429
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_unit, index, u) for index, u in enumerate(units)]
        for f in as_completed(futures):
            res = f.result()
            if res:
                final_skills.append(res)

    return {**state, "final_skills": final_skills}


def index_node(state: AgentState) -> AgentState:
    report_progress(state, "phase_started", phase="index")
    print("--- [Node: Index] 生成全书导航 ---", flush=True)
    try:
        book_dir_name = state["metadata"]["dir_name"]
        book_dir = Path(OUTPUT_DIR) / book_dir_name

        # 扫描磁盘获取实际产出
        skills_found = []
        skills_root = book_dir / "skills"
        if skills_root.exists():
            for skill_dir in sorted(skills_root.iterdir()):
                skill_file = skill_dir / "SKILL.md"
                if skill_dir.is_dir() and skill_file.exists():
                    content = skill_file.read_text(encoding="utf-8")
                    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                    title = (
                        title_match.group(1).strip() if title_match else skill_dir.name
                    )
                    skills_found.append(
                        {
                            "slug": skill_dir.name,
                            "title": title,
                            "path": f"./skills/{skill_dir.name}/SKILL.md",
                        }
                    )

        stats = state.get("stats", {})
        stats["end_time"] = datetime.now().isoformat()
        stats["final_count"] = len(skills_found)
        stats["ratio"] = (
            f"{len(state.get('full_text', '')) / max(1, len(skills_found)):.0f} chars/skill"
        )

        prompt = f"""为书籍《{state["metadata"]["title"]}》生成一份极具专业感的 INDEX.md 索引文件。

输出要求：
1. 排版精美：使用清晰的标题层级、引用块和美化的表格。
2. 逻辑分组：将技能按深度和应用场景分为 3-5 个逻辑模块，并用表格列出模块内的技能。
3. 【致命警告：防止路径张冠李戴】：在表格中附上技能链接时，**必须完全、逐字**从下方的【数据源：技能列表】中提取对应标题的 `path` 字段。大模型极易在此处产生幻觉，请务必在填入路径前，重新检索数据源校验 `path` 值！严禁篡改或拼凑路径。
4. 增强版 Mermaid：生成关系图，节点必须使用【技能标题】全称，严禁使用 A, B, C 等代号。线条应清晰标注关系类型（如：组合、依赖）。
5. 统计面板：展示原始字符数、最终技能数、平均压缩比、处理耗时等。
6. 学习路径：根据逻辑关系，为用户设计一条由浅入深的通关路线图。
7. 审计追踪：提及 rejected 文件夹中记录了详细的审计淘汰理由，体现专业严谨性。

数据源：
技能列表: {json.dumps(skills_found, ensure_ascii=False)}
逻辑关系: {json.dumps(state.get("relations", {}), ensure_ascii=False)}
工程统计: {json.dumps(stats, ensure_ascii=False)}
书籍概览: {state["overview"][:1500]}"""

        res = safe_invoke([SystemMessage(content=prompt)])
        report_progress(state, "index_completed", final_count=len(skills_found))
        (book_dir / "INDEX.md").write_text(res.content, encoding="utf-8")
        (book_dir / "metadata.json").write_text(
            json.dumps(state["metadata"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"--- [Node: Index] 成功写入 INDEX.md ---", flush=True)
    except Exception as e:
        print(f"Index node failed: {e}")
    return state


# --- 构建图 ---
workflow = StateGraph(AgentState)
workflow.add_node("parser", parser_node)
workflow.add_node("overview", overview_node)
workflow.add_node("extract", extract_node)
workflow.add_node("verify", verify_node)
workflow.add_node("relate", relate_node)
workflow.add_node("ria", ria_node)
workflow.add_node("index", index_node)

def _should_continue(state: AgentState) -> str:
    """如果已有错误则终止流程。"""
    if state.get("errors"):
        return "end"
    return "continue"


workflow.set_entry_point("parser")
workflow.add_conditional_edges(
    "parser",
    _should_continue,
    {"continue": "overview", "end": END},
)
workflow.add_conditional_edges(
    "overview",
    _should_continue,
    {"continue": "extract", "end": END},
)
workflow.add_conditional_edges(
    "extract",
    _should_continue,
    {"continue": "verify", "end": END},
)
workflow.add_edge("verify", "relate")
workflow.add_edge("relate", "ria")
workflow.add_edge("ria", "index")
workflow.add_edge("index", END)

app = workflow.compile()
