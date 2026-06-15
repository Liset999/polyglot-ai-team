# Host Integration

## Python Host

```python
from polyglot_skill_bridge import handle_text

reply = handle_text("/status", session_id="hermes")
```

## Non-Python Host

Run:

```powershell
python C:\Users\ROG\.codex\skills\polyglot-team-os\scripts\polyglot_skill_bridge.py --session hermes --text "/status"
```

Read stdout and send it back to the chat.

## Recommended Command Mapping

- `polyglot status` -> `/status`
- `polyglot run <goal>` -> `/run <goal>`
- `polyglot steer <text>` -> `/steer <text>`
- `polyglot report` -> `/report`
- `polyglot handoff` -> `/handoff`
