#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polyglot AI Team CLI.

Run:
    python polyglot_cli.py
    python polyglot_cli.py run "build a date converter with tests"
    .\polyglot.bat
"""

import argparse
import ast
import os
import shlex
import subprocess
import sys
from datetime import datetime

from polyglot_ai.agents import read_agent_config, select_agent
from polyglot_ai.main_agent import MainAgent
from polyglot_ai.runtime import Runtime

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def find_workspace_dir():
    configured = os.environ.get("POLYGLOT_WORKSPACE")
    if configured:
        return os.path.abspath(configured)
    cwd = os.path.abspath(os.getcwd())
    if os.path.exists(os.path.join(cwd, "monitor.py")) and os.path.isdir(os.path.join(cwd, "polyglot_ai")):
        return cwd
    return os.path.dirname(os.path.abspath(__file__))


WORKSPACE_DIR = find_workspace_dir()
ARTIFACTS_DIR = os.path.join(WORKSPACE_DIR, "artifacts")
SESSION_ID = os.environ.get("POLYGLOT_SESSION", "default")
runtime = Runtime(WORKSPACE_DIR, SESSION_ID)
main_agent = MainAgent(WORKSPACE_DIR, runtime)
KNOWN_COMMANDS = {
    "run", "plan", "steer", "status", "events", "cancel", "agents",
    "board", "packet", "sessions", "session-new", "route", "pause", "resume", "stop",
    "chat", "history", "timeline", "handoff", "approval", "approve", "deny",
    "lock", "unlock", "about", "doctor", "help", "exit", "quit", "q",
}
SLASH_HELP = "Chat normally. Use /run, /status, /timeline, /approve, /steer."
console = Console(highlight=False, emoji=False) if HAS_RICH else None


def configure_stdio():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def print_banner():
    if HAS_RICH:
        title = Text("Polyglot AI Team OS", style="bold cyan")
        body = Text()
        body.append("Terminal-first local agent runtime\n", style="white")
        body.append(SLASH_HELP, style="dim")
        console.print(Panel(body, title=title, border_style="cyan", padding=(1, 2)))
        return
    print("=" * 64)
    print("  Polyglot AI Team OS")
    print(f"  {SLASH_HELP}")
    print("=" * 64)


def discover_agent_paths(env=None):
    return main_agent.discover_agent_paths(env)


def release_files():
    return main_agent.release_files()


def show_status():
    print(main_agent.status_text())


def show_events(limit=12):
    print(main_agent.events_text(limit=limit))


def show_board():
    print(main_agent.board_text())


def show_packet():
    print(main_agent.latest_packet_text())


def show_history(limit=12):
    print(main_agent.history_text(limit=limit))


def show_timeline(limit=16):
    print(main_agent.timeline_text(limit=limit))


def show_handoff():
    print(main_agent.handoff_text())


def show_approval():
    print(main_agent.approval_text())


def show_lock():
    print(main_agent.lock_text())


def unlock_run(reason="manual unlock"):
    print(main_agent.unlock_text(reason or "manual unlock"))


def approve_pending():
    print(main_agent.approve_text())


def deny_pending(reason=""):
    print(main_agent.deny_text(reason))


def show_sessions():
    print(main_agent.sessions_text())


def create_session(session_id, title=""):
    print(main_agent.create_session_text(session_id, title=title))


def discover_agents():
    print(main_agent.agents_text())


def show_about():
    print(main_agent.about_text())


def show_route(goal, env=None):
    print(main_agent.route_text(goal, env))


def run_doctor():
    print("\n[doctor]")
    print(f"  workspace: {WORKSPACE_DIR}")
    print(f"  artifacts: {ARTIFACTS_DIR}")
    print(f"  session:   {runtime.session_dir}")

    problems = []
    if not os.path.isdir(WORKSPACE_DIR):
        problems.append("workspace directory does not exist")
    if not os.path.isdir(os.path.join(WORKSPACE_DIR, "polyglot_ai")):
        problems.append("polyglot_ai package not found")
    if not os.path.exists(os.path.join(WORKSPACE_DIR, "monitor.py")):
        problems.append("monitor.py not found")

    agents = discover_agent_paths()
    selected = select_agent()
    config = read_agent_config()
    print(f"  agent cfg: {config.get('path', '')}")
    if config.get("_error"):
        print(f"             error: {config.get('_error')}")
    elif config.get("default"):
        print(f"             default: {config.get('default')}")
    if agents:
        print("  agents:")
        for agent in agents:
            marker = "*" if agent["name"] == selected.name else "-"
            print(f"    {marker} {agent['name']}: {agent['path']} [{agent.get('adapter', '')}, {agent.get('source', '')}]")
    else:
        print("  agents:    none found on PATH")
        print("             mock-agent is available for offline verification")

    print(f"  selected:  {selected.name} ({selected.backend_name})")
    print(f"  source:    {selected.source}")
    print(f"  env agent: {os.environ.get('POLYGLOT_AGENT', 'auto')}")
    print(f"  deepseek:  {'set' if os.environ.get('DEEPSEEK_API_KEY') else 'not set'}")
    print(f"  feishu:    {'webhook set' if os.environ.get('FEISHU_WEBHOOK_URL') else 'webhook not set'}")
    print(f"  mock:      {'forced' if os.environ.get('FORCE_MOCK') else 'not forced'}")

    steer = runtime.read_steer()
    if steer and not steer.get("_error"):
        print(f"  steer:     pending - {steer.get('message', '')}")
    else:
        print("  steer:     none")

    syntax_targets = [
        "polyglot_ai/agents.py",
        "polyglot_ai/runtime.py",
        "polyglot_ai/main_agent.py",
        "polyglot_ai/task_packet.py",
        "polyglot_ai/worker_adapters.py",
        "polyglot_ai/task_board.py",
        "polyglot_ai/v0_planner.py",
        "polyglot_ai/v0_worker.py",
        "polyglot_ai/v1_worker.py",
        "monitor.py",
        "steer.py",
        "status.py",
        "feishu_bridge.py",
        "feishu_listener.py",
        "polyglot_cli.py",
    ]
    syntax_errors = []
    for target in syntax_targets:
        path = os.path.join(WORKSPACE_DIR, target)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                ast.parse(f.read(), filename=path)
        except Exception as exc:
            syntax_errors.append(f"{target}: {exc}")
    if syntax_errors:
        print("  syntax:    failed")
        for error in syntax_errors:
            print(f"             {error}")
        problems.append("python syntax check failed")
    else:
        print("  syntax:    ok")

    if problems:
        print("\n  problems:")
        for problem in problems:
            print(f"    - {problem}")
        return 1

    print("\n  result:    ok")
    return 0


def estimate_complexity(goal):
    return main_agent.estimate_complexity(goal)


def build_team_plan(goal, env=None):
    return main_agent.build_team_plan(goal, env)


def print_team_plan(plan):
    print(main_agent.render_team_plan(plan))


def save_team_plan(plan):
    main_agent.save_team_plan(plan)


def format_run_report(exit_code=None):
    return main_agent.format_run_report(exit_code)


def compact_status():
    return main_agent.compact_status()


def send_steer(message):
    print(main_agent.send_steer(message))


def set_control(action, message=""):
    print(main_agent.set_control_text(action, message))


def cancel_steer():
    print(main_agent.cancel_steer())


def parse_env_and_goal(words):
    return main_agent.parse_env_and_goal(words)


def run_monitor(goal, extra_env=None):
    return main_agent.run_monitor(goal, extra_env)


def plan_goal(goal, env=None):
    plan, text = main_agent.plan_goal(goal, env)
    print(text)
    return plan


def run_goal(goal, env=None):
    exit_code, text = main_agent.run_goal(goal, env)
    print(text)
    return exit_code


def should_delegate_to_worker(message):
    return main_agent.should_delegate_to_worker(message)


def main_agent_reply(message):
    return main_agent.chat_reply(message)


def print_help():
    print(
        """
Commands:
  <message>          Chat with the main agent without calling a worker
  /plan <goal>       Generate a structured team plan only
  /route <goal>      Explain worker routing and permission profile
  /run <goal>        Start a monitored agent run
  /approval          Show pending approval, if any
  /approve           Approve and execute a pending high-trust run
  /deny [reason]     Deny a pending high-trust run
  /lock              Show active run lock, if any
  /unlock [reason]   Clear a stale run lock
  /steer <message>   Send a steering instruction to the active run
  /pause [message]   Pause the active worker at the next checkpoint
  /resume [message]  Resume a paused worker
  /stop [message]    Stop the active worker at the next checkpoint
  /status            Show session state and pending steer
  /board             Show structured task board with tasks and artifacts
  /packet            Show latest delegated task packet
  /timeline          Show recent action/observation flow
  /handoff           Write and show a compact session handoff pack
  /history           Show recent main-agent conversation
  /sessions          List local sessions
  /session-new <id>  Create a new local session
  /events            Show recent session events
  /cancel            Cancel pending steer instruction
  /agents            Show discovered local CLI agents
  /about             Show product, session, interface, and worker self-knowledge
  /doctor            Check workspace, agents, env, and Python files
  /help              Show this help
  /exit              Leave the CLI

Examples:
  hello
  chat hello
  /plan build a backend API with JWT and tests
  /steer constrain dates to year 2000 or later
  /run FORCE_MOCK=1 build a string utility with unit tests
  set POLYGLOT_SESSION=my-demo before launching to work in another session
"""
    )


def repl():
    print_banner()
    last_exit_code = None
    while True:
        try:
            prompt = f"polyglot [{compact_status()}]> "
            raw = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not raw:
            continue

        if not raw.startswith("/"):
            message = raw.strip()
            if should_delegate_to_worker(message):
                print("[main] This looks like an engineering task. I will delegate it to the local worker.")
                last_exit_code = run_goal(message, None)
            else:
                _ = last_exit_code
                print(f"[main] {main_agent_reply(message)}")
            continue

        command_text = raw[1:].strip()
        try:
            parts = shlex.split(command_text, posix=False)
        except ValueError as exc:
            print(f"[ERROR] {exc}")
            continue
        if not parts:
            continue

        cmd = parts[0].lower()
        words = parts[1:] if cmd in KNOWN_COMMANDS else parts

        if cmd in ("exit", "quit", "q"):
            return 0
        if cmd in ("help", "h", "?"):
            print_help()
        elif cmd == "run":
            env, goal = parse_env_and_goal(words)
            if not goal:
                print("[ERROR] usage: /run <goal>")
                continue
            last_exit_code = run_goal(goal, env)
        elif cmd == "approval":
            show_approval()
        elif cmd == "approve":
            approve_pending()
        elif cmd == "deny":
            deny_pending(" ".join(words).strip())
        elif cmd == "lock":
            show_lock()
        elif cmd == "unlock":
            unlock_run(" ".join(words).strip())
        elif cmd == "plan":
            env, goal = parse_env_and_goal(words)
            if not goal:
                print("[ERROR] usage: /plan <goal>")
                continue
            plan_goal(goal, env)
        elif cmd == "route":
            env, goal = parse_env_and_goal(words)
            if not goal:
                print("[ERROR] usage: /route <goal>")
                continue
            show_route(goal, env)
        elif cmd == "chat":
            message = " ".join(words).strip()
            if not message:
                print("[ERROR] usage: /chat <message>")
                continue
            print(f"[main] {main_agent_reply(message)}")
        elif cmd == "steer":
            message = " ".join(words).strip()
            if not message:
                print("[ERROR] usage: /steer <message>")
                continue
            send_steer(message)
        elif cmd in ("pause", "resume", "stop"):
            set_control(cmd, " ".join(words).strip())
        elif cmd == "status":
            show_status()
        elif cmd == "board":
            show_board()
        elif cmd == "packet":
            show_packet()
        elif cmd == "history":
            show_history()
        elif cmd == "timeline":
            show_timeline()
        elif cmd == "handoff":
            show_handoff()
        elif cmd == "sessions":
            show_sessions()
        elif cmd == "session-new":
            if not words:
                print("[ERROR] usage: /session-new <id> [title]")
                continue
            create_session(words[0], " ".join(words[1:]).strip())
        elif cmd == "events":
            show_events()
        elif cmd == "cancel":
            cancel_steer()
        elif cmd == "agents":
            discover_agents()
        elif cmd == "about":
            show_about()
        elif cmd == "doctor":
            run_doctor()
        else:
            print(f"[ERROR] unknown command: {cmd}")
            print("Type /help for available commands.")


def build_parser():
    parser = argparse.ArgumentParser(description="Polyglot AI Team CLI")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="start a monitored run")
    run_p.add_argument("goal", nargs="+")

    plan_p = sub.add_parser("plan", help="generate a structured team plan")
    plan_p.add_argument("goal", nargs="+")

    route_p = sub.add_parser("route", help="explain worker routing")
    route_p.add_argument("goal", nargs="+")

    chat_p = sub.add_parser("chat", help="send one message to the main agent")
    chat_p.add_argument("message", nargs="+")

    steer_p = sub.add_parser("steer", help="send a steering instruction")
    steer_p.add_argument("message", nargs="+")

    for action in ("pause", "resume", "stop"):
        control_p = sub.add_parser(action, help=f"send a {action} control signal")
        control_p.add_argument("message", nargs="*")

    sub.add_parser("status", help="show current state")
    sub.add_parser("board", help="show structured task board")
    sub.add_parser("packet", help="show latest delegated task packet")
    sub.add_parser("timeline", help="show recent action/observation flow")
    sub.add_parser("handoff", help="write and show a compact session handoff pack")
    sub.add_parser("approval", help="show pending approval")
    sub.add_parser("approve", help="approve and execute pending high-trust run")
    deny_p = sub.add_parser("deny", help="deny pending approval")
    deny_p.add_argument("reason", nargs="*")
    sub.add_parser("lock", help="show active run lock")
    unlock_p = sub.add_parser("unlock", help="clear a stale run lock")
    unlock_p.add_argument("reason", nargs="*")
    sub.add_parser("history", help="show recent main-agent conversation")
    session_new_p = sub.add_parser("session-new", help="create a local session")
    session_new_p.add_argument("session_id")
    session_new_p.add_argument("title", nargs="*")
    sub.add_parser("sessions", help="list local sessions")
    sub.add_parser("events", help="show recent session events")
    sub.add_parser("cancel", help="cancel pending steer")
    sub.add_parser("agents", help="show discovered local agents")
    sub.add_parser("about", help="show product/session/worker self-knowledge")
    sub.add_parser("doctor", help="check workspace, agents, env, and Python files")
    return parser


def main(argv=None):
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        return repl()
    if args.command == "run":
        env, goal = parse_env_and_goal(args.goal)
        if not goal:
            print("[ERROR] usage: run <goal>")
            return 1
        return run_goal(goal, env)
    if args.command == "plan":
        env, goal = parse_env_and_goal(args.goal)
        if not goal:
            print("[ERROR] usage: plan <goal>")
            return 1
        plan_goal(goal, env)
        return 0
    if args.command == "route":
        env, goal = parse_env_and_goal(args.goal)
        if not goal:
            print("[ERROR] usage: route <goal>")
            return 1
        show_route(goal, env)
        return 0
    if args.command == "chat":
        print(main_agent_reply(" ".join(args.message)))
        return 0
    if args.command == "steer":
        send_steer(" ".join(args.message))
        return 0
    if args.command in ("pause", "resume", "stop"):
        set_control(args.command, " ".join(args.message).strip())
        return 0
    if args.command == "status":
        show_status()
        return 0
    if args.command == "board":
        show_board()
        return 0
    if args.command == "packet":
        show_packet()
        return 0
    if args.command == "history":
        show_history()
        return 0
    if args.command == "timeline":
        show_timeline()
        return 0
    if args.command == "handoff":
        show_handoff()
        return 0
    if args.command == "approval":
        show_approval()
        return 0
    if args.command == "approve":
        approve_pending()
        return 0
    if args.command == "deny":
        deny_pending(" ".join(args.reason).strip())
        return 0
    if args.command == "lock":
        show_lock()
        return 0
    if args.command == "unlock":
        unlock_run(" ".join(args.reason).strip())
        return 0
    if args.command == "sessions":
        show_sessions()
        return 0
    if args.command == "session-new":
        create_session(args.session_id, " ".join(args.title).strip())
        return 0
    if args.command == "events":
        show_events()
        return 0
    if args.command == "cancel":
        cancel_steer()
        return 0
    if args.command == "agents":
        discover_agents()
        return 0
    if args.command == "about":
        show_about()
        return 0
    if args.command == "doctor":
        return run_doctor()
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
