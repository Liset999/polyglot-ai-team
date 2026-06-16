#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thin bridge from skills/IM hosts into Polyglot AI Team OS."""

import argparse
import os
from pathlib import Path
import shlex
import sys


LOCAL_WINDOWS_EXAMPLE = r"D:\Repository\polyglot-ai-team"


def configure_stdio():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                try:
                    stream.reconfigure(errors="replace")
                except Exception:
                    pass


def looks_like_workspace(path):
    return os.path.isdir(os.path.join(path, "polyglot_ai"))


def find_workspace(configured=None):
    candidates = []
    if configured:
        candidates.append(configured)
    if os.environ.get("POLYGLOT_WORKSPACE"):
        candidates.append(os.environ["POLYGLOT_WORKSPACE"])
    candidates.append(os.getcwd())

    script_path = Path(__file__).resolve()
    candidates.extend(str(parent) for parent in script_path.parents)
    candidates.append(LOCAL_WINDOWS_EXAMPLE)

    for candidate in candidates:
        if not candidate:
            continue
        path = os.path.abspath(candidate)
        if looks_like_workspace(path):
            return path

    raise RuntimeError(
        "Could not find Polyglot workspace. Pass --workspace <path> or set POLYGLOT_WORKSPACE."
    )


def load_main_agent(workspace, session_id):
    workspace = find_workspace(workspace)
    if workspace not in sys.path:
        sys.path.insert(0, workspace)
    from polyglot_ai.main_agent import MainAgent
    from polyglot_ai.runtime import Runtime

    runtime = Runtime(workspace, session_id or os.environ.get("POLYGLOT_SESSION", "default"))
    return MainAgent(workspace, runtime)


def handle_text(text, session_id="default", workspace=None):
    text = (text or "").strip()
    agent = load_main_agent(workspace, session_id)
    lowered = text.lower()

    if not text:
        return "Empty message ignored."
    if lowered.startswith("/run "):
        raw_goal = text[len("/run "):].strip()
        try:
            words = shlex.split(raw_goal, posix=False)
        except ValueError:
            words = raw_goal.split()
        env, goal = agent.parse_env_and_goal(words)
        if not goal:
            return "Usage: /run [KEY=VALUE ...] <goal>"
        code, reply = agent.run_goal(goal, env)
        return f"[exit {code}]\n{reply}"
    if lowered in ("/status", "status"):
        return agent.status_text()
    if lowered in ("/workspace", "workspace", "/repo", "repo"):
        return agent.workspace_text()
    if lowered in ("/board", "board"):
        return agent.board_text()
    if lowered in ("/timeline", "timeline"):
        return agent.timeline_text()
    if lowered in ("/packet", "packet"):
        return agent.latest_packet_text()
    if lowered in ("/report", "report"):
        return agent.read_final_report()
    if lowered in ("/handoff", "handoff"):
        return agent.handoff_text()
    if lowered in ("/approval", "approval"):
        return agent.approval_text()
    if lowered in ("/approve", "approve"):
        return agent.approve_text()
    if lowered == "/deny" or lowered.startswith("/deny ") or lowered == "deny" or lowered.startswith("deny "):
        reason = text.split(" ", 1)[1].strip() if " " in text else ""
        return agent.deny_text(reason)
    if lowered in ("/lock", "lock"):
        return agent.lock_text()
    if lowered == "/unlock" or lowered.startswith("/unlock ") or lowered == "unlock" or lowered.startswith("unlock "):
        reason = text.split(" ", 1)[1].strip() if " " in text else "skill bridge unlock"
        return agent.unlock_text(reason)
    if lowered.startswith("/steer "):
        return agent.send_steer(text[len("/steer "):].strip())

    for action in ("pause", "resume", "stop"):
        prefix = f"/{action}"
        if lowered == prefix or lowered.startswith(prefix + " "):
            message = text[len(prefix):].strip()
            return agent.set_control_text(action, message)

    if lowered.startswith("/route "):
        return agent.route_text(text[len("/route "):].strip())
    if lowered in ("/about", "about"):
        return agent.about_text()
    if lowered in ("/agents", "agents"):
        return agent.agents_text()
    if lowered in ("/history", "history"):
        return agent.history_text()
    if lowered in ("/sessions", "sessions"):
        return agent.sessions_text()
    if lowered in ("/events", "events"):
        return agent.events_text()

    return agent.chat_reply(text, channel="skill")


def main(argv=None):
    configure_stdio()
    parser = argparse.ArgumentParser(description="Polyglot Team OS skill bridge")
    parser.add_argument("--workspace", default=os.environ.get("POLYGLOT_WORKSPACE", ""))
    parser.add_argument("--session", default=os.environ.get("POLYGLOT_SESSION", "default"))
    parser.add_argument("--text", required=True)
    args = parser.parse_args(argv)
    print(handle_text(args.text, session_id=args.session, workspace=args.workspace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
