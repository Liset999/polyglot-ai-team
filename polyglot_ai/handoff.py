"""Structured Handoff — build continuation packs for paused/interrupted sessions.
Pure functions only. No LLM calls.
"""

import json
import os
from datetime import datetime


def build_handoff_pack(runtime, session_id):
    """Build a structured handoff pack for a session.

    Reads run_state, team_plan, timeline, task_packets from the Runtime.
    Returns a dict suitable for serializing to JSON and exposing via MCP.

    Return schema:
    {
        "session_state": {"status", "goal", "complexity_level", "attempt",
                           "backend", "last_error_summary"},
        "completed_tasks": [TaskNode, ...],
        "remaining_tasks": [TaskNode, ...],
        "key_context_refs": [{"type", "ref", "summary"}, ...],
        "next_action": str,
        "budget_remaining": {"attempts_left", "max_total_attempts",
                              "preferred_model_tier", "budget_exceeded"},
        "metadata": {"generated_at", "session", "version"},
    }
    """
    try:
        state = runtime.read_run_state() or {}
        if not isinstance(state, dict):
            state = {}
    except Exception:
        state = {}

    try:
        plan = runtime.read_team_plan() or {}
        if not isinstance(plan, dict):
            plan = {}
    except Exception:
        plan = {}

    task_graph = plan.get("task_graph") or []
    if not isinstance(task_graph, list):
        task_graph = []

    completed = []
    remaining = []
    for node in task_graph:
        if not isinstance(node, dict):
            continue
        status = str(node.get("status", "pending")).lower()
        if status in ("done", "completed", "success"):
            completed.append(node)
        else:
            remaining.append(node)

    refs = []
    try:
        timeline = runtime.read_timeline(limit=3) or []
        for t in timeline:
            if isinstance(t, dict):
                refs.append({
                    "type": "timeline_event",
                    "ref": str(t.get("ts", "")),
                    "summary": str(t.get("action") or t.get("observation") or "")[:160],
                })
    except Exception:
        pass

    try:
        packets = runtime.read_task_packets(limit=2) or []
        for p in packets:
            if isinstance(p, dict):
                refs.append({
                    "type": "task_packet",
                    "ref": str(p.get("phase") or p.get("packet_id", "")),
                    "summary": str(p.get("prompt_preview") or p.get("target_file") or "")[:160],
                })
    except Exception:
        pass

    try:
        budget = plan.get("budget") or {}
        max_attempts = int(budget.get("max_total_attempts") or 3)
        preferred_tier = str(budget.get("preferred_cost_tier") or "cheap")
        attempts_used = int(state.get("attempt") or 0)
    except (TypeError, ValueError):
        max_attempts = 3
        preferred_tier = "cheap"
        attempts_used = 0

    budget_exceeded = bool(state.get("budget_exceeded", False)) or attempts_used > max_attempts

    return {
        "session_state": {
            "status": str(state.get("status", "idle")),
            "goal": str(state.get("goal") or plan.get("goal") or ""),
            "complexity_level": str(plan.get("complexity_level") or "simple"),
            "attempt": attempts_used,
            "backend": str(state.get("backend") or ""),
            "last_error_summary": str(state.get("last_error_summary") or ""),
        },
        "completed_tasks": completed,
        "remaining_tasks": remaining,
        "key_context_refs": refs,
        "next_action": str(
            plan.get("next_action") or state.get("next_action") or
            (remaining[0].get("description") if remaining else "no further action needed")
        ),
        "budget_remaining": {
            "attempts_left": max(0, max_attempts - attempts_used),
            "max_total_attempts": max_attempts,
            "preferred_model_tier": preferred_tier,
            "budget_exceeded": budget_exceeded,
        },
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "session": str(session_id),
            "version": "2.0",
        },
    }


def build_handoff_markdown(pack):
    """Render a handoff pack to human-readable markdown.

    Args: pack: dict from build_handoff_pack()
    Returns: markdown string
    """
    if not isinstance(pack, dict):
        return "# Session Handoff\n\nNo state available."

    state = pack.get("session_state") or {}
    remaining = pack.get("remaining_tasks") or []
    refs = pack.get("key_context_refs") or []
    budget = pack.get("budget_remaining") or {}

    lines = []
    lines.append("# Session Handoff")
    lines.append("")
    lines.append(f"**Goal:** {state.get('goal', 'unknown')}")
    lines.append(f"**Status:** {state.get('status', 'idle')}")
    lines.append(f"**Complexity:** {state.get('complexity_level', 'simple')}")
    lines.append(f"**Attempts used:** {state.get('attempt', 0)} "
                 f"(budget: {budget.get('max_total_attempts', 3)})")
    if state.get("last_error_summary"):
        lines.append(f"**Last error:** {state.get('last_error_summary')}")
    lines.append("")

    lines.append("## Next Action")
    lines.append("")
    lines.append(f"{pack.get('next_action', 'continue from here')}")
    lines.append("")

    if remaining:
        lines.append("## Remaining Tasks")
        lines.append("")
        for t in remaining:
            phase = t.get("phase", "task")
            desc = t.get("description", "(no description)")
            max_attempts = t.get("max_attempts", "?")
            lines.append(f"- **[{phase}]** {desc} (attempts left: {max_attempts})")
        lines.append("")

    if refs:
        lines.append("## Context References")
        lines.append("")
        for r in refs:
            rtype = r.get("type", "ref")
            summary = r.get("summary", "")
            lines.append(f"- **{rtype}:** {summary}")
        lines.append("")

    if budget.get("budget_exceeded"):
        lines.append("## ⚠ Budget Exceeded")
        lines.append("")
        lines.append("Attempt count exceeds configured budget. Consider reducing")
        lines.append("task complexity or switching to a cheaper model for remaining work.")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated {pack.get('metadata', {}).get('generated_at', '')}*")
    lines.append("")
    return "\n".join(lines)
