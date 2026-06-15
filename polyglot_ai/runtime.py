import json
import os
import re
import shutil
from datetime import datetime


SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def validate_session_id(session_id):
    session_id = (session_id or "default").strip()
    if not SESSION_ID_RE.match(session_id):
        raise ValueError("session id may only contain letters, numbers, dot, dash, and underscore")
    if session_id in (".", ".."):
        raise ValueError("invalid session id")
    return session_id


class Runtime:
    def __init__(self, workspace_dir, session_id="default"):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.artifacts_dir = os.path.join(self.workspace_dir, "artifacts")
        self.session_id = validate_session_id(session_id)
        self.session_dir = os.path.join(self.artifacts_dir, "sessions", self.session_id)
        self.team_plan_path = os.path.join(self.session_dir, "team_plan.json")
        self.events_path = os.path.join(self.session_dir, "events.jsonl")
        self.timeline_path = os.path.join(self.session_dir, "timeline.jsonl")
        self.messages_path = os.path.join(self.session_dir, "messages.jsonl")
        self.task_packets_path = os.path.join(self.session_dir, "task_packets.jsonl")
        self.run_state_path = os.path.join(self.session_dir, "run_state.json")
        self.steer_path = os.path.join(self.session_dir, "steer.json")
        self.control_path = os.path.join(self.session_dir, "control.json")
        self.approval_path = os.path.join(self.session_dir, "approval.json")
        self.run_lock_path = os.path.join(self.session_dir, "run_lock.json")
        self.final_report_path = os.path.join(self.session_dir, "final_report.md")
        self.handoff_md_path = os.path.join(self.session_dir, "handoff.md")
        self.handoff_json_path = os.path.join(self.session_dir, "handoff.json")
        self.snapshot_dir = os.path.join(self.session_dir, "artifacts")

    def ensure(self):
        os.makedirs(self.session_dir, exist_ok=True)

    def session_meta_path(self):
        return os.path.join(self.session_dir, "session.json")

    def create_session(self, title=""):
        self.ensure()
        meta = {
            "session_id": self.session_id,
            "title": title or self.session_id,
            "created_at": self.now(),
            "workspace_dir": self.workspace_dir,
        }
        if not os.path.exists(self.session_meta_path()):
            self.write_json(self.session_meta_path(), meta)
            self.append_event("session.created", f"Created session: {self.session_id}", meta)
        return self.read_json(self.session_meta_path(), meta)

    def list_sessions(self):
        sessions_dir = os.path.join(self.artifacts_dir, "sessions")
        if not os.path.isdir(sessions_dir):
            return []
        sessions = []
        for name in sorted(os.listdir(sessions_dir)):
            try:
                safe_name = validate_session_id(name)
            except ValueError:
                continue
            path = os.path.join(sessions_dir, safe_name)
            if not os.path.isdir(path):
                continue
            meta_path = os.path.join(path, "session.json")
            meta = self.read_json(meta_path, {}) or {}
            events_path = os.path.join(path, "events.jsonl")
            run_state_path = os.path.join(path, "run_state.json")
            sessions.append({
                "session_id": safe_name,
                "title": meta.get("title", safe_name),
                "created_at": meta.get("created_at", ""),
                "events": self._count_lines(events_path),
                "status": (self.read_json(run_state_path, {}) or {}).get("status", "idle"),
                "updated_at": self._mtime_iso(path),
            })
        return sessions

    def _count_lines(self, path):
        if not os.path.exists(path):
            return 0
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return sum(1 for _ in f)
        except OSError:
            return 0

    def _mtime_iso(self, path):
        try:
            return datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
        except OSError:
            return ""

    def now(self):
        return datetime.now().isoformat()

    def read_json(self, path, default=None):
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            return {"_error": str(exc)}

    def write_json(self, path, data):
        self.ensure()
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)

    def append_event(self, event_type, summary, data=None):
        self.ensure()
        event = {
            "ts": self.now(),
            "session_id": self.session_id,
            "type": event_type,
            "summary": summary,
            "data": data or {},
        }
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        if not event_type.startswith("timeline."):
            self.append_timeline(
                actor="runtime",
                action=event_type,
                observation=summary,
                status=self._status_from_event_type(event_type),
                data=data or {},
                mirror_event=False,
            )
        return event

    def _status_from_event_type(self, event_type):
        tail = (event_type or "").split(".")[-1]
        if tail in ("failed", "failure", "error"):
            return "failed"
        if tail in ("success", "completed", "written", "created", "snapshotted", "resumed"):
            return "success"
        if tail in ("started", "filling", "testing", "healing", "paused"):
            return "running"
        return "observed"

    def append_timeline(self, actor, action, observation="", status="observed", data=None, mirror_event=True):
        self.ensure()
        item = {
            "ts": self.now(),
            "session_id": self.session_id,
            "actor": actor,
            "action": action,
            "observation": observation,
            "status": status,
            "data": data or {},
        }
        with open(self.timeline_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        if mirror_event:
            self.append_event(f"timeline.{action}", observation or action, item)
        return item

    def read_timeline(self, limit=None):
        if not os.path.exists(self.timeline_path):
            return []
        items = []
        with open(self.timeline_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    items.append({"actor": "runtime", "action": "corrupt", "observation": line, "status": "failed"})
        return items[-limit:] if limit else items

    def read_events(self, limit=None):
        if not os.path.exists(self.events_path):
            return []
        events = []
        with open(self.events_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    events.append({"type": "runtime.corrupt_event", "summary": line})
        return events[-limit:] if limit else events

    def append_message(self, role, content, channel="terminal", data=None):
        self.ensure()
        message = {
            "ts": self.now(),
            "session_id": self.session_id,
            "role": role,
            "channel": channel,
            "content": content,
            "data": data or {},
        }
        with open(self.messages_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")
        return message

    def read_messages(self, limit=None):
        if not os.path.exists(self.messages_path):
            return []
        messages = []
        with open(self.messages_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    messages.append({"role": "system", "content": line})
        return messages[-limit:] if limit else messages

    def append_task_packet(self, packet):
        self.ensure()
        enriched = dict(packet)
        enriched.setdefault("ts", self.now())
        enriched.setdefault("session_id", self.session_id)
        with open(self.task_packets_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(enriched, ensure_ascii=False) + "\n")
        self.append_event(
            "task_packet.created",
            f"Task packet: {enriched.get('phase', '')} {enriched.get('target_file', '')}",
            {
                "packet_id": enriched.get("packet_id", ""),
                "phase": enriched.get("phase", ""),
                "target_file": enriched.get("target_file", ""),
                "backend": enriched.get("backend", ""),
            },
        )
        return enriched

    def read_task_packets(self, limit=None):
        if not os.path.exists(self.task_packets_path):
            return []
        packets = []
        with open(self.task_packets_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    packets.append(json.loads(line))
                except json.JSONDecodeError:
                    packets.append({"phase": "corrupt", "summary": line})
        return packets[-limit:] if limit else packets

    def save_team_plan(self, plan):
        self.write_json(self.team_plan_path, plan)
        if self.session_id == "default":
            self.write_json(os.path.join(self.artifacts_dir, "team_plan.json"), plan)
        self.append_event("team_plan.created", f"Created team plan: {plan.get('task_name', '')}", plan)

    def read_team_plan(self):
        return self.read_json(self.team_plan_path)

    def save_run_state(self, state):
        self.write_json(self.run_state_path, state)

    def read_run_state(self):
        state = self.read_json(self.run_state_path)
        if state:
            return state
        if self.session_id != "default":
            return None
        return self.read_json(os.path.join(self.artifacts_dir, "run_state.json"))

    def send_steer(self, message):
        payload = {"message": message, "timestamp": self.now()}
        self.write_json(self.steer_path, payload)
        if self.session_id == "default":
            self.write_json(os.path.join(self.artifacts_dir, "steer.json"), payload)
        self.append_event("user.steer", message, payload)
        return payload

    def cancel_steer(self):
        removed = False
        paths = [self.steer_path]
        if self.session_id == "default":
            paths.append(os.path.join(self.artifacts_dir, "steer.json"))
        for path in paths:
            if os.path.exists(path):
                os.remove(path)
                removed = True
        if removed:
            self.append_event("user.steer_cancelled", "Cancelled pending steer")
        return removed

    def read_steer(self):
        if self.session_id != "default":
            return self.read_json(self.steer_path)
        return self.read_json(self.steer_path) or self.read_json(os.path.join(self.artifacts_dir, "steer.json"))

    def set_control(self, action, message=""):
        action = (action or "").strip().lower()
        if action not in ("pause", "resume", "stop"):
            raise ValueError("control action must be pause, resume, or stop")
        payload = {
            "action": action,
            "message": (message or "").strip(),
            "timestamp": self.now(),
        }
        self.write_json(self.control_path, payload)
        if self.session_id == "default":
            self.write_json(os.path.join(self.artifacts_dir, "control.json"), payload)
        self.append_event(f"user.control.{action}", payload["message"] or action, payload)
        return payload

    def read_control(self):
        if self.session_id != "default":
            return self.read_json(self.control_path)
        return self.read_json(self.control_path) or self.read_json(os.path.join(self.artifacts_dir, "control.json"))

    def request_approval(self, payload):
        data = dict(payload)
        data.setdefault("status", "pending")
        data.setdefault("created_at", self.now())
        data.setdefault("approval_id", f"approval-{data['created_at'].replace(':', '').replace('.', '-')}")
        self.write_json(self.approval_path, data)
        self.append_event("approval.requested", f"Approval requested: {data.get('reason', '')}", data)
        return data

    def read_approval(self):
        return self.read_json(self.approval_path)

    def read_run_lock(self):
        return self.read_json(self.run_lock_path)

    def acquire_run_lock(self, goal, owner="main_agent"):
        self.ensure()
        payload = {
            "session_id": self.session_id,
            "goal": goal,
            "owner": owner,
            "pid": os.getpid(),
            "created_at": self.now(),
        }
        try:
            fd = os.open(self.run_lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            return False, self.read_run_lock() or {"goal": "unknown", "owner": "unknown"}
        except OSError as exc:
            return False, {"_error": str(exc)}

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            self.append_event("run_lock.acquired", f"Run lock acquired: {goal}", payload)
            return True, payload
        except Exception:
            try:
                os.remove(self.run_lock_path)
            except OSError:
                pass
            raise

    def release_run_lock(self, reason=""):
        lock = self.read_run_lock() or {}
        if os.path.exists(self.run_lock_path):
            os.remove(self.run_lock_path)
        if lock and not lock.get("_error"):
            lock["released_at"] = self.now()
            lock["release_reason"] = reason
            self.append_event("run_lock.released", reason or "Run lock released", lock)
        return lock

    def clear_approval(self, status="cleared", reason=""):
        approval = self.read_approval() or {}
        if os.path.exists(self.approval_path):
            os.remove(self.approval_path)
        if approval:
            approval["status"] = status
            approval["closed_at"] = self.now()
            approval["close_reason"] = reason
            self.append_event(f"approval.{status}", reason or status, approval)
        return approval

    def release_files(self):
        release_dir = self.artifact_dir("release")
        if not os.path.isdir(release_dir):
            return []
        return sorted(
            name for name in os.listdir(release_dir)
            if os.path.isfile(os.path.join(release_dir, name))
        )

    def artifact_dir(self, kind):
        snapshot_path = os.path.join(self.snapshot_dir, kind)
        if os.path.isdir(snapshot_path):
            return snapshot_path
        return os.path.join(self.artifacts_dir, kind)

    def working_artifact_dir(self, kind):
        if self.session_id == "default":
            return os.path.join(self.artifacts_dir, kind)
        return os.path.join(self.snapshot_dir, kind)

    def working_artifact_path(self, *parts):
        if not parts:
            return self.working_artifact_dir("")
        if parts[0] in ("inputs", "draft", "release"):
            return os.path.join(self.working_artifact_dir(parts[0]), *parts[1:])
        if self.session_id == "default":
            return os.path.join(self.artifacts_dir, *parts)
        return os.path.join(self.snapshot_dir, *parts)

    def snapshot_artifacts(self):
        self.ensure()
        os.makedirs(self.snapshot_dir, exist_ok=True)
        copied = []
        for dirname in ("inputs", "draft", "release"):
            src = self.working_artifact_dir(dirname)
            if not os.path.isdir(src):
                continue
            dst = os.path.join(self.snapshot_dir, dirname)
            if os.path.abspath(src) == os.path.abspath(dst):
                copied.append(dirname)
                continue
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".claude", "*.pyc", "*.pyo"),
            )
            copied.append(dirname)

        for filename in ("test_run.log", "claude_run.log", "run_state.json", "team_plan.json"):
            src = self.working_artifact_path(filename)
            if not os.path.isfile(src):
                continue
            dst = os.path.join(self.snapshot_dir, filename)
            if os.path.abspath(src) == os.path.abspath(dst):
                copied.append(filename)
                if filename == "run_state.json":
                    state = self.read_json(src)
                    if state and not state.get("_error"):
                        self.save_run_state(state)
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            if filename == "run_state.json":
                state = self.read_json(src)
                if state and not state.get("_error"):
                    self.save_run_state(state)
            copied.append(filename)

        manifest = {
            "session_id": self.session_id,
            "created_at": self.now(),
            "copied": copied,
        }
        self.write_json(os.path.join(self.snapshot_dir, "manifest.json"), manifest)
        self.append_event("artifacts.snapshotted", f"Snapshotted artifacts: {', '.join(copied) if copied else 'none'}", manifest)
        return manifest

    def write_final_report(self, text):
        self.ensure()
        with open(self.final_report_path, "w", encoding="utf-8") as f:
            f.write(text)
        self.append_event("report.written", "Wrote final report", {"path": self.final_report_path})

    def write_handoff(self, markdown_text, data):
        self.ensure()
        with open(self.handoff_md_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        self.write_json(self.handoff_json_path, data)
        self.append_event(
            "handoff.written",
            "Wrote session handoff",
            {"markdown": self.handoff_md_path, "json": self.handoff_json_path},
        )
        return {"markdown": self.handoff_md_path, "json": self.handoff_json_path}

    def mirror_legacy_artifact(self, filename):
        src = os.path.join(self.artifacts_dir, filename)
        if not os.path.exists(src):
            return False
        dst = os.path.join(self.session_dir, filename)
        shutil.copy2(src, dst)
        return True
