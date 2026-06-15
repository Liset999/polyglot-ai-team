#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import sys

from polyglot_ai.runtime import Runtime
from polyglot_ai.task_board import build_task_board, render_task_board


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


def main(argv=None):
    configure_stdio()
    parser = argparse.ArgumentParser(description="Show the Polyglot structured task board")
    parser.add_argument("--session", default=os.environ.get("POLYGLOT_SESSION", "default"))
    args = parser.parse_args(argv)

    runtime = Runtime(find_workspace_dir(), args.session)
    board = build_task_board(runtime)
    print(render_task_board(board))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
