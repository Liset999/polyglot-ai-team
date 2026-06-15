#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal Feishu bridge for Polyglot AI Team OS.

This is intentionally small: it reuses the local Runtime, Task Board, and CLI
instead of introducing a web platform or daemon first.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from polyglot_ai.main_agent import MainAgent
from polyglot_ai.runtime import Runtime


def find_workspace_dir():
    configured = os.environ.get("POLYGLOT_WORKSPACE")
    if configured:
        return os.path.abspath(configured)
    return os.path.dirname(os.path.abspath(__file__))


def configure_stdio():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def truncate_text(text, limit=1800):
    if len(text) <= limit:
        return text
    return text[: limit - 80].rstrip() + "\n\n[truncated locally; run `python polyglot_cli.py board` for full state]"


def post_feishu_text(text, webhook_url=None, dry_run=False):
    webhook_url = webhook_url or os.environ.get("FEISHU_WEBHOOK_URL", "")
    payload = {
        "msg_type": "text",
        "content": {"text": truncate_text(text)},
    }
    if dry_run or not webhook_url:
        print("[feishu dry-run]")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return True

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
        print(f"[OK] Feishu message sent: HTTP {response.status}")
        if body:
            print(body)
        return True
    except urllib.error.URLError as exc:
        print(f"[ERROR] Feishu webhook failed: {exc}", file=sys.stderr)
        return False


def dispatch_text(main_agent, text):
    text = text.strip()
    if not text:
        return "Empty message ignored."
    lowered = text.lower()
    if lowered.startswith("/steer "):
        message = text[len("/steer "):].strip()
        return main_agent.send_steer(message)
    for action in ("pause", "resume", "stop"):
        prefix = f"/{action}"
        if lowered == prefix or lowered.startswith(prefix + " "):
            message = text[len(prefix):].strip()
            return main_agent.set_control_text(action, message)
    if lowered in ("/approval", "approval"):
        return main_agent.approval_text()
    if lowered in ("/approve", "approve"):
        return main_agent.approve_text()
    if lowered == "/deny" or lowered.startswith("/deny ") or lowered == "deny" or lowered.startswith("deny "):
        if lowered.startswith("/deny"):
            reason = text[len("/deny"):].strip()
        else:
            reason = text[len("deny"):].strip()
        return main_agent.deny_text(reason)
    if lowered in ("/lock", "lock"):
        return main_agent.lock_text()
    if lowered == "/unlock" or lowered.startswith("/unlock ") or lowered == "unlock" or lowered.startswith("unlock "):
        if lowered.startswith("/unlock"):
            reason = text[len("/unlock"):].strip()
        else:
            reason = text[len("unlock"):].strip()
        return main_agent.unlock_text(reason or "feishu unlock")
    if lowered in ("/status", "/board"):
        return main_agent.compact_board_text()
    if lowered in ("/board-full", "/status-full"):
        return main_agent.board_text()
    if lowered in ("/report", "report"):
        return main_agent.read_final_report()
    if lowered in ("/packet", "packet"):
        return main_agent.latest_packet_text()
    if lowered in ("/timeline", "timeline"):
        return main_agent.timeline_text()
    if lowered in ("/handoff", "handoff"):
        return main_agent.handoff_text()
    if lowered in ("/history", "history"):
        return main_agent.history_text()
    if lowered in ("/sessions", "sessions"):
        return main_agent.sessions_text()
    if lowered in ("/events", "events"):
        return main_agent.events_text()
    if lowered in ("/agents", "agents"):
        return main_agent.agents_text()
    if lowered in ("/about", "about"):
        return main_agent.about_text()
    if lowered.startswith("/route "):
        goal = text[len("/route "):].strip()
        return main_agent.route_text(goal)
    if lowered.startswith("/session-new "):
        raw = text[len("/session-new "):].strip()
        parts = raw.split(maxsplit=1)
        if not parts:
            return "Usage: /session-new <id> [title]"
        title = parts[1] if len(parts) > 1 else ""
        return main_agent.create_session_text(parts[0], title)
    if lowered.startswith("/run "):
        goal = text[len("/run "):].strip()
        exit_code, report = main_agent.run_goal(goal)
        if exit_code == 2:
            return report
        return f"Run finished with exit code {exit_code}\n\n{report}\n\n{main_agent.board_text()}"

    return main_agent.chat_reply(text, channel="feishu")


def handle_text(main_agent, text, dry_run=False, webhook_url=None):
    return post_feishu_text(dispatch_text(main_agent, text), webhook_url=webhook_url, dry_run=dry_run)


def main(argv=None):
    configure_stdio()
    parser = argparse.ArgumentParser(description="Minimal Feishu bridge for Polyglot AI Team OS")
    parser.add_argument("--session", default=os.environ.get("POLYGLOT_SESSION", "default"))
    parser.add_argument("--dry-run", action="store_true", help="print Feishu payload instead of posting")
    parser.add_argument("--webhook-url", default=os.environ.get("FEISHU_WEBHOOK_URL", ""))

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("post-board", help="post the current task board")
    sub.add_parser("post-board-full", help="post the full current task board")
    sub.add_parser("post-report", help="post the latest final report")
    sub.add_parser("post-packet", help="post the latest delegated task packet")
    sub.add_parser("post-timeline", help="post recent action/observation flow")
    sub.add_parser("post-handoff", help="post and write compact session handoff")
    sub.add_parser("post-history", help="post recent main-agent conversation")
    sub.add_parser("post-sessions", help="post local session list")
    sub.add_parser("post-about", help="post product/session/worker self-knowledge")
    sub.add_parser("post-approval", help="post pending approval")
    sub.add_parser("approve", help="approve and execute pending high-trust run")
    deny_p = sub.add_parser("deny", help="deny pending approval")
    deny_p.add_argument("reason", nargs="*")
    sub.add_parser("post-lock", help="post active run lock")
    unlock_p = sub.add_parser("unlock", help="clear a stale run lock")
    unlock_p.add_argument("reason", nargs="*")

    steer_p = sub.add_parser("steer", help="send a steering instruction")
    steer_p.add_argument("message", nargs="+")

    for action in ("pause", "resume", "stop"):
        control_p = sub.add_parser(action, help=f"send a {action} control signal")
        control_p.add_argument("message", nargs="*")

    run_p = sub.add_parser("run", help="run a goal locally and post report")
    run_p.add_argument("goal", nargs="+")

    route_p = sub.add_parser("route", help="post worker routing explanation")
    route_p.add_argument("goal", nargs="+")

    text_p = sub.add_parser("handle-text", help="handle one Feishu-style text command")
    text_p.add_argument("text", nargs="+")

    args = parser.parse_args(argv)
    workspace_dir = find_workspace_dir()
    runtime = Runtime(workspace_dir, args.session)
    main_agent = MainAgent(workspace_dir, runtime)

    def post(text):
        return post_feishu_text(text, webhook_url=args.webhook_url, dry_run=args.dry_run)

    if args.command == "post-board":
        ok = post(main_agent.compact_board_text())
        return 0 if ok else 1
    if args.command == "post-board-full":
        ok = post(main_agent.board_text())
        return 0 if ok else 1
    if args.command == "post-report":
        ok = post(main_agent.read_final_report())
        return 0 if ok else 1
    if args.command == "post-packet":
        ok = post(main_agent.latest_packet_text())
        return 0 if ok else 1
    if args.command == "post-timeline":
        ok = post(main_agent.timeline_text())
        return 0 if ok else 1
    if args.command == "post-handoff":
        ok = post(main_agent.handoff_text())
        return 0 if ok else 1
    if args.command == "post-history":
        ok = post(main_agent.history_text())
        return 0 if ok else 1
    if args.command == "post-sessions":
        ok = post(main_agent.sessions_text())
        return 0 if ok else 1
    if args.command == "post-about":
        ok = post(main_agent.about_text())
        return 0 if ok else 1
    if args.command == "post-approval":
        ok = post(main_agent.approval_text())
        return 0 if ok else 1
    if args.command == "approve":
        ok = post(main_agent.approve_text())
        return 0 if ok else 1
    if args.command == "deny":
        ok = post(main_agent.deny_text(" ".join(args.reason).strip()))
        return 0 if ok else 1
    if args.command == "post-lock":
        ok = post(main_agent.lock_text())
        return 0 if ok else 1
    if args.command == "unlock":
        ok = post(main_agent.unlock_text(" ".join(args.reason).strip() or "feishu unlock"))
        return 0 if ok else 1
    if args.command == "steer":
        message = " ".join(args.message).strip()
        ok = post(main_agent.send_steer(message))
        return 0 if ok else 1
    if args.command in ("pause", "resume", "stop"):
        ok = post(main_agent.set_control_text(args.command, " ".join(args.message).strip()))
        return 0 if ok else 1
    if args.command == "run":
        goal = " ".join(args.goal).strip()
        exit_code, report = main_agent.run_goal(goal)
        if exit_code == 2:
            ok = post(report)
            return 0 if ok else 1
        ok = post(f"Run finished with exit code {exit_code}\n\n{report}\n\n{main_agent.board_text()}")
        return 0 if ok and exit_code == 0 else 1
    if args.command == "route":
        goal = " ".join(args.goal).strip()
        ok = post(main_agent.route_text(goal))
        return 0 if ok else 1
    if args.command == "handle-text":
        ok = handle_text(main_agent, " ".join(args.text), dry_run=args.dry_run, webhook_url=args.webhook_url)
        return 0 if ok else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
