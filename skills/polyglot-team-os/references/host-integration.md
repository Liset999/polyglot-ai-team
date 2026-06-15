# Host Integration

## Workspace Discovery

Prefer configuration over hardcoded paths.

Priority:

1. Host passes `--workspace <polyglot_repo>`.
2. Host sets `POLYGLOT_WORKSPACE`.
3. Host runs the bridge from the Polyglot repo root.

Local Windows example:

```powershell
$env:POLYGLOT_WORKSPACE="D:\Repository\polyglot-ai-team"
```

Linux server example:

```bash
export POLYGLOT_WORKSPACE=/opt/polyglot-ai-team
```

## Python Host

```python
import sys

sys.path.insert(0, "/path/to/skills/polyglot-team-os/scripts")

from polyglot_skill_bridge import handle_text

def on_message(text: str, user_id: str) -> str:
    return handle_text(
        text,
        session_id=f"hermes-{user_id}",
        workspace="/path/to/polyglot-ai-team",
    )
```

## Non-Python Host

Run the bridge as a subprocess:

```bash
python /path/to/skills/polyglot-team-os/scripts/polyglot_skill_bridge.py \
  --workspace /path/to/polyglot-ai-team \
  --session hermes \
  --text "/status"
```

Read stdout and send it back to the chat.

## HTTP Host Alternative

If Polyglot runs on another machine, call its token-protected listener instead of importing this bridge:

```bash
curl -X POST https://your-tunnel.example.com \
  -H "Content-Type: application/json" \
  -H "X-Polyglot-Token: <secret>" \
  -d '{"text":"/status"}'
```

Use the JSON `reply` field as the chat response.

## Recommended Command Mapping

- `polyglot status` -> `/status`
- `polyglot run <goal>` -> `/run <goal>`
- `polyglot steer <text>` -> `/steer <text>`
- `polyglot report` -> `/report`
- `polyglot handoff` -> `/handoff`
- `polyglot agents` -> `/agents`
