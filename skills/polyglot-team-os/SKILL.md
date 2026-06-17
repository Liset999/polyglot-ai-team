---
name: polyglot-team-os
description: Route chat, coding goals, status checks, steering instructions, approval commands, and handoff requests into a local Polyglot AI Team OS runtime. Use when connecting Hermes, Lobster, Feishu, Codex, or another host to Polyglot; when a user asks to delegate work to local Claude/Codex/OpenCode workers through Polyglot; or when a host needs to inspect or continue a Polyglot session.
---

# Polyglot Team OS

## Purpose

Use this as a host integration skill. It is not the project README and not a runtime pitfall note.

Preferred usage:

- call Polyglot through MCP when the host supports MCP
- use the local bridge script only as a fallback path

This skill should teach the host agent when to call Polyglot and which Polyglot surface to use. It should not become a second copy of Polyglot runtime logic.

## Runtime Contract

For fallback bridge usage, the host must provide or discover the Polyglot workspace by one of these methods:

1. Pass `--workspace <path>` to `scripts/polyglot_skill_bridge.py`.
2. Set `POLYGLOT_WORKSPACE`.
3. Run the bridge from a directory that contains `polyglot_ai/`.

Use a stable session id per host/chat with `--session` or `POLYGLOT_SESSION`.

## Preferred MCP Surface

When MCP is available, prefer these runtime tools/resources instead of text-to-CLI bridging:

### MCP Tools

| Tool | Description |
|------|-------------|
| `polyglot_start_goal` | Start a delegated workflow with optional model/worker overrides |
| `polyglot_status` | Read current session status with team plan, control state, and approval info |
| `polyglot_get_task_board` | Get structured task board data for host rendering |
| `polyglot_steer` | Send steering instructions to an active run |
| `polyglot_pause` | Request pause at the next safe worker checkpoint |
| `polyglot_resume` | Resume a paused session |
| `polyglot_stop` | Request stop at the next safe worker checkpoint |
| `polyglot_get_report` | Retrieve the final or current run report |
| `polyglot_get_handoff` | Retrieve the continuation handoff pack |
| `polyglot_list_models` | List configured worker model profiles |
| `polyglot_refresh_model_registry` | Refresh the local model price registry |
| `polyglot_preview_plan` | Preview the team plan for a goal without starting work — Meta Planner output only |
| `polyglot_smoke` | Lightweight end-to-end verification of MCP surface before real work |

### MCP Resources

| Resource | Description |
|----------|-------------|
| `polyglot://session/{session}/status` | Current session status with detailed runtime info |
| `polyglot://session/{session}/task-board` | Structured task board state |
| `polyglot://session/{session}/run-state` | Raw persisted run state |
| `polyglot://session/{session}/timeline` | Recent timeline events |
| `polyglot://session/{session}/latest-packet` | Most recent task packet |
| `polyglot://session/{session}/report` | Saved run report (markdown) |
| `polyglot://session/{session}/handoff` | Saved session handoff pack |
| `polyglot://models` | Worker model profiles and capabilities |
| `polyglot://model-registry` | Local SuperCLUE price registry snapshot |
| `polyglot://workspace-summary` | Deterministic workspace summary |

### MCP Prompts

| Prompt | Description |
|--------|-------------|
| `teamwork-preview` | Preview how Polyglot would route and execute a goal |
| `debug-runtime` | Inspect current runtime state and control surface |
| `review-task-board` | Read the structured task board before taking action |
| `continue-from-handoff` | Resume from the latest saved handoff pack |

## Install Paths

If you are wiring this skill into a host, prefer the smallest installer that matches the host's needs:

| Installer | Purpose | Target |
|-----------|---------|--------|
| `scripts/install_host_bundle.ps1` | Generic skill + MCP installation | Any host |
| `scripts/install_mcp_config.ps1` | MCP registration only | Any host |
| `scripts/install_codex_host.ps1` | Codex-specific packaging | Codex |
| `scripts/install_skill.ps1` | Skill-only installation | Any host |
| `scripts/install_polyglot_launcher.ps1` | PATH-visible CLI launcher | All (optional) |

The host should use these install scripts instead of hand-editing scattered config files.

## Fallback Bridge Commands

```powershell
python scripts/polyglot_skill_bridge.py --workspace <polyglot_repo> --session hermes --text "/status"
python scripts/polyglot_skill_bridge.py --workspace <polyglot_repo> --session hermes --text "/run build a date converter with tests"
python scripts/polyglot_skill_bridge.py --workspace <polyglot_repo> --session hermes --text "hello"
```

Windows PowerShell hosts should prefer the repo-level wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\polyglot_skill_bridge.ps1 -Workspace <polyglot_repo> -Session hermes -Text "/status"
```

For longer or more complex Chinese prompts on Windows, prefer the file-based wrapper path:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\polyglot_skill_bridge.ps1 -Workspace <polyglot_repo> -Session hermes -TextFile <prompt.txt>
```

## Host Decision Rules

### When to Use Polyglot

Call Polyglot when the user asks for:

- multi-step coding work
- implementation with tests
- work that should continue after the first answer
- work that needs task state, steering, or handoff
- work requiring team planning or coordination
- work requiring approval gates before execution

### When NOT to Use Polyglot

Do not call Polyglot when the user asks for:

- hello / casual chat
- small explanation
- lightweight rewrite
- a one-command answer
- brainstorming with no workspace execution
- simple question-answering

## Fallback Message Routing

- `/run <goal>`: plan, delegate to the selected local worker, verify, and report.
- `/status`: show plan, run state, lock, steer, control, and approval.
- `/workspace` or `/repo`: show deterministic workspace summary.
- `/board`: show the structured task board.
- `/timeline`: show recent action/observation flow.
- `/packet`: show the latest worker packet.
- `/report`: show the latest final report.
- `/handoff`: write and return a compact continuation handoff.
- `/model`: inspect current worker profiles.
- `/steer <text>`: steer an active run.
- `/pause [text]`, `/resume [text]`, `/stop [text]`: control an active run.
- `/approval`, `/approve`, `/deny [reason]`: handle approval gates.
- `/lock`, `/unlock [reason]`: inspect or clear local run locks. Only expose `/unlock` to trusted operators.
- Any other text: call `MainAgent.chat_reply` without invoking a worker.

## Host Integration Guide

### Session Management

Hosts should:
- Use a unique session ID per conversation or user
- Use the `default` session only for shared interactions
- Call `/session-new <id>` for dedicated workspaces

### State Inspection Flow

For host UI rendering:
1. Call `polyglot_status` or read `polyglot://session/{session}/status`
2. Read `polyglot://session/{session}/task-board` for task visualization
3. Read `polyglot://session/{session}/timeline` for activity history
4. Read `polyglot://session/{session}/report` when run completes

### Error Handling

The MCP server returns explicit states:
- `ok: true` for success
- `blocked` status with reason for preflight failures
- `pending` approval status when confirmation is required
- Error codes for invalid input or missing resources

### Security Considerations

- `/unlock` should only be exposed to trusted operators
- `/approve` and `/deny` require user confirmation
- Sensitive data is redacted in logs and output

## References

Read `references/host-integration.md` when wiring this skill into Hermes, Lobster, Feishu, or a custom host.

Read `references/runtime-capabilities.md` when checking which Polyglot commands and state files are expected.
