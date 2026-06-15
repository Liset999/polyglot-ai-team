---
name: polyglot-team-os
description: Route chat, coding goals, status checks, steering instructions, and handoff requests into the user's local Polyglot AI Team OS runtime. Use when the user wants to invoke Polyglot, connect Hermes, Lobster, Feishu, or IM messages to Polyglot, delegate work to local Claude/Codex/OpenCode workers, inspect Polyglot sessions, or continue a Polyglot main-agent conversation.
---

# Polyglot Team OS

## Quick Use

Use the local project at `D:\Repository\polyglot-ai-team` as the runtime root unless the user provides another path.

For direct command-line use, run:

```powershell
python C:\Users\ROG\.codex\skills\polyglot-team-os\scripts\polyglot_skill_bridge.py --text "/status"
```

For a coding task:

```powershell
python C:\Users\ROG\.codex\skills\polyglot-team-os\scripts\polyglot_skill_bridge.py --session work --text "/run build a date converter with tests"
```

For lightweight chat, do not call a worker:

```powershell
python C:\Users\ROG\.codex\skills\polyglot-team-os\scripts\polyglot_skill_bridge.py --text "hello"
```

## Message Routing

Route user text through `scripts/polyglot_skill_bridge.py` when the user wants Polyglot behavior from another host such as Hermes, Lobster, Feishu, WeChat, or a custom CLI.

Supported messages:

- `/run <goal>`: plan, delegate to the selected local worker, verify, and report.
- `/status`: show plan, run state, lock, steer, control, and approval.
- `/board`: show structured task board.
- `/timeline`: show recent action/observation flow.
- `/packet`: show latest worker packet.
- `/report`: show latest final report.
- `/handoff`: write and return a compact continuation handoff.
- `/steer <text>`: steer an active run.
- `/pause [text]`, `/resume [text]`, `/stop [text]`: control an active run.
- `/approval`, `/approve`, `/deny [reason]`: handle high-trust worker approvals.
- `/lock`, `/unlock [reason]`: inspect or clear stale run locks.
- Any other text: route to `MainAgent.chat_reply` without calling a worker.

## Embedding In Hermes Or Lobster

Prefer importing the bridge instead of shelling out when the host is Python:

```python
from pathlib import Path
import sys

skill_scripts = Path(r"C:\Users\ROG\.codex\skills\polyglot-team-os\scripts")
sys.path.insert(0, str(skill_scripts))

from polyglot_skill_bridge import handle_text

def on_message(text: str) -> str:
    return handle_text(text, session_id="hermes")
```

If the host is not Python, call the script as a subprocess and use stdout as the reply.

## Safety Defaults

Keep normal chat inside the main agent. Only `/run` should delegate intentionally.

Use a stable session id per host or chat:

- `hermes` for Hermes global room.
- `lobster` for Lobster global room.
- `feishu-<group-id>` for Feishu groups.

If a run crashes and future `/run` calls return `[BUSY]`, inspect `/lock` first and only use `/unlock` when the process is stale.

## Runtime Assumptions

The bridge expects:

- `D:\Repository\polyglot-ai-team\polyglot_ai\runtime.py`
- `D:\Repository\polyglot-ai-team\polyglot_ai\main_agent.py`
- Python available on PATH.

If the runtime lives somewhere else, pass `--workspace <path>` or set `POLYGLOT_WORKSPACE`.
