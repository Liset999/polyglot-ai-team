import os
import re
import subprocess
import sys


def extract_target_path(prompt):
    matches = re.findall(r"['\"]([^'\"]+\.py)['\"]", prompt)
    for match in matches:
        if not os.path.basename(match).startswith("test_"):
            return match
    return matches[0] if matches else ""


def mock_implementation(path, prompt):
    if path == "string_processor.py":
        return '''# -*- coding: utf-8 -*-
def reverse_string(s: str) -> str:
    return s[::-1]

def alternate_case(s: str) -> str:
    result = []
    alpha_index = 0
    for ch in s:
        if ch.isalpha():
            result.append(ch.upper() if alpha_index % 2 == 0 else ch.lower())
            alpha_index += 1
        else:
            result.append(ch)
    return "".join(result)

def to_camel_case(s: str) -> str:
    import re
    parts = [p for p in re.split(r"[_\\s]+", s.strip("_ ")) if p]
    if not parts:
        return ""
    first = parts[0][0].lower() + parts[0][1:] if parts[0] else ""
    return first + "".join(p[:1].upper() + p[1:].lower() for p in parts[1:])
'''
    if path == "date_converter.py":
        enforce_2000 = "2000" in prompt
        guard = (
            "    if value.year < 2000:\n"
            "        raise ValueError(\"dates before 2000 are not supported\")\n"
        ) if enforce_2000 else ""
        return f'''# -*- coding: utf-8 -*-
from datetime import datetime

_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d")

def _parse_date(date_str: str):
    for fmt in _FORMATS:
        try:
            value = datetime.strptime(date_str, fmt).date()
{guard if guard else ""}            return value
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {{date_str}}")

def format_iso(date_str: str) -> str:
    return _parse_date(date_str).isoformat()

def date_diff(date_str1: str, date_str2: str) -> int:
    return abs((_parse_date(date_str1) - _parse_date(date_str2)).days)
'''
    if path == "data_converter.py":
        return '''# -*- coding: utf-8 -*-
import csv
import json
from io import StringIO

def parse_csv_to_json(csv_str: str) -> str:
    reader = csv.DictReader(StringIO(csv_str.strip()))
    if not reader.fieldnames:
        return "[]"
    return json.dumps(list(reader), ensure_ascii=False)
'''
    return None


class WorkerAdapter:
    def __init__(self, agent, workspace_dir, draft_dir, log_path, runtime=None):
        self.agent = agent
        self.workspace_dir = workspace_dir
        self.draft_dir = draft_dir
        self.log_path = log_path
        self.runtime = runtime

    @property
    def backend_name(self):
        return self.agent.backend_name

    @property
    def adapter_name(self):
        return self.agent.adapter

    def query(self, prompt):
        raise NotImplementedError

    def write(self, prompt):
        raise NotImplementedError

    def append_log(self, prompt, exit_code, output):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as log_file:
            log_file.write("\n============================================================\n")
            log_file.write(f"AGENT CLI RUN ({self.backend_name})\n")
            log_file.write(f"Prompt: {prompt}\n")
            log_file.write(f"Exit Code: {exit_code}\n")
            log_file.write("------------------------------------------------------------\n")
            log_file.writelines(output)

    def append_event(self, event_type, summary, data=None):
        if self.runtime:
            self.runtime.append_event(event_type, summary, data or {})

    def append_timeline(self, action, observation="", status="observed", data=None):
        if self.runtime:
            self.runtime.append_timeline(
                actor=f"worker:{self.backend_name}",
                action=action,
                observation=observation,
                status=status,
                data=data or {},
            )


class LocalCliWorkerAdapter(WorkerAdapter):
    def _run(self, prompt, write_mode):
        cmd = self.agent.build_command(prompt, write_mode=write_mode)
        action = "worker.write" if write_mode else "worker.query"
        self.append_timeline(
            action,
            f"Starting {self.backend_name}",
            "running",
            {
                "backend": self.backend_name,
                "adapter": self.adapter_name,
                "cwd": self.draft_dir,
                "command": cmd[:2],
            },
        )
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self.draft_dir,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        output = []
        for line in process.stdout:
            output.append(line)
        process.wait()
        self.append_log(prompt, process.returncode, output)
        self.append_timeline(
            action,
            f"{self.backend_name} exited with {process.returncode}",
            "success" if process.returncode == 0 else "failed",
            {
                "backend": self.backend_name,
                "adapter": self.adapter_name,
                "exit_code": process.returncode,
                "output_tail": "".join(output[-8:]).strip(),
            },
        )
        return process.returncode, "".join(output).strip()

    def query(self, prompt):
        try:
            self.append_event(
                "worker.adapter.query",
                f"Query {self.backend_name}",
                {"backend": self.backend_name, "adapter": self.adapter_name},
            )
            return self._run(prompt, write_mode=False)[1]
        except Exception as exc:
            print(f"[ERROR] Agent CLI query failed: {exc}", file=sys.stderr)
            return ""

    def write(self, prompt):
        try:
            self.append_event(
                "worker.adapter.write",
                f"Write via {self.backend_name}",
                {"backend": self.backend_name, "adapter": self.adapter_name},
            )
            return self._run(prompt, write_mode=True)[0]
        except Exception as exc:
            print(f"[ERROR] Agent CLI write failed: {exc}", file=sys.stderr)
            return -1


class ClaudeWorkerAdapter(LocalCliWorkerAdapter):
    pass


class CodexWorkerAdapter(LocalCliWorkerAdapter):
    pass


class AiderWorkerAdapter(LocalCliWorkerAdapter):
    pass


class OpenClawWorkerAdapter(LocalCliWorkerAdapter):
    pass


class OpenHandsWorkerAdapter(LocalCliWorkerAdapter):
    pass


class MockWorkerAdapter(WorkerAdapter):
    def query(self, prompt):
        path = extract_target_path(prompt) or "target.py"
        self.append_timeline(
            "worker.query",
            f"mock-agent generated instruction for {path}",
            "success",
            {"target_file": path, "backend": self.backend_name},
        )
        self.append_event(
            "worker.adapter.query",
            f"Query {self.backend_name}",
            {"backend": self.backend_name, "adapter": self.adapter_name},
        )
        path = extract_target_path(prompt) or "target.py"
        if "Failure Details" in prompt:
            return f"Please fix the implementation in {path} so it satisfies the failing tests."
        return f"Please implement the functions in {path} according to the project goal and tests."

    def write(self, prompt):
        self.append_event(
            "worker.adapter.write",
            f"Write via {self.backend_name}",
            {"backend": self.backend_name, "adapter": self.adapter_name},
        )
        path = extract_target_path(prompt)
        if not path:
            self.append_timeline("worker.write", "mock-agent could not infer target file", "failed")
            print("[ERROR] mock-agent could not infer target file from prompt.", file=sys.stderr)
            return -1
        implementation = mock_implementation(path, prompt)
        if implementation is None:
            self.append_timeline("worker.write", f"mock-agent has no template for {path}", "failed", {"target_file": path})
            print(f"[ERROR] mock-agent has no template for {path}.", file=sys.stderr)
            return -1
        abs_path = os.path.abspath(os.path.join(self.draft_dir, path))
        if not abs_path.startswith(os.path.abspath(self.draft_dir)):
            self.append_timeline("worker.write", f"mock-agent refused unsafe path: {path}", "failed", {"target_file": path})
            print(f"[ERROR] mock-agent refused unsafe path: {path}", file=sys.stderr)
            return -1
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(implementation)
        print(f"[v1-Worker] [INFO] mock-agent wrote {path}")
        self.append_log(prompt, 0, [f"mock-agent wrote {path}\n"])
        self.append_timeline("worker.write", f"mock-agent wrote {path}", "success", {"target_file": path})
        return 0


def create_worker_adapter(agent, workspace_dir, draft_dir, log_path, runtime=None):
    if agent.is_mock:
        return MockWorkerAdapter(agent, workspace_dir, draft_dir, log_path, runtime)
    if agent.adapter == "claude":
        return ClaudeWorkerAdapter(agent, workspace_dir, draft_dir, log_path, runtime)
    if agent.adapter == "codex":
        return CodexWorkerAdapter(agent, workspace_dir, draft_dir, log_path, runtime)
    if agent.adapter == "aider":
        return AiderWorkerAdapter(agent, workspace_dir, draft_dir, log_path, runtime)
    if agent.adapter == "openclaw":
        return OpenClawWorkerAdapter(agent, workspace_dir, draft_dir, log_path, runtime)
    if agent.adapter == "openhands":
        return OpenHandsWorkerAdapter(agent, workspace_dir, draft_dir, log_path, runtime)
    return LocalCliWorkerAdapter(agent, workspace_dir, draft_dir, log_path, runtime)
