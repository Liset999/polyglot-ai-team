# Open Source Fusion Notes

Purpose: turn `ai-team-os-v2-merged.pdf` into an implementable Polyglot AI Team OS by borrowing proven product and architecture patterns without copying source code.

## Product North Star

Polyglot should not be a worse Claude chat shell. It should be a local-first control plane for installed AI workers.

The main session stays alive. The user talks to the main agent. The main agent plans, routes, asks for approval when needed, starts local workers, records events, receives steering, and reports back.

## Projects Reviewed

### PDF Competitor Frame: ClawSwarm

Source: `ai-team-os-v2-merged.pdf`, section 12.

What to keep:

- Strong multi-agent collaboration feel.
- A visible shared coordination surface where humans can understand what agents are doing.
- OpenClaw ecosystem compatibility as one possible worker/channel source.

What to avoid:

- Making free-form group chat the default coordination mechanism.
- Letting agents spend tokens talking to each other when structured state transitions would do.
- Designing the product around spectacle instead of interruptible execution.

Polyglot response:

- Keep the "team at work" feeling through events, task state, blockers, and final reports.
- Use structured task packets and event logs as the default coordination layer.
- Allow multi-agent expansion only when the task graph shows real parallel value.

### PDF Competitor Frame: Multica

Source: `ai-team-os-v2-merged.pdf`, section 12.

What to keep:

- Managed agents as durable team members.
- Squads, runtimes, issue lifecycle, and assignment/status semantics.
- More serious operational posture than a chat toy.

What to avoid:

- Heavy web platform and daemon-first setup before the local CLI loop feels excellent.
- Treating task management itself as the core product.
- Forcing the user into a provider/runtime before reusing what is already installed.

Polyglot response:

- Keep agent registry, task lifecycle, and squad vocabulary as internal structure.
- Start with terminal + local worker discovery, then add Feishu as a peer interface.
- Make "local-first, steerable, low-token" the differentiator against managed-agent platforms.

### OpenClaw

Source: <https://github.com/openclaw/openclaw>

What to keep:

- Gateway/control-plane shape: one local runtime owns sessions, channels, tools, events, and routing.
- Multi-channel interface idea: terminal and Feishu should be peers over the same session model.
- Session tools: list history, send into an existing session, spawn isolated sessions.
- Onboarding/doctor commands: make local setup explicit and inspectable.
- Security defaults: different permissions for local main session versus remote/IM sessions.

What to avoid:

- Heavy daemon/channel surface before the CLI core is excellent.
- Big remote-exposure story before local steering and reporting are reliable.

### Claude Code Architecture

Source: <https://arxiv.org/abs/2604.14228>

What to keep:

- Simple core loop: model call -> tool/action -> observation -> repeat.
- Append-only session storage.
- Permission modes and human authority.
- Context compaction pipeline.
- Skills, hooks, plugins, MCP-style extensibility.
- Subagent delegation with isolated workspaces.

What to avoid:

- Trying to replicate Claude Code itself. Claude/Codex/OpenCode are workers, not competitors.

### Claude Fable 5 Reference Prompt

Source: `docs/research/claude-fable5-reference-notes.md`

What to keep:

- Product self-knowledge surfaces such as doctor/about/status.
- Tool and skill trigger registries with clear boundaries.
- Explicit session, network, and filesystem state.
- Compact default replies with detail available on demand.

What to avoid:

- Copying provider-specific identity, product claims, or policy text.
- Treating a model system prompt as Polyglot's product design.

### Aider

Source: <https://github.com/Aider-AI/aider>

What to keep:

- Terminal-first pair programming ergonomics.
- Codebase map and explicit file context.
- Git-aware workflow, diffs, test/lint feedback.
- Support many model backends without forcing one provider.

What to avoid:

- Making Polyglot only a direct code editor. The PDF target is a runtime/control plane.

### OpenHands

Source: <https://github.com/OpenHands/OpenHands>

What to keep:

- Action/observation event model.
- Sandboxed execution environment concept.
- Agent controller separated from runtime environment.
- Evaluation and replay mindset.

What to avoid:

- Full web platform and heavy sandbox stack in the first local MVP.

### Task Master / Structured Task Managers

Source: <https://github.com/eyaltoledano/claude-task-master>

What to keep:

- Task graph as a first-class artifact.
- Status transitions, dependencies, and next-action tracking.
- Drop-in task state that other agents/editors can consume.

What to avoid:

- Treating task management as the product. It is the coordination substrate.

### CrewAI / AutoGen / MetaGPT

Sources:

- <https://github.com/crewAIInc/crewAI>
- <https://github.com/microsoft/autogen>
- <https://github.com/FoundationAgents/MetaGPT>

What to keep:

- Vocabulary: roles, tasks, flows, handoffs.
- Controlled flows instead of free-form group chat.

What to avoid:

- Default multi-agent conversation. The PDF explicitly prefers systems coordination over high-token group chat.

## Fusion Architecture

### 1. Gateway Runtime

Owns durable state and routes all interfaces into sessions.

Initial module:

- `polyglot_ai/runtime.py`

Responsibilities:

- create/load sessions
- append events
- read/write run state
- read/write team plan
- expose status snapshots

Current interface adapters:

- `polyglot_cli.py` is the terminal main session.
- `status.py` is a read-only task-board surface.
- `feishu_bridge.py` is the minimal IM bridge over Feishu incoming text and outgoing webhook messages.
- `feishu_listener.py` is a minimal stdlib HTTP listener that accepts incoming text payloads and routes them into the same Feishu bridge/MainAgent path.

Session management:

- Runtime validates session IDs and stores state under `artifacts/sessions/<session_id>/`.
- `polyglot_cli.py sessions` lists local sessions.
- `polyglot_cli.py session-new <id>` creates a session.
- `POLYGLOT_SESSION=<id>` selects the active session for CLI, status, monitor, worker, and Feishu bridge.
- Non-default sessions do not read legacy global `run_state.json` or `steer.json`, which prevents demo/history pollution.
- Completed runs snapshot global planner/worker outputs into `artifacts/sessions/<session_id>/artifacts/`, giving each session a durable artifact view while the legacy planner/worker still write `artifacts/draft` and `artifacts/release`.
- Non-default sessions now write planner/worker artifacts directly into `artifacts/sessions/<session_id>/artifacts/inputs|draft|release`; the default session keeps the legacy global paths for compatibility.
- Artifact snapshots deliberately exclude local caches and tool-private state such as `__pycache__`, `.pytest_cache`, `.claude`, and bytecode files.

Product self-knowledge:

- `polyglot_cli.py about` and Feishu `/about` show the current session, interfaces, selected worker, discovered workers, permission profile, state files, and common commands.
- Agent capability metadata lives in `polyglot_ai/agents.py` so routing and UI surfaces can share the same worker descriptions.
- `polyglot_cli.py route <goal>` and Feishu `/route <goal>` explain worker selection, permission profile, routing hint, complexity, and approval points before execution.

### 2. Main Agent Session

The user talks here. It does not blindly call workers.

Responsibilities:

- classify input: chat, plan, execute, steer, status, approval, stop
- maintain conversation state
- decide whether to answer directly or delegate
- produce final report from events

Current implementation:

- `polyglot_ai/main_agent.py` is the shared control layer for terminal and Feishu.
- It owns task classification, lightweight chat replies, planning, worker delegation, steering, board/report rendering, and event recording.
- `polyglot_cli.py` and `feishu_bridge.py` now call this layer instead of duplicating command semantics.
- Main-agent conversation is persisted in `messages.jsonl`, exposed through `polyglot_cli.py history`, and reused by terminal and Feishu so a run can finish and the user can keep asking follow-up questions in the same session.

### 3. Worker Registry

Discovers installed local agents.

Initial module:

- `polyglot_ai/agents.py`

Responsibilities:

- discover `claude`, `codex`, `opencode`, `openclaw`, `opendevin`
- expose capabilities and invocation templates
- never assume cloud API is required
- read optional `polyglot_agents.json` / `POLYGLOT_AGENT_CONFIG` for user-registered local CLIs, default worker selection, and disabled experimental agents

### 4. Task Board

Structured state instead of group chat.

Initial artifacts:

- `artifacts/sessions/<session_id>/team_plan.json`
- `artifacts/sessions/<session_id>/tasks.json`
- `artifacts/sessions/<session_id>/task_packets.jsonl`
- `artifacts/sessions/<session_id>/events.jsonl`
- `artifacts/sessions/<session_id>/run_state.json`
- `artifacts/sessions/<session_id>/final_report.md`

Current implementation:

- `polyglot_ai/task_board.py` builds a task-board snapshot from the latest session plan, run state, event log, and artifacts.
- `status.py` renders the same board outside the interactive CLI.
- `polyglot_cli.py board` exposes the board inside the main terminal session.
- `render_compact_task_board` gives Feishu a short IM-safe status message; full details stay available through `/board-full`.

This borrows Multica's lifecycle clarity without becoming a heavyweight managed-agent platform, and borrows ClawSwarm's "team at work" visibility without defaulting to agent group chat.

### 5. Orchestrator

Starts only the needed worker, with a narrow task packet.

Task packet:

- goal
- current task
- relevant file paths
- constraints
- steer messages
- verification command
- budget

Current implementation:

- `polyglot_ai/task_packet.py` creates structured task packets.
- `Runtime.append_task_packet` stores packets in `artifacts/sessions/<session_id>/task_packets.jsonl`.
- `v1_worker.py` records packets before fill and heal worker calls.
- Task packets include the selected worker's permission profile.
- `polyglot_ai/task_board.py` shows recent packets so terminal and Feishu can inspect what was actually delegated.
- `/packet` exposes the latest delegated packet without dumping the full board into IM.

### 6. Event Log

Append-only, replayable, low-token coordination layer.

Event shape:

```json
{
  "ts": "2026-06-15T00:00:00",
  "session_id": "default",
  "type": "worker.completed",
  "summary": "Tests passed",
  "data": {}
}
```

Timeline:

- `artifacts/sessions/<session_id>/timeline.jsonl` stores a replay-oriented action/observation stream.
- Shape: `actor`, `action`, `observation`, `status`, `data`.
- `events.jsonl` remains the compatibility/status event log; `timeline.jsonl` is the human/agent replay surface borrowed from action-observation systems such as OpenHands and Claude Code.
- `polyglot_cli.py timeline` and Feishu `/timeline` expose recent timeline items without dumping raw process logs.

Handoff:

- `artifacts/sessions/<session_id>/handoff.md` and `handoff.json` store a compact continuation packet for a human or another agent.
- The handoff is derived from the session plan, run state, release files, recent task packets, pending steer/control state, and recent timeline.
- `polyglot_cli.py handoff` and Feishu `/handoff` generate and display the packet.

Approval gates:

- Worker routing includes a permission profile.
- High-trust or ambiguous workers such as OpenClaw/OpenHands/AutoGPT/generic require explicit approval before execution.
- `approval.json` stores the pending run request; CLI and Feishu expose `/approval`, `/approve`, and `/deny`.
- Low-risk local-write workers and mock verification keep the fast path.

## First Correct MVP

Do not build Feishu first. Do not build multi-agent chat first. Do not build a web dashboard first.

Build this first:

1. `polyglot>` starts or resumes one durable session.
2. Normal user text goes to the main session.
3. `/plan <goal>` creates a structured task graph and saves it under `artifacts/sessions/default/`.
4. `/run <goal>` creates a plan, delegates to one selected local worker, streams structured events, verifies, and writes a final report.
5. `/steer <message>` appends a steering event and writes the current steer signal for active workers.
6. `/status` renders a concise session summary; `/board` renders the task board from session state, not scattered files.

## Current Code Gap

The current implementation is still a collection of scripts:

- `polyglot_cli.py` owns too much product logic.
- `monitor.py` owns display and runtime orchestration together.
- `v1_worker.py` owns worker discovery, prompts, healing, and state writes.
- artifacts are global, not session-scoped.

The next implementation step should extract a deep `Runtime` module behind a small interface before adding more user-facing commands.

## Immediate Implementation Slice

Create the session/event substrate:

- `polyglot_ai/runtime.py`
- `polyglot_ai/agents.py`
- `polyglot_ai/worker_adapters.py`
- migrate `polyglot_cli.py status/plan/steer` to use session-scoped artifacts
- leave existing planner/worker execution intact until the substrate is stable

This is the smallest move that makes the PDF more true instead of decorating the current shell.

## Implemented So Far

- PDF competitor framing added for ClawSwarm and Multica.
- Runtime session substrate: `artifacts/sessions/default/`.
- Append-only event log: `events.jsonl`.
- Session-scoped `team_plan.json`, `run_state.json`, and `final_report.md`.
- Shared main-agent control layer implemented in `polyglot_ai/main_agent.py`.
- Explicit local session management implemented: list/create/select sessions with `POLYGLOT_SESSION`.
- Product self-knowledge implemented through `/about` and agent capability metadata.
- Routing explainability implemented through `/route <goal>` and persisted `team_plan.routing`.
- Unified agent discovery in `polyglot_ai/agents.py`.
- Worker adapter seam in `polyglot_ai/worker_adapters.py`.
- `v1_worker.py` now calls workers through the adapter seam instead of owning backend discovery itself.
- `/doctor` command checks workspace paths, discovered local agents, DeepSeek key presence, pending steer state, and Python syntax sanity without writing `.pyc` files.
- Structured task board implemented in `polyglot_ai/task_board.py`, exposed through `status.py` and `polyglot_cli.py board`.
- Minimal Feishu bridge implemented in `feishu_bridge.py`: post board/report, accept `/run`, accept `/steer`, and reuse the same Runtime/Task Board as the terminal.
- Structured task packets implemented in `polyglot_ai/task_packet.py` and recorded by `v1_worker.py` for fill/heal worker calls.
- IM compact status implemented: Feishu `/status` posts a short board, `/packet` posts the latest task packet, and `/board-full` remains available for detail.
- Persistent main-agent chat implemented: `messages.jsonl`, `polyglot_cli.py chat`, `polyglot_cli.py history`, REPL `/chat`, REPL `/history`, and Feishu normal-message replies now share the same `MainAgent.chat_reply` path.
- First-class run controls implemented: `/pause`, `/resume`, and `/stop` write session-scoped control signals, appear in board/status, and are honored by `v1_worker.py` at safe checkpoints.
- Session artifact snapshots implemented: `Runtime.snapshot_artifacts()` copies `inputs`, `draft`, `release`, and key logs into the active session after monitor/main-agent runs; Task Board and reports prefer the session snapshot when available.
- Session-native artifact execution implemented for non-default sessions: `v0_planner.py`, `v0_worker.py`, `v1_worker.py`, and `monitor.py` use `Runtime.working_artifact_dir/path`, so a named session can run without polluting or reading global draft/release artifacts.
- Replay timeline implemented: `Runtime.append_timeline/read_timeline`, monitor planner/worker run actions, worker adapter query/write actions, CLI `timeline`, and Feishu `/timeline`.
- Session handoff implemented: `Runtime.write_handoff`, `MainAgent.handoff_text`, CLI `handoff`, Feishu `/handoff`, and persisted `handoff.md/json`.
- Approval gates implemented: `Runtime.request_approval/read_approval/clear_approval`, MainAgent run gating, CLI `approval/approve/deny`, and Feishu `/approval`, `/approve`, `/deny`.
- Configurable local agent registry implemented: `polyglot_ai/agents.py` reads `polyglot_agents.json` or `POLYGLOT_AGENT_CONFIG`; `polyglot_agents.example.json` documents the format; `agents` and `doctor` show config source/default.
- Minimal Feishu incoming listener implemented: `feishu_listener.py` accepts generic JSON text payloads, Feishu-style challenge payloads, and common message.content JSON, then reuses `feishu_bridge.handle_text`.

## Next Adapter Targets

Use installed tools directly where possible:

- Claude Code adapter: current default local CLI worker.
- Codex adapter: route coding tasks through `codex exec` when requested.
- Aider adapter: use for git-aware file-editing flows once installed.
- OpenClaw adapter: use as a long-lived gateway/channel worker rather than a simple coding worker.
- OpenHands adapter: use for sandboxed action/observation execution when available.
