# Polyglot AI Team OS v2

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-106%20passed-brightgreen.svg)](#)
[![MCP](https://img.shields.io/badge/MCP-18%20tools-orange.svg)](skills/polyglot-team-os/SKILL.md)

Polyglot AI Team OS is a local-first AI team runtime with a Model Context Protocol (MCP) surface. It runs as a runtime layer between a host agent (Codex, Claude Code, Antigravity, Hermes…) and local execution workers (Claude CLI, shell scripts, mock).

The intended product shape is:

- host client = the main agent and chat surface
- Polyglot = the runtime that host agent calls
- local workers = the execution layer behind Polyglot

That means Codex, WorkBuddy, Antigravity, Hermes, Claude Code, and similar clients are the natural host layer. Polyglot should not become a second chat client.

The CLI remains useful, but mainly as:

- local setup
- worker model configuration
- debug / fallback
- runtime inspection and manual control

Canonical architecture and roadmap:

- `docs/architecture-roadmap.md`
- `docs/vnext-host-runtime.md`
- `docs/mcp-server-minimal-spec.md`
- `docs/host-install-flow.md`
- `docs/codex-host-integration.md`

Host-facing install artifacts:

- `.codex-plugin/plugin.json`
- `configs/codex/mcp.json.example`
- `configs/mcp.json.example`
- `scripts/install_codex_host.ps1`
- `scripts/install_host_bundle.ps1`
- `scripts/install_mcp_config.ps1`
- `scripts/install_polyglot_launcher.ps1`
- `scripts/install_skill.ps1`
- `polyglot_mcp_server.py`

Model config locations:

- default launcher config: `%USERPROFILE%\polyglot_models.json`
- repo-local fallback: `D:\Repository\polyglot-ai-team\polyglot_models.json`
- override: `POLYGLOT_MODEL_CONFIG`

Note: encrypted API keys use Windows DPAPI, so the same Windows user context that saves the key must also read it back. If you copy the config to another account or run inside an isolated sandbox, `doctor` may report a decryption failure even though the file itself is valid.

Codex-first local install example:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_codex_host.ps1 -DryRun
```

## What It Does

- Keeps a main agent conversation alive after a worker run finishes.
- Answers lightweight chat without calling Claude.
- Lets you type normally; task-like messages auto-delegate to the selected local worker.
- Keeps `/chat` for chat-only messages and `/run <goal>` for forced execution.
- Generates a team plan, task packets, timeline, task board, final report, and handoff.
- Supports `/steer`, `/pause`, `/resume`, and `/stop` while work is running.
- Discovers local CLI agents and uses the mock worker only when explicitly requested for safe tests.
- Exposes a token-protected HTTP listener for Hermes/Feishu-style remote control.
- Ships a reusable Codex skill at `skills/polyglot-team-os`.

## Recommended Path

The intended first-use path is host-first:

1. Start in a host client such as Codex.
2. Configure the host model there.
3. Give the Polyglot GitHub repo URL to the host agent.
4. Let the host agent install:
   - the repo
   - runtime dependencies
   - MCP configuration
   - skills/plugin integration
5. Install the Polyglot launcher if you want a PATH-visible `polyglot` command from any directory.
6. Use the local Polyglot CLI only for worker-model configuration.

## MCP Quick Start

Connect any MCP-compatible host agent to Polyglot. After [MCP server setup](#host-facing-install-artifacts), you have 18 tools available:

### Start and Monitor

```json
// 1. Preview plan without running (read-only)
{"tool": "polyglot_preview_plan", "goal": "build a date diff utility with tests"}

// 2. Start a session
{"tool": "polyglot_start_goal", "goal": "build a date diff utility with tests"}

// 3. Poll status
{"tool": "polyglot_status"}

// 4. Get task board
{"tool": "polyglot_get_task_board"}

// 5. Get final report
{"tool": "polyglot_get_report"}

// 6. Get handoff pack (for continuation)
{"tool": "polyglot_get_handoff"}
```

### Control

```json
// Steer the running worker
{"tool": "polyglot_steer", "message": "switch to using Python 3.11 syntax"}

// Pause at next checkpoint
{"tool": "polyglot_pause"}

// Resume
{"tool": "polyglot_resume"}

// Stop
{"tool": "polyglot_stop"}
```

### Model Management

```json
// List available models
{"tool": "polyglot_list_models"}

// Refresh price registry
{"tool": "polyglot_refresh_model_registry"}

// Smoke test before real work
{"tool": "polyglot_smoke"}
```

Low-cost default:

- keep the main conversation in your host client
- use local Claude Code as the execution container
- prefer `haiku` mapped to `gpt-5.4-mini` when DeepSeek is unavailable or you want cheaper sidecar work

See:

- `docs/host-install-flow.md`
- `docs/architecture-roadmap.md`

Host-side MCP quick probes:

- `polyglot://models`
- `polyglot://model-registry`
- `polyglot_status`
- `polyglot_get_task_board`
- `polyglot://workspace-summary`
- `polyglot_list_models`
- `polyglot_refresh_model_registry`
- `polyglot_smoke`
- `polyglot://session/{session}/status`
- `polyglot://session/{session}/task-board`
- `polyglot://session/{session}/run-state`
- `polyglot://session/{session}/timeline`
- `polyglot://session/{session}/latest-packet`
- `polyglot://session/{session}/report`
- `polyglot://session/{session}/handoff`
- `polyglot_get_report`
- `polyglot_get_handoff`
- `continue-from-handoff`

Host-side MCP prompts:

- `teamwork-preview`
- `debug-runtime`
- `review-task-board`
- `continue-from-handoff`

## CLI Fallback Quick Start

```powershell
cd D:\Repository\polyglot-ai-team
python .\polyglot_cli.py setup
python .\polyglot_cli.py doctor
python .\polyglot_cli.py
```

After installing `scripts/install_polyglot_launcher.ps1`, you can use the same commands from any directory as:

```powershell
polyglot setup
polyglot doctor
polyglot
```

The launcher writes `POLYGLOT_WORKSPACE` and `POLYGLOT_MODEL_CONFIG` for you, so it can find the repo and your user-level model config from any directory.

Direct one-shot entrypoints `python .\polyglot_cli.py setup` and `python .\polyglot_cli.py config` are available again for local worker setup.

Repo-level host bridge entrypoints are also available:

```powershell
python .\scripts\polyglot_skill_bridge.py --workspace D:\Repository\polyglot-ai-team --session local --text "/status"
powershell -ExecutionPolicy Bypass -File .\scripts\polyglot_skill_bridge.ps1 -Workspace D:\Repository\polyglot-ai-team -Session local -Text "hello"
```

On Windows PowerShell, prefer the `.ps1` wrapper instead of calling Python bridge scripts directly. The wrapper now preserves Chinese prompt text correctly through the live runtime path and session files when you use `-Text`.

For longer or more complex Chinese prompts on Windows, prefer the file-based path:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\polyglot_skill_bridge.ps1 -Workspace D:\Repository\polyglot-ai-team -Session local -TextFile D:\path\to\prompt.txt
```

Inside the CLI:

```text
hello
写一个日期转换工具，先别写代码，先说计划
board
report
/setup
/config
/agents
/route build a date converter
/chat where are we
/status
/view board
/workspace
/timeline
```

After a run, plain chat such as `report` or `summary` reads the saved final report without starting a worker.

This CLI is the local fallback/debug shell. It is not the intended primary product chat surface.

If you prefer explicit execution only:

```powershell
$env:POLYGLOT_AUTO_DELEGATE="0"
python .\polyglot_cli.py
```

One-shot commands:

```powershell
python .\polyglot_cli.py status
python .\polyglot_cli.py agents
python .\polyglot_cli.py run "build a date converter with unit tests"
```

Use mock mode when you want to test the runtime without calling Claude:

```powershell
python .\polyglot_cli.py run FORCE_MOCK=1 "build a hello function with tests"
```

Normal auto-delegation and forced `/run` share two independent preflights:

- `worker=ok`: a local execution container such as Claude Code is installed, discoverable on `PATH`, or configured with `POLYGLOT_CLAUDE_CMD`.
- `model=ok`: the selected model profile has a usable encrypted key saved by `/config`; provider env vars remain fallback compatibility only.

If the model key is present but Claude Code is missing, Polyglot will not silently run the mock worker. It returns `[PREFLIGHT BLOCKED]` and tells you which layer to fix.

## Core Commands

```text
<message>            Talk normally; engineering tasks auto-delegate.
/chat <message>      Force chat without calling a worker.
/view <name>         Open a saved view such as status/board/timeline/report.
/run <goal>          Force plan, delegate, verify, self-heal, and report.
/plan <goal>         Create the team plan without running a worker.
/route <goal>        Explain which worker would be selected and why.
/status             Show plan, run state, lock, steer, control, approval.
/workspace          Show deterministic workspace summary.
/board              Show the structured task board.
/packet             Show the latest task packet sent to a worker.
/timeline           Show recent action/observation events.
/report             Show the latest final report.
/handoff            Write and show a compact continuation packet.
/history            Show main-agent conversation history.
/steer <message>    Send a steering instruction to the active run.
/pause [message]    Pause at the next safe worker checkpoint.
/resume [message]   Resume a paused worker.
/stop [message]     Stop at the next safe worker checkpoint.
/approval           Show pending high-trust worker approval.
/approve            Approve a pending high-trust run.
/deny [reason]      Deny a pending high-trust run.
/lock               Inspect the active run lock.
/unlock [reason]    Clear a stale local run lock.
/sessions           List local sessions.
/session-new <id>   Create a new session.
/agents             Show discovered local workers.
/setup             Check first-run readiness and next steps.
 /config            Add/edit encrypted custom models.
/about              Show runtime, interface, and worker self-knowledge.
```

In the REPL, bare saved-view names also work, so you can type `board`, `report`, `timeline`, `history`, or `latest` directly without adding `/view`.

For the cheapest real path, use `setup`, `config`, `doctor`, and then either:

```powershell
python .\scripts\polyglot_skill_bridge.py --workspace D:\Repository\polyglot-ai-team --session local --text "hello"
python .\polyglot_cli.py run "build a tiny utility with tests"
```

When DeepSeek is unavailable, prefer local Claude Code with `haiku -> gpt-5.4-mini` on your compatible host/proxy setup.

## Sessions

Use `POLYGLOT_SESSION` to keep different chats or integrations isolated:

```powershell
$env:POLYGLOT_SESSION="demo"
python .\polyglot_cli.py
```

Session state lives under:

```text
artifacts/sessions/<session_id>/
```

Important files:

```text
team_plan.json
run_state.json
events.jsonl
timeline.jsonl
messages.jsonl
task_packets.jsonl
final_report.md
handoff.md
artifacts/
```

## Local Agent Discovery

Run:

```powershell
python .\polyglot_cli.py agents
```

The runtime can discover common local CLIs on `PATH`, including Claude Code, Codex, OpenCode, and OpenClaw. For MVP execution, auto-routing intentionally uses **Claude Code only**. Other CLIs remain visible in `/agents` as future integration candidates, but they do not take over `/run` unless explicitly requested.

For Claude Code, `doctor` should show a line like:

```text
run preflight: worker=ok; model=ok
```

If `worker` is not `ok`, install Claude Code, put `claude` on `PATH`, or set:

```powershell
$env:POLYGLOT_CLAUDE_CMD="C:\path\to\claude.cmd"
```

Start from the example:

```powershell
copy .\polyglot_agents.example.json .\polyglot_agents.json
```

Example:

```json
{
  "default": "Claude Code",
  "agents": [
    {
      "name": "Claude Code",
      "command": "claude",
      "adapter": "claude",
      "enabled": true
    }
  ]
}
```

Force a worker for one command:

```powershell
python .\polyglot_cli.py run POLYGLOT_AGENT=claude "build a small utility with tests"
```

Run the same Claude Code worker against one or more configured model profiles:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_claude_models.ps1 -ProbeOnly
powershell -ExecutionPolicy Bypass -File .\scripts\start_claude_models.ps1 -Profiles minimax-m3 -Goal "Build a tiny hello_name function and report which model profile was used."
```

The starter script now only launches configured, enabled profiles that you name explicitly. Configure keys through `/config`; environment variables are only a fallback.

## Model Profiles

Claude Code can be used as an execution container while the actual model endpoint is selected by a Polyglot profile.

This is the intended two-layer setup:

```text
Polyglot main agent -> Claude Code CLI worker -> Anthropic-compatible endpoint selected by profile
```

So `DEEPSEEK_API_KEY=set` proves the model endpoint can authenticate; it does not by itself prove that the local Claude Code execution container is installed and runnable.

If DeepSeek is unavailable or you want the cheapest sidecar path, keep Claude Code as the local execution container and prefer `haiku` mapped to `gpt-5.4-mini` on your compatible host/proxy setup.

Recommended first-use flow:

```powershell
python .\polyglot_cli.py setup
python .\polyglot_cli.py config
python .\polyglot_cli.py doctor
```

Inside `/config`, first-run setup is custom-only. Add your own encrypted model profile and point it at your relay URL and model name.

The profile file stores `api_key_encrypted` when configured through `/config`. Older `api_key_env` profiles still work as a fallback, but the CLI-first path is preferred. When the worker starts Claude Code, Polyglot maps the selected profile into the child process as `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, `API_TIMEOUT_MS`, and `CLAUDE_CODE_ENABLE_MCP_UNOFFICIAL`.

Profile selection:

```powershell
python .\polyglot_cli.py model minimax-m3
python .\polyglot_cli.py route "build a small utility with tests"
python .\polyglot_cli.py run "build a small utility with tests"
```

If `POLYGLOT_MODEL_PROFILE` is not set, the main agent auto-routes among enabled, key-ready profiles. It only considers models you have already configured.

Current scoring inputs:

- task shape: simple chat/summary vs coding vs agent/planning
- profile capabilities: `chat`, `simple-code`, `coding`, `repair`, `agent`, `long-context`, `planning`
- local SuperCLUE snapshot: blended price and overall latency
- profile cost tier: `low` vs `pro`

To inspect the currently selected profile and route:

```powershell
python .\polyglot_cli.py model
python .\polyglot_cli.py route "hello"
```

Explicit selection still wins:

```powershell
python .\polyglot_cli.py model gpt-5.4-mini
python .\polyglot_cli.py route "build a small utility with tests"
```

## Model Registry And Pricing

Polyglot keeps model routing local-first and can still use the checked-in model registry snapshot when choosing among configured profiles.

```powershell
python .\polyglot_cli.py model
python .\polyglot_cli.py route "build a small utility with tests"
```

Current sync source:

```text
https://www.superclueai.com/data/latency_and_price/2026骞?鏈坃2.xlsx
```

Policy:

- `polyglot_refresh_model_registry` refreshes the local SuperCLUE snapshot on demand for host clients.
- `/run` refreshes the registry once before task routing when the local snapshot is missing or stale.
- `/config` refreshes the registry after an interactive profile add/edit/delete/switch.
- Chat, `/status`, `/route`, self-heal loops, and worker retries do not repeatedly scrape SuperCLUE.
- If SuperCLUE is unavailable, Polyglot keeps using the last local snapshot and emits a warning.

The checked-in `polyglot_models.example.json` intentionally starts empty so you can add the worker models you want through `/config`. First-run setup is custom-only; the repo does not pre-bake GPT or MiniMax as canonical presets.

## Hermes Or Lobster Integration

The simplest integration is HTTP: Hermes sends user text to the local listener and returns the `reply` field to chat.

Start the local listener:

```powershell
cd D:\Repository\polyglot-ai-team
powershell -ExecutionPolicy Bypass -File .\start_feishu.ps1 -Session hermes-remote -HostName 127.0.0.1 -Token "replace-with-a-long-secret"
```

Expose it with Cloudflare Tunnel:

```powershell
cloudflared tunnel --url http://127.0.0.1:8787
```

Hermes server request:

```bash
curl -X POST https://your-trycloudflare-url.trycloudflare.com \
  -H "Content-Type: application/json" \
  -H "X-Polyglot-Token: replace-with-a-long-secret" \
  -d '{"text":"/status"}'
```

Response shape:

```json
{
  "ok": true,
  "text": "/status",
  "session": "hermes-remote",
  "reply": "Polyglot Task Board\nsession: hermes-remote\n..."
}
```

Hermes should send `reply` back to the user:

```python
resp = requests.post(
    POLYGLOT_URL,
    headers={"X-Polyglot-Token": POLYGLOT_TOKEN},
    json={"text": user_text},
    timeout=120,
)
return resp.json()["reply"]
```

Recommended first probes:

```text
/help
/status
/board
/report
/model
/agents
/events
/diff
hello
/plan build a date converter
/route build a date converter
```

Only allow trusted users to trigger `/run`.

## Feishu / HTTP Listener

The HTTP listener accepts JSON payloads like:

```json
{"text": "/status"}
```

Start in dry-run mode:

```powershell
python .\feishu_listener.py --host 127.0.0.1 --port 8787 --session demo --token "replace-with-a-long-secret" --dry-run
```

POST locally:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8787 `
  -Headers @{"X-Polyglot-Token"="replace-with-a-long-secret"} `
  -ContentType "application/json" `
  -Body '{ "text": "/status" }'
```

Remote `/unlock` is disabled by default. Enable it only for trusted private environments:

```powershell
python .\feishu_listener.py --allow-unlock
```

## Host Skills

This repo includes a reusable skill:

```text
skills/polyglot-team-os/
```

Dry-run the installer first:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_skill.ps1 -Scope codex-global -DryRun
powershell -ExecutionPolicy Bypass -File .\scripts\install_skill.ps1 -Scope antigravity-cli-global -DryRun
powershell -ExecutionPolicy Bypass -File .\scripts\install_skill.ps1 -Scope antigravity-app-global -DryRun
```

The installer targets common host skill paths such as `.codex\skills\polyglot-team-os`, `.gemini\antigravity-cli\skills\polyglot-team-os`, `.gemini\config\plugins\polyglot-team-os\skills\polyglot-team-os`, `.agents\skills\polyglot-team-os`, and project-local `.agent\skills\polyglot-team-os`.

Install into Codex:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_skill.ps1 -Scope codex-global
```

Install into Antigravity CLI global skills:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_skill.ps1 -Scope antigravity-cli-global
```

Install as an Antigravity app plugin:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_skill.ps1 -Scope antigravity-app-global
```

Optional Antigravity CLI status line:

```json
{
  "statusLine": {
    "type": "",
    "command": "powershell -ExecutionPolicy Bypass -File D:\\Repository\\polyglot-ai-team\\scripts\\polyglot_statusline.ps1 -Workspace D:\\Repository\\polyglot-ai-team -Session default",
    "enabled": true
  }
}
```

Smoke test it locally:

```powershell
'{"cwd":"D:\\Repository\\polyglot-ai-team","terminal_width":120}' | powershell -ExecutionPolicy Bypass -File .\scripts\polyglot_statusline.ps1 -Workspace D:\Repository\polyglot-ai-team -Session default
```

Project-local installs:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_skill.ps1 -Scope agents-project -Target D:\Repository\polyglot-ai-team
powershell -ExecutionPolicy Bypass -File .\scripts\install_skill.ps1 -Scope agent-project -Target D:\Repository\polyglot-ai-team
```

The skill exposes a bridge script:

```powershell
python .\scripts\polyglot_skill_bridge.py --workspace D:\Repository\polyglot-ai-team --session hermes --text "/status"
```

Python hosts can import it:

```python
import sys
sys.path.insert(0, r".\skills\polyglot-team-os\scripts")

from polyglot_skill_bridge import handle_text

reply = handle_text("/status", session_id="hermes")
```

## Safety Notes

- Do not expose the listener without `X-Polyglot-Token`.
- Use a long random token, not `test-123456`, for real use.
- Keep `--host 127.0.0.1` when using Cloudflare Tunnel or ngrok.
- Do not let untrusted users trigger `/run`, `/approve`, or `/unlock`.
- Use remote `/cancel` to clear an accidental pending `/steer` instruction before the next worker checkpoint.
- High-trust or ambiguous local agents require approval before execution.
- Use `FORCE_MOCK=1` for integration tests that should not call external workers.

## Validation

Run:

```powershell
python .\polyglot_cli.py doctor
python .\scripts\polyglot_skill_bridge.py --workspace D:\Repository\polyglot-ai-team --session validate --text "/status"
```

Smoke test:

```powershell
python .\polyglot_cli.py run FORCE_MOCK=1 "build a hello function with tests"
```

## Project Map

```text
polyglot_cli.py                  Main terminal session.
monitor.py                       Live terminal monitor around planner/worker.
steer.py                         Standalone steering/status CLI.
status.py                        Read-only task board view.
feishu_listener.py               Token-protected HTTP listener.
feishu_bridge.py                 Text command router for IM-style hosts.
start_feishu.ps1                 One-command Windows listener launcher.
polyglot_ai/runtime.py           Session state, events, locks, handoff, artifacts.
polyglot_ai/main_agent.py        Shared main-agent control layer.
polyglot_ai/agents.py            Local worker discovery and registry.
polyglot_ai/worker_adapters.py   Worker CLI adapters and mock adapter.
polyglot_ai/v0_planner.py        Goal to tests/scaffold planner.
polyglot_ai/v1_worker.py         Runtime orchestrator and self-healing loop.
polyglot_ai/task_board.py        Structured task board renderer.
polyglot_ai/task_packet.py       Worker delegation packet builder.
docs/research/                   Architecture notes and project comparisons.
skills/polyglot-team-os/         Installable skill bridge.
```

## Architecture Notes

The current development direction is anchored by the latest planning PDFs:

```text
polyglot-ai-team-dev-plan-v5.pdf
polyglot-ai-team-dev-plan-v5.txt
polyglot-main-agent-no-extra-llm-styled.pdf
polyglot-main-agent-no-extra-llm-styled.txt
```

The older `ai-team-os-v2-merged.pdf` and `pdf_content_v2.txt` remain as historical blueprint material.

See:

```text
docs/research/open-source-fusion.md
```

for the OpenClaw, Claude Code, Aider, OpenHands, CrewAI, ClawSwarm, and Multica-inspired fusion plan.
