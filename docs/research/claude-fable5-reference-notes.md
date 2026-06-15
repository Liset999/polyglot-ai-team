# Claude Fable 5 Reference Notes

Source: `E:\xwechat_files\wxid_ow8osi7f92kq22_e7bc\msg\file\2026-06\CLAUDE-FABLE5(1).txt`

Purpose: extract product/runtime patterns that can improve Polyglot AI Team OS without copying a model provider's system prompt or policy text.

## What To Keep

### 1. Product Self-Knowledge As A Runtime Capability

The reference separates product facts, model facts, settings, and "search before answering current product questions" behavior.

Polyglot adaptation:

- Add a `doctor` and future `/about` surface that reports installed local agents, configured providers, Feishu state, current session, and permission mode.
- Keep product/provider facts inspectable instead of baking assumptions into prompts.
- For fast-changing provider details, prefer local `doctor` checks or official docs lookup instead of memory.

### 2. Tool And Skill Trigger Registry

The reference describes tools and skills with trigger conditions, skip conditions, and JSON schemas.

Polyglot adaptation:

- Treat local agents, skills, Feishu, and worker adapters as registry entries with capabilities and routing hints.
- Extend `polyglot_ai/agents.py` over time from "command discovery" to "capability discovery."
- Add task-packet fields for required tools, allowed tools, and verification commands.

### 3. Session And State Transparency

The reference repeatedly explains current interface, available tools, network boundaries, filesystem boundaries, and context handling.

Polyglot adaptation:

- Make session identity explicit in CLI prompt, board, Feishu compact status, and artifacts.
- Add session list/new commands so demos and real work do not pollute one another.
- Keep append-only events and task packets as auditable state.

### 4. Compact Interaction Defaults

The reference avoids over-formatting in normal conversation and separates short answers from full reports.

Polyglot adaptation:

- CLI can stay conversational for lightweight questions.
- Feishu should default to compact board/status and expose `/packet`, `/report`, and `/board-full` for detail.
- MainAgent should decide chat vs delegation instead of always calling a worker.

### 5. Safety And Permission Boundaries

The reference has explicit network and filesystem boundaries.

Polyglot adaptation:

- Add a future permission profile to task packets: local write, shell, network, Feishu, external service.
- Require approval before destructive actions or remote side effects.
- Distinguish trusted local terminal sessions from remote/IM sessions.

## What Not To Copy

- Do not copy provider-specific identity claims, product names, model names, or policy text.
- Do not embed Anthropic-specific system prompt rules into Polyglot.
- Do not make Polyglot a Claude clone. Claude/Codex/OpenClaw are workers behind a local control plane.
- Do not expose long provider prompt text to workers; use small task packets and local policy/permission metadata.

## Implementation Targets

Near-term:

- Done: explicit session management: list, create, select through `POLYGLOT_SESSION`.
- Done: `/about` output inspired by product self-knowledge.
- Done: capability metadata on discovered agents.
- Done: `/route <goal>` explains selected worker, permission profile, routing hint, and approval points.
- Done: task packets include permission profiles.

Later:

- Add a tool/skill registry with trigger and skip conditions.
- Add context compaction for long-running sessions.
