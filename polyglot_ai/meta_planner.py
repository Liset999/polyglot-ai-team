"""Meta Planner — lightweight, low-token task planning for Polyglot.
Pure functions only. No LLM calls. No external dependencies.
"""

import json
import math
import os
from datetime import datetime


# --- Keyword scoring tables ---

COMPLEXITY_KEYWORDS = {
    # Simple / token keywords (+5 each)
    "hello": 5, "hi": 5, "summary": 5, "explain": 5,
    "utility": 5, "script": 5, "helper": 5, "quick": 5,
    "简单": 5, "工具": 5, "脚本": 5, "解释": 5, "摘要": 5,
    # Medium keywords (+15 each)
    "api": 15, "database": 15, "db": 15, "auth": 15,
    "login": 15, "jwt": 15, "crawler": 15, "scraper": 15,
    "web": 15, "server": 15, "frontend": 15, "backend": 15,
    "pipeline": 15, "workflow": 15, "refactor": 15,
    "重构": 15, "接口": 15, "认证": 15, "登录": 15,
    "中间件": 15, "爬虫": 15,
    # Complex keywords (+30 each)
    "dashboard": 30, "distributed": 30, "concurrency": 30,
    "multi-agent": 30, "plugin": 30, "extension": 30,
    "framework": 30, "cli tool": 30, "microservice": 30,
    "event loop": 30, "async": 30, "orm": 30, "graph": 30,
    "分布式": 30, "框架": 30, "插件": 30, "仪表盘": 30,
    "并发": 30, "高并发": 30,
}

TESTING_KEYWORDS = {
    "test": 20, "tests": 20, "unit test": 25, "pytest": 20,
    "测试": 20, "单元测试": 25, "冒烟测试": 20,
    "integration test": 25, "e2e": 25, "verify": 15,
    "测试覆盖": 25, "assert": 15,
}


def score_complexity_text(goal_text):
    """Count keyword-match score from goal text only.
    Returns (int_score, list_of_hit_keywords).
    """
    text = (goal_text or "").lower()
    score = 0
    hits = []
    for keyword, weight in COMPLEXITY_KEYWORDS.items():
        if keyword in text:
            score += weight
            hits.append(keyword)
    length_bonus = min(20, len(goal_text or "") // 30)
    score += length_bonus
    return score, hits


def score_testing_presence(goal_text):
    """Count how strongly a goal implies testing requirements.
    Returns (int_score, list_of_hit_keywords).
    """
    text = (goal_text or "").lower()
    score = 0
    hits = []
    for keyword, weight in TESTING_KEYWORDS.items():
        if keyword in text:
            score += weight
            hits.append(keyword)
    return score, hits


def complexity_level_from_score(score):
    """Map numeric score to level string.
    0-19 -> simple; 20-59 -> medium; 60+ -> complex
    """
    if score < 20:
        return "simple"
    if score < 60:
        return "medium"
    return "complex"


def assess_complexity(goal, task_count_hint=0, complexity_hint=""):
    """Assess goal complexity. Returns dict with level, score, reasons.
    
    Args:
        goal: natural language goal text
        task_count_hint: number of expected files/tasks (0 if unknown)
        complexity_hint: optional host override like "simple"/"medium"/"complex"
    
    Returns:
        dict with keys: level, score, reasons, testing_score, length_score, task_hint_score
    """
    goal_text = str(goal or "")
    keyword_score, keyword_hits = score_complexity_text(goal_text)
    testing_score, _ = score_testing_presence(goal_text)
    length_score = min(20, len(goal_text) // 30)
    task_hint_score = min(20, (task_count_hint or 0) * 5)
    
    total_score = keyword_score + length_score + task_hint_score
    total_score = max(0, min(100, total_score))
    
    if complexity_hint:
        hint_lower = str(complexity_hint).lower()
        if hint_lower in ("tiny", "small", "simple"):
            level = "simple"
            total_score = min(total_score, 19)
        elif hint_lower == "medium":
            level = "medium"
            total_score = max(20, min(total_score, 59))
        elif hint_lower in ("complex", "hard"):
            level = "complex"
            total_score = max(60, total_score)
        else:
            level = complexity_level_from_score(total_score)
    else:
        level = complexity_level_from_score(total_score)
    
    reasons = []
    if keyword_hits:
        reasons.append("keywords: " + ", ".join(keyword_hits[:3]))
    if testing_score > 0:
        reasons.append("testing implied")
    if length_score >= 10:
        reasons.append("long description")
    if task_hint_score > 0:
        reasons.append(f"{task_count_hint} task(s) expected")
    if not reasons:
        reasons.append("no strong signals; default simple")
    
    return {
        "level": level,
        "score": total_score,
        "reasons": reasons,
        "testing_score": testing_score,
        "length_score": length_score,
        "task_hint_score": task_hint_score,
    }


def _default_roles_for_level(level):
    base = ["meta_planner", "runtime_orchestrator", "coder", "test_runner"]
    if level == "medium":
        base.append("reviewer")
    elif level == "complex":
        base.extend(["reviewer", "architect", "quality_assurance"])
    return base


def generate_task_graph(goal, complexity_level, file_hints=None):
    """Generate a structured task_graph from goal and complexity level.
    
    Args:
        goal: natural language goal text
        complexity_level: "simple" | "medium" | "complex"
        file_hints: optional list of target filenames
    
    Returns:
        list[TaskNode], each a dict with: id, phase, description,
        depends_on, status, max_attempts, model_preference
    """
    files = list(file_hints or [])
    level = (complexity_level or "simple").lower()
    nodes = []
    
    if level == "simple":
        nodes.append({
            "id": "fill_main",
            "phase": "fill",
            "description": f"Implement: {goal}",
            "depends_on": [],
            "status": "pending",
            "max_attempts": 3,
            "model_preference": "cheap",
        })
        nodes.append({
            "id": "verify_main",
            "phase": "verify",
            "description": "Run tests and verify the implementation",
            "depends_on": ["fill_main"],
            "status": "pending",
            "max_attempts": 3,
            "model_preference": "cheap",
        })
    
    elif level == "medium":
        nodes.append({
            "id": "plan_scaffold",
            "phase": "plan",
            "description": "Analyze goal and prepare file-level task scaffold",
            "depends_on": [],
            "status": "pending",
            "max_attempts": 1,
            "model_preference": "cheap",
        })
        prev = "plan_scaffold"
        fill_count = max(1, len(files) if files else 2)
        for idx in range(fill_count):
            fid = f"fill_{idx+1}"
            fdesc = files[idx] if idx < len(files) else f"implementation file {idx+1}"
            nodes.append({
                "id": fid,
                "phase": "fill",
                "description": f"Write {fdesc}",
                "depends_on": [prev],
                "status": "pending",
                "max_attempts": 3,
                "model_preference": "cheap",
            })
            prev = fid
        nodes.append({
            "id": "verify_all",
            "phase": "verify",
            "description": "Run tests and verify all implementations",
            "depends_on": [prev],
            "status": "pending",
            "max_attempts": 3,
            "model_preference": "cheap",
        })
        nodes.append({
            "id": "report_summary",
            "phase": "report",
            "description": "Generate completion report and handoff",
            "depends_on": ["verify_all"],
            "status": "pending",
            "max_attempts": 1,
            "model_preference": "cheap",
        })
    
    else:  # complex
        nodes.append({
            "id": "architect_review",
            "phase": "plan",
            "description": "Review architecture: file layout, dependency graph, acceptance criteria",
            "depends_on": [],
            "status": "pending",
            "max_attempts": 2,
            "model_preference": "pro",
        })
        nodes.append({
            "id": "plan_scaffold",
            "phase": "plan",
            "description": "Prepare detailed task packet scaffold per file",
            "depends_on": ["architect_review"],
            "status": "pending",
            "max_attempts": 2,
            "model_preference": "cheap",
        })
        prev = "plan_scaffold"
        fill_count = max(3, len(files) if files else 3)
        for idx in range(fill_count):
            fid = f"fill_{idx+1}"
            fdesc = files[idx] if idx < len(files) else f"implementation file {idx+1}"
            nodes.append({
                "id": fid,
                "phase": "fill",
                "description": f"Write {fdesc}",
                "depends_on": [prev],
                "status": "pending",
                "max_attempts": 3,
                "model_preference": "pro" if idx == 0 else "cheap",
            })
            prev = fid
        nodes.append({
            "id": "verify_all",
            "phase": "verify",
            "description": "Run integration tests + unit tests",
            "depends_on": [prev],
            "status": "pending",
            "max_attempts": 3,
            "model_preference": "cheap",
        })
        nodes.append({
            "id": "quality_gate",
            "phase": "report",
            "description": "Manual/automated quality review checkpoint",
            "depends_on": ["verify_all"],
            "status": "pending",
            "max_attempts": 1,
            "model_preference": "pro",
        })
        nodes.append({
            "id": "report_summary",
            "phase": "report",
            "description": "Generate completion report with artifact references",
            "depends_on": ["quality_gate"],
            "status": "pending",
            "max_attempts": 1,
            "model_preference": "cheap",
        })
    
    return nodes


# --- Skill recommendation ---

SKILL_KEYWORDS = {
    "date_diff_pitfalls.md": [
        "date", "datetime", "day", "month", "year",
        "时间", "日期", "天", "diff", "interval", "deadline",
    ],
    "cli_no_edit_recovery.md": [
        "cli", "command-line", "terminal", "shell",
        "命令行", "终端", "claude", "no edit", "tool call",
    ],
    "traceback_to_fix_prompt.md": [
        "traceback", "error", "exception", "assert",
        "失败", "报错", "异常", "修复", "bug", "fix",
        "stacktrace", "debug",
    ],
}


def recommend_skills(goal, skills_dir=None, skill_index=None):
    """Recommend skill files based on goal keyword matching.
    
    Args:
        goal: natural language goal text
        skills_dir: optional path to skills directory
        skill_index: optional dict {skill_name: {total_uses, success_rate, ...}}
            When provided, recommendations are reordered by success-weighted
            history: score = hit_count + (success_rate or 0.5) * log2(total_uses + 1)
    
    Returns:
        list[str] of skill file names, ordered by relevance
    """
    text = str(goal or "").lower()
    matches = []  # list of (skill_name, hit_count, history_score)
    
    for skill_file, triggers in SKILL_KEYWORDS.items():
        hit_count = sum(1 for t in triggers if t.lower() in text)
        if hit_count > 0:
            # Compute history score
            if skill_index and isinstance(skill_index, dict):
                idx = skill_index.get(skill_file) or {}
                sr = idx.get("success_rate")
                uses = idx.get("total_uses", 0)
                if sr is None:
                    history = 0.5
                else:
                    history = float(sr) * math.log(int(uses) + 1, 2)
            else:
                history = 0.0
            matches.append((skill_file, hit_count, history))
    
    # Sort by (hit_count + history) descending
    matches.sort(key=lambda x: x[1] + x[2], reverse=True)
    
    return [skill for skill, _, _ in matches]


def build_team_plan(goal, skills_dir=None, existing_files=None,
                    complexity_hint="", skill_index=None):
    """Build a full Team Plan 2.0 dict from a natural-language goal.
    No LLM calls. Pure function.
    
    Returns dict ready for runtime.save_team_plan().
    """
    goal_text = str(goal or "").strip()
    files = list(existing_files or [])
    
    assessment = assess_complexity(
        goal_text,
        task_count_hint=len(files),
        complexity_hint=complexity_hint,
    )
    level = assessment["level"]
    task_graph = generate_task_graph(goal_text, level, files)
    skills = recommend_skills(goal_text, skills_dir, skill_index)
    roles = _default_roles_for_level(level)
    
    # Approval points: complex plan pro-model tasks
    approval_points = [
        n["id"] for n in task_graph
        if n.get("model_preference") == "pro" and level == "complex"
    ]
    
    return {
        "goal": goal_text,
        "task_name": goal_text[:48] if goal_text else "untitled",
        "complexity_level": level,
        "estimated_complexity_score": assessment["score"],
        "estimated_score": assessment["score"],
        "roles_needed": roles,
        "execution_mode": "single-agent" if level == "simple" else "single-agent-with-self-heal",
        "selected_agent": "",
        "task_graph": task_graph,
        "budget": {
            "max_total_attempts": 3,
            "preferred_cost_tier": "cheap" if level != "complex" else "pro",
            "fallback_cost_tier": "cheap",
        },
        "approval_points": approval_points,
        "recommended_skills": skills,
        "next_action": (
            "delegate task packets to worker" if task_graph
            else "await goal details from host"
        ),
        "complexity_reasons": assessment["reasons"],
        "team_plan_version": "2.0",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


if __name__ == "__main__":
    import sys
    goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "write a date utility"
    plan = build_team_plan(goal)
    print(json.dumps(plan, indent=2, ensure_ascii=False))
