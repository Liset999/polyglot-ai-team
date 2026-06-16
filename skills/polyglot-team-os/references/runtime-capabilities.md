# Runtime Capabilities

## Commands

- `/run <goal>` delegates work to the selected worker.
- `/status` and `/board` inspect current task state.
- `/workspace` and `/repo` return deterministic workspace summaries.
- `/timeline` shows action/observation flow.
- `/packet` shows the latest worker task packet.
- `/report` returns the latest final report.
- `/handoff` writes and returns a compact continuation packet.
- `/steer <text>` changes the next worker prompt.
- `/pause`, `/resume`, and `/stop` write safe checkpoint controls.
- `/approval`, `/approve`, and `/deny` handle high-trust worker gates.
- `/lock` and `/unlock` inspect or clear local run locks.

## Session State

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

## Safety

- Do not expose `/run` to untrusted users.
- Do not expose `/approve` or `/unlock` remotely unless the host has its own operator allowlist.
- Prefer `FORCE_MOCK=1` for connectivity tests.
