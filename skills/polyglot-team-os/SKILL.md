---
name: polyglot-team-os
description: Route chat, coding goals, status checks, steering instructions, approval commands, and handoff requests into a local Polyglot AI Team OS runtime. Use when connecting Hermes, Lobster, Feishu, Codex, or another host to Polyglot; when a user asks to delegate work to local Claude/Codex/OpenCode workers through Polyglot; or when a host needs to inspect or continue a Polyglot session.
---

# Polyglot Team OS

## Purpose

Use this as a host integration skill. It is not the project README and not a runtime pitfall note.

This skill receives user text from a host, routes it into Polyglot's `MainAgent`, and returns a plain text reply that the host can send back to the user.

## Runtime Contract

The host must provide or discover the Polyglot workspace by one of these methods:

1. Pass `--workspace <path>` to `scripts/polyglot_skill_bridge.py`.
2. Set `POLYGLOT_WORKSPACE`.
3. Run the bridge from a directory that contains `polyglot_ai/`.

Use a stable session id per host/chat with `--session` or `POLYGLOT_SESSION`.

## Minimal Commands

```powershell
python scripts/polyglot_skill_bridge.py --workspace <polyglot_repo> --session hermes --text "/status"
python scripts/polyglot_skill_bridge.py --workspace <polyglot_repo> --session hermes --text "/run build a date converter with tests"
python scripts/polyglot_skill_bridge.py --workspace <polyglot_repo> --session hermes --text "hello"
```

## Message Routing

- `/run <goal>`: plan, delegate to the selected local worker, verify, and report.
- `/status`: show plan, run state, lock, steer, control, and approval.
- `/board`: show the structured task board.
- `/timeline`: show recent action/observation flow.
- `/packet`: show the latest worker packet.
- `/report`: show the latest final report.
- `/handoff`: write and return a compact continuation handoff.
- `/steer <text>`: steer an active run.
- `/pause [text]`, `/resume [text]`, `/stop [text]`: control an active run.
- `/approval`, `/approve`, `/deny [reason]`: handle approval gates.
- `/lock`, `/unlock [reason]`: inspect or clear local run locks. Only expose `/unlock` to trusted operators.
- Any other text: call `MainAgent.chat_reply` without invoking a worker.

## References

Read `references/host-integration.md` when wiring this skill into Hermes, Lobster, Feishu, or a custom host.

Read `references/runtime-capabilities.md` when checking which Polyglot commands and state files are expected.
