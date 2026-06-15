# Polyglot AI Team OS v2

Polyglot AI Team OS is a terminal-first, local-agent-first AI team runtime.

It keeps a durable **main agent session** alive, routes real engineering work to local CLI workers such as Claude Code/Codex/OpenCode, records structured task state, supports human steering during a run, and can be driven from CLI, Feishu, Hermes, Lobster, or any webhook-style host.

The project is intentionally small and incremental: make the local session loop solid first, then add integrations as thin adapters.

## What It Does

- Keeps a main agent conversation alive after a worker run finishes.
- Answers lightweight chat without calling Claude.
- Uses `/run <goal>` to intentionally delegate work to a selected local worker.
- Generates a team plan, task packets, timeline, task board, final report, and handoff.
- Supports `/steer`, `/pause`, `/resume`, and `/stop` while work is running.
- Discovers local CLI agents and can fall back to a mock worker for safe tests.
- Exposes a token-protected HTTP listener for Hermes/Feishu-style remote control.
- Ships a reusable Codex skill at `skills/polyglot-team-os`.

## Quick Start

```powershell
cd D:\Repository\polyglot-ai-team
python .\polyglot_cli.py doctor
python .\polyglot_cli.py
```

Inside the CLI:

```text
hello
/agents
/route build a date converter
/run build a date converter with unit tests
/status
/board
/timeline
/report
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

## Core Commands

```text
/run <goal>          Plan, delegate, verify, self-heal, and report.
/plan <goal>         Create the team plan without running a worker.
/route <goal>        Explain which worker would be selected and why.
/status             Show plan, run state, lock, steer, control, approval.
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
/about              Show runtime, interface, and worker self-knowledge.
```

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

The runtime can discover common local CLIs on `PATH`, including Claude Code, Codex, OpenCode, and OpenClaw. You can also configure agents with `polyglot_agents.json`.

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
/status
/agents
/events
hello
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

## Codex Skill

This repo includes a reusable skill:

```text
skills/polyglot-team-os/
```

Install into Codex:

```powershell
copy .\skills\polyglot-team-os C:\Users\ROG\.codex\skills\polyglot-team-os -Recurse
```

The skill exposes a bridge script:

```powershell
python C:\Users\ROG\.codex\skills\polyglot-team-os\scripts\polyglot_skill_bridge.py --session hermes --text "/status"
```

Python hosts can import it:

```python
import sys
sys.path.insert(0, r"C:\Users\ROG\.codex\skills\polyglot-team-os\scripts")

from polyglot_skill_bridge import handle_text

reply = handle_text("/status", session_id="hermes")
```

## Safety Notes

- Do not expose the listener without `X-Polyglot-Token`.
- Use a long random token, not `test-123456`, for real use.
- Keep `--host 127.0.0.1` when using Cloudflare Tunnel or ngrok.
- Do not let untrusted users trigger `/run`, `/approve`, or `/unlock`.
- High-trust or ambiguous local agents require approval before execution.
- Use `FORCE_MOCK=1` for integration tests that should not call external workers.

## Validation

Run:

```powershell
python .\polyglot_cli.py doctor
python C:\Users\ROG\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\skills\polyglot-team-os
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

The current design follows the project blueprint in `ai-team-os-v2-merged.pdf` and the extracted notes in `pdf_content_v2.txt`.

See:

```text
docs/research/open-source-fusion.md
```

for the OpenClaw, Claude Code, Aider, OpenHands, CrewAI, ClawSwarm, and Multica-inspired fusion plan.
