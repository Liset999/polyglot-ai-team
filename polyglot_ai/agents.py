import os
import json
import shutil
import shlex
from dataclasses import asdict, dataclass


@dataclass
class AgentInfo:
    name: str
    command: str
    path: str
    kind: str = "local-cli"
    adapter: str = "generic"
    source: str = "path"

    def to_dict(self):
        data = asdict(self)
        data.update(agent_capabilities(self.adapter))
        return data

    @property
    def is_mock(self):
        return self.kind == "mock"

    @property
    def backend_name(self):
        if self.is_mock:
            return "mock-agent"
        normalized = self.name.lower().replace(" ", "-")
        return f"{normalized}-cli"

    def command_parts(self):
        if self.is_mock:
            return []
        if self.kind == "configured-cli":
            return split_command(self.command)
        return [self.path]

    def build_command(self, prompt, write_mode=False):
        base = self.command_parts()
        command = self.command.lower()
        name = self.name.lower()
        if "claude" in name or command == "claude":
            cmd = base + ["-p", prompt]
            if write_mode:
                cmd += ["--permission-mode", "bypassPermissions"]
            return cmd
        if "codex" in name or command == "codex":
            return base + ["exec", prompt]
        if "aider" in name or command == "aider":
            return base + ["--message", prompt]
        return base + [prompt]


KNOWN_AGENT_COMMANDS = [
    ("Claude Code", "claude", "claude"),
    ("Codex", "codex", "codex"),
    ("OpenCode", "opencode", "opencode"),
    ("OpenClaw", "openclaw", "openclaw"),
    ("OpenDevin", "opendevin", "openhands"),
    ("Aider", "aider", "aider"),
    ("OpenHands", "openhands", "openhands"),
    ("CrewAI", "crewai", "crewai"),
    ("AutoGPT", "agpt", "autogpt"),
    ("Task Master", "task-master", "task-master"),
]


AGENT_CAPABILITIES = {
    "claude": {
        "best_for": ["coding", "repo edits", "test repair"],
        "permission_profile": "local-write",
        "routing_hint": "default coding worker when installed",
    },
    "codex": {
        "best_for": ["coding", "repo edits", "terminal tasks"],
        "permission_profile": "local-write",
        "routing_hint": "coding worker alternative",
    },
    "opencode": {
        "best_for": ["coding", "terminal agent workflows"],
        "permission_profile": "local-write",
        "routing_hint": "coding worker alternative",
    },
    "openclaw": {
        "best_for": ["gateway", "long-running assistant", "message channels"],
        "permission_profile": "high-trust-local",
        "routing_hint": "future channel/gateway worker, not default fill-code worker",
    },
    "openhands": {
        "best_for": ["sandboxed execution", "action-observation loops"],
        "permission_profile": "sandbox-preferred",
        "routing_hint": "future isolated runtime worker",
    },
    "aider": {
        "best_for": ["git-aware edits", "patch workflows"],
        "permission_profile": "local-write",
        "routing_hint": "future git-aware edit worker",
    },
    "crewai": {
        "best_for": ["role flows", "multi-agent vocabulary"],
        "permission_profile": "planner-only",
        "routing_hint": "reference pattern, not default worker",
    },
    "autogpt": {
        "best_for": ["autonomous workflows"],
        "permission_profile": "high-trust-local",
        "routing_hint": "future optional worker",
    },
    "task-master": {
        "best_for": ["task graph", "dependency tracking"],
        "permission_profile": "state-management",
        "routing_hint": "future task-board importer/exporter",
    },
    "mock": {
        "best_for": ["offline verification", "tests"],
        "permission_profile": "no-external-side-effects",
        "routing_hint": "fallback for development and CI",
    },
    "generic": {
        "best_for": ["unknown"],
        "permission_profile": "ask-before-use",
        "routing_hint": "manual review recommended",
    },
}


def agent_capabilities(adapter):
    return AGENT_CAPABILITIES.get(adapter, AGENT_CAPABILITIES["generic"])


def split_command(command_text):
    if os.name == "nt":
        return shlex.split(command_text, posix=False)
    return shlex.split(command_text)


def agent_config_path(env=None):
    env = env or os.environ
    configured = env.get("POLYGLOT_AGENT_CONFIG")
    if configured:
        return configured
    workspace = env.get("POLYGLOT_WORKSPACE") or os.getcwd()
    return os.path.join(workspace, "polyglot_agents.json")


def read_agent_config(env=None):
    path = agent_config_path(env)
    if not os.path.exists(path):
        return {"path": path, "agents": [], "default": ""}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"path": path, "agents": [], "default": "", "_error": "config root must be an object"}
        data.setdefault("agents", [])
        data.setdefault("default", "")
        data["path"] = path
        return data
    except Exception as exc:
        return {"path": path, "agents": [], "default": "", "_error": str(exc)}


def configured_agents(env=None):
    config = read_agent_config(env)
    agents = []
    for item in config.get("agents", []):
        if not isinstance(item, dict):
            continue
        if item.get("enabled", True) is False:
            continue
        name = item.get("name") or item.get("command") or "Configured Agent"
        command = item.get("command") or item.get("path") or ""
        if not command:
            continue
        adapter = item.get("adapter") or "generic"
        path = item.get("path") or command
        kind = item.get("kind") or "configured-cli"
        agents.append(AgentInfo(name, command, path, kind, adapter, source=config.get("path", "config")))
    return agents


def discover_agents(env=None):
    env = env or os.environ
    agents = []

    agents.extend(configured_agents(env))

    configured_claude = env.get("POLYGLOT_CLAUDE_CMD")
    if configured_claude:
        agents.append(AgentInfo("Claude Code", configured_claude, configured_claude, "configured-cli", "claude", "env"))

    for name, command, adapter in KNOWN_AGENT_COMMANDS:
        path = shutil.which(command)
        if path and not any(agent.command == command for agent in agents):
            agents.append(AgentInfo(name, command, path, "local-cli", adapter, "path"))

    return agents


def select_agent(env=None):
    env = env or os.environ
    if env.get("FORCE_MOCK"):
        return AgentInfo("mock-agent", "mock", "built-in", "mock", "mock")
    requested = env.get("POLYGLOT_AGENT", "auto").strip().lower()
    if requested in ("mock", "offline"):
        return AgentInfo("mock-agent", "mock", "built-in", "mock", "mock")
    agents = discover_agents(env)
    if requested and requested != "auto":
        for agent in agents:
            if requested in agent.name.lower() or requested == agent.command.lower():
                return agent
    config = read_agent_config(env)
    default_name = (config.get("default") or "").strip().lower()
    if default_name:
        for agent in agents:
            if default_name in agent.name.lower() or default_name == agent.command.lower():
                return agent
    if agents:
        return agents[0]
    return AgentInfo("mock-agent", "mock", "built-in", "mock", "mock")
