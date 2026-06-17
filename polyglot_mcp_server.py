import json
import os
import sys
from typing import Optional

from polyglot_ai.main_agent import MainAgent
from polyglot_ai.model_profiles import read_model_config
from polyglot_ai.model_registry import read_registry, refresh_registry_if_needed, sync_superclue_registry
from polyglot_ai.meta_planner import build_team_plan
from polyglot_ai.runtime import Runtime
from polyglot_ai.task_board import build_task_board


SERVER_NAME = "polyglot-mcp"
SERVER_VERSION = "0.1.0"
JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2025-06-18"


def server_workspace():
    return os.path.abspath(os.environ.get("POLYGLOT_WORKSPACE") or os.getcwd())


def server_runtime(session_id="default"):
    return Runtime(server_workspace(), session_id)


def server_agent(runtime):
    return MainAgent(server_workspace(), runtime)


def session_exists(session_id):
    """Check if a session directory exists."""
    runtime = server_runtime(session_id)
    return os.path.isdir(runtime.session_dir)


def ok_result(result):
    return {"ok": True, **(result or {})}


def err_result(message, code=-32000, data=None):
    payload = {"code": code, "message": message}
    if data is not None:
        payload["data"] = data
    return payload


def session_status_payload(runtime, session_id):
    state = runtime.read_run_state() or {}
    team_plan = runtime.read_team_plan() or {}
    steer = runtime.read_steer() or {}
    control = runtime.read_control() or {}
    approval = runtime.read_approval() or {}
    run_lock = runtime.read_run_lock() or {}
    
    timeline = runtime.read_timeline(limit=5)
    recent_events = [
        {"actor": t.get("actor", ""), "action": t.get("action", ""), "ts": t.get("ts", ""), "status": t.get("status", "")}
        for t in timeline
    ]
    
    packets = runtime.read_task_packets(limit=3)
    recent_packets = [
        {"phase": p.get("phase", ""), "target_file": p.get("target_file", ""), "ts": p.get("ts", ""), "summary": p.get("summary", "")}
        for p in packets
    ]
    
    messages = runtime.read_messages(limit=3)
    recent_messages = [
        {"role": m.get("role", ""), "ts": m.get("ts", ""), "channel": m.get("channel", "")}
        for m in messages
    ]
    
    next_action = team_plan.get("next_action") or state.get("next_action") or ""

    # Budget state
    try:
        budget_state = runtime.read_budget_state()
    except Exception:
        budget_state = {
            "attempts_used": 0,
            "max_total_attempts": 3,
            "budget_exceeded": False,
            "downgrade_events": [],
            "model_tier": "cheap",
        }

    is_default_session = session_id == "default"
    lock_is_stale = runtime.run_lock_is_stale(run_lock)
    
    return {
        "session": session_id,
        "status": state.get("status", "idle"),
        "attempt": state.get("attempt", 0),
        "backend": state.get("backend", ""),
        "failure_type": state.get("failure_type", "none"),
        "last_error_summary": state.get("last_error_summary", ""),
        "goal": state.get("goal") or team_plan.get("goal") or "",
        "next_action": next_action,
        "selected_agent": team_plan.get("selected_agent", ""),
        "complexity_level": team_plan.get("complexity_level", ""),
        "budget_state": budget_state,
        "steer": steer,
        "control": control,
        "approval": approval,
        "run_lock": run_lock,
        "lock_is_stale": lock_is_stale,
        "is_default_session": is_default_session,
        "team_plan_uri": f"polyglot://session/{session_id}/task-board",
        "session_info": {
            "workspace": runtime.workspace_dir,
            "session_dir": runtime.session_dir,
        },
        "timeline_summary": {
            "count": len(timeline),
            "recent": recent_events,
        },
        "packets_summary": {
            "count": len(packets),
            "recent": recent_packets,
        },
        "messages_summary": {
            "count": len(messages),
            "recent": recent_messages,
        },
        "metadata": {
            "runtime_version": SERVER_VERSION,
            "timestamp": runtime.now(),
        },
    }


def tool_start_goal(arguments):
    goal = str((arguments or {}).get("goal") or "").strip()
    if not goal:
        raise ValueError("goal is required")
    workspace = os.path.abspath((arguments or {}).get("workspace") or server_workspace())
    session_id = str((arguments or {}).get("session") or "default").strip() or "default"
    env = {}
    model_profile = str((arguments or {}).get("model_profile") or "").strip()
    if model_profile:
        env["POLYGLOT_MODEL_PROFILE"] = model_profile
    mode = str((arguments or {}).get("mode") or "").strip()
    if mode:
        env["POLYGLOT_MODE"] = mode
    worker = str((arguments or {}).get("worker") or "").strip().lower()
    if worker:
        env["POLYGLOT_AGENT"] = worker
        if worker == "mock":
            env["FORCE_MOCK"] = "1"
    if bool((arguments or {}).get("force_run")):
        env["POLYGLOT_FORCE_RUN"] = "1"
    runtime = Runtime(workspace, session_id)
    agent = MainAgent(workspace, runtime)
    decision = agent.route_decision(goal, env)
    if decision.get("worker_runnable") is False:
        return ok_result({
            "session": session_id,
            "status": "blocked",
            "reason": "worker_not_runnable",
            "detail": decision.get("worker_preflight", ""),
        })
    if decision.get("model_profile_runnable") is False:
        return ok_result({
            "session": session_id,
            "status": "blocked",
            "reason": "model_not_runnable",
            "detail": decision.get("model_profile_preflight", ""),
        })
    if bool((arguments or {}).get("force_run")):
        exit_code, text = agent.run_goal(goal, env, require_approval=True)
        state = runtime.read_run_state() or {}
        return ok_result({
            "session": session_id,
            "status": state.get("status", "idle"),
            "goal": goal,
            "exit_code": exit_code,
            "approval_required": exit_code == 2,
            "report_preview": text[:400],
            "task_board_uri": f"polyglot://session/{session_id}/task-board",
            "run_state_uri": f"polyglot://session/{session_id}/run-state",
            "report_uri": f"polyglot://session/{session_id}/report",
        })
    plan, _text = agent.plan_goal(goal, env)
    return ok_result({
        "session": session_id,
        "status": "planning",
        "goal": goal,
        "next_action": plan.get("next_action", ""),
        "task_board_uri": f"polyglot://session/{session_id}/task-board",
    })


def tool_status(arguments):
    session_id = str((arguments or {}).get("session") or "default").strip() or "default"
    runtime = server_runtime(session_id)
    return ok_result(session_status_payload(runtime, session_id))


def tool_get_task_board(arguments):
    session_id = str((arguments or {}).get("session") or "default").strip() or "default"
    runtime = server_runtime(session_id)
    board = build_task_board(runtime)
    return ok_result(board)


def tool_steer(arguments):
    session_id = str((arguments or {}).get("session") or "default").strip() or "default"
    message = str((arguments or {}).get("message") or "").strip()
    if not message:
        raise ValueError("message is required")
    runtime = server_runtime(session_id)
    runtime.send_steer(message)
    return ok_result({"session": session_id, "accepted": True, "applies_at": "next_worker_checkpoint"})


def tool_pause(arguments):
    session_id = str((arguments or {}).get("session") or "default").strip() or "default"
    reason = str((arguments or {}).get("reason") or "").strip()
    runtime = server_runtime(session_id)
    runtime.set_control("pause", reason)
    return ok_result({"session": session_id, "status": "pause_requested"})


def tool_resume(arguments):
    session_id = str((arguments or {}).get("session") or "default").strip() or "default"
    message = str((arguments or {}).get("message") or "").strip()
    runtime = server_runtime(session_id)
    runtime.set_control("resume", message)
    return ok_result({"session": session_id, "status": "resuming"})


def tool_stop(arguments):
    session_id = str((arguments or {}).get("session") or "default").strip() or "default"
    reason = str((arguments or {}).get("reason") or "").strip()
    runtime = server_runtime(session_id)
    runtime.set_control("stop", reason)
    return ok_result({"session": session_id, "status": "stop_requested"})


def tool_get_report(arguments):
    session_id = str((arguments or {}).get("session") or "default").strip() or "default"
    if not session_exists(session_id):
        return ok_result({"session": session_id, "available": False, "reason": "no_such_session", "report_markdown": ""})
    runtime = server_runtime(session_id)
    agent = server_agent(runtime)
    report = agent.read_final_report()
    available = "No final_report.md found" not in report and len(report.strip()) > 0
    return ok_result({
        "session": session_id,
        "available": available,
        "reason": "" if available else "no_report_yet",
        "report_markdown": report if available else "",
    })


def tool_get_handoff(arguments):
    session_id = str((arguments or {}).get("session") or "default").strip() or "default"
    if not session_exists(session_id):
        return ok_result({
            "session": session_id,
            "available": False,
            "reason": "no_such_session",
            "handoff_markdown": "",
            "handoff_json": {},
        })
    runtime = server_runtime(session_id)

    # Legacy: if a handoff.md file was written previously, use it.
    handoff_path = os.path.join(runtime.session_dir, "handoff.md")
    has_legacy = os.path.isfile(handoff_path) and os.path.getsize(handoff_path) > 0

    # Try building a structured pack from runtime state
    try:
        from polyglot_ai.handoff import build_handoff_pack, build_handoff_markdown
        pack = build_handoff_pack(runtime, session_id)
        markdown = build_handoff_markdown(pack)
    except Exception as exc:
        if has_legacy:
            try:
                with open(handoff_path, "r", encoding="utf-8") as f:
                    markdown = f.read()
            except OSError:
                markdown = ""
        else:
            markdown = ""
        pack = {"session_state": {"status": "idle", "error": str(exc)},
                "remaining_tasks": [], "key_context_refs": [], "next_action": "retry",
                "budget_remaining": {}, "metadata": {"version": "legacy-fallback"}}

    # Determine availability: legacy file OR meaningful runtime state
    state = runtime.read_run_state() or {}
    plan = runtime.read_team_plan() or {}
    has_state = isinstance(state, dict) and bool(state)
    has_plan = isinstance(plan, dict) and bool(plan.get("goal")) and bool(plan.get("task_graph"))

    if not has_legacy and not has_state and not has_plan:
        return ok_result({
            "session": session_id,
            "available": False,
            "reason": "no_handoff_yet",
            "handoff_markdown": "",
            "handoff_json": {},
        })

    # Persist the handoff pack to disk
    try:
        pack_path = os.path.join(runtime.session_dir, "handoff.json")
        os.makedirs(os.path.dirname(os.path.abspath(pack_path)), exist_ok=True)
        with open(pack_path, "w", encoding="utf-8") as f:
            json.dump(pack, f, indent=2, ensure_ascii=False)
    except OSError:
        pass

    return ok_result({
        "session": session_id,
        "available": True,
        "reason": "",
        "handoff_markdown": markdown,
        "handoff_json": pack,
        "handoff_version": pack.get("metadata", {}).get("version", "2.0"),
    })


def tool_list_models(arguments):
    _ = arguments
    config = read_model_config(os.environ, server_workspace())
    profiles = []
    for profile in config.get("profiles", []):
        if not isinstance(profile, dict):
            continue
        profiles.append({
            "id": profile.get("id", ""),
            "name": profile.get("name", ""),
            "provider": profile.get("provider", ""),
            "model": profile.get("model") or profile.get("model_name", ""),
            "base_url": profile.get("base_url", ""),
            "capabilities": profile.get("capabilities", []),
            "enabled": bool(profile.get("enabled", True)),
            "cost_tier": profile.get("cost_tier", ""),
        })
    return ok_result({
        "default_model": config.get("default", config.get("default_model", "")),
        "profiles": profiles,
    })


def tool_refresh_model_registry(arguments):
    arguments = arguments or {}
    workspace = os.path.abspath(arguments.get("workspace") or server_workspace())
    force_refresh = bool(arguments.get("force_refresh", True))
    timeout_sec = int(arguments.get("timeout_sec") or 20)
    if force_refresh:
        registry = sync_superclue_registry(os.environ, workspace, timeout_sec=timeout_sec)
    else:
        registry = refresh_registry_if_needed(os.environ, workspace, timeout_sec=timeout_sec)
    return ok_result({
        "workspace": workspace,
        "refreshed": bool(registry.get("refreshed")),
        "reason": registry.get("reason", ""),
        "warning": registry.get("warning", ""),
        "source": registry.get("source", ""),
        "source_url": registry.get("source_url", ""),
        "benchmark_date": registry.get("benchmark_date", ""),
        "models": len(registry.get("models", [])),
        "path": registry.get("path", ""),
    })


def tool_smoke(arguments):
    workspace = os.path.abspath((arguments or {}).get("workspace") or server_workspace())
    session_id = str((arguments or {}).get("session") or "smoke-test").strip() or "smoke-test"
    
    checks = []
    all_passed = True
    
    runtime = Runtime(workspace, session_id)
    os.makedirs(runtime.session_dir, exist_ok=True)
    run_state = runtime.read_run_state()
    checks.append({"check": "session_state_readable", "ok": True})
    
    try:
        agent = MainAgent(workspace, runtime)
        checks.append({"check": "main_agent_initialized", "ok": True})
    except Exception as e:
        checks.append({"check": "main_agent_initialized", "ok": False, "error": str(e)})
        all_passed = False
    
    try:
        board = build_task_board(runtime)
        checks.append({"check": "task_board_buildable", "ok": True})
    except Exception as e:
        checks.append({"check": "task_board_buildable", "ok": False, "error": str(e)})
        all_passed = False
    
    try:
        models = read_model_config(os.environ, workspace)
        checks.append({"check": "model_config_readable", "ok": True, "profiles": len(models.get("profiles", []))})
    except Exception as e:
        checks.append({"check": "model_config_readable", "ok": False, "error": str(e)})
        all_passed = False
    
    try:
        from polyglot_ai.local_smoke import run_local_smoke
        checks.append({"check": "smoke_validator_available", "ok": True})
    except Exception as e:
        checks.append({"check": "smoke_validator_available", "ok": False, "error": str(e)})
        all_passed = False
    
    return ok_result({
        "ok": all_passed,
        "session": session_id,
        "workspace": workspace,
        "checks": checks,
        "summary": f"{sum(1 for c in checks if c.get('ok'))}/{len(checks)} checks passed",
        "server_version": SERVER_VERSION,
    })


def tool_preview_plan(arguments):
    """Preview the team plan for a goal without starting work or writing files.
    Read-only. No side effects.
    """
    goal = str((arguments or {}).get("goal") or "").strip()
    if not goal:
        raise ValueError("goal is required")
    session_id = str((arguments or {}).get("session") or "default").strip() or "default"
    complexity_hint = str((arguments or {}).get("complexity_hint") or "").strip()
    
    plan = build_team_plan(goal, skills_dir=None, existing_files=None,
                           complexity_hint=complexity_hint)
    
    phase_counts = {}
    for node in plan.get("task_graph", []):
        p = node.get("phase", "unknown")
        phase_counts[p] = phase_counts.get(p, 0) + 1
    
    return {
        "session": session_id,
        "goal": goal,
        "complexity_level": plan["complexity_level"],
        "estimated_complexity_score": plan["estimated_complexity_score"],
        "reasons": plan.get("complexity_reasons", []),
        "roles_needed": plan["roles_needed"],
        "task_graph": plan["task_graph"],
        "task_count": len(plan["task_graph"]),
        "phase_distribution": phase_counts,
        "budget": plan["budget"],
        "approval_points": plan["approval_points"],
        "recommended_skills": plan["recommended_skills"],
        "next_action": plan["next_action"],
        "execution_mode": plan["execution_mode"],
        "preview_only": True,
        "team_plan_version": plan["team_plan_version"],
    }


TOOLS = {
    "polyglot_start_goal": tool_start_goal,
    "polyglot_status": tool_status,
    "polyglot_get_task_board": tool_get_task_board,
    "polyglot_steer": tool_steer,
    "polyglot_pause": tool_pause,
    "polyglot_resume": tool_resume,
    "polyglot_stop": tool_stop,
    "polyglot_get_report": tool_get_report,
    "polyglot_get_handoff": tool_get_handoff,
    "polyglot_list_models": tool_list_models,
    "polyglot_refresh_model_registry": tool_refresh_model_registry,
    "polyglot_smoke": tool_smoke,
    "polyglot_preview_plan": tool_preview_plan,
}


TOOL_SCHEMAS = {
    "polyglot_start_goal": {
        "description": "Start a Polyglot runtime workflow for a coding goal.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Natural-language goal to delegate."},
                "workspace": {"type": "string", "description": "Optional workspace path."},
                "session": {"type": "string", "description": "Optional session id."},
                "model_profile": {"type": "string", "description": "Optional worker model profile override."},
                "mode": {"type": "string", "description": "Optional runtime mode hint from the host."},
                "worker": {"type": "string", "description": "Optional worker override such as claude or mock."},
                "force_run": {"type": "boolean", "description": "Force execution instead of preview-only planning."},
            },
            "required": ["goal"],
        },
    },
    "polyglot_status": {
        "description": "Read the current run state for a session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "Target session id."},
            },
        },
    },
    "polyglot_get_task_board": {
        "description": "Return the structured task board for a session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "Target session id."},
            },
        },
    },
    "polyglot_steer": {
        "description": "Send a steering message into the active session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "Target session id."},
                "message": {"type": "string", "description": "Steering instruction."},
            },
            "required": ["message"],
        },
    },
    "polyglot_pause": {
        "description": "Request pause at the next safe worker checkpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "Target session id."},
                "reason": {"type": "string", "description": "Optional pause reason."},
            },
        },
    },
    "polyglot_resume": {
        "description": "Resume a paused session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "Target session id."},
                "message": {"type": "string", "description": "Optional resume note."},
            },
        },
    },
    "polyglot_stop": {
        "description": "Request stop at the next safe worker checkpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "Target session id."},
                "reason": {"type": "string", "description": "Optional stop reason."},
            },
        },
    },
    "polyglot_get_report": {
        "description": "Return the saved worker report for a session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "Target session id."},
            },
        },
    },
    "polyglot_get_handoff": {
        "description": "Return the latest session handoff pack.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session": {"type": "string", "description": "Target session id."},
            },
        },
    },
    "polyglot_list_models": {
        "description": "List worker model profiles and the current default.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    "polyglot_refresh_model_registry": {
        "description": "Refresh the local model price registry snapshot from SuperCLUE.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Optional workspace path."},
                "force_refresh": {"type": "boolean", "description": "Force a fresh fetch instead of reusing a fresh snapshot."},
                "timeout_sec": {"type": "integer", "description": "Optional network timeout in seconds."},
            },
        },
    },
    "polyglot_smoke": {
        "description": "Lightweight end-to-end verification of the Polyglot MCP surface. Use this to verify the MCP server is reachable and functional before starting real work.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Optional workspace path."},
                "session": {"type": "string", "description": "Optional session id for smoke test."},
            },
        },
    },
    "polyglot_preview_plan": {
        "description": "Preview the team plan for a goal without starting work or writing files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Natural-language goal to plan."},
                "session": {"type": "string", "description": "Optional session id."},
                "complexity_hint": {"type": "string", "description": "Optional complexity hint: simple/medium/complex."},
            },
            "required": ["goal"],
        },
    },
}


def resource_task_board(uri):
    session_id = uri.split("/session/", 1)[1].split("/", 1)[0]
    runtime = server_runtime(session_id)
    return build_task_board(runtime)


def resource_run_state(uri):
    session_id = uri.split("/session/", 1)[1].split("/", 1)[0]
    return server_runtime(session_id).read_run_state() or {}


def resource_status(uri):
    session_id = uri.split("/session/", 1)[1].split("/", 1)[0]
    runtime = server_runtime(session_id)
    return session_status_payload(runtime, session_id)


def resource_timeline(uri):
    session_id = uri.split("/session/", 1)[1].split("/", 1)[0]
    return server_runtime(session_id).read_timeline(limit=64)


def resource_latest_packet(uri):
    session_id = uri.split("/session/", 1)[1].split("/", 1)[0]
    packets = server_runtime(session_id).read_task_packets(limit=1)
    return packets[-1] if packets else {}


def resource_report(uri):
    session_id = uri.split("/session/", 1)[1].split("/", 1)[0]
    runtime = server_runtime(session_id)
    report = server_agent(runtime).read_final_report()
    available = "No final_report.md found" not in report and len(report.strip()) > 0
    return {"report_markdown": report if available else "", "available": available, "reason": "" if available else "no_report_yet"}


def resource_handoff(uri):
    session_id = uri.split("/session/", 1)[1].split("/", 1)[0]
    runtime = server_runtime(session_id)
    handoff_path = os.path.join(runtime.session_dir, "handoff.md")
    has_handoff = os.path.isfile(handoff_path) and os.path.getsize(handoff_path) > 0
    if not has_handoff:
        return {"handoff_markdown": "", "handoff_json": {}, "available": False, "reason": "no_handoff_yet"}
    agent = server_agent(runtime)
    data, markdown, _paths = agent.build_handoff()
    return {"handoff_markdown": markdown, "handoff_json": data, "available": True, "reason": ""}


def resource_models(_uri):
    return tool_list_models({})


def resource_model_registry(_uri):
    registry = read_registry(os.environ, server_workspace())
    return {
        "source": registry.get("source", ""),
        "source_url": registry.get("source_url", ""),
        "homepage": registry.get("homepage", ""),
        "updated_at": registry.get("updated_at", ""),
        "benchmark_date": registry.get("benchmark_date", ""),
        "unit": registry.get("unit", ""),
        "warning": registry.get("warning", ""),
        "models": registry.get("models", []),
    }


def resource_workspace_summary(_uri):
    runtime = server_runtime("default")
    return {"workspace_summary": runtime.workspace_summary_text()}


RESOURCES = {
    "polyglot://models": resource_models,
    "polyglot://model-registry": resource_model_registry,
    "polyglot://workspace-summary": resource_workspace_summary,
}


PROMPTS = {
    "teamwork-preview": {
        "name": "teamwork-preview",
        "title": "Teamwork Preview",
        "description": "Preview how Polyglot would route and execute a coding goal.",
        "arguments": [{"name": "goal", "required": False}],
    },
    "debug-runtime": {
        "name": "debug-runtime",
        "title": "Debug Runtime",
        "description": "Inspect current runtime state, timeline, and control surface.",
        "arguments": [{"name": "session", "required": False}],
    },
    "review-task-board": {
        "name": "review-task-board",
        "title": "Review Task Board",
        "description": "Read the structured task board before deciding what to do next.",
        "arguments": [{"name": "session", "required": False}],
    },
    "continue-from-handoff": {
        "name": "continue-from-handoff",
        "title": "Continue From Handoff",
        "description": "Resume work from the latest Polyglot handoff pack.",
        "arguments": [{"name": "session", "required": False}],
    },
}


def read_resource(uri):
    if uri in RESOURCES:
        return RESOURCES[uri](uri)
    if uri.endswith("/task-board") and "/session/" in uri:
        return resource_task_board(uri)
    if uri.endswith("/run-state") and "/session/" in uri:
        return resource_run_state(uri)
    if uri.endswith("/status") and "/session/" in uri:
        return resource_status(uri)
    if uri.endswith("/timeline") and "/session/" in uri:
        return resource_timeline(uri)
    if uri.endswith("/latest-packet") and "/session/" in uri:
        return resource_latest_packet(uri)
    if uri.endswith("/report") and "/session/" in uri:
        return resource_report(uri)
    if uri.endswith("/handoff") and "/session/" in uri:
        return resource_handoff(uri)
    raise ValueError(f"unknown resource: {uri}")


def tool_descriptors():
    return [
        {
            "name": name,
            "title": name.replace("polyglot_", "").replace("_", " ").title(),
            "description": TOOL_SCHEMAS.get(name, {}).get("description", name.replace("polyglot_", "").replace("_", " ")),
            "inputSchema": TOOL_SCHEMAS.get(name, {}).get("inputSchema", {"type": "object", "properties": {}}),
        }
        for name in TOOLS
    ]


def resource_descriptors():
    return [
        {"uri": "polyglot://models", "name": "models", "title": "Models", "description": "Worker model profiles and current default."},
        {"uri": "polyglot://model-registry", "name": "model-registry", "title": "Model Registry", "description": "Local SuperCLUE price registry snapshot."},
        {"uri": "polyglot://workspace-summary", "name": "workspace-summary", "title": "Workspace Summary", "description": "Deterministic workspace summary."},
        {"uriTemplate": "polyglot://session/{session}/status", "name": "status", "title": "Status", "description": "Current run/session status for a session."},
        {"uriTemplate": "polyglot://session/{session}/task-board", "name": "task-board", "title": "Task Board", "description": "Structured task board for a session."},
        {"uriTemplate": "polyglot://session/{session}/run-state", "name": "run-state", "title": "Run State", "description": "Current persisted run state for a session."},
        {"uriTemplate": "polyglot://session/{session}/timeline", "name": "timeline", "title": "Timeline", "description": "Recent timeline events for a session."},
        {"uriTemplate": "polyglot://session/{session}/latest-packet", "name": "latest-packet", "title": "Latest Packet", "description": "Most recent task packet for a session."},
        {"uriTemplate": "polyglot://session/{session}/report", "name": "report", "title": "Report", "description": "Saved run report for a session."},
        {"uriTemplate": "polyglot://session/{session}/handoff", "name": "handoff", "title": "Handoff", "description": "Saved session handoff pack for a session."},
    ]


def resource_template_descriptors():
    return [
        {"uriTemplate": "polyglot://session/{session}/task-board", "name": "task-board", "title": "Task Board", "description": "Structured task board for a session."},
        {"uriTemplate": "polyglot://session/{session}/status", "name": "status", "title": "Status", "description": "Current run/session status for a session."},
        {"uriTemplate": "polyglot://session/{session}/run-state", "name": "run-state", "title": "Run State", "description": "Current persisted run state for a session."},
        {"uriTemplate": "polyglot://session/{session}/timeline", "name": "timeline", "title": "Timeline", "description": "Recent timeline events for a session."},
        {"uriTemplate": "polyglot://session/{session}/latest-packet", "name": "latest-packet", "title": "Latest Packet", "description": "Most recent task packet for a session."},
        {"uriTemplate": "polyglot://session/{session}/report", "name": "report", "title": "Report", "description": "Saved run report for a session."},
        {"uriTemplate": "polyglot://session/{session}/handoff", "name": "handoff", "title": "Handoff", "description": "Saved session handoff pack for a session."},
    ]


def prompt_descriptors():
    return list(PROMPTS.values())


def get_prompt(name, arguments=None):
    arguments = arguments or {}
    if name == "teamwork-preview":
        goal = arguments.get("goal", "<goal>")
        return {
            "description": "Preview the execution path for a coding goal before actually starting it.",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": f"Preview how Polyglot would handle this goal: {goal}"},
                }
            ],
        }
    if name == "debug-runtime":
        session = arguments.get("session", "default")
        return {
            "description": "Inspect current runtime status, events, and control surface for a session.",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": f"Inspect the Polyglot runtime for session: {session}"},
                }
            ],
        }
    if name == "review-task-board":
        session = arguments.get("session", "default")
        return {
            "description": "Read the task board before deciding what to do next.",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": f"Review the task board for session: {session}"},
                }
            ],
        }
    if name == "continue-from-handoff":
        session = arguments.get("session", "default")
        runtime = server_runtime(session)
        agent = server_agent(runtime)
        _data, markdown, _paths = agent.build_handoff()
        return {
            "description": "Resume from the latest handoff pack.",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": f"Continue from the latest handoff for session: {session}\n\n{markdown}",
                    },
                }
            ],
        }
    raise ValueError(f"unknown prompt: {name}")


def success_response(request_id, result):
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def error_response(request_id, message, code=-32000, data=None):
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": err_result(message, code=code, data=data)}


def handle_request(request):
    request_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params") or {}
    try:
        if request_id is None and method.startswith("notifications/"):
            return None
        if method == "initialize":
            return success_response(request_id, {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                },
                "instructions": "Polyglot MCP exposes runtime-oriented tools for delegated work, state inspection, steering, and reports. It is not a chat model.",
            })
        if method == "tools/list":
            return success_response(request_id, {"tools": tool_descriptors()})
        if method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments") or {}
            if name not in TOOLS:
                return error_response(request_id, f"unknown tool: {name}", code=-32602)
            return success_response(request_id, TOOLS[name](arguments))
        if method == "resources/list":
            return success_response(request_id, {"resources": resource_descriptors()})
        if method == "resources/templates/list":
            return success_response(request_id, {"resourceTemplates": resource_template_descriptors()})
        if method == "resources/read":
            uri = params.get("uri", "")
            data = read_resource(uri)
            mime_type = "application/json"
            text = json.dumps(data, ensure_ascii=False)
            if uri.endswith("/report"):
                mime_type = "text/markdown"
                text = data.get("report_markdown", "") if isinstance(data, dict) else str(data)
            elif uri == "polyglot://workspace-summary":
                mime_type = "text/plain"
                text = data.get("workspace_summary", "") if isinstance(data, dict) else str(data)
            return success_response(request_id, {"contents": [{"uri": uri, "mimeType": mime_type, "text": text}]})
        if method == "prompts/list":
            return success_response(request_id, {"prompts": prompt_descriptors()})
        if method == "prompts/get":
            name = params.get("name", "")
            arguments = params.get("arguments") or {}
            return success_response(request_id, get_prompt(name, arguments))
        return error_response(request_id, f"unknown method: {method}", code=-32601)
    except ValueError as exc:
        return error_response(request_id, str(exc), code=-32602)
    except Exception as exc:
        return error_response(request_id, str(exc), code=-32000)


def encode_message(payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def decode_message(stream) -> Optional[dict]:
    headers = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n", b""):
            break
        key, value = line.split(b":", 1)
        headers[key.strip().lower().decode("ascii")] = value.strip().decode("ascii")
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        raise ValueError("missing content-length")
    body = stream.read(length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def write_message(payload):
    sys.stdout.buffer.write(encode_message(payload))
    sys.stdout.buffer.flush()


def main():
    stream = sys.stdin.buffer
    while True:
        try:
            request = decode_message(stream)
        except json.JSONDecodeError as exc:
            write_message(error_response(None, f"invalid json: {exc}", code=-32700))
            continue
        except ValueError as exc:
            write_message(error_response(None, str(exc), code=-32700))
            continue
        if request is None:
            return 0
        response = handle_request(request)
        write_message(response)


if __name__ == "__main__":
    raise SystemExit(main())
