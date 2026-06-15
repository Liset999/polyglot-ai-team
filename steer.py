#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Human steering CLI for the active Polyglot session."""

import argparse
import os
import sys

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


def show_status(runtime):
    state = runtime.read_run_state()
    pending = runtime.read_steer()
    control = runtime.read_control()

    print("=" * 60)
    print("  Polyglot AI Team -- Human Steering")
    print("=" * 60)

    print("\n[run]")
    if not state:
        print("  No run state found.")
    elif state.get("_error"):
        print(f"  Could not read run state: {state['_error']}")
    else:
        print(f"  goal:    {state.get('goal', '')}")
        print(f"  status:  {state.get('status', 'unknown')}")
        print(f"  attempt: {state.get('attempt', 0)}")
        print(f"  backend: {state.get('backend', 'unknown')}")
        if state.get("last_error_summary"):
            print(f"  error:   {state.get('last_error_summary')}")

    print("\n[steer]")
    if not pending:
        print("  No pending steer instruction.")
    elif pending.get("_error"):
        print(f"  Could not read steer: {pending['_error']}")
    else:
        print(f"  message: {pending.get('message', '')}")
        print(f"  sent:    {pending.get('timestamp', '')}")

    print("\n[control]")
    if not control:
        print("  No control signal.")
    elif control.get("_error"):
        print(f"  Could not read control: {control['_error']}")
    else:
        print(f"  action:  {control.get('action', '')}")
        if control.get("message"):
            print(f"  message: {control.get('message', '')}")
        print(f"  sent:    {control.get('timestamp', '')}")


def main(argv=None):
    configure_stdio()
    parser = argparse.ArgumentParser(description="Send steering instructions to the active Polyglot run")
    parser.add_argument("message", nargs="*", help="steering instruction")
    parser.add_argument("--status", action="store_true", help="show current run and steer state")
    parser.add_argument("--cancel", action="store_true", help="cancel pending steer instruction")
    parser.add_argument("--pause", action="store_true", help="pause the active worker at the next checkpoint")
    parser.add_argument("--resume", action="store_true", help="resume a paused worker")
    parser.add_argument("--stop", action="store_true", help="stop the active worker at the next checkpoint")
    parser.add_argument("--session", default=os.environ.get("POLYGLOT_SESSION", "default"))
    args = parser.parse_args(argv)

    runtime = Runtime(find_workspace_dir(), args.session)

    if args.status:
        show_status(runtime)
        return 0
    if args.cancel:
        if runtime.cancel_steer():
            print("[OK] pending steer cancelled.")
        else:
            print("No pending steer instruction.")
        return 0

    control_actions = [name for name in ("pause", "resume", "stop") if getattr(args, name)]
    if control_actions:
        if len(control_actions) > 1:
            print("[ERROR] choose only one of --pause, --resume, or --stop.")
            return 1
        action = control_actions[0]
        message = " ".join(args.message).strip()
        payload = runtime.set_control(action, message)
        suffix = f": {payload.get('message')}" if payload.get("message") else ""
        print(f"[OK] control set: {payload.get('action')}{suffix}")
        return 0

    message = " ".join(args.message).strip()
    if not message:
        try:
            message = input("steer> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
    if not message:
        print("[ERROR] steer instruction cannot be empty.")
        return 1

    runtime.send_steer(message)
    print(f"[OK] steer sent: {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
