import re
from pathlib import Path

root = Path(r"c:\Users\Pisces\Desktop\skills-chat\books\孙子兵法-三十六计")
skills_dir = root / "skills"

def parse_front(text):
    data = {}
    if not text.startswith("---"):
        return data
    end = text.find("---", 3)
    if end == -1:
        return data
    block = text[3:end]
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "|":
                collected = []
                i += 1
                while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("-")):
                    collected.append(lines[i].strip())
                    i += 1
                data[key] = " ".join(collected)
                continue
            if key == "related_skills":
                value = [x.strip().strip(",") for x in value.strip("[]").split(",") if x.strip()]
            data[key] = value
        i += 1
    return data

def first_sentence(text):
    for line in text.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## R"):
            continue
        if line.strip() == "":
            continue
        return line.strip().split("。")[0]
    return ""

entries = []
relations = []

for p in sorted(skills_dir.iterdir()):
    if not p.is_dir():
        continue
    md = p / "SKILL.md"
    if not md.exists():
        continue
    text = md.read_text(encoding="utf-8")
    meta = parse_front(text)
    title = None
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    desc = (meta.get("description") or "").replace("\n", " ").strip()
    if not desc:
        desc = first_sentence(text)
    entries.append({
        "slug": p.name,
        "title": title or p.name,
        "desc": desc,
    })
    for rel in (meta.get("related_skills") or []):
        relations.append((p.name, rel))

# 分组
decision = ["five-elements-assessment", "know-enemy-know-self", "dialectical-thinking"]
strategy = [
    "defense-first", "adaptability-framework", "avoid-solid-strike-void",
    "initiative-control", "indirect-approach", "resource-leverage",
    "attrition-strategy", "desperation-breakthrough", "intelligence-gathering",
    "deception-framework", "character-risk-framework", "weakness-attack",
    "key-point-leverage", "timing-momentum", "patience-concealment",
    "retreat-wisdom", "multi-strategy-combination", "pathfinding-indirect",
    "optimal-victory", "leverage-third-party", "root-cause-analysis",
]
management = ["team-alignment", "management-balance"]

slug_to_entry = {e["slug"]: e for e in entries}

def render_group(title, slugs):
    lines = [f"### {title}", ""]
    for s in slugs:
        e = slug_to_entry.get(s)
        if e:
            lines.append(f"- [`{e['slug']}`](./skills/{e['slug']}/SKILL.md) — {e['title']}：{e['desc']}")
    lines.append("")
    return "\n".join(lines)

graph_lines = ["```mermaid", "graph LR"]
seen_edges = set()
for a, b in relations:
    if a == b:
        continue
    edge = (a, b)
    if edge in seen_edges:
        continue
    seen_edges.add(edge)
    graph_lines.append(f"    {a} -.-> {b}")
graph_lines.append("```")

index = f"""# 《孙子兵法·三十六计谋略全本》 — Skill Index

> 本书由 book2skill 蒸馏，共产出 **{len(entries)}** 个 skills。
> 处理时间：2026-05-08

## 关于这本书

- **作者**：【春秋】孙武（原著），后世编者整合《三十六计》
- **出版年**：现代整理版（原典成书于春秋末期/明末清初）
- **一句话主旨**：系统阐述在对抗性环境中如何通过信息优势、资源调配和心理博弈取得胜利的决策方法论。
- **整书理解**：见 [BOOK_OVERVIEW.md](./BOOK_OVERVIEW.md)

---

## Skill 列表（按主题分组）

{render_group("决策与评估", decision)}
{render_group("策略与执行", strategy)}
{render_group("组织与管理", management)}

---

## 引用图

{chr(10).join(graph_lines)}

图例：
- `-.->`  相关/组合关系（related skills）

---

## 推荐学习顺序

1. **five-elements-assessment** — 最基础的评估框架，任何重大决策前先用它
2. **know-enemy-know-self** — 信息收集是决策的前提
3. **dialectical-thinking** — 利弊权衡的辩证翻转机制
4. **defense-first** — 先确保自己立于不败之地
5. **initiative-control** — 掌握主动权，不被对手牵着走
6. **avoid-solid-strike-void** — 避实击虚，集中优势突破
7. **indirect-approach** — 以迂为直，绕路反而更快到达
8. **adaptability-framework** — 因敌制胜，灵活应变
9. 其他 skill 根据具体场景按需调用

---

## 接入 darwin-skill

所有 skill 均带有 `test-prompts.json`（darwin-skill 兼容格式），可直接接入自动进化：

```
darwin evolve books/孙子兵法-三十六计/
```

---

## 审计轨迹

- 候选单元池：[candidates/](./candidates/)
- 被淘汰的候选（含原因）：[rejected/](./rejected/)
- BOOK_OVERVIEW：[BOOK_OVERVIEW.md](./BOOK_OVERVIEW.md)
- 验证记录：[verified.md](./verified.md)
- 场景映射：[scenario-mapping.md](./scenario-mapping.md)
"""

(root / "INDEX.md").write_text(index, encoding="utf-8")
rejected = root / "rejected" / "README.md"
rejected.write_text("""# 被淘汰的候选单元

本目录用于存放阶段 1.5 三重验证中未通过的候选方法论单元及淘汰原因。

当前状态：无淘汰记录。

## 说明

在《孙子兵法·三十六计》的拆解过程中，所有提取的候选框架均通过了三重验证（V1 跨域、V2 预测力、V3 独特性），因此本目录为空。

如需查看通过验证的候选列表，请参见：
- [verified.md](../verified.md) — 通过验证的 25 个框架
- [scenario-mapping.md](../scenario-mapping.md) — 真实场景映射
""", encoding="utf-8")
print("INDEX and rejected readme created")
