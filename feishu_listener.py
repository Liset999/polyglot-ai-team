#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal HTTP listener for Feishu-style incoming messages.

This intentionally stays small and local-first. It accepts generic JSON payloads
and routes extracted text into the same MainAgent/Feishu bridge used by CLI
commands.
"""

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from feishu_bridge import handle_text
from polyglot_ai.main_agent import MainAgent
from polyglot_ai.runtime import Runtime


def configure_stdio():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def find_workspace_dir():
    configured = os.environ.get("POLYGLOT_WORKSPACE")
    if configured:
        return os.path.abspath(configured)
    return os.path.dirname(os.path.abspath(__file__))


def _maybe_json(value):
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def extract_text(payload):
    if not isinstance(payload, dict):
        return ""

    for key in ("text", "message", "content"):
        value = payload.get(key)
        if isinstance(value, str):
            decoded = _maybe_json(value)
            if isinstance(decoded, dict):
                text = decoded.get("text") or decoded.get("content") or ""
                if isinstance(text, str):
                    return text.strip()
            return value.strip()

    event = payload.get("event") or {}
    message = event.get("message") or {}
    content = _maybe_json(message.get("content") or "")
    if isinstance(content, dict):
        text = content.get("text") or content.get("content") or ""
        if isinstance(text, str):
            return text.strip()

    return ""


def make_handler(workspace_dir, session_id, webhook_url, dry_run):
    class FeishuHandler(BaseHTTPRequestHandler):
        server_version = "PolyglotFeishuListener/0.1"

        def _send_json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            print("[feishu-listener] " + (fmt % args))

        def do_GET(self):
            self._send_json(200, {"ok": True, "service": "polyglot-feishu-listener", "session": session_id})

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8", errors="replace")
                payload = json.loads(raw) if raw else {}
            except Exception as exc:
                self._send_json(400, {"ok": False, "error": f"invalid json: {exc}"})
                return

            if isinstance(payload, dict) and payload.get("challenge"):
                self._send_json(200, {"challenge": payload.get("challenge")})
                return

            text = extract_text(payload)
            if not text:
                self._send_json(200, {"ok": True, "ignored": "no text found"})
                return

            runtime = Runtime(workspace_dir, session_id)
            main_agent = MainAgent(workspace_dir, runtime)
            runtime.append_event("feishu.incoming", text, {"source": "http-listener"})
            ok = handle_text(main_agent, text, dry_run=dry_run, webhook_url=webhook_url)
            self._send_json(200, {"ok": bool(ok), "text": text, "session": session_id})

    return FeishuHandler


def main(argv=None):
    configure_stdio()
    parser = argparse.ArgumentParser(description="Run a minimal Feishu incoming-message listener")
    parser.add_argument("--host", default=os.environ.get("POLYGLOT_FEISHU_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("POLYGLOT_FEISHU_PORT", "8787")))
    parser.add_argument("--session", default=os.environ.get("POLYGLOT_SESSION", "default"))
    parser.add_argument("--webhook-url", default=os.environ.get("FEISHU_WEBHOOK_URL", ""))
    parser.add_argument("--dry-run", action="store_true", help="print outgoing Feishu payloads instead of posting")
    args = parser.parse_args(argv)

    workspace_dir = find_workspace_dir()
    handler = make_handler(workspace_dir, args.session, args.webhook_url, args.dry_run)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"[feishu-listener] listening on http://{args.host}:{args.port} session={args.session}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[feishu-listener] stopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
