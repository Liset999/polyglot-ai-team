# Polyglot AI Team OS Development Log

This file records product decisions, implementation direction, and active development notes so the project can survive chat context compression.

Keep entries concise, concrete, and useful for the next engineer or agent.

## 2026-06-18 - Meta Planner + Skill Compounding + Budget Control + Structured Handoff (v2 Feature Batch)

Implemented 4 core capabilities inspired by the Polyglot AI Team OS v2 design document. All features are Host-first + MCP-exposed — no CLI or Feishu dependencies.

### New Modules

**`polyglot_ai/meta_planner.py`** (new) — Keyword-based task planning without LLM calls:
- `assess_complexity(goal)`: scores goal complexity (simple/medium/complex) and returns reasoning
- `generate_task_graph(goal, complexity_level)`: generates a structured task graph with nodes (id, phase, description, depends_on, status, max_attempts, model_preference)
- `recommend_skills(goal, skill_index)`: keyword matching + history-weighted sorting
- `build_team_plan(goal, ...)`: high-level composer — produces Team Plan v2.0 dict

**`polyglot_ai/skill_compound.py`** (new) — Cross-session skill tracking:
- `record_skill_usage(session_dir, skill_name, phase, outcome)`: records per-session skill use
- `update_skill_index(artifacts_dir, session_dir)`: aggregates into a global skill index with total_uses / success_rate / last_used_at / triggers
- `recommend_by_history(skill_index, top_n)`: returns skills sorted by `success_rate * log(uses+1)`

**`polyglot_ai/handoff.py`** (new) — Structured continuation packs:
- `build_handoff_pack(runtime, session_id)`: produces `{ session_state, completed_tasks, remaining_tasks, key_context_refs, next_action, budget_remaining, metadata }`
- `build_handoff_markdown(pack)`: human-readable markdown rendering

### Modified Modules

- **`polyglot_ai/runtime.py`** — Added `normalize_team_plan(plan)` (upgrade/backwards-compat), `Runtime.record_budget_downgrade(reason)`, `Runtime.read_budget_state()`. `save_team_plan()` and `read_team_plan()` now auto-normalize.
- **`polyglot_ai/v1_worker.py`** — Additive only: skill usage tracking inside `load_relevant_skills`, skill index finalization before exits, budget check before each healing iteration.
- **`polyglot_mcp_server.py`** — New `polyglot_preview_plan` tool (read-only, no side effects); `session_status_payload` now includes `budget_state` field; `tool_get_handoff` rewritten to build structured handoff packs (with legacy handoff.md fallback).

### New Test Files

- `polyglot_ai/test_meta_planner.py` — 34 tests (complexity assessment, task graph generation, skill recommendation, team plan integration, backward compatibility)
- `polyglot_ai/test_skill_compound.py` — 14 tests (skill usage recording, cross-session aggregation, budget tracking, handoff pack generation)

### Verification Summary

| Test file | Result |
|-----------|--------|
| `polyglot_ai/test_meta_planner.py` | **34 / 34 passed** ✅ |
| `polyglot_ai/test_skill_compound.py` | **14 / 14 passed** ✅ |
| `polyglot_ai/test_mcp_server.py` | **58 / 58 passed** ✅ |
| Total new feature tests | **106 passed** ✅ |

**Design principles maintained:**
- Pure functions → fully testable without LLM/network
- Backward compatible → all existing MCP tools unchanged; normalize_team_plan handles old formats
- Host-first → all new features exposed through MCP (`polyglot_preview_plan`, `budget_state` in status, `handoff_version` in handoff)
- Token-efficient → Meta Planner produces compact task graphs; no redundant data in status payloads

## 2026-06-17 - Gap Analysis Reconciled And Follow-On Task Released

- Reconciled the latest handoff summary against the live worktree.
- Confirmed the blueprint gap-analysis findings are reflected in the repo:
  - `polyglot_smoke` is listed in `skills/polyglot-team-os/SKILL.md` and `README.md`
  - `polyglot_get_report` / `polyglot_get_handoff` return explicit `no_such_session`, `no_report_yet`, and `no_handoff_yet` reasons
  - the smoke and host-facing regressions are in place
- Released the next focused task in [docs/task-release-host-install-smoke.md](file:///d:/Repository/polyglot-ai-team/docs/task-release-host-install-smoke.md) so another model can continue with host install flow and end-to-end smoke hardening.
- Latest verification: `python -m pytest polyglot_ai/test_mcp_server.py polyglot_ai/test_skill_packaging.py -q` -> `109 passed`.

## 2026-06-17 - Full Blueprint Alignment And Self-Testing

Completed full alignment with blueprint documents and self-testing:

- **Documentation alignment**:
  - Added `polyglot_smoke` to MCP Tools table in [skills/polyglot-team-os/SKILL.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/SKILL.md)
  - Added `polyglot_smoke` to Host-side MCP quick probes in [README.md](file:///d:/Repository/polyglot-ai-team/README.md)

- **Error contract fixes** ([polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py)):
  - Added `session_exists()` helper function
  - Fixed `tool_get_report`: now returns `available: false` with explicit `reason` field
    - `no_such_session`: session directory doesn't exist
    - `no_report_yet`: session exists but no final_report.md
  - Fixed `tool_get_handoff`: same error contract pattern
    - `no_such_session`: session directory doesn't exist
    - `no_handoff_yet`: session exists but no handoff.md
  - Fixed `resource_report` and `resource_handoff` to match tool error contract

- **Smoke tool fixes**:
  - Fixed `read_model_config` parameter order (env, workspace)
  - Fixed import: use `run_local_smoke` instead of non-existent `validate_smoke_output`
  - Ensure session directory exists before reading state

- **New tests** ([polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py)):
  - `test_get_report_no_such_session`
  - `test_get_handoff_no_such_session`
  - `test_get_report_session_exists_no_report`
  - `test_get_handoff_session_exists_no_handoff`
  - `test_get_report_session_with_report`
  - `test_get_handoff_session_with_handoff`

- **Self-testing results**:
  - `polyglot_smoke` tool: 5/5 checks passed
  - All MCP tools discoverable via `tools/list`
  - Error contract working correctly

- **Verification**: `python -m pytest polyglot_ai/test_mcp_server.py polyglot_ai/test_skill_packaging.py -q` -> `109 passed`

## 2026-06-17 - UX + Token Reduction (First-User Perspective)

As a first-time user of Polyglot, walked through the MCP surface and identified token waste issues.

**Token waste found:**
- `polyglot_status` with active session: 6159 chars, 83% was `team_plan` dict containing redundant data (issue_graph, available_agents, workspace_context, routing, product_strategy, budget — none needed for status polling)
- `polyglot_get_task_board`: product_strategy duplicated across both status and task board
- session_info had duplicate fields

**Changes made:**

1. **`session_status_payload`** — Removed full `team_plan` dict (5122 chars). Replaced with `team_plan_uri` pointing to task_board resource. Removed redundant top-level fields. Status payload went from ~6159 to ~984 chars (**84% reduction**).

2. **`build_task_board`** — Removed `product_strategy` (345 chars). Task board went from ~3878 to ~3511 chars (**9% reduction**).

3. **`session_info`** — Removed duplicate `session_id` and `is_default` fields since they already exist at top-level. Minor savings.

4. **Tests updated** — `test_tool_status`, `test_status_returns_enhanced_fields`, `test_status_for_non_default_session` updated to match new payload shape.

**Results:**
| Call | Before | After | Reduction |
|------|--------|-------|-----------|
| Status (with plan) | 6159 chars | 984 chars | **84%** |
| Task board | 3878 chars | 3511 chars | **9%** |
| Status (idle) | 825 chars | 776 chars | **6%** |

**Tests:** `python -m pytest polyglot_ai/test_mcp_server.py polyglot_ai/test_skill_packaging.py -q` → `109 passed`

## 2026-06-17 - Full Blueprint Alignment And Self-Testing (Part 2)

As a user of Polyglot, walked through the complete MCP surface:

- **Environment check**: Workspace and runtime properly detected (POLYGLOT_WORKSPACE fallback to cwd)
- **Tools discovery**: 12 tools available in `tools/list`, all with proper descriptions
- **Resources discovery**: 10 resources in `resources/list` (3 static + 7 session templates)
- **Prompts discovery**: 4 prompts in `prompts/list`
- **Smoke test**: `polyglot_smoke` → 5/5 checks passed on fresh session
- **Status check**: `polyglot_status` works for existing and non-existing sessions
- **Goal start**: `polyglot_start_goal` returns plan with `task_board_uri`, report_uri, run_state_uri
- **Task board**: Structured JSON with tasks (plan/implement/verify) and their status
- **Error contract**: `polyglot_get_report`/`handoff` return explicit `available: false` with reason
- **Resource read**: Session resources accessible via `polyglot://session/{id}/status`, etc.

**Fixes made during self-testing**:

1. **Status payload inconsistency** - `goal` field was reading from `run_state` only, missing the goal from `team_plan`. Fixed: `"goal": state.get("goal") or team_plan.get("goal") or ""` in `session_status_payload()`.

2. **Resource descriptors function** - Cleaned up `resource_descriptors()` and `resource_template_descriptors()` to match expected structure.

3. **polyglot_smoke robustness** - Fixed `read_model_config` parameter order (env, workspace) and import of `run_local_smoke`.

4. **Report/handoff error contract** - `tool_get_report` now checks `session_exists()` and file content; returns `available: false, reason: "no_report_yet"` / `"no_handoff_yet"` instead of empty strings. `resource_report` and `resource_handoff` get same treatment.

**Tests**: `python -m pytest polyglot_ai/test_mcp_server.py polyglot_ai/test_skill_packaging.py -q` → `109 passed`

**Remaining UX observations** (non-blocking, CLI fallback territory):
- `profiles: 0` returns empty list - user needs to know about `polyglot_models.json` config
- `polyglot_start_goal` without model profiles → host must understand this requires setup

## 2026-06-17 - Host Install Flow And Smoke Tightened

Completed the host install flow and smoke verification per [docs/task-release-host-install-smoke.md](file:///d:/Repository/polyglot-ai-team/docs/task-release-host-install-smoke.md):

- **Install scripts enhanced** (`scripts/install_host_bundle.ps1`, `scripts/install_mcp_config.ps1`, `scripts/install_codex_host.ps1`):
  - Added verification checklists in dry-run output
  - Added `expected_tools` and `expected_resources` output
  - Added `mcp_server_command` and `next_steps` guidance
  - Added post-install verification checklists

- **New `polyglot_smoke` MCP tool** (`polyglot_mcp_server.py`):
  - Lightweight end-to-end verification of MCP surface
  - Checks: session_state_readable, main_agent_initialized, task_board_buildable, model_config_readable, smoke_validator_available
  - Returns structured `ok`, `checks`, `summary`, and `server_version`

- **New smoke tests** (`polyglot_ai/test_mcp_server.py`):
  - `test_smoke_returns_ok_with_checks`
  - `test_smoke_with_custom_session`
  - `test_tools_list_includes_all_expected_tools`

- **New Host-Facing Smoke Verification section** (`docs/host-install-flow.md`):
  - MCP tool smoke test with expected JSON response
  - CLI fallback smoke test
  - Verification checklist table
  - Smoke check failure handling guide

- **Verification**: `python -m pytest polyglot_ai/test_mcp_server.py polyglot_ai/test_skill_packaging.py -q` -> all pass

## 2026-06-17 - Next Task Released For Another Model

- Released a focused follow-on task in [docs/task-release-host-install-smoke.md](file:///d:/Repository/polyglot-ai-team/docs/task-release-host-install-smoke.md).
- The next task keeps the work on the host side:
  - tighten the host install flow
  - make the smoke path explicit
  - keep the skill contract minimal and MCP-first
- This keeps the team from drifting back into CLI-centered work while preserving the current MCP + skills alignment.

## 2026-06-17 - Dogfooding Improved The Host Install And MCP Surface

- Applied the "use the project to develop the project" feedback directly: the repo is now being exercised through its own host-facing MCP and skill surface instead of treating the CLI as the center.
- Updated [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md) to make the host install path more explicit:
  - verification checklist for MCP tools, resources, and prompts
  - host-specific installation guidance for Codex and generic hosts
  - environment variable reference table
  - clearer acceptance criteria for MCP discoverability and regression coverage
- Expanded `session_status_payload()` in [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py) to return richer runtime context:
  - `session_info`
  - `timeline_summary`
  - `packets_summary`
  - `messages_summary`
  - `metadata`
  - `lock_is_stale`
  - `is_default_session`
- Updated [skills/polyglot-team-os/SKILL.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/SKILL.md) so host agents see the MCP tools/resources/prompts and the host integration flow in one place.
- Added/updated regression coverage in [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) for the richer status payload and host-visible state.
- Verification: `python -m pytest polyglot_ai/test_mcp_server.py polyglot_ai/test_skill_packaging.py -q` -> `100 passed`.

## 2026-06-17 - Host install flow documentation enhanced

- Updated [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md) with:
  - Verification checklist for MCP tools, resources, and prompts
  - Host-specific installation guides (Codex, generic hosts)
  - Environment variables reference table
  - Expanded acceptance criteria including MCP discoverability and regression test pass requirements
- This makes the host-first installation story more complete and testable.

## 2026-06-17 - MCP status payload enhanced with richer runtime information

- Updated [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py) `session_status_payload()` to include:
  - `session_info`: session metadata including workspace and session directory paths
  - `timeline_summary`: recent timeline events count and samples
  - `packets_summary`: recent task packets count and samples
  - `messages_summary`: recent messages count and samples
  - `metadata`: runtime version and timestamp
  - `lock_is_stale`: indicator for stale run locks
  - `is_default_session`: flag for default session identification
- Extended [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) with 13 new tests for:
  - Error handling (missing goal, missing message, unknown tool, unknown method)
  - Enhanced status fields verification
  - Blocked state handling (worker not runnable, model not runnable)
  - Empty config handling
- Verification: `python -m pytest polyglot_ai/test_mcp_server.py` -> 49 tests passed.
- This gives host clients richer runtime state information without requiring multiple MCP calls.

## 2026-06-17 - Skill documentation updated with comprehensive host integration guide

- Updated [skills/polyglot-team-os/SKILL.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/SKILL.md) with:
  - Tables for MCP tools, resources, and prompts with descriptions
  - Expanded "When to Use Polyglot" and "When NOT to Use Polyglot" sections
  - New Host Integration Guide covering session management, state inspection flow, error handling, and security considerations
- This makes the skill contract more explicit for host agents integrating with Polyglot.

## 2026-06-17 - Launcher now targets the user-level model config

- Updated [scripts/install_polyglot_launcher.ps1](file:///d:/Repository/polyglot-ai-team/scripts/install_polyglot_launcher.ps1) so the installed `polyglot.cmd` launcher sets both `POLYGLOT_WORKSPACE` and `POLYGLOT_MODEL_CONFIG`.
- The launcher now defaults `POLYGLOT_MODEL_CONFIG` to `%USERPROFILE%\polyglot_models.json`, which matches the user-owned config file used by the first-run UI flow.
- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) and [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) so the launcher/config location contract is documented and regression-tested.
- Verification: `python -B -m unittest polyglot_ai.test_config_tui polyglot_ai.test_skill_packaging` -> 58 tests passed.
- This keeps the launch path aligned with the user’s expectation that Polyglot should be invokable from any directory while still using the user’s own model registry.

## 2026-06-17 - First-run config now flows through custom models only

- Updated [polyglot_cli.py](file:///d:/Repository/polyglot-ai-team/polyglot_cli.py) so `/config` no longer starts from GPT or MiniMax presets; first-run setup now says "Custom profile only" and asks for a model, display name, blank relay URL, and encrypted key.
- The visible config language now centers on `Model` / `Model name` instead of `Profile id`, while the internal id stays hidden and is derived automatically from the model text when needed.
- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) and [polyglot_ai/test_config_tui.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_config_tui.py) to match the custom-only flow and the blank relay URL input behavior.
- Verification: `python -B -m unittest polyglot_ai.test_config_tui polyglot_ai.test_skill_packaging` -> 58 tests passed.
- This keeps first-run configuration aligned with the user-owned model workflow instead of assuming repo-owned presets.

## 2026-06-17 - Polyglot launcher installer added for PATH-visible startup

- Added [scripts/install_polyglot_launcher.ps1](file:///d:/Repository/polyglot-ai-team/scripts/install_polyglot_launcher.ps1) so the repo can install a `polyglot.cmd` launcher that points at the workspace and works from any directory after being added to PATH.
- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) and [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to name and verify the launcher installer.
- Verified the installer locally by generating a launcher into [output/launcher-test](file:///d:/Repository/polyglot-ai-team/output/launcher-test).
- This closes the first-run gap where a user would otherwise need to know the repo path before starting Polyglot.

## 2026-06-17 - Config UI should show model labels, not "Profile id"

- User feedback: the first-run config screen should present the official model label such as `Model` or `Model name`, not a technical `Profile id` label that forces the user to think about internal identifiers first.
- Product direction: keep the internal `id` as a hidden system key or advanced field, but make the visible prompt match the user's mental model and the provider's naming where possible.
- This reduces first-run friction and keeps `/config` closer to a normal "choose or define a model" flow instead of a developer-oriented registry editor.
- Supersedes the earlier wording that surfaced `Profile id` as the primary user-facing label.

## 2026-06-17 - Relay URL input should be blank by default

- User feedback: the config screen should not prefill the relay/base URL field or suggest a default URL, because the user should type their own proxy endpoint explicitly.
- Product direction: keep the field label as `API base URL / relay URL`, but present an empty input so the first-run flow does not imply a preferred upstream service.
- This keeps the config UI aligned with self-owned middlebox setups and reduces accidental coupling to any specific relay provider.

## 2026-06-17 - First-run config should be custom-only

- User feedback: the first configuration flow should only expose `Custom` as the built-in path; `gpt` and `minimax` are user-owned model choices, not repo-owned presets.
- Product direction: `/config` should treat model registration as a user-authored step, so the first run teaches the user to define their own model endpoints instead of assuming any vendor preset is canonical.
- This also keeps the product honest for the host-first design: Polyglot should help the user wire their own models, not quietly bake in provider preferences at the first prompt.

## 2026-06-17 - First-run CLI entry should be globally invokable

- User feedback: the current local CLI startup flow still assumes the user already knows the repo path and can `cd` into it, which is too brittle for first-time installs.
- Product direction: the host installer should expose a PATH-visible launcher or shim so users can type a short command from any directory, while `POLYGLOT_WORKSPACE` points the runtime at the actual project/workspace root.
- The repo-local `python .\polyglot_cli.py` flow remains useful for development, but it should be the fallback, not the only discoverable startup path.
- This matters especially for new installs where the repo location is unknown or the user is operating from a host client that should bootstrap Polyglot for them.

## 2026-06-17 - Model config reset to a blank first-run state

- Reset [polyglot_models.json](file:///d:/Repository/polyglot-ai-team/polyglot_models.json) and [polyglot_models.example.json](file:///d:/Repository/polyglot-ai-team/polyglot_models.example.json) to empty templates with `default_model` blank and no configs, so the next local run starts from a clean CLI-first setup.
- Updated [polyglot_cli.py](file:///d:/Repository/polyglot-ai-team/polyglot_cli.py) so the first-run config flow and worker defaults now center on `gpt-5.4-mini` and `minimax-m3` instead of steering new runs toward DeepSeek as the default path.
- Updated [scripts/start_claude_models.ps1](file:///d:/Repository/polyglot-ai-team/scripts/start_claude_models.ps1) so it reads both `configs` and legacy `profiles`, and exits cleanly with guidance when no profiles have been configured yet.
- Verification: `python -B -m unittest polyglot_ai.test_config_tui polyglot_ai.test_skill_packaging` -> 57 tests passed; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_claude_models.ps1 -ProbeOnly` -> clean no-config message.
- This keeps the repo honest for the user flow you asked for: wipe the existing config, restart the local CLI, and set up models from scratch in the UI instead of via environment-variable editing.

## 2026-06-17 - Generic MCP config example added for host-neutral installs

- Added [configs/mcp.json.example](file:///d:/Repository/polyglot-ai-team/configs/mcp.json.example) as a host-neutral MCP config example alongside the Codex-specific example.
- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md), [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md), and [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) to mention the generic example.
- Extended [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to verify the generic example exists and points to the real MCP server entrypoint with `POLYGLOT_WORKSPACE`.
- This reduces the risk that the repo only appears Codex-ready while silently lacking a host-neutral MCP config sample.

## 2026-06-17 - Host bundle installer added as a reusable skill+MCP orchestrator

- Added [scripts/install_host_bundle.ps1](file:///d:/Repository/polyglot-ai-team/scripts/install_host_bundle.ps1) so a host can install both skill packaging and MCP registration through one generic entrypoint.
- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md), [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md), [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md), and [docs/vnext-host-runtime.md](file:///d:/Repository/polyglot-ai-team/docs/vnext-host-runtime.md) to name the new orchestrator explicitly.
- Extended [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) with dry-run and write-path coverage for the host bundle installer.
- Verification: `python -B -m unittest polyglot_ai.test_skill_packaging polyglot_ai.test_mcp_server` -> 51 tests passed.
- This keeps the host install story closer to the vNext plan: the host agent can now reuse smaller installers without hand-building the install sequence every time.

## 2026-06-17 - Codex installer now wraps the shared host bundle installer

- Updated [scripts/install_codex_host.ps1](file:///d:/Repository/polyglot-ai-team/scripts/install_codex_host.ps1) so it now delegates the shared skill+MCP work to [scripts/install_host_bundle.ps1](file:///d:/Repository/polyglot-ai-team/scripts/install_host_bundle.ps1).
- Updated [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) to say the Codex installer is now a thin Codex-specific wrapper around the shared host bundle path.
- This removes one more duplicate install path and makes the Codex story line up better with the repo-level “reuse the project to install the project” principle.

## 2026-06-17 - Skill docs now name the reusable host install scripts

- Updated [skills/polyglot-team-os/SKILL.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/SKILL.md) so host readers can see the install script split directly inside the portable skill contract.
- Updated [skills/polyglot-team-os/references/host-integration.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/host-integration.md) with the same install path guidance.
- Extended [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) so the skill docs are now regression-tested for `install_host_bundle.ps1`, `install_mcp_config.ps1`, and `install_codex_host.ps1`.
- This tightens the "skills" half of MCP + skills by making the install story visible where a host agent is most likely to read it.

## 2026-06-17 - MCP start_goal now accepts the spec's mode hint

- Updated [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py) so `polyglot_start_goal` now accepts an optional `mode` input and forwards it as a runtime env hint.
- Updated [docs/mcp-server-minimal-spec.md](file:///d:/Repository/polyglot-ai-team/docs/mcp-server-minimal-spec.md) so the sample input now matches the implementation more closely.
- Extended [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) so the mode hint is regression-tested.
- This keeps the minimal MCP contract closer to the blueprint instead of silently dropping a field the host may already try to send.

## 2026-06-17 - Config TUI no longer offers DeepSeek Pro as a first-run preset

- Updated [polyglot_cli.py](file:///d:/Repository/polyglot-ai-team/polyglot_cli.py) so the first-run `/config` preset menu now only offers DeepSeek Flash and Custom.
- Extended [polyglot_ai/test_config_tui.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_config_tui.py) so the menu text is regression-tested and DeepSeek Pro cannot quietly reappear as a default choice.
- This is a direct dogfood fix: the user-facing config surface now stops steering new users toward a pro preset when the current product direction is flash-first.

## 2026-06-17 - MCP resource list now mirrors session templates for host discoverability

- Updated [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py) so `resources/list` now includes the session-scoped resource templates in addition to the static `models` and `workspace-summary` entries.
- Updated [docs/mcp-server-minimal-spec.md](file:///d:/Repository/polyglot-ai-team/docs/mcp-server-minimal-spec.md) so the spec now explicitly allows mirroring the same session resources in `resources/list` for host discoverability while keeping `resources/templates/list` available.
- Extended [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) so `resources/list` is now regression-tested for `task-board` and `handoff` discovery.
- This closes a small but real host UX gap: some clients look at `resources/list` first, so the session surfaces should be visible there instead of only via the templates API.

## 2026-06-17 - Codex installer now reuses the generic MCP config installer

- Updated [scripts/install_codex_host.ps1](file:///d:/Repository/polyglot-ai-team/scripts/install_codex_host.ps1) so it now delegates MCP config merging to [scripts/install_mcp_config.ps1](file:///d:/Repository/polyglot-ai-team/scripts/install_mcp_config.ps1).
- The Codex-specific installer still copies the skill bundle and plugin manifest, but the `mcp.json` merge now comes from the shared host-neutral helper.
- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md), [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md), and [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) to name the reusable installer explicitly.
- Added regression coverage in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) so both the docs and the generic installer path stay visible.
- This is the most direct "use the project to install the project" improvement in the current slice: one reusable MCP bootstrapper instead of duplicated per-host merge logic.

## 2026-06-17 - README now names the actual MCP server entrypoint

- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so the host-facing install artifacts list now includes `polyglot_mcp_server.py`.
- Added a regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the README naming the actual MCP server entrypoint.
- This makes the front door clearer for host installers: the repo doesn't just talk about MCP abstractly, it names the file that hosts should wire up.

## 2026-06-17 - README now lists the generic skill installer alongside the Codex installer

- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so the host-facing install artifacts list now includes `scripts/install_skill.ps1`.
- Added a regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the README naming the generic skill installer.
- This keeps the front door honest about the host-agnostic installation path instead of implying the Codex installer is the only supported packaging route.

## 2026-06-17 - Host install flow now names the generic skill installer fallback

- Updated [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md) so the in-repo host-facing artifact list includes `scripts/install_skill.ps1`.
- The same document now states that `scripts/install_skill.ps1` is the generic fallback installer for non-Codex skill packaging.
- Added a regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep that fallback installer mentioned in the host install flow.
- This keeps the host-agnostic installation story closer to the vNext runtime spec instead of making the Codex path feel like the only supported host.

## 2026-06-17 - Codex integration doc now names workspace-summary as the fast context probe

- Updated [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) so Codex readers now see `polyglot://workspace-summary` as the fast deterministic snapshot before deciding what to do next.
- Added a regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep that host-facing guidance present.
- This keeps the Codex entry path aligned with the MCP resource surface already exposed by the runtime.

## 2026-06-17 - README now surfaces host-side MCP quick probes

- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so the front door now names the host-side MCP quick probes:
  - `polyglot://workspace-summary`
  - `polyglot_get_handoff`
  - `continue-from-handoff`
- Added a regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep those probes visible in the README.
- This makes the main entry page consistent with the host-first, MCP-first runtime story instead of leaving those capabilities buried only in lower-level docs.

## 2026-06-17 - Workspace summary is now discoverable through MCP resources list

- Added a regression test in [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) to ensure `resources/list` advertises `workspace-summary`.
- This makes the resource not just readable by URI, but also discoverable by host clients that render the MCP resource list first.
- The change keeps `workspace-summary` aligned with the "MCP is how clients call Polyglot" rule from the vNext runtime spec.

## 2026-06-17 - Host install flow now names the MCP summary and handoff surfaces

- Updated [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md) so the install steps now explicitly tell the host agent to verify:
  - workspace summary MCP access
  - session handoff MCP access
- Updated the acceptance criteria so the host install flow is not considered complete unless the host can read both surfaces without scraping logs.
- Added a regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep those phrases present.
- This keeps the first-use host story aligned with the actual minimal MCP slice instead of only talking about generic install/register behavior.

## 2026-06-17 - vNext roadmap now names the full minimal MCP slice

- Updated [docs/vnext-host-runtime.md](file:///d:/Repository/polyglot-ai-team/docs/vnext-host-runtime.md) so the first implementation slice now explicitly includes:
  - `get_handoff`
  - `task-board`, `handoff`, and `workspace-summary` resources
- Updated the acceptance bullets to state that handoffs and deterministic workspace summaries should be readable through MCP without scraping logs.
- Added a regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) so the roadmap doc keeps naming the same minimal MCP slice as the implementation and spec docs.
- This closes a subtle doc drift where the runtime already exposed the surfaces, but the top-level roadmap had not named all of them yet.

## 2026-06-17 - Workspace summary resource now explicit in the skill contract

- Updated [skills/polyglot-team-os/SKILL.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/SKILL.md) so the preferred MCP resources list now includes `polyglot://workspace-summary`.
- Updated [skills/polyglot-team-os/references/host-integration.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/host-integration.md) to name `polyglot://workspace-summary` as part of the recommended MCP path.
- Added a regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to ensure the skill doc keeps advertising the workspace summary resource.
- This keeps the skill contract aligned with the MCP server's actual resource surface and helps host clients do a quick deterministic workspace read.

## 2026-06-17 - Codex plugin manifest is now regression-tested

- Added a regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) that checks `.codex-plugin/plugin.json` still declares:
  - `skills: "./skills/"`
  - `name: "polyglot-ai-team-os"`
- This keeps the packaged plugin contract stable now that the installer copies the skill bundle into the plugin package itself.

## 2026-06-17 - Codex plugin bundle now ships the skill directory

- Updated [scripts/install_codex_host.ps1](file:///d:/Repository/polyglot-ai-team/scripts/install_codex_host.ps1) so the Codex plugin package now copies `skills/polyglot-team-os` into the plugin bundle itself.
- This makes the `.codex-plugin/plugin.json` `skills` path self-consistent instead of pointing at a directory that was never packaged.
- Extended [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to verify the packaged plugin bundle contains:
  - `skills/polyglot-team-os/SKILL.md`
  - `.codex-plugin/plugin.json`
- Updated [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) so the Codex install flow now explicitly says the skill bundle is copied into the plugin package.
- The Codex host install story is now closer to a real installable package, not just a manifest plus a separate global skill copy.

## 2026-06-17 - Codex MCP example and installer now have regression coverage

- Added a regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to ensure `configs/codex/mcp.json.example` points at:
  - `polyglot_mcp_server.py`
  - `POLYGLOT_WORKSPACE`
- Extended the Codex installer test so the generated `mcp.json` is checked for the same real server entrypoint and workspace env.
- This makes the Codex host-install story more durable and keeps the host-facing MCP entry aligned with the vNext runtime spec.

## 2026-06-17 - Host integration reference now says MCP first

- Updated [skills/polyglot-team-os/references/host-integration.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/host-integration.md) so host readers see MCP as the preferred path before the text bridge.
- The reference now explicitly calls out:
  - `polyglot_get_handoff`
  - `continue-from-handoff`
- This keeps the host-facing guidance aligned with the vNext runtime spec instead of steering readers back to bridge-only usage.

## 2026-06-17 - Handoff contract now covered by tests

- Added explicit coverage in [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) for:
  - `polyglot_get_handoff` in `tools/list`
  - `continue-from-handoff` in `prompts/list`
- This makes the MCP continuation surface part of the verified contract instead of just a documentation promise.

## 2026-06-17 - MCP handoff contract aligned with host skill

- Updated [skills/polyglot-team-os/SKILL.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/SKILL.md) so the preferred MCP surface now includes:
  - `polyglot_get_handoff`
  - `polyglot://session/{session}/handoff`
  - `continue-from-handoff`
- Updated [skills/polyglot-team-os/references/runtime-capabilities.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/runtime-capabilities.md) to mention the MCP continuation prompt explicitly.
- Updated [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) so Codex-first integration guidance prefers the handoff surface instead of scraping logs.
- This tightens the MCP + skills story around the actual continuation artifact, not just status/report inspection.

## 2026-06-17 - Dogfood rule added

- Added an explicit operating rule to both [.clauderules](file:///d:/Repository/polyglot-ai-team/.clauderules) and [.cursorrules](file:///d:/Repository/polyglot-ai-team/.cursorrules): the Main Agent is also a user of the system.
- New rule intent:
  - use Polyglot while building Polyglot
  - treat user-facing friction as a product signal, not just a test failure
  - turn discovered issues into repo changes instead of leaving them as chat observations
- This keeps the project aligned with the user's expectation that the developer role and the user role are the same working loop.

## Operating Note

User explicitly asked to record important development context in the repository so chat compression cannot erase it and so the repo itself becomes a learning record.

## 2026-06-17 - CLI self-use repair

- Restored the missing `setup` and `config` entrypoints in `polyglot_cli.py` for both shell and REPL use.
- Verified real project self-use with `python .\polyglot_cli.py setup`; the CLI now reports worker profile readiness again instead of failing argparse.
- Verified the host-skill path with `python .\skills\polyglot-team-os\scripts\polyglot_skill_bridge.py --workspace D:\Repository\polyglot-ai-team --session codex-local --text "hello"` and `--text "/status"`.
- Reconfirmed a product boundary: Polyglot should not write `.claude/settings.json`; worker routing belongs in `polyglot_models.json` plus per-process env injection.
- Noted one remaining ergonomics gap: the bridge entrypoint is currently under `skills/polyglot-team-os/scripts/` rather than a short root-level wrapper.

## 2026-06-17 - Bridge entrypoint and low-cost default path

- Added repo-level bridge entrypoints:
  - `scripts/polyglot_skill_bridge.py`
  - `scripts/polyglot_skill_bridge.ps1`
- Verified both repo-level bridge entrypoints with real project messages:
  - `hello`
  - `/status`
- Updated README to make the low-cost default explicit: when DeepSeek is unavailable, keep Claude Code as the execution container and prefer `haiku -> gpt-5.4-mini` for cheaper sidecar work.

## 2026-06-17 - README/script reality alignment

- Cleaned a garbled CLI example line in `README.md`.
- Removed stale README guidance that still referenced non-existent CLI commands such as `probe-models`, `smoke-local`, and `smoke-claude`.
- Reworked `scripts/start_claude_models.ps1` so it no longer calls missing CLI subcommands.
- Verified `powershell -ExecutionPolicy Bypass -File .\scripts\start_claude_models.ps1 -ProbeOnly` now reports a real configured profile (`minimax-m3`) instead of failing on an invalid CLI command.

## 2026-06-17 - Global Claude boundary cleanup

- Promoted the product boundary out of development notes and into first-class docs.
- Updated `docs/host-install-flow.md` to say users should not need to let Polyglot rewrite or own global `.claude/settings.json`.
- Updated `docs/vnext-host-runtime.md` to state that worker routing belongs in `polyglot_models.json` plus per-process env injection, not persistent global Claude settings.

## 2026-06-17 - Boundary wording tightened across core docs

- Updated `.clauderules` to make the worker-env rule explicit: Polyglot injects env into each worker subprocess only and does not own the user's global Claude host config.
- Updated `docs/architecture-roadmap.md` to rename the Claude profile example as a per-worker execution profile rather than something that could read like a global Claude setting.
- Updated `docs/host-install-flow.md` to say the CLI setup step changes only Polyglot local worker/runtime state, not Claude app-level or system-wide settings.
- Updated `docs/vnext-host-runtime.md` security/ownership wording so "worker config through Polyglot CLI" reads as per-worker runtime setup rather than global host auth management.

## 2026-06-17 - README command surface re-aligned with current CLI

- Removed more stale README command examples that referenced unsupported CLI commands such as `model-scores`, `sync-model-registry`, and `model-registry`.
- Replaced them with commands that exist in the current parser and were re-verified directly: `model`, `route`, `run`, `setup`, `config`, and `doctor`.
- Re-ran `python .\polyglot_cli.py model` and `python .\polyglot_cli.py route "hello"` to confirm the revised README examples match current behavior.
- Noted one remaining product-behavior gap for future cleanup: `route "hello"` still returns worker-routing output even though normal lightweight chat is supposed to stay on the main-agent side.

## 2026-06-17 - Route behavior aligned with lightweight chat

- Updated `polyglot_ai/main_agent.py` so `route_text()` now checks `should_delegate_to_worker()` before rendering worker-routing details.
- Lightweight messages such as `hello` now return `stay in main-agent chat` instead of misleading Claude worker routing output.
- Verified both sides of the split directly:
  - `python .\polyglot_cli.py route "hello"`
  - `python .\polyglot_cli.py route "build a small utility with tests"`
- Updated the README's explicit-selection example to use a real execution-shaped goal instead of `route "hello"`, so the documentation matches the new lightweight-chat route behavior.

## 2026-06-17 - Integration probe commands cleaned up

- Removed the last ghost probe commands from the README integration section.
- Replaced stale `/state` and `/brief` probes with commands that exist today and were verified on the repo-level bridge path: `/status`, `/board`, and `/report`.
- Re-ran the bridge with `/status` and `/board` to confirm the replacement probes map to the current runtime surface.

## 2026-06-17 - Interactive `/report` command restored

- Fixed a real REPL/runtime mismatch: the README documented `/report`, but the interactive CLI dispatcher did not handle it.
- Added `report` back to `KNOWN_COMMANDS` in `polyglot_cli.py` and wired `/report` into the REPL command dispatcher.
- Verified the interactive path directly by piping:
  - `/report`
  - `/exit`
  into `python .\polyglot_cli.py`

## 2026-06-17 - Prompt stale-state detection

- Fixed a prompt-status UX bug where the interactive CLI could keep showing an active-looking state such as `filling | alive ... | locked` long after the underlying run/lock had gone stale.
- Updated `MainAgent.compact_status()` to detect stale locks and old worker heartbeats, and to render `stale` / `stale-lock` instead of pretending the worker is still alive.
- Verified through the real REPL prompt path by piping `/exit` into `python .\polyglot_cli.py`; the prompt now reports the old state as stale rather than active.

## 2026-06-17 - Stale-state wording aligned across prompt, status, and lock

- Found a second-layer mismatch after fixing the prompt: `/status` still said `filling` + `alive`, and `/lock` still reported `[BUSY] active run` for the same dead process.
- Added shared stale-state helpers in `polyglot_ai/main_agent.py` so prompt/status/lock views use the same stale-lock and heartbeat-freshness logic.
- Verified all three current surfaces now agree on the same stale state:
  - `python .\polyglot_cli.py status`
  - `python .\polyglot_cli.py lock`
  - REPL prompt via `python .\polyglot_cli.py`

## 2026-06-17 - Stale-lock recovery wording tightened

- Exercised the real recovery flow with `python .\polyglot_cli.py unlock "clear stale lock"` and then re-checked `status`, `lock`, and the REPL prompt.
- The recovery behavior was already functionally correct, but `/status` still used an "active-looking run_state" note even after the lock had been cleared and the effective status was `stale`.
- Updated `polyglot_ai/main_agent.py` so the no-lock note now says the stale run state is being kept for inspection and the old lock is gone.

## 2026-06-17 - Bare saved-view names made real

- Fixed another REPL/runtime mismatch: the README promised bare saved-view names like `report` and `latest`, but `report` was missing from the saved-view map and bare aliases were not resolved before intent routing.
- Updated `polyglot_cli.py` so bare input now checks saved-view aliases first, and added `report` to `show_view()`.
- Verified the real interactive path for:
  - `report`
  - `latest`
  - `board`
  by piping them into `python .\polyglot_cli.py`.

## 2026-06-17 - Board header and model summary aligned with current behavior

- Fixed another stale-state inconsistency: the task-board header still showed the raw run status (`filling`) even after prompt/status/lock had been aligned to `stale`.
- Updated `polyglot_ai/task_board.py` so the board header now derives an effective run status using the same stale-lock / heartbeat-freshness idea and shows a stale worker note when appropriate.
- Updated `polyglot_ai/main_agent.py` model configuration summary so its suggested next step now points to `/route <goal>` instead of the removed `/model-scores`.
- Verified through:
  - bare `board` in the real REPL
  - `python .\scripts\polyglot_skill_bridge.py --workspace D:\Repository\polyglot-ai-team --session default --text "看看模型配置"`

## 2026-06-17 - Task-board row rendering cleaned up

- Fixed a CLI display-layer bug where task-board rows like `running` and `pending` were being mangled into `runningg` / `pendingding` by `print_formatted()`.
- Updated `polyglot_cli.py` so plain table sections such as `Tasks`, `Artifacts`, and `Recent Task Packets` are printed without the extra task-line formatter trying to reinterpret them.
- Verified via the real REPL `board` path that task rows now render cleanly.

## 2026-06-17 - ASCII-safe board section headers

- Replaced the remaining garbled board section decoration in `print_formatted()` with a simple ASCII-safe style: `== Section ==`.
- Verified through the real REPL `board` path that `Tasks`, `Artifacts`, `Recent Task Packets`, and `Product Strategy` headers now render cleanly on the current terminal.

## 2026-06-17 - Non-TTY prompt fallback cleaned up

- Fixed another display-layer artifact in `polyglot_cli.py`: when the REPL was driven through piped input or another non-TTY path, readline prompt control markers were rendered literally as `...`.
- Updated the REPL prompt builder so ANSI/readline-wrapped prompts are only used for real interactive TTY sessions; non-TTY runs now use a plain text prompt like `polyglot [stale | ...]>`.
- Verified by piping `/exit` into `python .\polyglot_cli.py`.

## 2026-06-17 - Live model guidance no longer points to removed commands

- Removed the last active `/model-scores` references from user-facing main-agent summaries in `polyglot_ai/main_agent.py`.
- Replaced them with current commands the user can actually run now: `/model`, `/config`, and `/route`.
- Verified through live bridge replies for:
  - `模型怎么选`
  - `怎么看模型配置`

## 2026-06-17 - Default session carry-over guardrail for `/report`

- Confirmed a real default-session confusion path: `/report` on the shared `default` session immediately surfaced an old saved report, while a fresh session showed no report at all.
- Added a small guardrail in `polyglot_ai/main_agent.py` so `/report` now prepends a note when the user is reading a saved report from the shared `default` session.
- Verified through the repo-level bridge on:
  - `--session default --text "/report"`
  - `--session fresh-check --text "/report"`

## 2026-06-17 - Default session carry-over guardrail for `/status`

- Confirmed the same shared-session confusion path on `/status`: the `default` session surfaced an old team plan and stale run state, while a fresh session showed an empty status view.
- Added a matching note in `polyglot_ai/main_agent.py` so `/status` warns when the user is inspecting saved state from the shared `default` session and points them to `/session-new <id>` for a fresh isolated thread.
- Verified through the repo-level bridge on:
  - `--session default --text "/status"`
  - `--session fresh-check --text "/status"`

## 2026-06-17 - Default session carry-over guardrail for `/board`

- Confirmed the same shared-session confusion path on `/board`: the `default` session immediately surfaced an old task board, while a fresh session showed an empty board.
- Added a matching note in `polyglot_ai/main_agent.py` so `/board` warns when the user is inspecting saved state from the shared `default` session and points them to `/session-new <id>` for a fresh isolated thread.
- Verified through the repo-level bridge on:
  - `--session default --text "/board"`
  - `--session fresh-check --text "/board"`

## 2026-06-17 - Default session guardrail extended to saved views

- Confirmed the same shared-session carry-over on `/packet`, `/timeline`, and `/history`: the `default` session surfaced old saved state while a fresh session stayed clean.
- Added the same `default`-session note to these saved views in `polyglot_ai/main_agent.py` so the runtime is explicit about when the user is inspecting shared historical state.
- Verified through the repo-level bridge on:
  - `--session default --text "/packet"`
  - `--session default --text "/timeline"`
  - `--session default --text "/history"`
  - `--session fresh-check --text "/history"`

## 2026-06-17 - Sessions view now shows effective status

- Fixed another summary-layer mismatch: `/sessions` still showed raw saved statuses such as `filling` and `planning` even for sessions that were already stale elsewhere in the product.
- Updated `polyglot_ai/main_agent.py` so the sessions table now reuses the same effective-status logic used by prompt/status/lock, including stale detection from old heartbeats and dead locks.
- Verified through the repo-level bridge on:
  - `--session default --text "/sessions"`
  - `--session fresh-check --text "/sessions"`

## 2026-06-17 - Session brief aligned with stale/default-session reality

- Fixed a live summary mismatch where `Session Brief` could already say `last run: stale` but still offer "running" next steps like `/timeline`, `/steer`, and `/pause`.
- Updated `polyglot_ai/main_agent.py` so `session_brief_text()` and its next-step helper use the effective status instead of the raw saved run status.
- Kept the same shared-`default` session guardrail note on this path as well.
- Verified through the repo-level bridge with `--session default --text "现在做到哪一步了"`.

## 2026-06-17 - Suggested-next-view summary aligned with effective status

- Fixed another raw-status summary seam in `polyglot_ai/main_agent.py`: `suggested_next_view_text()` was still reading the saved `run_state.status` directly.
- Updated it to use the same effective status logic as the rest of the runtime-facing summaries, so stale sessions now recommend `/report`, `/diff`, and `/board` instead of active-run views.
- Verified directly by calling `suggested_next_view_text()` against the shared `default` session.

## 2026-06-17 - Last-run and issue summaries now report stale honestly

- Fixed two more live summary paths in `polyglot_ai/main_agent.py` that still reported the raw saved run status:
  - `Last Run Summary`
  - `Issue Summary`
- Updated both to use the same effective status logic, so stale sessions now say `stale` instead of pretending they are still `filling`.
- Verified through the repo-level bridge on:
  - `--session default --text "刚才做了什么"`
  - `--session default --text "现在有什么问题"`

## 2026-06-17 - ASCII-safe list bullets in formatted output

- Fixed the remaining garbled list bullet in `polyglot_cli.py`'s `print_formatted()` path.
- Replaced the old corrupted glyph with a plain ASCII `- ` marker so high-frequency views like `/report` no longer render broken bullets.
- Verified by piping `/report` into `python .\polyglot_cli.py`.

## 2026-06-17 - Default-session note wording unified

- Unified the shared-`default` session guardrail wording on `/report` with the wording already used on `/status`, `/board`, and the other saved views.
- Replaced the old report-specific note text with the same `prepend_default_session_note(...)` helper used elsewhere.
- Verified through the repo-level bridge on `--session default --text "/report"`.

## 2026-06-17 - Last-run and issue summaries now carry the same default-session note

- Extended the shared-`default` session guardrail note to two more live summaries:
  - `Last Run Summary`
  - `Issue Summary`
- These summaries already reported `stale` correctly after earlier fixes; this change makes their historical-state framing match the rest of the saved-view surface.
- Verified through the repo-level bridge on:
  - `--session default --text "刚才做了什么"`
  - `--session default --text "现在有什么问题"`

## 2026-06-17 - `/report` note now explains cross-run history explicitly

- Tightened the shared-`default` session note for `/report` so it now says the output may come from an earlier run in the same shared session.
- This makes the common `/status` vs `/report` mismatch easier to understand when the default session contains both a stale current run state and an older completed saved report.
- Verified through the repo-level bridge on `--session default --text "/report"`.

## 2026-06-17 - Intent classifier string corruption repaired

- While fixing a control-surface routing bug, exercising the live bridge exposed multiple dormant syntax errors inside `polyglot_ai/main_agent.py`.
- Root cause: several older Chinese example/keyword strings inside preview extractors, delegation heuristics, and `classify_chat_intent()` had become corrupted into invalid Python string literals.
- Repaired those strings to valid Chinese/English keyword lists and examples, then re-verified the live bridge path.
- This also fixed the originally targeted behavior issue: prompts like
  - `控制面现在什么情况`
  - `锁现在什么情况`
  - `有待批准的吗`
  now correctly route to `Control Surface Summary` instead of falling through to a broader session summary.

## 2026-06-17 - Bridge bare-view aliases aligned with CLI

- Fixed a cross-surface mismatch where the CLI already treated bare aliases like `latest`, `recent`, and `messages` as saved views, but the repo-level bridge still treated them as ordinary chat.
- Added the same minimal alias mapping to `skills/polyglot-team-os/scripts/polyglot_skill_bridge.py`.
- Verified through the repo-level bridge on:
  - `latest`
  - `recent`
  - `messages`

## 2026-06-17 - Shell help path and intent keyword tables repaired

- Fixed another shell-vs-chat mismatch: `python .\polyglot_cli.py help` now works as a real subcommand and matches the existing `/help` and natural-language help replies.
- While validating that path, repaired a broader class of dormant import-time failures in `polyglot_ai/main_agent.py`: several corrupted Chinese keyword/example strings inside preview extractors, delegation heuristics, and `classify_chat_intent()` had become invalid Python literals.
- Verified all three help surfaces after the repair:
  - `python .\polyglot_cli.py help`
  - `--text "/help"`
  - `--text "怎么用"`

## 2026-06-17 - Preview/example text cluster repaired

- Continued the same import-stability cleanup in `polyglot_ai/main_agent.py` by repairing another cluster of corrupted Chinese strings:
  - `goal_artifact_hint(...)` keyword hints
  - delegation summary guardrail example text
  - plan/model/cost preview fallback examples
- Verified that `main_agent.py` now compiles cleanly and that the affected live bridge prompts work again:
  - `如果我说：写一个日期转换工具，你会怎么做`
  - `这句话会用哪个模型：写一个带单元测试的日期转换工具`
  - `这句话会不会花钱：现在做到哪一步了`

## 2026-06-17 - Auto-run final report now synthesizes missing session state

- Fixed a core runtime/report mismatch in `polyglot_ai/main_agent.py`: some successful auto-delegated runs completed without a session-level `run_state.json`, which made the final `Run report` show `status: unknown` and `backend: unknown`.
- Added a minimal synthesized session run state fallback at the end of `run_goal()` when monitor execution finishes but no readable session `run_state` was written.
- Verified on a real auto-delegated bridge run with `--session bridge-auto-4 --text "修复这个 bug 并加测试"`; the final report now shows `status: success` and `backend: claude-code-cli`.

## 2026-06-17 - Windows bridge invocation guidance tightened

- Updated the README bridge examples to prefer the PowerShell wrapper for Windows text input:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\polyglot_skill_bridge.ps1 -Workspace ... -Session ... -Text "..."`
- Added an explicit note that the wrapper encodes `-Text` as UTF-8 base64 before invoking Python, which is safer than relying on raw shell argv encoding for Chinese text.
- Verified the documented wrapper shape with a live `-Text "hello"` call.

## 2026-06-17 - Chinese goal text now survives the Windows wrapper path

- Extended the bridge/monitor/planner handoff to use `POLYGLOT_GOAL_B64` instead of relying on raw argv when launching `monitor.py` and `v0_planner.py`.
- Replaced the damaged `v0_planner.py` mock-plan implementation with a smaller, clean UTF-8-safe version and repaired several structural breakages in both `v0_planner.py` and `monitor.py` that were blocking the path.
- Verified with a real PowerShell wrapper call using `-TextFile` and a Chinese task prompt that the live console output now shows:
  - `task: 修复这个 bug 并加测试`
  - `goal: 修复这个 bug 并加测试`
  instead of mojibake.
- Verified directly from session files using Python UTF-8 reads that the saved values are also correct in:
  - `messages.jsonl`
  - `team_plan.json`
  - `run_state.json`

## 2026-06-17 - Bridge -> monitor -> planner Chinese handoff fully aligned

- Continued the UTF-8-safe handoff work by finishing the last two layers:
  - `monitor.py` now prefers `POLYGLOT_GOAL_B64`
  - `v0_planner.py` now prefers `POLYGLOT_GOAL_B64`
- Repaired the broken sections of `monitor.py` and `v0_planner.py` that were still blocking the path with syntax/indentation/docstring damage from older corrupted text.
- Verified end to end with a real PowerShell wrapper `-TextFile` run (`textfile-check-11`) that all of the following now preserve the Chinese goal text correctly:
  - live monitor console output
  - `messages.jsonl`
  - `team_plan.json`
  - `run_state.json`

## 2026-06-17 - Windows PowerShell `-Text` path promoted to first-class

- Follow-up verification confirmed that the PowerShell wrapper `-Text "中文"` path now preserves Chinese correctly not only in live monitor output, but also in saved session files.
- Verified on `ps-text-direct-2` that the following all retain the original Chinese goal text:
  - `messages.jsonl`
  - `team_plan.json`
  - `run_state.json`
- Updated the README guidance accordingly: on Windows, the `.ps1` wrapper with `-Text` is now the primary recommended path, while `-TextFile` remains the better choice for longer or more complex prompts.

## 2026-06-17 - Skill and host-integration docs realigned to the wrapper path

- Updated `skills/polyglot-team-os/SKILL.md` so the fallback bridge section now includes the repo-level PowerShell wrapper path for Windows hosts.
- Updated `skills/polyglot-team-os/references/host-integration.md` with a dedicated Windows PowerShell host section, including both `-Text` and `-TextFile` usage.
- Verified the documented wrapper shape with a live `/status` call through:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\polyglot_skill_bridge.ps1 -Workspace ... -Session skill-doc-check -Text "/status"`

## 2026-06-17 - Monitor live output strings cleaned up

- Cleaned the remaining user-visible mojibake in `monitor.py`’s live output strings, including:
  - rich-not-installed warning
  - rich-mode key hint line
  - rich-mode log panel titles
  - final completion rule title
- Re-checked that `monitor.py` still compiles after the cleanup.

## 2026-06-17 - Doctor trust restored after Windows encoding edits

- A follow-up `python .\polyglot_cli.py doctor` run exposed a Windows-specific regression from PowerShell `Set-Content -Encoding utf8`: several core Python files had been rewritten with UTF-8 BOMs, and the doctor syntax pass was reading them as plain `utf-8` instead of `utf-8-sig`.
- Rewrote the affected Python files (`polyglot_cli.py`, `polyglot_ai/main_agent.py`, `monitor.py`, `polyglot_ai/v0_planner.py`) as UTF-8 without BOM.
- Re-ran:
  - `python .\polyglot_cli.py doctor`
  - targeted `py_compile`
  and confirmed `syntax: ok` / `result: ok`.

## 2026-06-17 - Repeated BOM regression on `main_agent.py` cleared

- Another later PowerShell write reintroduced a UTF-8 BOM on `polyglot_ai/main_agent.py`, which immediately broke `doctor` again even though the live bridge paths still worked.
- Rewrote `polyglot_ai/main_agent.py` back to UTF-8 without BOM and re-ran:
  - `python .\polyglot_cli.py doctor`
  - `python -m py_compile .\polyglot_ai\main_agent.py`
- Result returned to `syntax: ok` / `result: ok`.

## 2026-06-17 - Repeated BOM regression on `monitor.py` cleared

- After the later monitor/planner repairs, another PowerShell write left `monitor.py` with a UTF-8 BOM, which again made `doctor` report a false syntax failure even though the wrapper path still ran.
- Rewrote `monitor.py` back to UTF-8 without BOM and re-ran:
  - `python .\polyglot_cli.py doctor`
  - a direct `compile(...)` check on `monitor.py`
- Result returned to `syntax: ok` / `result: ok`.

## 2026-06-17 - Windows wrapper guidance narrowed to the truly reliable path

- Follow-up verification showed an important nuance: the PowerShell wrapper with raw `-Text "中文"` now displays Chinese correctly in the live console path, but session-file persistence can still be mojibake depending on the shell path.
- Tightened the README guidance accordingly:
  - use the PowerShell wrapper instead of calling Python directly on Windows
  - use `-TextFile` for Chinese prompts when persistence fidelity matters
  - keep raw `-Text` mainly for simpler/ASCII-friendly cases

## 2026-06-17 - Specific current-status phrases no longer fall into session brief

- Tightened `classify_chat_intent()` ordering so explicit status phrases such as `当前状态` and `现在状态` resolve to `Current Status Summary` before the broader `session_brief` catch-all.
- Verified through the repo-level bridge on:
  - `--text "当前状态"`
  - `--text "现在状态"`

## 2026-06-17 - Saved-goal route summary now carries the default-session guardrail

- Fixed a subtle shared-session mismatch: a bare `route` on the `default` session reused the last saved engineering goal without warning, even though other saved-state views already explained that they were historical.
- Updated `route_chat_text_for_saved_goal()` so the default session now prepends the same shared-history note before showing a saved-goal route decision.
- Verified through the repo-level bridge on:
  - `--session default --text "route"`
  - `--session fresh-check --text "route"`

## 2026-06-17 - Explicit next-step prompts now hit Suggested Next View

- Tightened the intent routing again so explicit prompts like `what next` and `next step` resolve to `Suggested Next View` instead of falling back to the generic chat reply.
- Verified through the repo-level bridge on:
  - `--text "what next"`
  - `--text "next step"`

## 2026-06-17 - Task board status now respects the latest successful run

- Fixed a trust-breaking inconsistency where `/status` could say `success` while `/board` still showed `plan: failed` and carried forward old error counts from previous attempts in the shared session.
- Updated `polyglot_ai/task_board.py` so successful latest runs override stale task failure/error carry-over for the high-level task statuses and error counts.
- Verified by comparing the current default session through:
  - `python .\polyglot_cli.py status`
  - `python .\polyglot_cli.py board`

## 2026-06-17 - Successful runs no longer leave core todos pending

- Tightened the success semantics in `polyglot_ai/task_board.py` so a clean successful run now marks the high-level task chain as complete:
  - `plan`
  - `implement`
  - `verify`
  - `docs`
  - `report`
- This removes the confusing case where `Run report` could say `success` while still listing `implement/docs/report` as `pending`.
- Verified against a successful session (`ps-text-direct-2`) in both:
  - `format_run_report(0)`
  - `python .\polyglot_cli.py board`

## 2026-06-17 - Planning-first engineering prompts now get a useful preview

- Improved the fallback path in `polyglot_ai/main_agent.py` for natural requests such as `写一个日期转换工具，先别写代码，先说计划`.
- Instead of returning the generic `I will not call a worker for this...` message, the runtime now returns a plan-preview-style reply while still honoring the no-code/no-worker constraint.
- Verified through the repo-level bridge on `--text "写一个日期转换工具，先别写代码，先说计划"`.

## 2026-06-17 - Planning-first preview now includes a real plan skeleton

- Refined `plan_preview_chat_text()` so planning-first engineering prompts no longer stop at a generic “stay in chat” message.
- These prompts now return a concrete preview-only plan summary with:
  - complexity
  - the issue-graph step chain (`plan -> implement -> verify -> report`)
  - clear next actions for refining, routing, or starting execution
- Verified again through the repo-level bridge on `--text "写一个日期转换工具，先别写代码，先说计划"`.

## 2026-06-17 - English planning-first prompts no longer misfire

- Tightened `classify_chat_intent()` so common English planning-first phrases such as:
  - `show me the plan`
  - `plan first`
  - `do not code yet`
  resolve to `plan_preview` instead of accidentally auto-running or falling back to the generic chat reply.
- Cleaned the `Plan Preview` fallback examples at the same time so the prompt help text is readable again.
- Verified through the repo-level bridge on:
  - `write a date converter, but do not code yet; show me the plan`
  - `show me the plan first for a date converter`

## 2026-06-17 - Non-TTY Windows PowerShell Chinese pipe limitation confirmed

- Re-tested plain CLI auto-delegation with a PowerShell here-string pipe carrying Chinese text.
- Result: the Python process receives the message as `???? bug ????` before Polyglot logic sees it, so the fallback chat reply is expected on that exact path.
- This confirms the remaining mismatch is upstream of Polyglot's intent/delegation logic in the current Windows PowerShell pipe encoding path, not in `chat_reply()` itself.

## 2026-06-16 - Current Direction

### vNext Product Direction Update

The product direction has changed from "CLI-centered product" to "host-agnostic local runtime".

The CLI remains important as a fallback and developer surface, but Polyglot should be built so Codex, Antigravity, WorkBuddy, Hermes, Claude Code, Cursor, and other AI clients can call it.

New source-of-truth direction document:

- `docs/vnext-host-runtime.md`

Key decision:

- MCP is the primary interface.
- Skill is the workflow instruction layer.
- Plugin is the install/package layer.
- CLI is debug and fallback.
- Polyglot Runtime remains the actual product.

### Product Shape

Historical note: the following section describes the earlier local-first CLI stabilization phase. For current product positioning and host integration strategy, prefer `docs/vnext-host-runtime.md`.

Polyglot AI Team OS should stay small, terminal-first, and local-agent-first.

The immediate goal is not to build a large multi-agent platform. The goal is to make a reliable local Team Runtime:

1. Main Agent can see the workspace.
2. Main Agent can explain current state.
3. Runtime can plan, run, test, self-heal, report, and hand off.
4. Human steering is first-class.
5. Worker execution remains low-token and structured.

### Important Constraint

Do not add a separate LLM layer for the Main Agent right now.

The Main Agent's current weakness is not "lack of intelligence"; it is lack of deterministic workspace awareness. Use local code for workspace introspection before adding another model/prompt layer.

### Phase 0 Implemented

Implemented deterministic workspace awareness:

- `Runtime.workspace_snapshot()`
- `Runtime.workspace_summary_text()`
- `MainAgent.workspace_text()`
- CLI `/workspace` and `/repo`
- HTTP/Hermes bridge `/workspace` and `/repo`
- Team Plan now includes `workspace_context`

This lets the Main Agent answer questions such as:

- What is in this repo?
- Where should I look first?
- What kind of project is this?
- Which files are core entry points?

### New PDF Inputs

Latest planning artifacts added to the repo:

- `polyglot-ai-team-dev-plan-v5.pdf`
- `polyglot-ai-team-dev-plan-v5.txt`
- `polyglot-main-agent-no-extra-llm-styled.pdf`
- `polyglot-main-agent-no-extra-llm-styled.txt`

Important conclusion from these documents:

- First make the Main Agent not blind.
- Then stabilize the Team OS loop.
- Then introduce Worker Fabric/profile routing.
- Then deepen security, Feishu/Hermes, and skills.

### HTML Input: Model-Independent Execution Container

User clarified the intended model strategy:

Claude Code should be treated as a general execution container, not as a Claude-only worker.

The selected model should be switched by process-level environment variable injection when launching the Claude Code subprocess.

Relevant environment variables:

- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_AUTH_TOKEN`
- `ANTHROPIC_MODEL`
- `API_TIMEOUT_MS`
- `CLAUDE_CODE_ENABLE_MCP_UNOFFICIAL`

The correct direction:

1. User owns model/API access.
2. Polyglot stores or references model profiles.
3. Main Agent selects only a profile id, such as `deepseek-pro`.
4. Runtime/worker launcher resolves that profile.
5. Runtime injects environment variables into the child process only.
6. Runtime starts Claude Code as the execution container.
7. The global user environment is not modified.

### Key Security Boundary

The Main Agent must not see secrets.

The Main Agent may know:

- profile id
- display name
- capability tags
- cost tier
- model name, if non-sensitive

The Main Agent must not know:

- API key plaintext
- decrypted key
- raw auth token

Small MVP-safe approach:

- Do not store plaintext keys in repo.
- First use `api_key_env`, e.g. `DEEPSEEK_API_KEY`.
- Profile config stores only the environment variable name.
- Runtime maps `DEEPSEEK_API_KEY` to `ANTHROPIC_AUTH_TOKEN` only when starting the worker subprocess.

Later hardening:

- Windows DPAPI encrypted key storage.
- Redaction for terminal output, logs, events, reports, and artifacts.
- Allowlist for remote commands and sensitive operations.
- Audit records with profile id, task id, latency, and status, but no secret.

### In-Progress Slice

Started a minimal `polyglot_ai/model_profiles.py` module.

Intended MVP behavior:

- Read `polyglot_models.json`.
- Select profile from `POLYGLOT_MODEL_PROFILE` or config default.
- Profile contains `id`, `name`, `base_url`, `model`, `api_key_env`, `timeout_ms`, `capabilities`, and `cost_tier`.
- Build child-process environment for Claude Code.
- Do not expose or log API key values.

This slice is not complete until:

- worker adapter uses profile environment when launching Claude Code.
- `polyglot_models.example.json` exists.
- CLI/doctor can show active profile without secrets.
- smoke test proves no key appears in event/log output.

### What Not To Do Yet

Do not implement all of these now:

- full TUI model configuration screen
- DPAPI storage
- parallel multi-worker scheduler
- model cost optimizer
- full Worker Fabric abstraction
- cloud account management

These are real future features, but they are not the next small step.

### Next Best Step

Finish the smallest model profile slice:

1. Add `polyglot_models.example.json`.
2. Wire `model_profiles.build_claude_env()` into `LocalCliWorkerAdapter._run()`.
3. Record active profile id/name in timeline/task metadata.
4. Add doctor visibility for model profile config.
5. Verify with a fake env var that secret values are injected into the subprocess environment but never printed.

### 2026-06-16 Update

The model profile slice now has a first implementation pass:

- `polyglot_ai/model_profiles.py` reads `polyglot_models.json`.
- `polyglot_models.example.json` documents the DeepSeek-via-Claude-Code pattern.
- `LocalCliWorkerAdapter` builds a child-process environment from the selected profile.
- `polyglot_cli.py doctor` reports selected profile metadata without printing key values.

### 2026-06-16 DeepSeek Documentation & Rules Alignment

Aligned Model Profiles with the latest DeepSeek API documentation and user requirements:
- Updated `polyglot_models.example.json` to use official model names (`deepseek-v4-pro[1m]` and `deepseek-v4-flash`).
- Expanded `polyglot_ai/model_profiles.py` to support propagating custom environment variables (e.g., `ANTHROPIC_DEFAULT_*`, `CLAUDE_CODE_*`) from the profile config's `env` dictionary to the child process environment. This enables complete native integration with DeepSeek via Claude Code.
- Added a `Mandatory Documentation Rule` to repository rules (`docs/development-log.md`, `.cursorrules`, and `.clauderules`) to guarantee AI actions are recorded for future agent handover and user learning.

### 2026-06-16 CLI upgrade to benchmark Claude Code Terminal UX

Successfully completed the comprehensive upgrade of `polyglot_cli.py` to match Claude Code's terminal UX:
- **New Commands Added**:
  - `/clear`: Clears terminal screen.
  - `/cost`: Tracks and estimates session API costs based on model profiles and execution statistics, and displays git diff changes (added/removed lines).
  - `/model`: Lists configuration profiles and supports process-wide model profile switching.
  - `/diff`: Renders uncommitted repository changes using `rich.syntax.Syntax` diff colorization.
- **Enhanced Autocomplete**:
  - Context-aware autocomplete in `PolyglotCompleter` completes active model profile IDs when entering `/model` or `/profile`.
  - Slash commands that do not accept file paths suppress folder/file completions, ensuring clean terminal TAB output.
- **Visual Refinement**:
  - Added `print_error` helper for bold red error reporting under the REPL shell and direct commands parser.
  - Subcommands can also be directly run from the system shell (`python polyglot_cli.py cost`, `python polyglot_cli.py model`, `python polyglot_cli.py diff`).
- **Configuration Defaults**:
  - Copied `polyglot_models.example.json` to `polyglot_models.json` for out-of-the-box model settings.

All syntax and system diagnostics check out successfully via `python polyglot_cli.py doctor`.

### 2026-06-16 Global CLI & Multi-Directory Execution Enablement

Enabled Polyglot OS to run globally in any directory on the user's system:
- **Workspace Isolation**:
  - Simplified `find_workspace_dir()` in `polyglot_cli.py` to default to `os.getcwd()` (current working directory) when `POLYGLOT_WORKSPACE` environment variable is not explicitly set. This maps the target workspace to whichever project directory the user launched from.
  - Modified `polyglot.bat` to remove the hardcoded `POLYGLOT_WORKSPACE=%~dp0` environment override, allowing correct working directory detection.
- **Global Configuration Fallback**:
  - Updated configuration readers in `polyglot_ai/agents.py` and `polyglot_ai/model_profiles.py` to fall back to the global installation folder (`d:\Repository\polyglot-ai-team`) for reading `polyglot_agents.json` and `polyglot_models.json` if they are not defined locally in the target project workspace directory.
  - This allows a user to run the tool globally while maintaining centralized model profiles and agent definitions, while still letting them optionally override configs locally by dropping json files in the target project.
- **Doctor Diagnostic and Executable Paths**:
  - Updated `run_doctor()` to scan package/code syntax integrity target directories relative to the OS installation folder (`INSTALL_DIR`) instead of the active workspace, ensuring the diagnostic tool passes successfully when run in arbitrary project directories.
  - Fixed `run_monitor()` in `polyglot_ai/main_agent.py` to correctly resolve the monitor subprocess executable script path relative to the installation directory.

## Development Rule

1. **Mandatory Documentation Rule**: Whatever changes, modifications, or implementations the AI performs must be documented in the development log (`docs/development-log.md`). The entry should clearly outline:
   - What was done (files created/modified, changes made)
   - The design decisions and rationale (why it was done this way)
   - Verification results (how it was verified)
   - Next steps / pending items
   This ensures a smooth hand-off to the next AI agent and serves as an explicit learning record for the user.

### 2026-06-16 Local-First Scope Correction

User explicitly deprioritized Feishu for the current development slice: "飞书这个可以最后弄，先把本地弄好".

Current priority order:

1. Make the local terminal Team OS loop feel solid first.
2. Stabilize Main Agent behavior, natural chat/task routing, Task Board, Team Plan, Claude execution, self-healing, report, and handoff.
3. Keep model configuration and model routing local and CLI-driven.
4. Treat Feishu/Hermes as later host adapters after the local loop is dependable.

Implementation note:

- `MainAgent.build_issue_graph()` now adds a `docs` task not only for explicit documentation goals, but also for CLI/test/user-visible delivery goals. This makes the task graph closer to a real delivery checklist: plan, implement, verify, document when behavior changes, then report.

Verification:

- `python -B -m unittest polyglot_ai.test_task_board polyglot_ai.test_runtime_flow` passed.

### 2026-06-16 Local Team OS Smoke Gate

Added a deterministic local smoke gate so the local OS loop can be verified before spending real Claude/model calls.

What changed:

- Added `polyglot_ai/local_smoke.py`.
- Added CLI/REPL command `smoke-local`.
- `smoke-local` runs a separate session, defaults to `local-smoke`, forces `FORCE_MOCK=1` and `POLYGLOT_AGENT=mock`, then verifies:
  - process exit is clean
  - `run_state.status` is `success`
  - Team Plan and issue graph exist
  - issue graph entries include `owner`, `intent`, `acceptance`, and `next`
  - Task Board has tasks
  - task packets were recorded
  - final report includes `Todos` and `Next`
  - handoff was written

Bug found and fixed:

- The first smoke run succeeded at the planner/worker/test level but failed the new gate because no task packet was recorded.
- Root cause: `v1_worker.py` only wrote packets for model fill/heal calls. When the draft already contained implementation code, the worker skipped fill and went straight to verification, leaving no structured handoff packet.
- Fix: `v1_worker.py` now records a `verify` task packet for verification-only paths and for existing-implementation skip-fill paths.

Verification:

- `python -B .\polyglot_cli.py smoke-local --session local-smoke-codex-2` passed.
- `python -B -m unittest polyglot_ai.test_local_smoke` passed.

### 2026-06-16 Real Claude Smoke Gate

Added a second explicit smoke command for the real execution container:

- `smoke-local`: cheap deterministic OS-loop verification using the mock worker.
- `smoke-claude`: real Claude Code execution-container verification using the selected model profile.

Design decision:

- Do not make the default smoke command spend model calls.
- Keep real execution verification explicit so the user can first validate local orchestration without cost, then separately validate Claude/model connectivity.

Verification scope:

- `smoke-claude` reuses the same local smoke gate and therefore checks plan, task board, task packets, final report, and handoff for a real worker run.
- Static command wiring and help output were verified before any real model call.

User cost decision:

- User clarified that DeepSeek Pro had insufficient balance during testing and asked: "你下次都用flash别用pro测试了".
- Therefore smoke/test paths must prefer `deepseek-v4-flash`, not `deepseek-v4-pro[1m]`.
- MiniMax currently has remaining balance and can stay as a later backup/comparison profile, but local smoke should not default to MiniMax unless explicitly requested.

Follow-up hardening:

- `smoke-claude` now forces `POLYGLOT_MODEL_PROFILE=deepseek-v4-flash`.
- It also sets a short worker timeout and disables model profile fallback so smoke behaves like a fast diagnostic, not a long production run.
- Windows `taskkill` now has its own timeout while terminating worker subprocess trees, so a hung Claude child process is less likely to hang the orchestrator.

### 2026-06-16 DeepSeek Flash Probe Diagnosis

User observed that DeepSeek balance did not decrease during Claude smoke attempts and asked whether the model was called.

Evidence:

- `claude-smoke-flash-1` reached `worker.adapter.query`, so Polyglot did start the Claude Code CLI path.
- No `claude_run.log` content was written and `date_converter.py` remained a stub, so no successful Claude/model response was observed.
- In the normal Codex sandbox, direct `probe-models deepseek-v4-flash` failed immediately with `WinError 10013`, meaning socket creation was blocked by the execution environment.
- Re-running the same probe outside the sandbox succeeded:
  - `python -B .\polyglot_cli.py probe-models deepseek-v4-flash`
  - result: `ok`
  - latency: about `14.41s`

Conclusion:

- DeepSeek flash key/balance is usable.
- The failed smoke attempts did not prove a successful billable DeepSeek model call.
- Balance not decreasing is consistent with the request being blocked or stuck before a successful model response.
- For future validation, run `probe-models deepseek-v4-flash` first, then run `smoke-claude` from a normal user terminal rather than from a network-restricted sandbox.

### 2026-06-16 Monitor Watchdog Hardening

Problem found:

- `smoke-claude` could start the Claude CLI path and write `worker.adapter.query`, but if the Claude CLI/subprocess tree stalled, the outer smoke command could remain stuck until the parent shell timeout.
- That made the smoke result ambiguous and could leave a stale run lock with `run_state.status=filling`.

What changed:

- `MainAgent.run_monitor()` now supports `POLYGLOT_MONITOR_TIMEOUT_SEC`.
- On monitor timeout it terminates the monitor process tree, waits for cleanup, records `monitor.timeout`, and returns `-4`.
- `MainAgent.run_goal()` now converts monitor timeout into a durable failed `run_state`:
  - `status=failed`
  - `failure_type=monitor_timeout`
  - `last_exit_code=-4`
  - `last_error_summary=Monitor timed out before the worker returned.`
- `POLYGLOT_MONITOR_SCRIPT` was added as a test-only override so watchdog behavior can be verified without invoking Claude or spending model calls.

Verification:

- Added `TestRuntimeControlFlow.test_run_goal_monitor_timeout_writes_failed_state`.
- Ran with `-W error::ResourceWarning` to ensure the timed-out subprocess is waited cleanly.
- Targeted tests passed:
  - `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow polyglot_ai.test_runtime_flow.TestWorkerProfileFallback polyglot_ai.test_local_smoke polyglot_ai.test_provider_probe`
- `python -B .\polyglot_cli.py smoke-local --session local-smoke-watchdog` passed.

### 2026-06-16 Claude Smoke Preflight Split

Further tightened `smoke-claude` so it does not start Claude Code when the selected model endpoint is not reachable.

What changed:

- `smoke-claude` now forces `deepseek-v4-flash` and first runs a direct provider probe for that exact profile.
- If the probe fails, smoke returns a failed diagnostic result with:
  - `model endpoint probe passed = FAIL`
  - `claude execution skipped after failed model probe = OK`
- This separates three cases:
  1. model endpoint/key/network is broken
  2. Claude CLI starts but does not return
  3. Claude CLI returns and the full Team OS smoke gate can validate artifacts

Reason:

- The user noticed DeepSeek balance did not move. That is useful evidence: a started Claude subprocess is not the same as a successful billable model call.
- The smoke gate should make that distinction explicit instead of implying that "Claude started" means "model was called".

Verification:

- Added local unit coverage for model probe check rendering and failed smoke result rendering.

2. When unsure, choose the smallest change that makes the desired final system more true.
 
 3. Avoid large rewrites unless they remove real complexity or unblock the next verified slice.

### 2026-06-16 - Rich Brackets Markup Bug Fix & Chinese Intent Verification

- **Fixed Rich Markup Parsing Bug**:
  - Found that Rich parses lowercase bracketed text (like `[main]` and `[none]`) as style tags, causing them to disappear when printed via `console.print(f"...")`.
  - Refactored `print_formatted` in [polyglot_cli.py](file:///d:/Repository/polyglot-ai-team/polyglot_cli.py) to construct `Text` objects directly for status lines, bulleted lists, and colon key-values, and use `rich.markup.escape` as a fallback. This makes CLI formatted prints completely immune to bracket parsing bugs.
  - Corrected `[main]` print statements in REPL loop and `/chat` to use escaped or Text-styled prefixes and message bodies.
- **Verified Chinese Intent Matching**:
  - Confirmed that typing `"甯垜鐪嬬湅浣犵幇鍦ㄨ繖涓洰褰曟湁浠€涔?` in the interactive REPL correctly routes to the `Workspace Summary` instead of printing the `Session Brief`.
  - Verified that the `[main]` prefix and workspace file counts (like `[none]:3`) print correctly with colored styling.
- **Fixed Global monitor.py Path Resolution**:
  - Identified that global execution of `/run` failed because `monitor.py` resolved the executable scripts `v0_planner.py` and `v1_worker.py` relative to `WORKSPACE_DIR` instead of its own installation directory `INSTALL_DIR`.
  - Updated [monitor.py](file:///d:/Repository/polyglot-ai-team/monitor.py) to resolve script command paths relative to `INSTALL_DIR` while keeping `cwd` as `WORKSPACE_DIR` for correct artifact output.
- **Emergency Secret Key Removal**:
  - Immediately identified and removed a hardcoded fallback API key in [polyglot_ai/v0_planner.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/v0_planner.py#L382). Checked the entire codebase to confirm no other exposed secrets exist.
- **Aligned Model Config Profile IDs with Official DeepSeek IDs**:
  - Updated model profile configurations in [polyglot_models.json](file:///d:/Repository/polyglot-ai-team/polyglot_models.json) and [polyglot_models.example.json](file:///d:/Repository/polyglot-ai-team/polyglot_models.example.json) to use the official model names (`deepseek-v4-pro[1m]` and `deepseek-v4-flash`) as the profile identifiers (`id`) instead of custom descriptors (`deepseek-pro` and `deepseek-fast`). This ensures direct mapping and alignment with official API naming conventions.

### 2026-06-16 - Codex Handoff Stabilization Pass

Gemini handoff requested redaction, config TUI, and parallel worker execution. Codex deliberately limited this pass to safety and compatibility stabilization:

- Added `polyglot_ai/redaction.py` with `redact_secrets()` and recursive `redact_value()`.
- Integrated redaction into `Runtime.append_event()`, `Runtime.append_timeline()`, and `WorkerAdapter.append_log()`.
- Added CLI output/error redaction at `print_formatted()` and `print_error()`.
- Replaced broken Unicode/Rich decorations in `print_formatted()` with ASCII-only `===` and `-` markers to avoid Windows GBK rendering failures.
- Added `polyglot_models.json` to `.gitignore` because it is local private configuration.
- Updated `model_profiles.py` to read both legacy `profiles/default` and HTML-style `configs/default_model/model_name` schemas.
- Removed UTF-8 BOM from `polyglot_cli.py` after PowerShell editing introduced it.

Verification:

- `python -m py_compile polyglot_cli.py polyglot_ai\model_profiles.py polyglot_ai\runtime.py polyglot_ai\worker_adapters.py polyglot_ai\redaction.py polyglot_ai\encryption.py`
- `python .\polyglot_cli.py workspace`
- `$env:POLYGLOT_WORKSPACE='D:\Repository\polyglot-ai-team'; python .\polyglot_cli.py doctor`
- model schema smoke test for `configs/default_model/model_name`
- runtime redaction smoke test for `sk-...`
- repository scan for naked `sk-[A-Za-z0-9_-]{16,}` returned no matches in Python/Markdown entrypoints

Deferred on purpose:

- Config TUI
- Parallel worker execution
- Committing Gemini's large CLI UX changes without separate review

### 2026-06-16 - DeepSeek Official Docs Check

Checked DeepSeek official docs at `https://api-docs.deepseek.com/zh-cn/`.

Confirmed for Claude Code integration:

- `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`
- `ANTHROPIC_AUTH_TOKEN=<DeepSeek API Key>`
- `ANTHROPIC_MODEL=deepseek-v4-pro[1m]`
- `ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]`
- `ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]`
- `ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash`
- `CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash`
- `CLAUDE_CODE_EFFORT_LEVEL=max`

This confirms the current `polyglot_models.example.json` model names and Claude Code env keys are aligned with DeepSeek's public guide as of 2026-06-16.

### 2026-06-16 - Claude Source Reference Boundary

User confirmed `C:\Users\ROG\Desktop\src` is the local Claude source reference used by Gemini.

Use it as a product and interaction reference:

- command routing shape
- REPL/history/completion ideas
- status/cost/diff interaction patterns
- terminal UX conventions

Do not directly copy large source blocks into this repository. Polyglot should keep a small Python-native CLI and reimplement only the behavior that fits the project architecture.

Local runtime artifacts and personal configs should stay out of Git:

- `.agents/`
- `polyglot_models.json`
- `polyglot_agents.json`
- scratch extraction files

### 2026-06-16 - Precision Pass Toward PDF Runtime Loop

User emphasized that the final system should reach the PDF effect, but must stay precise rather than broad.

Small fixes completed:

- Verified mock plan -> run -> report flow through `python .\polyglot_cli.py run "鍐欎竴涓畝鍗曞瓧绗︿覆宸ュ叿"` with `FORCE_MOCK=1`.
- Verified post-run main-agent continuity through `chat`, `status`, and `agents`.
- Added `Runtime.clear_control()` and clear stale control signals before a new run starts.
- Fixed worker launcher behavior so a Claude profile missing its API key does not spawn a doomed subprocess before trying fallback.
- Refined redaction so real key/token/secret values are hidden while non-secret env var names such as `DEEPSEEK_API_KEY` remain visible for diagnostics.

Verification:

- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 34 tests passed.
- `$env:POLYGLOT_WORKSPACE='D:\Repository\polyglot-ai-team'; python .\polyglot_cli.py doctor` -> passed.
- `python -m py_compile polyglot_cli.py polyglot_ai\model_profiles.py polyglot_ai\runtime.py polyglot_ai\worker_adapters.py polyglot_ai\redaction.py polyglot_ai\encryption.py` -> passed.
- `python .\polyglot_cli.py status` after a run now reports `No control signal.`

Next precise milestone:

Run one tiny real Claude Code + DeepSeek profile task after the user is ready to spend model quota, then inspect the timeline/logs for secret redaction and profile audit behavior.

### 2026-06-16 - Runtime Flow Regression Tests

Added `polyglot_ai/test_runtime_flow.py` to lock down two PDF-critical runtime behaviors:

- Starting a new run clears stale control signals, so old `/resume`, `/pause`, or `/stop` commands do not pollute the next run's status.
- If the selected Claude profile is not runnable because its API key env var is missing, the worker does not spawn a doomed subprocess first; it attempts a runnable fallback profile and records the fallback without leaking secrets.

Also closed worker subprocess stdout handles after reading to avoid ResourceWarning noise.

Verification:

- `python -m unittest polyglot_ai.test_runtime_flow -v`
- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 36 tests passed.
- `$env:POLYGLOT_WORKSPACE='D:\Repository\polyglot-ai-team'; python .\polyglot_cli.py doctor` -> passed.
- `$env:POLYGLOT_WORKSPACE='D:\Repository\polyglot-ai-team'; $env:FORCE_MOCK='1'; python .\polyglot_cli.py run "鍐欎竴涓甫娴嬭瘯鐨勬棩鏈熻浆鎹㈠伐鍏?` -> passed.

### 2026-06-16 - Minimal Encrypted Model Config TUI

Added a small, ASCII-only encrypted model profile config flow:

- `python .\polyglot_cli.py config`
- `/config` inside the REPL

The config flow supports:

- add profile
- switch default profile
- edit profile
- delete profile
- view active config

Design constraints:

- Keep it small and terminal-native; do not copy Claude's Ink UI.
- Save local config as `default_model` + `configs`.
- Store API keys only as `api_key_encrypted`; do not write plaintext keys.
- For DeepSeek model names, auto-fill the Claude Code environment defaults from the official DeepSeek guide.

Verification:

- Added `polyglot_ai/test_config_tui.py`.
- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 37 tests passed.
- `python .\polyglot_cli.py --help` shows `config`.
- `$env:POLYGLOT_WORKSPACE='D:\Repository\polyglot-ai-team'; python .\polyglot_cli.py doctor` -> passed.

### 2026-06-16 - Config TUI Refinement

Refined the minimal config flow:

- Escaped model profile cells in `/model` Rich table so official model IDs such as `deepseek-v4-pro[1m]` are not interpreted as Rich markup.
- Added regression coverage for switching the default model profile and deleting a profile.
- Kept the flow ASCII-only and Python-native instead of expanding into a large UI.

Verification:

- `python -m unittest polyglot_ai.test_config_tui -v` -> 2 tests passed.
- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 38 tests passed.
- `python -m py_compile polyglot_cli.py polyglot_ai\model_profiles.py polyglot_ai\runtime.py polyglot_ai\worker_adapters.py polyglot_ai\redaction.py polyglot_ai\encryption.py` -> passed.
- `$env:POLYGLOT_WORKSPACE='D:\Repository\polyglot-ai-team'; python .\polyglot_cli.py doctor` -> passed.

### 2026-06-16 - Monitor Exit Semantics and Real Claude Probe

Tightened the monitor/main-agent contract after a real DeepSeek + Claude Code probe exposed stale-success reporting:

- `monitor.py` now returns the actual planner/worker exit code to the parent process.
- Planner failure paths now write `run.completed` and snapshot events instead of exiting halfway.
- Each monitor run writes a fresh `planning` run state at start, so stale `run_state.json` cannot make a new run look successful.
- `MainAgent.format_run_report()` treats any non-zero monitor process exit as failed even if an old run state says success.
- `MainAgent.run_monitor()` disables monitor input handling when it wraps monitor as a subprocess. Direct `python monitor.py ...` still keeps interactive `i` steering, but `polyglot_cli.py run` no longer lets EOF stop the monitor while planner/worker are still running.

Verification:

- `python -m py_compile monitor.py polyglot_ai\main_agent.py` -> passed.
- Added a regression test ensuring non-zero monitor exits override stale successful run state in the final report.
- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 40 tests passed.
- Mock run with `FORCE_MOCK=1` still succeeds end to end.
- Real run without `FORCE_MOCK` progressed through:
  - planner completed with exit `0`
  - worker started
  - worker status `filling`
  - `claude-code-cli` launched via `C:\Users\ROG\AppData\Roaming\npm\claude.CMD -p`
  - model profile `deepseek-v4-pro[1m]` with base URL `https://api.deepseek.com/anthropic`

The real run exceeded the local tool timeout while Claude was still filling code, so the spawned Python/Claude processes were stopped manually and the session state was marked `failed/interrupted`. This proves the local Claude execution path is now reached; the next precise milestone is timeout/streaming control around long-running Claude calls, not more architecture.

### 2026-06-16 - Claude Worker Timeout Control

Added a small hard-timeout layer around local CLI worker subprocesses:

- `LocalCliWorkerAdapter` now runs local CLI calls through a shared `_run_process()` helper.
- Worker timeout comes from `POLYGLOT_WORKER_TIMEOUT_MS`, then the active model profile `timeout_ms`, then a conservative default.
- On timeout, the subprocess is stopped and the adapter returns exit code `-4`.
- On Windows, timeout cleanup uses `taskkill /F /T /PID ...` so the `.CMD` wrapper and its child process are stopped together.
- Timeout events are recorded as `worker.timeout`.
- Query-mode failures now return an empty response instead of letting timeout/error text become a generated coding instruction.
- `v1_worker.py` maps local CLI exit codes to readable failure types:
  - `-4` -> `worker_timeout`
  - `-3` -> `profile_not_runnable`
  - `-2` -> `subprocess_start_failed`

Verification:

- `python -m py_compile polyglot_ai\worker_adapters.py polyglot_ai\v1_worker.py polyglot_ai\test_runtime_flow.py` -> passed.
- `python -m unittest polyglot_ai.test_runtime_flow.TestWorkerTimeout -v` -> passed.
- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 41 tests passed.
- `$env:FORCE_MOCK='1'; python .\polyglot_cli.py run "鍐欎竴涓?hello_name(name) 鍑芥暟鍜屼竴涓渶灏忔祴璇?` -> passed.

This moves the real Claude path closer to the PDF behavior: the main runtime can now supervise a long-running local worker instead of becoming a black box. The next precise milestone is live progress/heartbeat and user-visible cancellation while a Claude worker is still running.

### 2026-06-16 - Worker Heartbeat and Stop Control

Made long-running local worker calls observable and interruptible:

- Replaced the blocking `communicate(timeout=...)` wait with a small supervised process loop.
- A background reader thread collects worker stdout while the main loop keeps checking runtime state.
- While a local CLI worker is running, the adapter emits `worker.heartbeat` events at a configurable interval.
- Heartbeat interval can be overridden with `POLYGLOT_WORKER_HEARTBEAT_SEC`.
- If `/stop` writes a runtime control signal while a worker subprocess is active, the adapter stops the process tree and returns exit code `130`.
- Stop-triggered local CLI failures map to `user_stopped`.
- Timeout and stop no longer trigger automatic model-profile fallback, because both are control/supervision outcomes rather than ordinary model failures.
- `terminate_process_tree()` now falls back to `process.kill()` after Windows `taskkill`, which made stop reliable in tests.

Verification:

- `python -m py_compile polyglot_ai\worker_adapters.py polyglot_ai\v1_worker.py polyglot_ai\test_runtime_flow.py` -> passed.
- `python -m unittest polyglot_ai.test_runtime_flow.TestWorkerTimeout -v` -> passed.
- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 42 tests passed.
- `$env:FORCE_MOCK='1'; python .\polyglot_cli.py run "鍐欎竴涓?hello_name(name) 鍑芥暟鍜屼竴涓渶灏忔祴璇?` -> passed.

This is a meaningful step toward the intended main-agent feel: a delegated Claude run is now supervised by Polyglot instead of being an uninterruptible subprocess.

### 2026-06-16 - Heartbeat Visibility in Status

Surfaced worker heartbeat information in the main-agent status surface:

- Added `MainAgent.latest_worker_heartbeat()` to read the latest `worker.heartbeat` timeline item.
- `/status` now shows `worker: alive <seconds>` for active run states such as `filling`, `testing`, and `healing`.
- Compact status now includes `alive <seconds>` when a worker is actively running.
- Completed runs do not show stale heartbeat information.

Verification:

- Added a regression test for heartbeat visibility in `polyglot_ai/test_runtime_flow.py`.
- `python -m py_compile polyglot_ai\main_agent.py polyglot_ai\test_runtime_flow.py` -> passed.
- `python -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow -v` -> passed.
- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 43 tests passed.
- `$env:FORCE_MOCK='1'; python .\polyglot_cli.py run "鍐欎竴涓?hello_name(name) 鍑芥暟鍜屼竴涓渶灏忔祴璇?` -> passed.

This makes the heartbeat work user-visible, not just an internal event log detail.

### 2026-06-16 - Heartbeat Visibility in Monitor Header

Surfaced worker heartbeat information in the live terminal monitor:

- `MonitorState` now polls the latest `worker.heartbeat` timeline event while reading run state.
- The Rich header shows `Worker: alive <seconds> via <backend>` during active run states.
- Completed runs do not show stale heartbeat information.
- Header height remains compact in normal completed/mock runs.

Verification:

- `python -m py_compile monitor.py` -> passed.
- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 43 tests passed.
- `$env:FORCE_MOCK='1'; python .\polyglot_cli.py run "鍐欎竴涓?hello_name(name) 鍑芥暟鍜屼竴涓渶灏忔祴璇?` -> passed and the header remained compact when no heartbeat was active.

This brings the live terminal surface in line with the main-agent status surface: active delegated work is visible as alive, not silent.

### 2026-06-16 - Real Claude Timeout Probe and Exit-Code Normalization

Ran a tiny real DeepSeek + Claude Code probe with short supervision settings:

```powershell
$env:POLYGLOT_WORKER_TIMEOUT_MS='5000'
$env:POLYGLOT_WORKER_HEARTBEAT_SEC='1'
python .\polyglot_cli.py run "鍐欎竴涓?hello_name(name) 鍑芥暟鍜屼竴涓渶灏忔祴璇?
```

Observed real-path evidence:

- Planner used DeepSeek API and completed successfully.
- Planner generated `hello_name.py` and `test_hello_name.py`.
- Worker launched `claude-code-cli` through `C:\Users\ROG\AppData\Roaming\npm\claude.CMD -p`.
- The active model profile was `deepseek-v4-pro[1m]`.
- `worker.heartbeat` events appeared at roughly 1s, 2s, 3s, and 4s.
- `worker.timeout` fired at the configured 5s limit.
- `run_state.json` captured `failure_type: worker_timeout` and internal worker exit code `-4`.
- No Claude process was left running after timeout cleanup.

The probe exposed a Windows-specific process exit issue: `sys.exit(-4)` was reported by parent processes as unsigned values such as `4294967292`.

Fixes:

- `v1_worker.py` now keeps internal negative worker codes in `run_state.json`, but exits the process with a normal code (`1`, or `130` for user stop).
- `monitor.py` normalizes Windows unsigned subprocess return codes back to signed internal codes for events and timeline records.
- `monitor.py` maps internal negative codes to a stable external process exit code.
- `MainAgent.format_run_report()` now preserves specific worker failures such as `worker_timeout` instead of replacing them with generic `monitor exited with 1` text.

Verification:

- `python -m py_compile monitor.py polyglot_ai\v1_worker.py polyglot_ai\main_agent.py polyglot_ai\test_runtime_flow.py` -> passed.
- `python -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow -v` -> passed.
- `python -m unittest polyglot_ai.test_runtime_flow.TestWorkerTimeout -v` -> passed.
- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 44 tests passed.
- `python -c "import monitor; print(monitor.normalize_subprocess_returncode(4294967292)); print(monitor.process_exit_code(-4)); print(monitor.process_exit_code(130))"` -> `-4`, `1`, `130`.
- `$env:FORCE_MOCK='1'; python .\polyglot_cli.py run "鍐欎竴涓?hello_name(name) 鍑芥暟鍜屼竴涓渶灏忔祴璇?` -> passed.

This is the first verified real-worker supervision loop: Polyglot can now launch Claude via DeepSeek, observe heartbeats, enforce a timeout, classify the timeout cleanly, and return a sane process code on Windows.

### 2026-06-16 - Real Claude Stop Probe

Ran a real DeepSeek + Claude Code stop-control probe:

- Started `python .\polyglot_cli.py run "鍐欎竴涓?hello_name(name) 鍑芥暟鍜屼竴涓渶灏忔祴璇?` with real Claude routing.
- Waited for a new `worker.heartbeat` event.
- Sent `python .\polyglot_cli.py stop "auto stop verification"` while the Claude worker was running.

Observed real-path evidence:

- Planner used DeepSeek and exited `0`.
- Worker reached `filling`.
- Claude Code launched via `C:\Users\ROG\AppData\Roaming\npm\claude.CMD -p`.
- A `worker.heartbeat` event appeared.
- The stop control was written as `user.control.stop`.
- The active Claude process was stopped and recorded `worker.control.stopped`.
- Worker subprocess exit was `130`.
- `run_state.json` captured `failure_type: user_stopped`.
- The outer run process exited `130`.
- No Claude process was left running afterward.

Follow-up fix from the probe:

- After a query-mode Claude call returns, `v1_worker.py` now checks control signals again before launching the write/edit Claude call.
- This prevents a user stop during instruction-generation from starting a second Claude subprocess just to stop it immediately.

Verification:

- `python -m py_compile polyglot_ai\v1_worker.py` -> passed.
- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 44 tests passed.
- `$env:FORCE_MOCK='1'; python .\polyglot_cli.py run "鍐欎竴涓?hello_name(name) 鍑芥暟鍜屼竴涓渶灏忔祴璇?` -> passed.

This verifies the user steering/control promise on the real Claude path: the main runtime can stop an active delegated worker, not only observe it.

### 2026-06-16 - Monitor Quit Is Stop

Fixed a direct-monitor safety issue:

- Previously, pressing `q` in `monitor.py` only exited the UI loop.
- That could leave the worker pipeline or child CLI process running without the monitor surface.
- `q` now writes a `stop` control signal through the runtime and waits for the pipeline to finish.
- Ctrl-C in the input handler also writes `stop`.
- Monitor footer/help text now says `q stop`, not `q quit`.

Verification:

- `python -m py_compile monitor.py` -> passed.
- `python -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 44 tests passed.
- `$env:FORCE_MOCK='1'; python .\polyglot_cli.py run "鍐欎竴涓?hello_name(name) 鍑芥暟鍜屼竴涓渶灏忔祴璇?` -> passed and showed `q stop`.

This closes an important terminal-first UX gap: leaving the live monitor no longer abandons a local worker.

Follow-up test:

- Added `TestMonitorControlFlow.test_request_stop_writes_runtime_control_signal`.
- The test patches `monitor.RUNTIME` to a temporary runtime, calls `MonitorState.request_stop("monitor q")`, and verifies that a `stop` control signal is written.
- This keeps the monitor contract narrow and explicit: terminal quit intent must flow through runtime control, not by abandoning the UI loop.

Verification:

- `python -m unittest polyglot_ai.test_runtime_flow -v` -> 8 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 45 tests passed.
- `python -m py_compile monitor.py polyglot_ai\test_runtime_flow.py` hit a Windows `__pycache__` permission/lock error after tests had already imported the files successfully; `-B` unittest was used to avoid pyc writes.

### 2026-06-16 - Main Agent Chat Does Not Auto-Delegate By Default

Tightened the terminal-first main-agent experience:

- Bare REPL messages now remain main-agent chat by default.
- The old heuristic that detects task-like prompts is preserved, but it only runs when `POLYGLOT_AUTO_DELEGATE=1`.
- `/run <goal>` remains the explicit execution boundary for worker delegation.
- CLI banner/help now says normal chat is safe and `/run` is the way to delegate.

Why:

- This aligns with the product requirement that the main agent stays available after a worker run and can answer lightweight messages such as `hello` without calling Claude.
- It also reduces accidental cost and side effects when a user is still discussing or refining a task.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow -v` -> 9 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 46 tests passed.
- `python -B .\polyglot_cli.py chat "write code for a hello.py function with unit test"` -> returned the main-agent non-delegation reply.
- `python -B .\polyglot_cli.py chat hello` -> returned the main-agent greeting.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Team Plan Shows Model Profile Route

Improved pre-run team plan transparency:

- `render_team_plan(...)` now includes the selected model profile summary from `plan.routing`.
- `/plan <goal>` shows model profile id, model name, base URL, and key env state when the selected worker route has that data.
- Secret key values are not printed.

Why:

- `/plan` is the lightweight planning surface before execution.
- The user needs to see both the local worker, such as Claude Code, and the actual model endpoint, such as DeepSeek, before delegating work.

Verification:

- `python -B .\polyglot_cli.py plan "鍐欎竴涓棩鏈熻浆鎹㈠伐鍏?` -> showed `deepseek-v4-pro[1m]`, DeepSeek Anthropic-compatible base URL, and `DEEPSEEK_API_KEY:set`.
- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 15 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 67 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Feishu Bridge Dispatch Is Real Runtime Reply

Locked down the remote-control dispatch contract:

- `/status` and `/board` route to `MainAgent.compact_board_text()`.
- `/agents` routes to `MainAgent.agents_text()`.
- Plain text routes to `MainAgent.chat_reply(..., channel="feishu")` and does not run a worker.
- `/run <goal>` remains the explicit remote execution boundary.
- `/steer <message>` routes to `MainAgent.send_steer(...)`.

Why:

- A previous manual webhook probe proved the HTTP listener accepted requests, but that alone only proved the ingress layer.
- These tests prove the command chain calls the main-agent runtime methods and returns their replies, not just an echo of the incoming text.

Verification:

- Added `polyglot_ai/test_feishu_bridge.py`.
- `python -B -m unittest polyglot_ai.test_feishu_bridge -v` -> 5 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /status` -> returned a Feishu payload containing `Polyglot Task Board`.
- `python -B .\feishu_bridge.py --dry-run handle-text hello` -> returned the main-agent greeting.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 51 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - HTTP Listener Token And Reply Contract

Added entry-level coverage for the Feishu/Hermes HTTP listener:

- Direct JSON payloads such as `{"text": "/status"}` extract the command text.
- Feishu-style nested event payloads extract `event.message.content.text`.
- Missing `X-Polyglot-Token` is rejected with HTTP 403 when a token is configured.
- A valid token POST to `/bridge` returns JSON with `ok`, `text`, `session`, and a real `reply`.
- The `/status` reply contains the live `Polyglot Task Board` for the target session.

Why:

- Bridge dispatch tests prove command routing.
- HTTP listener tests prove the external ingress layer preserves auth and returns the actual main-agent reply field that Hermes/Feishu should send back to the user.

Verification:

- `python -B -m unittest polyglot_ai.test_feishu_bridge -v` -> 8 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 54 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Remote Steering Writes Runtime Steer

Added end-to-end HTTP coverage for the human steering path:

- A token-authenticated POST to `/bridge` with `{"text": "/steer limit dates after 2000"}` returns an `[OK] steer sent` reply.
- The listener writes the pending instruction to the target session runtime via `Runtime.send_steer(...)`.
- The target session records a `user.steer` event.
- The default session remains clean after the isolated HTTP test.

Why:

- The product promise is not just remote status viewing; Feishu/Hermes users must be able to interrupt or redirect an active local worker.
- This test proves the remote text command reaches the same `steer.json` mechanism consumed by `v1_worker.py` during self-healing.

Verification:

- `python -B -m unittest polyglot_ai.test_feishu_bridge -v` -> 9 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 55 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Remote Stop And Unlock Safety

Added HTTP listener coverage for remote stop control and remote unlock safety:

- A token-authenticated POST to `/bridge` with `{"text": "/stop user changed direction"}` returns an `[OK] control set: stop` reply.
- The listener writes `control.json` in the target session with `action: stop` and the provided message.
- The target session records a `user.control.stop` event.
- Remote `/unlock` remains disabled by default and returns HTTP 403.
- A lock present in the target session remains in place when remote unlock is rejected.

Why:

- Remote users must be able to stop a local worker through the same runtime control file that the worker adapter watches.
- Unlock is more dangerous than status/steer/stop because it can break active run ownership, so it stays opt-in through the listener's `--allow-unlock` flag.

Verification:

- `python -B -m unittest polyglot_ai.test_feishu_bridge -v` -> 11 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 57 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Remote Pause And Resume Control

Extended HTTP listener coverage for the remaining remote control actions:

- Token-authenticated `/pause need review` writes `control.json` with `action: pause` and the provided message.
- Token-authenticated `/resume go ahead` replaces it with `action: resume` and the provided message.
- The target session records `user.control.pause` and `user.control.resume` events.

Why:

- Feishu/Hermes control should cover the full safe runtime-control vocabulary: steer, pause, resume, and stop.
- These all use the same runtime control path watched by workers, so remote and terminal control stay equivalent.

Verification:

- `python -B -m unittest polyglot_ai.test_feishu_bridge -v` -> 12 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 58 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Worker Pause Checkpoint Actually Waits For Resume

Added direct worker checkpoint coverage for pause/resume:

- `v1_worker.honor_control_signal(...)` sees `pause`, writes `run_state.status = paused`, and does not return immediately.
- While paused, a later `resume` control lets the worker continue.
- The worker restores the previous active status after resume.
- The target runtime records `worker.control.paused` and `worker.control.resumed` events.

Why:

- HTTP tests proved remote `/pause` and `/resume` write control files.
- This test proves the worker-side checkpoint consumes those controls as a real pause/resume flow, not just as inert state.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow -v` -> 10 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 59 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Compact Task Board Shows Control Reason

Improved the structured task board used by remote `/status`:

- `render_compact_task_board(...)` now includes the control message for active non-resume controls.
- Example: `control: pause | need human review before continuing`.
- Added task-board rendering coverage for run status, control reason, and artifact line counts.

Why:

- Feishu/Hermes usually consume the compact board, not the full terminal board.
- If a run is paused or stopped, the remote user needs to see the reason, not just the raw action name.
- This keeps low-token coordination structured while preserving enough context for human steering.

Verification:

- Added `polyglot_ai/test_task_board.py`.
- `python -B -m unittest polyglot_ai.test_task_board -v` -> 1 test passed.
- `python -B -m unittest polyglot_ai.test_feishu_bridge -v` -> 12 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 60 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Configured Agent Paths Resolve To Real CLI Executables

Improved local agent discovery transparency:

- Configured CLI agents keep their configured `command` unchanged.
- Their displayed `path` now resolves the first command token through `PATH`.
- On Windows, a configured `command: "claude"` now displays the real `claude.CMD` path when available.
- Runtime command construction already resolved the executable before launch; this change makes `/agents` and route/status surfaces honest about the actual local CLI being used.

Why:

- Local-first agent discovery should make it clear which installed worker will run.
- This also avoids confusion around Windows `.ps1` execution-policy failures by showing the `.CMD` command that will actually be used.

Verification:

- `python -B -m unittest polyglot_ai.test_agents -v` -> 2 tests passed.
- `python -B .\polyglot_cli.py agents` -> displayed `Claude Code CLI: C:\Users\ROG\AppData\Roaming\npm\claude.CMD`.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 61 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Model Profile Route Is Visible Without Leaking Keys

Improved `/model` transparency for the "Claude Code as execution container, user-selected model endpoint underneath" design:

- `/model` still shows the compact profile table.
- It now adds active profile details below the table:
  - `base_url`
  - key env state such as `DEEPSEEK_API_KEY:set`
  - Claude Code worker env names: `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, `ANTHROPIC_AUTH_TOKEN`
- It does not print the secret key value.

Why:

- The user should be able to see whether Polyglot will route Claude Code through DeepSeek or another configured endpoint.
- The model routing surface must be explicit enough to debug, but safe enough to paste into chat/logs.

Verification:

- `python -B .\polyglot_cli.py model` -> displayed `base_url: https://api.deepseek.com/anthropic` and `key: DEEPSEEK_API_KEY:set`.
- `python -B -m unittest polyglot_ai.test_redaction -v` -> 5 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 62 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Model Switch Scope Is Explicit

Clarified `/model <profile-id>` behavior:

- Switching a model profile sets `POLYGLOT_MODEL_PROFILE` for the current CLI process.
- The command now prints that scope explicitly.
- It tells users to use `POLYGLOT_MODEL_PROFILE=<id>` for a one-command override or `/config` to persist a default.

Why:

- In the interactive CLI, `/model <id>` correctly affects later `/run` calls in that same process.
- In a one-shot command such as `python polyglot_cli.py model deepseek-v4-flash`, the process exits immediately, so the switch cannot affect future shells.
- Being explicit avoids the false impression that `/model <id>` silently rewrites `polyglot_models.json`.

Verification:

- `python -B .\polyglot_cli.py model deepseek-v4-flash` -> printed the scope hint.
- `python -B .\polyglot_cli.py model` -> config default remained `deepseek-v4-pro[1m]`.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 62 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Route Decision Shows Claude Model Profile

Improved pre-run routing transparency:

- `MainAgent.route_decision(...)` now merges the current environment with per-command overrides before selecting workers and model profiles.
- When the selected worker adapter is Claude, route output includes:
  - model profile id
  - model name
  - base URL
  - key env state such as `DEEPSEEK_API_KEY:set`
- Secret key values are not printed.

Why:

- `/model` shows the current model configuration, but `/route <goal>` is the user's pre-run decision surface.
- Before delegating to Claude Code, users should see whether the execution will use the configured DeepSeek endpoint or another profile.

Verification:

- `python -B .\polyglot_cli.py route "鍐欎竴涓棩鏈熻浆鎹㈠伐鍏?` -> showed `model: deepseek-v4-pro[1m]`, `base_url: https://api.deepseek.com/anthropic`, and `key: DEEPSEEK_API_KEY:set`.
- `python -B -m unittest polyglot_ai.test_runtime_flow -v` -> 11 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 63 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Task Board Carries Model Profile Summary

Connected model routing into structured task state:

- `build_task_board(...)` now carries `model_profile` and `model_profile_warning` from `team_plan.routing`.
- Full task board renders the model profile id, model name, and base URL.
- Compact task board includes the model profile id in the status line.

Why:

- `/route` is the pre-run explanation surface.
- `/status` and `/board` are the during-run coordination surfaces, especially for Feishu/Hermes.
- Remote collaborators should be able to see which model profile is associated with the current plan without asking the main agent separately.

Verification:

- `python -B -m unittest polyglot_ai.test_task_board -v` -> 1 test passed.
- `python -B .\polyglot_cli.py board` -> rendered the current default session successfully.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 63 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Main Agent Answers Model Questions Without Delegating

Improved lightweight main-agent chat:

- Questions like `鐜板湪鐢ㄤ粈涔堟ā鍨媊 now return the route/model summary instead of a generic session brief.
- The reply includes worker, model profile, base URL, and key env state.
- It does not start a run or leak secret key values.

Why:

- The user explicitly wanted the main agent to remain conversational after runs and not call Claude for simple questions.
- Model routing is one of the most common lightweight questions in this project because Claude Code is the execution container while DeepSeek or another endpoint may be the actual model.

Verification:

- `python -B .\polyglot_cli.py chat "鐜板湪鐢ㄤ粈涔堟ā鍨?` -> returned route/model information with `DEEPSEEK_API_KEY:set`.
- `python -B -m unittest polyglot_ai.test_runtime_flow -v` -> 12 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 64 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Handoff Preserves Model Profile Route

Improved handoff durability:

- Session handoff plan sections now include model profile id, model name, base URL, and key env state when the route has a model profile.
- Secret key values are not included.

Why:

- The user wanted durable development notes so context compaction or agent handoff does not lose important decisions.
- For this project, the model route is a key decision: Claude Code may be the execution container while DeepSeek or another endpoint is the actual model profile.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow -v` -> 13 tests passed.
- `python -B .\polyglot_cli.py handoff` -> rendered current default session handoff successfully.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 65 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Approval Prompts Show Model Profile Route

Improved pre-run approval visibility:

- Approval request text now includes the same model profile summary used by route output.
- `/approval` also shows the model profile summary from the stored approval decision.
- The rendered fields include model profile id, model name, base URL, and key env state.
- Secret key values are not printed.

Why:

- Approval is the last human checkpoint before a higher-trust worker action.
- If Claude Code is the execution container but DeepSeek or another endpoint is the real model route, the approver should see that before approving.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow -v` -> 14 tests passed.
- `python -B .\polyglot_cli.py route "鍐欎竴涓棩鏈熻浆鎹㈠伐鍏?` -> route format still shows model/base_url/key state.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py" -v` -> 66 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Run Report Shows Model Profile Route

Improved final main-agent reporting:

- `format_run_report(...)` now includes model profile summary from `team_plan.routing`.
- The final run report shows model profile id, model name, base URL, and key env state when available.
- Secret key values are not printed.

Why:

- The user expects the main agent to report after Claude finishes and remain available for follow-up conversation.
- That report should state both the local execution worker and the actual model endpoint used for the run.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 16 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 68 tests passed.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Session Brief And Status Show Model Profile Route

Improved post-run and lightweight chat visibility:

- `status_text()` now shows model profile summary in the team plan section.
- `session_brief_text()` now shows model profile summary when a team plan has routing data.
- Plain chat can answer the current worker/model route without delegating to Claude.
- Secret key values are not printed.

Why:

- The user wants the main agent to remain useful after Claude finishes.
- Lightweight follow-up questions should explain the current run/session without starting another worker.
- The model route is a core distinction: Claude Code may be the execution container while DeepSeek or another profile is the actual model endpoint.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 17 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 69 tests passed.
- `python -B .\polyglot_cli.py chat "<status question>"` -> returned session brief with model/base_url/key state and no worker run.
- `python -B .\polyglot_cli.py status` -> showed model route, no run lock, no steer, no control signal.

### 2026-06-16 - CLI Report Command Reads Final Report

Aligned local CLI with the existing Feishu/Hermes report surface:

- Added `report` / `/report` to `polyglot_cli.py` command discovery, completion, help, REPL dispatch, argparse parser, and non-interactive command dispatch.
- The command reuses `MainAgent.read_final_report()` and `print_formatted(...)`.
- Output goes through existing secret redaction before printing.

Why:

- The runtime already writes `final_report.md` after a worker run.
- Feishu/Hermes already supported `/report`, but the local CLI did not.
- The user wants to keep talking to the main agent after Claude finishes and quickly retrieve the final report without starting another worker.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 18 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 70 tests passed.
- `python -B .\polyglot_cli.py report` -> printed the latest final report.
- `python -B .\polyglot_cli.py --help` -> listed the `report` command.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Chat Report Reads Saved Final Report Safely

Improved post-run follow-up behavior:

- Plain chat messages containing `report`, `summary`, or `result` now read the saved `final_report.md` through `MainAgent.read_final_report()`.
- `read_final_report()` now redacts secrets at the source, so CLI, Feishu/Hermes, and chat surfaces share the same safer output.
- Fixed an intent collision where `report` matched the substring `repo` and incorrectly returned the workspace summary.
- README now documents that plain chat `report` / `summary` reads the saved report without starting a worker.

Why:

- The user wants the main agent to remain conversational after Claude finishes.
- A final report should be a stable saved artifact, not a regenerated approximation.
- Secret redaction belongs at shared output sources, not only at one CLI printing path.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 19 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 71 tests passed.
- `python -B .\polyglot_cli.py chat report` -> returned the saved final report, not workspace summary.
- `python -B .\feishu_bridge.py --dry-run handle-text /report` -> returned the saved final report through the remote bridge path.

### 2026-06-16 - Feishu Bridge Redacts Remote Replies

Improved remote-control safety:

- `dispatch_text(...)` now redacts secrets before returning replies to HTTP listener callers.
- `post_feishu_text(...)` also redacts before building webhook payloads, protecting direct `post-*` bridge commands.
- Runtime state still keeps the original steer/control text; only outbound reply surfaces are redacted.

Why:

- Feishu/Hermes is a collaboration boundary, so reply payloads should be safe by default.
- Previous redaction existed in CLI printing and final-report reading, but not every remote bridge output path.
- Commands like `/steer <secret>` can legitimately store the user instruction locally while avoiding echoing the secret back to the chat room.

Verification:

- `python -B -m unittest polyglot_ai.test_feishu_bridge` -> 14 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 73 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /steer sk-...` -> outgoing payload contained `[REDACTED]`.
- `python -B .\feishu_bridge.py --dry-run handle-text /report` -> returned the saved final report through the remote bridge path.
- `python -B .\polyglot_cli.py cancel` -> cleared the pending steer created by the dry-run probe.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Feishu Remote Help Command

Improved remote usability:

- Added `remote_help_text()` to `feishu_bridge.py`.
- `/help` and `help` now return a compact command directory for Feishu/Hermes users.
- The help path does not call the main agent and cannot start a worker.
- README remote examples now include `/help`.

Why:

- Feishu/Hermes users need a low-friction way to discover available commands from chat.
- Remote control should make safe read-only commands obvious and mark `/run` as trusted-users-only.
- This keeps the IM interface useful without adding a larger web UI or bot framework.

Verification:

- `python -B -m unittest polyglot_ai.test_feishu_bridge` -> 16 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 75 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /help` -> printed the compact remote command directory.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Feishu Remote Cancel For Pending Steer

Improved human steering recovery:

- Feishu/Hermes `dispatch_text(...)` now supports `/cancel` and `cancel`.
- Remote `/cancel` calls `MainAgent.cancel_steer()` and clears the pending steer instruction without starting a worker.
- Remote `/help` now lists `/cancel` next to `/steer`.
- README safety notes now mention remote `/cancel` for accidental pending steer instructions.

Why:

- Human steering is first-class only if users can correct accidental steering messages.
- The local CLI already had `/cancel`; the remote bridge should expose the same safe control path.
- This is a small consistency fix across terminal and IM surfaces.

Verification:

- `python -B -m unittest polyglot_ai.test_feishu_bridge` -> 18 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 77 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /cancel` -> returned no pending steer when clean.
- `python -B .\feishu_bridge.py --dry-run handle-text /help` -> listed `/cancel`.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Feishu Remote Plan Without Worker Run

Improved low-cost remote planning:

- Feishu/Hermes `dispatch_text(...)` now supports `/plan <goal>`.
- Remote `/plan` calls `MainAgent.plan_goal(...)`, saves `team_plan.json`, and returns the rendered team plan.
- It does not call `run_goal(...)`, start `monitor.py`, acquire a run lock, or invoke a worker.
- Remote `/help` and README remote probes now list `/plan`.

Why:

- The user does not want every message to call Claude.
- Remote users should be able to ask the main agent for a structured plan before approving or deciding to run a worker.
- This keeps Feishu/Hermes aligned with the local CLI's `/plan` behavior.

Verification:

- `python -B -m unittest polyglot_ai.test_feishu_bridge` -> 20 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 79 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /plan "build a tiny remote-only plan"` -> returned a team plan with model route and no worker run.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal; team plan updated by the dry-run plan probe.

### 2026-06-16 - Feishu Remote Full State Command

Improved remote observability:

- Added Feishu/Hermes `/state` and `state` command support.
- `/state` calls `MainAgent.status_text()` and returns the full session state: team plan, run state, run lock, pending steer, control signal, and approval state.
- Existing `/status` behavior remains unchanged and still returns the compact task board.
- Remote `/help` and README remote probes now list `/state`.

Why:

- Remote collaborators need a safe read-only way to inspect locks, pending steer, control, and approval state.
- Keeping `/status` compact avoids breaking existing Feishu/Hermes usage while `/state` gives deeper diagnostics.

Verification:

- `python -B -m unittest polyglot_ai.test_feishu_bridge` -> 22 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 81 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /state` -> returned full session state.
- `python -B .\feishu_bridge.py --dry-run handle-text /help` -> listed `/state`.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Feishu Remote Model Route Command

Improved remote model transparency:

- Added `MainAgent.model_text(...)` for a compact current model-profile summary.
- Feishu/Hermes `dispatch_text(...)` now supports `/model` and `model` as read-only commands.
- Remote `/model` shows model config path, default profile, selected profile, model name, base URL, key env state, and Claude worker env mapping.
- Remote `/help` and README remote probes now list `/model`.
- This command does not switch profiles and does not start a worker.

Why:

- The project uses Claude Code as an execution container while DeepSeek or another profile may be the actual model endpoint.
- Remote collaborators need a direct way to confirm the current worker/model route without reading a full agents list or generating a plan.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow polyglot_ai.test_feishu_bridge` -> 44 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 84 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /model` -> returned compact model route with key env state and no secret value.
- `python -B .\feishu_bridge.py --dry-run handle-text /help` -> listed `/model`.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Feishu Remote Diff Summary Command

Improved remote review visibility:

- Added `MainAgent.diff_text(...)` for a safe git diff summary.
- Feishu/Hermes `dispatch_text(...)` now supports `/diff` and `/diff <path...>`.
- Remote `/diff` returns changed file status and `git diff --stat`, not the full patch body.
- Remote `/help` and README remote probes now list `/diff`.

Why:

- Remote collaborators often need to ask what changed without opening the repository.
- Full patch bodies can be noisy and may expose sensitive content, so the remote command intentionally returns a compact summary.
- Local CLI `/diff` remains available for full patch inspection on the trusted machine.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow polyglot_ai.test_feishu_bridge` -> 46 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 86 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /diff README.md` -> returned name-status and stat only.
- `python -B .\feishu_bridge.py --dry-run handle-text /help` -> listed `/diff`.
- `python -B .\polyglot_cli.py status` -> no run lock, no steer, no control signal.

### 2026-06-16 - Feishu Remote Session Brief Command

Improved remote continuation:

- Added Feishu/Hermes `/brief` and `brief` command support.
- `/brief` reuses `MainAgent.session_brief_text()` and does not start a worker.
- Remote `/help` and README first probes now list `/brief`.

Why:

- The main agent should remain useful after a worker run finishes.
- Remote users often need a compact "where are we now" recap before continuing the conversation.
- This keeps lightweight chat and state inspection separate from explicit `/run` delegation.

Verification:

- `python -B -m unittest polyglot_ai.test_feishu_bridge` -> 26 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 87 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /brief` -> returned session recap without starting a worker.
- `python -B .\feishu_bridge.py --dry-run handle-text /help` -> listed `/brief`.

### 2026-06-16 - Session Brief Next-Step Guidance

Improved main-agent continuity:

- `MainAgent.session_brief_text()` now ends with a compact `Next` section.
- Active runs suggest `/timeline`, `/steer`, `/pause`, `/resume`, and `/stop`.
- Completed runs suggest `/report`, `/diff`, plain follow-up chat, or explicit `/run <goal>`.
- Empty sessions suggest lightweight chat, `/plan <goal>`, or explicit `/run <goal>`.

Why:

- The product should feel like a persistent main agent, not a one-shot worker launcher.
- After Claude or another worker finishes, the user needs a clear way to keep talking without accidentally starting another worker.
- The guidance is generated from current session state and remains read-only.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow polyglot_ai.test_feishu_bridge` -> 49 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 89 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /brief` -> returned session recap plus state-aware `Next` guidance.

### 2026-06-16 - Run Report Continuation Guidance

Improved post-worker continuity:

- `MainAgent.format_run_report(...)` now appends a state-aware `Next` section.
- Successful reports remind the user that the main agent stays active, suggest `/diff`, and keep `/run <goal>` explicit.
- Failed reports suggest `/timeline`, `/steer <message>`, and explicit retry via `/run <goal>`.
- `MainAgent.read_final_report()` now appends compatible continuation guidance when reading older saved `final_report.md` files that do not already contain `Next`.

Why:

- The user should not feel the session ends when Claude or another worker exits.
- `/report` should behave like a main-agent handback, not just a raw worker transcript.
- Backward-compatible wrapping matters because existing sessions may already have saved reports.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 23 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 89 tests passed.
- `python -B .\polyglot_cli.py report` -> older saved report displayed continuation guidance without rewriting the saved file.

### 2026-06-16 - Natural Follow-Up Chat Routes To Brief

Improved conversational continuity:

- `MainAgent.chat_reply(...)` now treats natural follow-up phrases as session-brief requests.
- Supported examples include `what next`, `next step`, `then what`, `然后呢`, `下一步`, `接下来`, and `到哪了`.
- The reply is the same state-aware `Session Brief` used by `/brief`, so it remains read-only and does not start a worker.

Why:

- Users should not need to remember slash commands for ordinary continuation questions.
- Asking "then what?" after a worker run should feel like the main agent is still present.
- This keeps accidental worker delegation behind explicit `/run <goal>`.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 25 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 91 tests passed.
- `python -B .\polyglot_cli.py chat "然后呢"` -> returned `Session Brief` plus `Next` guidance without running a worker.

### 2026-06-16 - Steer Acknowledgement Explains Checkpoint Semantics

Improved human steering feedback:

- `MainAgent.send_steer(...)` now returns a multi-line acknowledgement instead of only `[OK]`.
- The reply includes the steering message, compact run state, checkpoint semantics, and `/cancel` recovery.
- The underlying `steer.json` protocol is unchanged; the worker still consumes steering at the next self-heal/checkpoint.

Why:

- Human steering should feel first-class, not like a hidden file write.
- Remote users need to know whether a steer is pending and when it will take effect.
- Explicit `/cancel` guidance makes accidental steering less scary.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow polyglot_ai.test_feishu_bridge` -> 52 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 92 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /steer "limit dates after 2000"` -> returned checkpoint and cancel guidance.
- `python -B .\feishu_bridge.py --dry-run handle-text /cancel` -> cleared the dry-run steer side effect.
- `python -B .\polyglot_cli.py status` -> confirmed no pending steer, no control signal, and no run lock.

### 2026-06-16 - Worker Control Acknowledgement Explains Checkpoint Semantics

Improved pause/resume/stop feedback:

- `MainAgent.set_control_text(...)` now returns a multi-line acknowledgement for `/pause`, `/resume`, and `/stop`.
- Replies preserve the existing `[OK] control set: ...` prefix for compatibility.
- Replies include compact run state plus action-specific next steps:
  - pause: worker will pause at the next safe checkpoint; use `/resume`.
  - resume: paused worker will continue at the next checkpoint; use `/stop` if direction is invalid.
  - stop: worker will stop at the next safe checkpoint; inspect with `/status` or `/timeline`.
- The underlying `control.json` protocol is unchanged.

Why:

- Steering and run control should be understandable from CLI, Feishu, and Hermes.
- Users need to know whether a control command is immediate or checkpoint-based.
- Keeping the compatibility prefix avoids breaking existing remote assertions and integrations.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow polyglot_ai.test_feishu_bridge` -> 53 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 93 tests passed.
- `python -B .\feishu_bridge.py --dry-run handle-text /pause "need review"` -> returned checkpoint and resume guidance.
- `python -B .\feishu_bridge.py --dry-run handle-text /resume "probe done"` -> returned continuation and stop guidance.
- Removed the dry-run `control.json` files created by the probes, then `python -B .\polyglot_cli.py status` confirmed no pending steer, no control signal, and no run lock.

### 2026-06-16 - Status Explains Pending Steering And Control Semantics

Improved state inspection:

- `MainAgent.status_text()` now adds `next:` guidance under pending `[steer]`.
- `MainAgent.status_text()` now adds action-aware `next:` guidance under pending `[control]`.
- `/steer`, `/pause`, `/resume`, `/stop`, and `/state` now share the same checkpoint wording through small helper methods.

Why:

- A user may inspect `/status` or remote `/state` after sending a control command.
- Pending control files should not look like inert JSON fields; the UI should explain when they will take effect.
- Shared wording keeps CLI and Feishu/Hermes behavior consistent.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow polyglot_ai.test_feishu_bridge` -> 54 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 94 tests passed.
- Temporary `status-probe` session dry-ran `/steer`, `/pause`, and `/state`; `/state` showed `next:` guidance under both `[steer]` and `[control]`.
- Removed the temporary `artifacts/sessions/status-probe` probe directory.
- `python -B .\polyglot_cli.py status` -> confirmed default session has no pending steer, no control signal, and no run lock.

### 2026-06-16 - Compact Task Board Shows Pending Steering And Control

Improved remote `/status` visibility:

- `build_task_board(...)` now includes pending steer state.
- Full task board now shows pending `steer:` plus checkpoint/cancel guidance.
- Compact task board now shows pending `steer:` and `control:` semantics in the short Feishu/Hermes-friendly response.
- Existing control display remains compatible and gains concise checkpoint wording.

Why:

- Remote `/status` uses the compact task board, not full `/state`.
- Users should not need to know the difference between `/status` and `/state` to see pending control intent.
- Human steering/control should stay visible in the low-token coordination surface.

Verification:

- `python -B -m unittest polyglot_ai.test_task_board` -> 1 test passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 94 tests passed.
- Temporary `board-probe` session dry-ran `/steer`, `/pause`, and `/status`; compact `/status` showed pending steer and control checkpoint guidance.
- Removed the temporary `artifacts/sessions/board-probe` probe directory.

### 2026-06-16 - Approval Card Shows Route And Review Surface

Improved run-before-approval clarity:

- `request_run_approval_text(...)` and `/approval` now share `format_approval_card(...)`.
- The approval card shows adapter, permission profile, complexity, route reason, model profile, approval points, preview commands, and approve/deny actions.
- The trigger behavior is unchanged: approval is still required only for the existing high-trust or ambiguous worker classes.

Why:

- Before delegating to a high-trust local worker, the main agent should explain the route and review surface.
- Users should be able to inspect `/route <goal>` or `/plan <goal>` before approving.
- This improves safety and confidence without adding a new mandatory confirmation step for all runs.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 28 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 94 tests passed.
- `python -B .\polyglot_cli.py approval` -> confirmed no pending approval in the default session.

### 2026-06-16 - Antigravity Skill Packaging References

Reviewed user-provided reference projects:

- `https://codeberg.org/jochenkirstaetter/agy-statusline`
- `https://github.com/alicankiraz1/AntigravityQB`

Reusable takeaways:

- From `agy-statusline`: Antigravity statusline reads JSON from stdin, gracefully handles missing fields, supports PowerShell/Bash variants, and adapts output by terminal width. Future Polyglot statusline work should expose status fields such as session, model, worker state, pending steer/control, artifact count, and run lock in a similarly compact JSON-to-line adapter.
- From `AntigravityQB`: skill packaging benefits from explicit install scopes, dry-run installation, project/global targets, and packaging tests that verify install docs and required skill files.

Implemented now:

- Added `scripts/install_skill.ps1` for `skills/polyglot-team-os`.
- Supported install scopes: `codex-global`, `antigravity-cli-global`, `antigravity-app-global`, `agents-global`, `agents-project`, and `agent-project`.
- Added README host-skill installation commands for Codex and Antigravity.
- Added `polyglot_ai/test_skill_packaging.py` to verify required skill files, install target docs, dry-run behavior, and missing target errors.

Verification:

- `git ls-remote` succeeded for both referenced repositories.
- Shallow clones were read under `C:\tmp\polyglot-ref-agy-statusline` and `C:\tmp\polyglot-ref-AntigravityQB`.
- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 4 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 98 tests passed.
- Dry-run installer probes for `codex-global` and `antigravity-app-global` printed destinations without installing.

### 2026-06-16 - Polyglot Antigravity Statusline V1

Implemented a lightweight Antigravity CLI statusline adapter:

- Added `scripts/polyglot_statusline.ps1`.
- The script accepts optional Antigravity statusLine JSON from stdin.
- It reads Polyglot session state from `artifacts/sessions/<session>/`.
- Output is a single ASCII-safe line with session, run status, agent, model, attempt, pending steer/control, run lock, approval, event count, packet count, and goal.
- README now includes an Antigravity `statusLine` settings example and a local smoke-test command.

Why:

- `agy-statusline` showed that Antigravity statusline integration is a low-friction way to make the host feel native.
- Polyglot needs a small first version that works in Windows terminals without Nerd Fonts or Unicode rendering assumptions.
- This gives Antigravity users a live view of Polyglot state without opening `/status`.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 5 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 99 tests passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\polyglot_statusline.ps1 -Workspace D:\Repository\polyglot-ai-team -Session default` -> returned an ASCII single-line Polyglot summary.

Next possible refinement:

- Add width-aware compact/wide variants, following the `agy-statusline` responsive layout pattern, after the basic integration is used once in Antigravity.

### 2026-06-16 - Refocus On Core Model Routing

Course correction:

- User flagged that statusline work was drifting toward host polish.
- Decision: keep the V1 statusline and installer work, but stop further statusline beautification for now.
- Return focus to the core Polyglot loop: main agent, Claude execution container, DeepSeek/model profile routing, worker handback, and remote steering.

Implemented now:

- Enhanced `MainAgent.model_text(...)` so remote `/model` explains the actual route:
  `Claude Code executes; Polyglot injects this profile as the Anthropic-compatible endpoint`.
- Added explicit next steps for encrypted keys, missing `api_key_env`, selected profile errors, and no-profile cases.
- Updated local CLI `/model` output with the same route and next-step guidance.
- Missing key output now tells the user exactly to set `$env:<KEY>="..."` before `/run`, or use `/config` to save an encrypted key.

Why:

- The user's key design is that Claude is an execution tool while the real model endpoint can be DeepSeek or another Anthropic-compatible profile.
- `/model` is the natural place to diagnose that route before running a worker.
- This avoids confusion like "why mock?" or "which model is Claude really using?".

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 30 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 101 tests passed.
- `python -B .\polyglot_cli.py model` -> showed Claude execution container route and `/route`/`/run` next steps.

### 2026-06-16 - Route Preflight Shows Model Profile Runnable State

Improved run-before-routing diagnostics:

- `MainAgent.route_decision(...)` now records `model_profile_runnable` and `model_profile_preflight`.
- `/route <goal>` shows whether the selected Claude model profile is runnable before `/run`.
- If the selected profile has `api_key_env` but the env var is missing, `/route` now shows the exact PowerShell repair command and marks the route blocked.
- If the key is set or encrypted, `/route` shows `preflight: ok`.

Why:

- The main design is Claude Code as the execution container and DeepSeek/model profiles as the actual endpoint.
- Users need to know before a worker run whether the configured profile can actually launch.
- This reduces confusing failures and avoids the feeling that the system ignored a local DeepSeek key.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 31 tests passed.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 102 tests passed.
- `python -B .\polyglot_cli.py route "build a tiny tool"` -> showed `preflight: ok` with `DEEPSEEK_API_KEY:set`.

### 2026-06-16 - Run Preflight Blocks Unrunnable Model Profiles

Improved real-run safety:

- `MainAgent.run_goal(...)` now checks `model_profile_runnable` before acquiring a run lock, planning, or launching monitor/worker.
- If the selected Claude model profile is missing its required key, `/run` returns `[PREFLIGHT BLOCKED]` with the same repair guidance shown by `/route`.
- Feishu/Hermes `/run` now returns preflight-blocked text directly instead of wrapping it as a finished worker run.
- `read_model_config(...)` now opens JSON with `utf-8-sig`, so Windows/PowerShell-created `polyglot_models.json` files with a UTF-8 BOM still load correctly.

Why:

- `/route` should not be the only place that knows a profile is unrunnable.
- The system should not enter planner/monitor/Claude execution when it already knows the selected endpoint cannot authenticate.
- Windows users commonly create JSON files with tools that may include a BOM; model routing must tolerate that.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow polyglot_ai.test_feishu_bridge` -> 59 tests passed.
- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 33 tests passed after adding BOM regression coverage.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 105 tests passed.
- A temporary PowerShell-created `polyglot_models.json` with BOM and missing `POLYGLOT_PROBE_MISSING_KEY` returned `[PREFLIGHT BLOCKED]` before planner/monitor launch.
- Removed the temporary `%TEMP%\polyglot-preflight-probe` workspace after the probe.

### 2026-06-16 - Stop Silent Implicit Mock Runs

Tightened the main-agent routing path after a confusing real status report showed:

- current model profile: `deepseek-v4-pro[1m]` with `DEEPSEEK_API_KEY:set`
- last run backend: `mock-agent`

Decision:

- Treat Claude Code as the execution container and DeepSeek/model profiles as the endpoint configuration.
- A runnable model key alone is not enough; a runnable local worker CLI is also required.
- `mock-agent` is now allowed for `/run` only when explicitly requested with `FORCE_MOCK`, `POLYGLOT_AGENT=mock`, or `POLYGLOT_AGENT=offline`.
- If auto-routing would fall through to implicit mock, `/run` returns `[PREFLIGHT BLOCKED]` before acquiring a run lock, planning, or launching monitor/worker.
- `/route` now explains the worker preflight separately from the model preflight.
- `doctor` now prints `run preflight: worker=...; model=...` so users can see whether a failure is in the Claude CLI container layer or the API/model profile layer.
- `status` and final run reports now distinguish stale last-run backend from the current selected route, e.g. `last run used mock-agent; current route selects claude-code-cli`.

Why:

- The user has a local DeepSeek key, so silently showing or using `mock-agent` feels like the system ignored the real model.
- The correct mental model is two-layer routing: local CLI worker first, then injected Anthropic-compatible model endpoint.
- This keeps offline verification available while preventing production-like runs from quietly becoming mock demos.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 36 tests passed.
- `python -B .\polyglot_cli.py route "写一个 hello_name(name) 函数和一个最小测试"` -> selected `Claude Code (claude-code-cli)` with `preflight: ok`.
- `python -B .\polyglot_cli.py doctor` -> `run preflight: worker=ok; model=ok`.
- `python -B .\polyglot_cli.py status` -> old `mock-agent` run is clearly labeled as last-run state while current route selects `claude-code-cli`.

### 2026-06-16 - Recover Stale Run Locks And Interrupted Active State

A real non-mock smoke run was attempted in session `codex-real-smoke`:

```powershell
$env:POLYGLOT_SESSION='codex-real-smoke'
python -B .\polyglot_cli.py run "写一个 hello_name(name) 函数和一个最小测试"
```

The outer command timed out after about five minutes while the main process and monitor process were still alive. After stopping the smoke processes, the session showed an active-looking `planning` state with no active lock.

Fixes:

- `Runtime.acquire_run_lock(...)` now detects an existing lock whose recorded PID is dead.
- Dead-PID locks are logged as `run_lock.stale`, released, and then reacquired for the new run.
- `status` now warns when `run_state.json` looks active (`planning`, `running`, `filling`, `testing`, `healing`, etc.) but there is no active run lock.
- Compact status now appends `interrupted?` for the same active-state/no-lock condition.

Why:

- Local-first terminal workflows are often interrupted by closing a terminal, killing a process, or external command timeouts.
- The main agent must recover cleanly instead of leaving the next `/run` blocked or making an old active state look alive.

Verification:

- Stopped only the smoke `polyglot_cli.py run` and child `monitor.py` processes, then unlocked session `codex-real-smoke`.
- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 38 tests passed.
- `POLYGLOT_SESSION=codex-real-smoke python -B .\polyglot_cli.py status` -> displayed `active-looking run_state has no lock; previous run likely exited or was interrupted`.

### 2026-06-16 - Claude-Only Execution Container With Model Profiles

User direction:

- Do not make Codex/OpenCode another execution path right now.
- Use Claude Code as the single worker container.
- Test Claude launches with different model environments, starting with DeepSeek and MiniMax.

Implemented:

- `select_agent(auto)` now prefers Claude Code and does not automatically fall through to Codex/OpenCode when Claude is missing.
- Codex/OpenCode/OpenClaw remain discoverable via `/agents`, but MVP `/run` stays Claude-first.
- Added `polyglot_ai/provider_probe.py` to probe enabled model profiles concurrently without launching Claude.
- Added CLI command `probe-models [profile-id ...]`.
- Added profile examples:
  - `deepseek-v4-pro[1m]` via `DEEPSEEK_API_KEY`
  - `minimax-m3` via `MINIMAX_API_KEY`
- MiniMax profile uses Claude-compatible `base_url=https://api.minimaxi.com/anthropic` for worker execution and `openai_base_url=https://api.minimax.io/v1` for direct provider probing.
- Added `scripts/start_claude_models.ps1` to start separate Claude-backed sessions:
  - `claude-deepseek`
  - `claude-minimax`
- Model keys should be configured through `python -B .\polyglot_cli.py config`; environment variables are compatibility fallback, not the primary user flow.

Security note:

- Real user-provided MiniMax/YaiRouter keys were not written to repo files, tests, logs, README, or development log.
- GPT/YaiRouter was intentionally removed from default presets after user feedback; it remains possible only through custom `/config` if needed later.
- Provider probe output is redacted before display.

Verification:

- `python -B -m unittest polyglot_ai.test_provider_probe polyglot_ai.test_agents` -> 7 tests passed.
- `python -B .\polyglot_cli.py probe-models` -> DeepSeek profiles returned OK; MiniMax correctly reported missing key when not configured in the current process.
- `python -B .\polyglot_cli.py route POLYGLOT_MODEL_PROFILE=minimax-m3 "probe route"` -> selected Claude Code with MiniMax profile and blocked only on missing `MINIMAX_API_KEY`.

### 2026-06-16 - Future Main-Agent Model Registry From SuperCLUE

User direction:

- Later add a real main-agent model allocation layer.
- Crawl/sync `https://www.superclueai.com/homepage`.
- Use the current local model profiles as the execution candidates.
- Keep model pricing in sync with the same registry.

Design note:

- This belongs in the main-agent routing layer, not in `v1_worker.py`.
- Worker remains Claude Code only.
- Models are selected by profile/env:
  - DeepSeek via `DEEPSEEK_API_KEY`
  - MiniMax via `MINIMAX_API_KEY`
- A future `model_registry.json` should store model score, price, context length, provider, endpoint type, and last sync time.
- `/route` can then choose based on task type, budget, context length, and live availability.

Refresh policy:

- Refresh once at task startup, before route selection, when the registry is missing or stale.
- Refresh again after the user adds/edits model profiles via `/config` or direct config update.
- Do not scrape on every chat message.
- Do not run a background scheduler for MVP.
- Do not let repeated scraping happen inside self-heal loops; the selected route should stay stable for one task unless the user explicitly steers.

Implementation sketch for later:

- Add `polyglot_ai/model_registry.py`.
- Add `python -B .\polyglot_cli.py sync-model-registry`.
- First try SuperCLUE page API/static JSON discovery.
- If the page remains dynamic-only, use a browser-driven scraper with an explicit refresh command instead of scraping during every run.
- `/run` performs one bounded pre-route refresh if needed, then uses the local registry snapshot for the whole task.
- If refresh fails, `/run` should continue with the last known registry and warn; if no registry exists, fall back to explicit profile order.

Observation:

- `https://www.superclueai.com/homepage` returns a dynamic page to simple HTML fetch, so implementation will need API discovery or browser rendering.

### 2026-06-16 - CLI-First Model Configuration And Monitor Plain Mode

User correction:

- Model configuration should happen through the Polyglot CLI, not through users manually editing shell environment variables.
- First-time setup should guide the main agent configuration flow.
- Users can configure multiple models in one `/config` session.
- GPT/YaiRouter should not be included as a default preset for now.

Implemented:

- `/config` now has model presets:
  - DeepSeek V4 Pro
  - MiniMax M3
  - Custom
- Presets still save secrets through `api_key_encrypted`; real keys are not written as plaintext.
- Environment variables remain fallback compatibility, but README now points users to `/config` as the primary path.
- Removed GPT/YaiRouter from default profile examples, current local config, docs, and starter script.
- Replaced the misleading starter with `scripts/start_claude_models.ps1`, which runs configured Claude-backed sessions for:
  - `claude-deepseek`
  - `claude-minimax`
- The starter script probes profiles through `polyglot_cli.py probe-models`; it does not ask users to set key env vars.

Monitor fix:

- Non-interactive monitor runs now use `run_plain(...)` instead of Rich Live rendering.
- `finish_run(...)` now writes `success` when the monitor process exits 0 but the last visible state is still `planning` / `starting` / `running`.
- `Runtime.write_json(...)` now creates parent directories for nested session artifact paths before writing.
- This fixed the previous mock monitor smoke where the process could hang or leave a `planning` state.

Verification:

- `python -B -m unittest polyglot_ai.test_config_tui polyglot_ai.test_provider_probe polyglot_ai.test_agents` -> 10 tests passed.
- `POLYGLOT_SESSION=codex-monitor-plain python -B .\monitor.py FORCE_MOCK=1 "写一个 hello_name(name) 函数和一个最小测试"` -> completed with `final status: success exit=0`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_claude_models.ps1 -ProbeOnly` -> DeepSeek OK, MiniMax correctly reports missing key until configured through `/config`.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 116 tests passed.
- `python -B .\polyglot_cli.py doctor` -> all diagnostics passed.

Follow-up correction:

- User confirmed GPT/YaiRouter should not be added as an official/default profile.
- Default built-in profile path remains DeepSeek + MiniMax only.
- `/config` remains the primary way to add model keys and profiles; environment variables are fallback compatibility only.
- Updated route/model missing-key messages so the CLI guides users to `/config` first instead of asking them to edit shell environment variables before `/run`.
- Added `polyglot_cli.py setup` and `/setup` for first-run readiness checks:
  - verifies Claude Code worker discovery
  - shows selected model profile and key state
  - points the user to `/config`, `/probe-models`, then `/route` before the first real `/run`
- REPL now prints the setup check automatically when the worker/model path is not ready.
- README Quick Start and Model Profiles now start from `/setup` + `/config`, not manual `$env:` key editing.

Verification:

- Repository search found GPT/YaiRouter only in this development log as historical notes, not in config, docs, scripts, or tests.
- `python -B -m unittest discover -s polyglot_ai -p "test_*.py"` -> 116 tests passed.
- `python -B .\polyglot_cli.py setup` -> prints ready status for the current Claude + DeepSeek configuration.

### 2026-06-16 - SuperCLUE Model Registry MVP

User requirement:

- Main agent should later crawl/sync `https://www.superclueai.com/homepage`.
- Existing configured models should be allocated using this registry.
- Model prices should sync from that source.
- Refresh should happen at task startup and after users add/edit models, not continuously.

Implemented:

- Added `polyglot_ai/model_registry.py`.
- The SuperCLUE homepage currently lazy-loads data from:
  - `https://www.superclueai.com/data/latency_and_price/2026年5月_2.xlsx`
- The registry parser uses only Python standard library:
  - downloads the xlsx
  - parses shared strings and sheet XML from the zip package
  - extracts model name, provider, input/output/blended CNY per 1M tokens, overall latency, coding latency, and agent latency
- Added local registry file:
  - `artifacts/model_registry.json`
- Added CLI commands:
  - `python -B .\polyglot_cli.py sync-model-registry`
  - `python -B .\polyglot_cli.py model-registry`
- `/run` now refreshes the registry once before route selection if the local snapshot is missing or stale.
- `/route` only reads the local snapshot and never scrapes by itself.
- Interactive `/config` refreshes the registry after profile add/edit/delete/switch; quiet test mode skips network refresh.
- Route output now shows matched SuperCLUE model price/latency when the selected profile can be matched.

Observed real sync:

- `python -B .\polyglot_cli.py sync-model-registry` downloaded 13 rows.
- Current DeepSeek profile matches `DeepSeek-V4-Pro(max)`.
- `/route "写一个日期转换工具"` shows:
  - `price~3.75 CNY/1M tokens`
  - `latency~495.7s`

Limitations:

- This is still a registry snapshot, not full autonomous provider allocation.
- It uses the current SuperCLUE xlsx asset discovered from the homepage bundle; if the asset name changes, sync will warn and use the last local snapshot.
- The next precise step is a small routing scorer that chooses among configured and key-ready profiles using capability, price, latency, and task type.

### 2026-06-16 - Key-Ready Model Routing Scorer

User requirement:

- The main agent should allocate among the user's configured models.
- Claude remains the execution container; the selected profile changes the Claude-compatible endpoint.
- Do not add GPT/YaiRouter as a default profile.

Implemented:

- Added `polyglot_ai/model_router.py`.
- The router only scores enabled profiles that are already configured and key-ready.
- Explicit `POLYGLOT_MODEL_PROFILE` / `polyglot_cli.py model <id>` still wins.
- When no explicit model is selected, the router scores profiles using:
  - task type: simple, coding, agent/planning
  - profile capabilities
  - cost tier
  - local SuperCLUE price/latency snapshot when available
- `MainAgent.run_goal(...)` now writes the routed profile into the per-run env as `POLYGLOT_MODEL_PROFILE`, so the monitor/worker uses the same selected model that `/route` shows.
- Internal `POLYGLOT_MODEL_PROFILE_ROUTED=1` preserves the distinction between a user override and an automatic main-agent route.

Observed behavior:

- `python -B .\polyglot_cli.py route "hello"` selects `deepseek-v4-flash`.
- `python -B .\polyglot_cli.py route "规划一个多智能体系统架构并实现核心流程"` selects `deepseek-v4-pro[1m]`.

Verification:

- `python -B -m unittest polyglot_ai.test_model_router` -> 4 tests passed.

Follow-up:

- Added `rank_model_profiles(...)` for transparent routing diagnostics.
- Added CLI/REPL command:
  - `python -B .\polyglot_cli.py model-scores "hello"`
  - `/model-scores <goal>`
- The score view shows:
  - selected candidate marker
  - eligible yes/no
  - score
  - local SuperCLUE price/latency
  - exclusion reason such as `missing key: MINIMAX_API_KEY`
- Output avoids Rich table truncation and Unicode ellipsis to remain Windows-terminal safe.

Verification:

- `python -B .\polyglot_cli.py model-scores hello` -> selected `deepseek-v4-flash`; `minimax-m3` shown as missing key.
- `python -B -m unittest polyglot_ai.test_model_router` -> 5 tests passed.

### 2026-06-16 - DeepSeek Billing Evidence in Claude Smoke

User observation:

- After running from a normal user terminal, DeepSeek balance decreased.
- This confirms that the DeepSeek endpoint can be reached and that billable model responses occur outside the Codex network-restricted sandbox.

Diagnosis:

- `doctor` proves local configuration is readable and Claude Code is discoverable.
- `probe-models deepseek-v4-flash` proves the model endpoint can return a response.
- `smoke-claude` must prove both layers:
  - model endpoint probe succeeds
  - Claude Code worker is actually invoked and the Team OS artifacts pass the smoke gate

Change:

- `smoke-claude` now keeps the successful DeepSeek flash preflight probe in the final smoke result instead of only showing probe details on failure.
- Successful smoke output therefore includes `model endpoint probe passed` with provider, model, and latency before the worker checks.
- The smoke profile remains `deepseek-v4-flash` for cost control.

Verification:

- `python -B -m unittest polyglot_ai.test_local_smoke` -> 6 tests passed.
- `python -B -m py_compile polyglot_ai\local_smoke.py polyglot_ai\test_local_smoke.py` -> passed.
- In the Codex sandbox, `python -B .\polyglot_cli.py smoke-claude --session claude-smoke-preflight-sandbox` fails fast at the model probe with `WinError 10013` and skips Claude execution, which is the intended safe behavior under network restriction.

### 2026-06-16 - Chinese Intent Routing Guardrail

User direction:

- Local interaction should feel like a main agent, not a command wrapper.
- Simple chat such as `hello` should not call Claude.
- Short engineering requests still need to route as work, even when they are short Chinese phrases.

Problem:

- The model router used length as a fallback after checking simple and agent markers.
- A short Chinese coding request such as `修复这个 bug` could be classified as `simple`, causing the router to prefer a low-cost chat/simple profile.

Change:

- Added explicit coding markers before the length fallback in `polyglot_ai/model_router.py`.
- Examples now classify as:
  - `你好` -> `simple`
  - `修复这个 bug` -> `coding`
  - `写一个日期转换函数` -> `coding`
  - `规划一个多智能体团队` -> `agent`

Verification:

- `python -B -m unittest polyglot_ai.test_model_router` -> 6 tests passed.
- `python -B .\polyglot_cli.py model-scores "修复这个 bug"` -> selected `deepseek-v4-pro[1m]`.
- `python -B .\polyglot_cli.py model-scores "你好"` -> selected `deepseek-v4-flash`.

### 2026-06-16 - `model <id>` Now Persists Through CLI

User requirement:

- Model configuration should be handled through the CLI instead of asking users to manage environment variables by hand.
- Switching the active model should feel like a real product action, not a temporary shell trick.

Problem:

- `python .\polyglot_cli.py model deepseek-v4-flash` previously only changed `POLYGLOT_MODEL_PROFILE` in the current process.
- In one-shot CLI usage the process exits immediately, so the apparent switch did not survive to the next command.

Change:

- Added `switch_default_model_profile(...)` in `polyglot_cli.py`.
- `/model <id>` and `python .\polyglot_cli.py model <id>` now:
  - update `polyglot_models.json` `default_model`
  - sync the current process override for immediate use
  - refresh the local model registry as part of the config change path
- `/model` display now distinguishes config default from a temporary session override when they differ.

Verification:

- `python -B -m unittest polyglot_ai.test_config_tui polyglot_ai.test_model_router` -> 12 tests passed.
- `python -B -m py_compile polyglot_cli.py polyglot_ai\test_config_tui.py` -> passed.

### 2026-06-16 - Model Questions Now Sound Like A Main Agent

User-facing issue:

- Natural model questions such as `你现在用的是什么模型` and `为什么选这个模型` were answered with the full `Route Decision` diagnostic block.
- The information was accurate, but the tone and format felt like an internal debugger instead of a main-agent reply.

Change:

- Added `model_chat_text(...)` in `polyglot_ai/main_agent.py`.
- Natural chat model/profile questions now return a short `Model Summary`:
  - current worker
  - configured default profile
  - routed profile for this message
  - base URL
  - redacted key state
  - routing reason and preflight status
- `/route <goal>` remains the detailed engineering diagnostic path.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 35 tests passed.
- `python -B .\polyglot_cli.py chat "你现在用的是什么模型"` -> returned `Model Summary` with default + routed profile.
- `python -B .\polyglot_cli.py chat "为什么选这个模型"` -> returned the same concise summary rather than `Route Decision`.

### 2026-06-16 - Session Brief Distinguishes Current Work From History

User-facing issue:

- Natural progress questions such as `现在做到哪一步了` and `what next` were answered with a `Session Brief`, but the labels could blur current activity with historical state.
- A saved team plan and a completed historical run were both shown with present-tense labels such as `plan` and `run`, which made the CLI feel more like internal state inspection than a main-agent summary.

Change:

- `session_brief_text()` in `polyglot_ai/main_agent.py` now distinguishes active vs historical state.
- When a run is not active:
  - `plan` becomes `saved plan`
  - `run` becomes `last run`
  - `goal` becomes `last goal`
- Active runs still use present-tense labels so steering and control guidance remain immediate.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 36 tests passed.
- `python -B .\polyglot_cli.py chat "现在做到哪一步了"` -> returned `saved plan`, `last run`, and `last goal`.
- `python -B .\polyglot_cli.py chat "what next"` -> returned the same historical framing instead of implying an active run.

### 2026-06-16 - Natural Result Questions Now Use `Last Run Summary`

User-facing issue:

- Natural questions such as `刚才做了什么`, `上次`, or `what did you do` were answered with the full `Run report`.
- That blurred two different intents:
  - casual progress/result chat
  - explicit request for the full saved worker report

Change:

- Added `last_run_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural result/progress questions now return a concise `Last Run Summary` with:
  - goal
  - status
  - backend
  - routed model info when available
  - artifact list
  - next steps
- Explicit `report` / saved report queries still return the full `Run report`.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 37 tests passed.
- `python -B .\polyglot_cli.py chat "刚才做了什么"` -> returned `Last Run Summary`.
- `python -B .\polyglot_cli.py chat "report"` -> still returned the detailed `Run report`.

### 2026-06-16 - Natural Help Questions Now Return A Usage Summary

User-facing issue:

- Natural help questions such as `你能做什么`, `怎么用`, and `help` fell through to the generic fallback line.
- That made the main agent feel blunt right at the moment a user was asking how to work with it.

Change:

- Added `help_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural help/usage questions now return a short `How To Use Polyglot` summary covering:
  - normal chat
  - automatic worker delegation
  - explicit `/run`
  - `/report`
  - `/model`, `/model-scores`, and `/config`
- The explicit `/help` command still remains the full command reference.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 39 tests passed.
- `python -B .\polyglot_cli.py chat "你能做什么"` -> returned `How To Use Polyglot`.
- `python -B .\polyglot_cli.py chat "怎么用"` -> returned `How To Use Polyglot`.
- `python -B .\polyglot_cli.py chat "help"` -> returned `How To Use Polyglot`.

### 2026-06-16 - Artifact And Changed-File Questions Now Have Dedicated Summaries

User-facing issue:

- `产物有哪些` only returned a flat `Released files: ...` line.
- `改了哪些文件` was interpreted too broadly and fell into `Workspace Summary`.

Change:

- Added `artifact_chat_text()` in `polyglot_ai/main_agent.py`.
- Added `changed_files_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural chat now distinguishes:
  - artifact questions -> `Artifact Summary`
  - changed-file/diff questions -> `Changed Files Summary`
- This keeps natural questions aligned with the product surface while preserving explicit `/diff` and workspace commands.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 41 tests passed.
- `python -B .\polyglot_cli.py chat "产物有哪些"` -> returned `Artifact Summary`.
- `python -B .\polyglot_cli.py chat "改了哪些文件"` -> returned `Changed Files Summary`.
- `python -B .\polyglot_cli.py chat "files"` -> returned `Artifact Summary`.

### 2026-06-16 - Worker Questions Now Explain Delegation Instead Of Dumping Routing

User-facing issue:

- Natural questions such as `谁在做`, `which worker`, and `为什么没调用worker` returned the full `Route Decision` diagnostic.
- The information was technically correct, but it did not explain the everyday product behavior: who the default worker is and why this message did or did not trigger it.

Change:

- Added `worker_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural worker/delegation questions now return `Worker Summary` with:
  - selected worker
  - adapter
  - route reason
  - preflight status
  - routed model
  - explanation of whether the current message stayed in main-agent chat or would auto-delegate
- Explicit `/route <goal>` still remains the full routing diagnostic.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 43 tests passed.
- `python -B .\polyglot_cli.py chat "谁在做"` -> returned `Worker Summary`.
- `python -B .\polyglot_cli.py chat "为什么没调用worker"` -> returned `Worker Summary`.
- `python -B .\polyglot_cli.py chat "which worker"` -> returned `Worker Summary`.

### 2026-06-16 - `status` Now Means Current State, Not Last Result

User-facing issue:

- Natural queries like `status` and `progress` were routed to `Last Run Summary`.
- That blurred the line between:
  - what the session looks like now
  - what the previous run produced

Change:

- Added `current_status_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural chat now distinguishes:
  - `status`, `progress`, `当前状态`, `现在状态` -> `Current Status Summary`
  - `刚才做了什么`, `上次`, `what did you do` -> `Last Run Summary`
- The current-status reply now emphasizes:
  - compact current state
  - active/saved plan
  - current goal
  - routed model
  - next actions

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 44 tests passed.
- `python -B .\polyglot_cli.py chat "status"` -> returned `Current Status Summary`.
- `python -B .\polyglot_cli.py chat "progress"` -> returned `Current Status Summary`.
- `python -B .\polyglot_cli.py chat "刚才做了什么"` -> still returned `Last Run Summary`.

### 2026-06-16 - Delegation-Policy Questions Now Explain Auto-Delegation Rules

User-facing issue:

- Natural questions like `什么时候会调用worker`, `什么时候不会调用worker`, and `会不会自动调用Claude` were not distinct from worker identity/routing questions.
- Users asking about the policy behind delegation need the rule explained, not just the current selected worker.

Change:

- Added `delegation_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural delegation-policy questions now return `Delegation Summary` covering:
  - what stays in lightweight chat
  - what usually auto-delegates
  - how `/run <goal>` forces delegation
  - guardrails like `先别写代码` / `don't write` / `no code`
- Worker identity questions still go to `Worker Summary`.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 46 tests passed.
- `python -B .\polyglot_cli.py chat "什么时候会调用worker"` -> returned `Delegation Summary`.
- `python -B .\polyglot_cli.py chat "什么时候不会调用worker"` -> returned `Delegation Summary`.
- `python -B .\polyglot_cli.py chat "会不会自动调用Claude"` -> returned `Delegation Summary`.

### 2026-06-16 - Testing And Verification Goals Now Prefer Flash

User instruction:

- During testing, the main agent should avoid using the pro DeepSeek profile when flash is sufficient.

Problem:

- The general coding scorer still preferred `deepseek-v4-pro[1m]` for small coding tasks that happened to include unit tests.
- That made cheap verification loops spend more than necessary during product testing.

Change:

- Added `is_testing_goal(...)` to `polyglot_ai/model_router.py`.
- Added testing-mode scoring bias in `score_profile(...)`:
  - boost `simple-code` / chat-capable low-cost profiles
  - boost flash/lite models
  - lightly penalize pro-tier models
- Result: test/verification/smoke/probe style goals now bias toward `deepseek-v4-flash`.

Verification:

- `python -B -m unittest polyglot_ai.test_model_router` -> 7 tests passed.
- `python -B .\polyglot_cli.py model-scores "写一个带单元测试的日期转换工具"` -> selected `deepseek-v4-flash`.
- `python -B .\polyglot_cli.py route "写一个带单元测试的日期转换工具"` -> selected `deepseek-v4-flash`.

### 2026-06-16 - Workspace Default Switched Fully To DeepSeek Flash

User decision:

- Stop using the DeepSeek Pro profile for now and use DeepSeek Flash instead.

Applied change:

- Updated [polyglot_models.json](file:///d:/Repository/polyglot-ai-team/polyglot_models.json):
  - default profile -> `deepseek-v4-flash`
  - `deepseek-v4-pro[1m]` -> `enabled: false`

Verification:

- `python -B .\polyglot_cli.py model` -> default profile shown as `deepseek-v4-flash`.
- `python -B .\polyglot_cli.py route "写一个日期转换工具"` -> selected `deepseek-v4-flash`.
- `python -B .\polyglot_cli.py route "写一个带单元测试的日期转换工具"` -> selected `deepseek-v4-flash`.

Follow-up cleanup:

- Switched the `/config` DeepSeek preset from Pro to Flash.
- Updated README example command from `model deepseek-v4-pro[1m]` to `model deepseek-v4-flash`.
- Updated `polyglot_models.example.json` default to Flash and left Pro disabled in the example as well.

Verification:

- `python -B -m unittest polyglot_ai.test_config_tui` -> 6 tests passed.

### 2026-06-16 - Historical Views Now Show Current Default Model As A Contrast

User-facing issue:

- Some views such as `Session Brief`, `Task Board`, and `Handoff` legitimately showed historical route data from older plans.
- After switching the workspace default from DeepSeek Pro to Flash, those views could still show the older routed `deepseek-v4-pro[1m]`, which looked like the current model might still be Pro.

Change:

- Added current-default-model comparison in `polyglot_ai/main_agent.py` and `polyglot_ai/task_board.py`.
- Historical plan/routing views now keep the old route data but also show the current configured default model when it differs.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow polyglot_ai.test_task_board` -> 77 tests passed.
- `python -B .\polyglot_cli.py chat "现在做到哪一步了"` -> shows historical routed model plus `current default model: deepseek-v4-flash`.
- `python -B .\polyglot_cli.py chat "看看任务板"` -> shows `current default model: deepseek-v4-flash`.
- `python -B .\polyglot_cli.py chat "handoff"` -> shows `current_default_model: deepseek-v4-flash`.

Follow-up refinement:

- Renamed historical model fields in those views so the old route is explicitly labeled as historical instead of looking like the current active model.

Verification:

- `Session Brief` now shows `historical route model: ...` alongside `current default model: ...`.
- `Task Board` now shows `historical model: ...` alongside `current default model: ...`.
- `Handoff` now shows `historical_route_model` / `historical_model_name` alongside `current_default_model`.

Further consistency pass:

- `Planner Summary` now uses the same language:
  - `historical route model`
  - `historical base_url`
  - `historical key`
  - `current default model`

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> still passed.
- `python -B .\polyglot_cli.py chat "看一下planner"` -> now shows historical route model and current default model side by side.

### 2026-06-16 - Natural Delegation Preview For Sample Messages

User-facing issue:

- Users naturally want to ask things like `这句话会不会调用worker：...` before they trust auto-delegation.
- Previously those questions were treated like generic worker/routing questions, which could misread the whole sentence instead of judging the sample message itself.

Change:

- Added `extract_delegation_preview_candidate(...)` in `polyglot_ai/main_agent.py`.
- Added `delegation_preview_chat_text(...)` in `polyglot_ai/main_agent.py`.
- Natural preview questions now:
  - extract the sample message after `:` / `：` or from quotes
  - judge whether that sample would auto-delegate
  - explain the result without actually starting work

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 48 tests passed.
- `python -B .\polyglot_cli.py chat "这句话会不会调用worker：写一个日期转换工具"` -> returned `Delegation Preview` with `auto-delegate`.
- `python -B .\polyglot_cli.py chat "这句话会不会调用worker：现在做到哪一步了"` -> returned `Delegation Preview` with `stay in main-agent chat`.

### 2026-06-16 - Natural Plan Preview For Sample Goals

User-facing issue:

- Users often want to ask `如果我说 ... 你会怎么做` before they let the main agent run.
- Previously that kind of question fell through to the generic fallback reply instead of giving a useful preview.

Change:

- Added `plan_preview_chat_text(...)` in `polyglot_ai/main_agent.py`.
- Natural plan-preview questions now:
  - extract the sample goal from `:` / `：`
  - decide whether it would stay in chat or auto-delegate
  - when it would delegate, show the selected worker, routed model, and high-level step graph
- This preview does not write plans or start execution; it is only a conversational forecast.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 50 tests passed.
- `python -B .\polyglot_cli.py chat "如果我说：写一个日期转换工具，你会怎么做"` -> returned `Plan Preview` with `auto-delegate`.
- `python -B .\polyglot_cli.py chat "你会怎么做：现在做到哪一步了"` -> returned `Plan Preview` with `stay in main-agent chat`.

Follow-up refinement:

- Improved sample extraction for Chinese plan-preview prompts so trailing phrasing like `你会怎么做` is not treated as part of the goal itself.

Verification:

- `python -B .\polyglot_cli.py chat "如果我说：写一个日期转换工具，你会怎么做"` -> sample now renders as `写一个日期转换工具`.
- `python -B .\polyglot_cli.py chat "你会怎么做：修复这个 bug 并加测试"` -> sample renders as `修复这个 bug 并加测试`.

### 2026-06-16 - Natural Model Preview For Sample Messages

User-facing issue:

- Asking `这句话会用哪个模型：...` previously reused the generic model summary path.
- That was misleading for lightweight questions, because it would still name a model even when no worker execution would happen at all.

Change:

- Added `model_preview_chat_text(...)` in `polyglot_ai/main_agent.py`.
- Natural model-preview questions now:
  - extract the sample message
  - first decide whether it would execute via a worker
  - only show the routed model when worker execution would really happen
  - explicitly say `no worker model would be used` for chat-only samples

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 52 tests passed.
- `python -B .\polyglot_cli.py chat "这句话会用哪个模型：写一个带单元测试的日期转换工具"` -> returned `Model Preview` with `deepseek-v4-flash`.
- `python -B .\polyglot_cli.py chat "这句话会用哪个模型：现在做到哪一步了"` -> returned `Model Preview` with `no worker model would be used`.

### 2026-06-16 - Natural Execution Preview For “会发生什么”

User-facing issue:

- Users also naturally ask `如果我直接说 ... 会发生什么`.
- Previously this either fell through to a generic fallback or could treat trailing wording like `会发生什么` as part of the sample goal.

Change:

- Added `execution_preview_chat_text(...)` in `polyglot_ai/main_agent.py`.
- Added `extract_execution_preview_candidate(...)` so sample extraction trims trailing `会发生什么` / `what would happen`.
- Natural execution-preview questions now show:
  - whether the message would stay in chat or execute via a worker
  - the selected worker/model when execution would happen
  - the high-level step graph

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 54 tests passed.
- `python -B .\polyglot_cli.py chat "如果我直接说：写一个日期转换工具，会发生什么"` -> sample now renders as `写一个日期转换工具`.
- `python -B .\polyglot_cli.py chat "如果我直接说：现在做到哪一步了，会发生什么"` -> sample renders as `现在做到哪一步了`.

Follow-up refinement:

- Extended execution-preview sample trimming so combined prompts like `会用谁、会用哪个模型、会不会执行` are not treated as part of the sample goal.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 55 tests passed.
- `python -B .\polyglot_cli.py chat "如果我直接说：写一个带单元测试的日期转换工具，会用谁、会用哪个模型、会不会执行"` -> sample renders as `写一个带单元测试的日期转换工具`.
- `python -B .\polyglot_cli.py chat "如果我直接说：现在做到哪一步了，会用谁、会用哪个模型、会不会执行"` -> sample renders as `现在做到哪一步了`.

### 2026-06-16 - `Execution Preview` Now Includes A Cost Signal

User-facing need:

- The preview path should not only say whether a message would execute; it should also hint whether that execution is likely to spend model money.

Change:

- Extended `execution_preview_chat_text(...)` in `polyglot_ai/main_agent.py`.
- When worker execution would happen, the preview now also shows:
  - blended local price snapshot when the registry has one
  - or an explicit fallback note when no local registry price is available

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 57 tests passed.
- `python -B .\polyglot_cli.py chat "如果我直接说：写一个带单元测试的日期转换工具，会发生什么"` -> now includes `estimated: around 1.25 CNY / 1M blended tokens from local registry`.

### 2026-06-16 - Natural Board And Timeline Questions Now Open The Right View

User-facing issue:

- Natural viewing questions like `看看任务板`, `最近发生了什么`, and `timeline` still fell through to the generic fallback reply.
- That made the CLI feel command-oriented exactly where a main agent should have been able to surface the right view directly.

Change:

- Added `board_chat_text()` in `polyglot_ai/main_agent.py`.
- Added `timeline_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural chat now routes:
  - board/task-board phrasing -> `Board Summary`
  - recent-activity/timeline phrasing -> `Recent Activity`

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 59 tests passed.
- `python -B .\polyglot_cli.py chat "看看任务板"` -> returned `Board Summary`.
- `python -B .\polyglot_cli.py chat "最近发生了什么"` -> returned `Recent Activity`.
- `python -B .\polyglot_cli.py chat "timeline"` -> returned `Recent Activity`.

### 2026-06-16 - Natural Packet Questions Now Open The Latest Task Packet

User-facing issue:

- Questions like `看看最新任务包` and `上次发给worker的是什么` should lead to the latest delegated packet.
- Before this change, they either fell through to the generic fallback or were intercepted by worker-identity wording.

Change:

- Added `packet_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural packet/payload phrasing now opens `Task Packet Summary`.
- This summary reuses the existing latest-packet surface and points users to `/packet`, `/board`, and `/timeline`.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 61 tests passed.
- `python -B .\polyglot_cli.py chat "看看最新任务包"` -> returned `Task Packet Summary`.
- `python -B .\polyglot_cli.py chat "上次发给worker的是什么"` -> returned `Task Packet Summary`.
- `python -B .\polyglot_cli.py chat "packet"` -> returned `Task Packet Summary`.

### 2026-06-16 - Natural History And Handoff Questions Now Open The Right View

User-facing issue:

- Natural questions like `看看会话记录`, `history`, and `handoff` still fell through to the generic fallback reply.
- Those are clearly view-selection intents and should surface the existing conversation/handoff artifacts directly.

Change:

- Added `history_chat_text()` in `polyglot_ai/main_agent.py`.
- Added `handoff_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural chat now routes:
  - history/conversation-record phrasing -> `Conversation History`
  - handoff phrasing -> `Session Handoff`

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 63 tests passed.
- `python -B .\polyglot_cli.py chat "看看会话记录"` -> returned `Conversation History`.
- `python -B .\polyglot_cli.py chat "history"` -> returned `Conversation History`.
- `python -B .\polyglot_cli.py chat "handoff"` -> returned `Session Handoff`.

Follow-up refinement:

- Compressed self-referential view outputs inside conversation history so entries like `Conversation History` or `Session Handoff` appear as short `opened ...` markers instead of re-inlining large blocks.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 65 tests passed.
- `python -B .\polyglot_cli.py chat "history"` -> recent assistant entries now render as `opened Conversation History` / `opened Session Handoff`.

### 2026-06-16 - Natural “What Did I Just Open?” Summary

User-facing issue:

- After wiring more natural view-selection questions, it became useful to ask for a very light recap of what had just been opened.
- `history` was still too heavy for that specific need.

Change:

- Added `recent_views_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural questions like `我刚刚看了什么` and `最近打开了什么` now return `Recent View Summary`.
- The summary deduplicates repeated view opens so it stays short and readable.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 66 tests passed.
- `python -B .\polyglot_cli.py chat "我刚刚看了什么"` -> returned `Recent View Summary`.
- `python -B .\polyglot_cli.py chat "最近打开了什么"` -> returned `Recent View Summary`.

### 2026-06-16 - Natural Status, Cost, And Session Questions Now Open The Right View

User-facing issue:

- Short natural prompts like `看看状态`, `费用`, and `有哪些session` still either fell through to the generic fallback or hit a less suitable summary.

Change:

- Added `sessions_chat_text()` in `polyglot_ai/main_agent.py`.
- Added `cost_chat_text()` in `polyglot_ai/main_agent.py`.
- Extended current-status matching to include `看看状态`.
- Natural chat now routes:
  - status/check-state phrasing -> `Current Status Summary`
  - cost/spend phrasing -> `Cost Summary`
  - session-list phrasing -> `Session Summary`

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 69 tests passed.
- `python -B .\polyglot_cli.py chat "看看状态"` -> returned `Current Status Summary`.
- `python -B .\polyglot_cli.py chat "费用"` -> returned `Cost Summary`.
- `python -B .\polyglot_cli.py chat "有哪些session"` -> returned `Session Summary`.

### 2026-06-16 - Natural Planner/Route/Report Aliases Now Open The Matching View

User-facing issue:

- Phrases like `看一下planner`, `看一下路由`, and `看一下报告` are natural ways to ask for existing views.
- Before this change they still fell through to the generic fallback reply.

Change:

- Added `planner_chat_text()` in `polyglot_ai/main_agent.py`.
- Added `route_chat_text_for_saved_goal()` in `polyglot_ai/main_agent.py`.
- Added natural alias routing so:
  - `看一下planner` -> saved team plan view
  - `看一下路由` -> current route decision for the saved goal
  - `看一下报告` -> saved run report

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 83 tests passed.
- `python -B .\polyglot_cli.py chat "看一下planner"` -> returned `Planner Summary`.
- `python -B .\polyglot_cli.py chat "看一下路由"` -> returned `Route Summary`.
- `python -B .\polyglot_cli.py chat "看一下报告"` -> returned `Run report`.

### 2026-06-16 - Chat Reply Now Routes Through A Central Intent Router

User feedback:

- Continuing to hand-wire more and more natural-language aliases into `chat_reply()` would drift away from the intended product feel.
- The main agent should judge intent first, then decide whether to answer, open a view, preview execution, or delegate.

Change:

- Added `message_matches_any(...)` in `polyglot_ai/main_agent.py`.
- Added `classify_chat_intent(...)` in `polyglot_ai/main_agent.py`.
- `chat_reply()` now routes through a central intent classifier instead of a long sequence of direct keyword branches.
- This keeps current behavior while making future intent changes cheaper and more coherent.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 87 tests passed.
- Existing natural query behaviors such as `看一下planner`, `看一下审批`, `我下一步看什么`, and `这句话会不会花钱：现在做到哪一步了` still returned the correct views after the refactor.

Follow-up refinement:

- Split the intent layer into:
  - `classify_chat_intent(...)`
  - `resolve_chat_intent(...)`
- `chat_reply()` now just records the user message, classifies the intent, resolves the reply, and records the assistant message.

Why this matters:

- Future natural-language behaviors can now be added by:
  1. teaching the classifier a new intent
  2. wiring that intent to an existing or new view responder

instead of growing one long mixed control-flow block.

### 2026-06-17 - Formal Architecture Roadmap Added

User direction:

- Stop drifting in implementation details and make the product shape explicit first.
- Align around the real target:
  - host client = main agent
  - Polyglot = runtime
  - CLI = fallback/config/debug shell

Change:

- Added [docs/architecture-roadmap.md](file:///d:/Repository/polyglot-ai-team/docs/architecture-roadmap.md) as the concise architecture and roadmap source.
- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) to point to:
  - `docs/architecture-roadmap.md`
  - `docs/vnext-host-runtime.md`

Why this matters:

- The repo now has a short, stable product/engineering roadmap separate from:
  - the long-form development log
  - the host-runtime spec
  - the handoff prompt

This should reduce future drift back toward "CLI as product center".

### 2026-06-17 - Core Product Docs Aligned Around Host Client = Main Agent

Change:

- Re-aligned the core product docs so they now tell the same story:
  - `docs/architecture-roadmap.md`
  - `docs/vnext-host-runtime.md`
  - `docs/gemini-handoff.md`
  - `README.md`

Shared direction now made explicit:

- host client = main agent
- Polyglot = runtime
- CLI = local setup / config / debug / fallback shell
- users should give the GitHub repo URL to the host agent, which installs repo + MCP + skills
- users should use Polyglot CLI only for local worker-model configuration and runtime inspection

Why this matters:

- This is the boundary that future engineering should protect.
- It reduces the chance of drifting back toward "Polyglot as another client" or "CLI as the product center".

### 2026-06-16 - Added A Unified `/view <name>` CLI Entry Point

User direction:

- The CLI should feel closer to a consistent assistant surface and reduce command memorization cost.

Change:

- Added `show_view(...)` in `polyglot_cli.py`.
- Added `/view <name>` and `polyglot_cli.py view <name>` as a unified read-only view entry point.
- Supported view targets include:
  - `status`, `workspace`, `board`, `packet`, `timeline`, `report`, `handoff`
  - `history`, `sessions`, `events`, `approval`, `lock`, `cost`, `model`, `agents`, `about`
- Also added a few friendly aliases such as `tasks -> board` and `messages -> history`.

Verification:

- `python -B -m unittest polyglot_ai.test_cli_view polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 91 tests passed.
- `python -B .\polyglot_cli.py view status` -> opened the current status view.
- `python -B .\polyglot_cli.py view board` -> opened the full task board.

Follow-up usability pass:

- Added friendlier aliases such as:
  - `task-board` -> `board`
  - `recent` -> `timeline`
  - `latest` -> `packet`
- Invalid targets now suggest a likely intended `/view ...` command instead of only printing a bare usage line.

Verification:

- `python -B -m unittest polyglot_ai.test_cli_view polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 93 tests passed.
- `python -B .\polyglot_cli.py view task-board` -> opened the task board.
- `python -B .\polyglot_cli.py view recent` -> opened the timeline view.
- `python -B .\polyglot_cli.py view latest` -> opened the latest packet.
- `python -B .\polyglot_cli.py view last` -> printed a suggestion to try `/view packet`.

### 2026-06-16 - Bare View Names Now Open Saved Views In REPL

User direction:

- Keep moving the CLI toward a lower-learning-cost, Claude-like surface where users can type what they want to see instead of remembering many command prefixes.

Change:

- Added `resolve_view_name(...)` in `polyglot_cli.py`.
- The REPL now opens a saved view directly when the whole input is a known view alias such as:
  - `board`
  - `report`
  - `timeline`
  - `history`
  - `latest`
  - `recent`
- This happens before task auto-delegation, so pure viewing inputs do not accidentally route into the main-agent intent layer.

Verification:

- `python -B -m unittest polyglot_ai.test_cli_view polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 94 tests passed.
- `python -B .\polyglot_cli.py view board` -> still opened the task board.
- `python -B .\polyglot_cli.py view report` -> still opened the saved report.

### 2026-06-16 - Natural Model-Config Questions Now Open The Config View

User-facing issue:

- `你现在用的是什么模型` and `看一下模型配置` are close, but they are not the same request.
- One asks for the current routed model summary, the other asks for the saved configuration surface.

Change:

- Added `model_config_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural model-config phrasing now opens `Model Configuration`.
- Current-model phrasing still opens `Model Summary`.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 85 tests passed.
- `python -B .\polyglot_cli.py chat "看一下模型配置"` -> returned `Model Configuration`.
- `python -B .\polyglot_cli.py chat "你现在用的是什么模型"` -> still returned `Model Summary`.

### 2026-06-16 - Natural Error/Problem Questions Now Open `Issue Summary`

User-facing issue:

- `现在有什么问题` and `最近错误` are clearly asking for the problem state, not a timeline or generic status card.
- Before the fix, `最近错误` could be intercepted by the broader `最近` matcher and fall into `Recent Activity`.

Change:

- Added `issues_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural error/problem phrasing now routes to `Issue Summary`.
- Moved issue matching ahead of recent-activity matching so `最近错误` is interpreted correctly.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 71 tests passed.
- `python -B .\polyglot_cli.py chat "现在有什么问题"` -> returned `Issue Summary`.
- `python -B .\polyglot_cli.py chat "最近错误"` -> returned `Issue Summary`.

### 2026-06-16 - Natural Approval/Steer/Lock Questions Now Open `Control Surface Summary`

User-facing issue:

- Short control-surface questions such as `有待批准的吗`, `有打断指令吗`, `暂停了吗`, and `锁住了吗` were still falling through to the generic fallback reply.

Change:

- Added `control_surface_chat_text()` in `polyglot_ai/main_agent.py`.
- Natural control-surface phrasing now routes to `Control Surface Summary`.
- The summary shows:
  - pending approval
  - pending steer
  - active control signal
  - active run lock

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 76 tests passed.
- `python -B .\polyglot_cli.py chat "有待批准的吗"` -> returned `Control Surface Summary`.
- `python -B .\polyglot_cli.py chat "有打断指令吗"` -> returned `Control Surface Summary`.
- `python -B .\polyglot_cli.py chat "暂停了吗"` -> returned `Control Surface Summary`.
- `python -B .\polyglot_cli.py chat "锁住了吗"` -> returned `Control Surface Summary`.

Follow-up aliases and robustness:

- Added natural aliases:
  - `看一下审批` -> `Control Surface Summary`
  - `看一下工作流` -> `Board Summary`
  - `看一下最近消息` -> `Conversation History`
- Hardened `Runtime.read_messages()` with `errors="replace"` so damaged bytes in `messages.jsonl` do not crash the history view.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 80 tests passed.
- `python -B .\polyglot_cli.py chat "看一下审批"` -> returned `Control Surface Summary`.
- `python -B .\polyglot_cli.py chat "看一下工作流"` -> returned `Board Summary`.
- `python -B .\polyglot_cli.py chat "看一下最近消息"` -> returned `Conversation History`.

### 2026-06-16 - Action-Oriented Questions Now Suggest The Best Next View

User-facing issue:

- Questions like `我现在该干嘛`, `我下一步看什么`, and `现在最值得看什么` are not asking for a full session summary.
- They are asking for the next best lens to inspect the system.

Change:

- Added `suggested_next_view_text()` in `polyglot_ai/main_agent.py`.
- Natural action-oriented questions now return `Suggested Next View`.
- The recommendation adapts to run state:
  - active run -> timeline/status/packet
  - failed/stopped -> timeline/report/status
  - success/idle -> report/diff/board

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow.TestRuntimeControlFlow` -> 73 tests passed.
- `python -B .\polyglot_cli.py chat "我现在该干嘛"` -> returned `Suggested Next View`.
- `python -B .\polyglot_cli.py chat "我下一步看什么"` -> returned `Suggested Next View`.
- `python -B .\polyglot_cli.py chat "现在最值得看什么"` -> returned `Suggested Next View`.

### 2026-06-16 - Natural Input Auto-Delegation Becomes Default

User correction:

- Requiring `/run` for normal work feels wrong.
- The desired product is a main agent: the user talks normally; the main agent decides whether to answer directly or invoke Claude.

Decision:

- Plain CLI input is now the primary interface.
- Task-like plain messages auto-delegate to the local worker by default.
- `/run <goal>` remains as an explicit force-run command for scripts and power users.
- `/chat <message>` remains as a force-chat command when the user wants to avoid workers.
- `POLYGLOT_AUTO_DELEGATE=0` disables auto-delegation for explicit-only mode.

Guardrails:

- `hello`, status-like questions, explanations, and planning-only requests stay in main-agent chat.
- Hard stop phrases such as `先别`, `不要写`, `别写代码`, `先说`, and `no code` prevent delegation.
- Engineering intent such as write/implement/fix/build plus an artifact hint triggers delegation.
- Before auto-delegating, the REPL prints a compact route line showing worker + model.

Verification:

- `python -B -m unittest polyglot_ai.test_runtime_flow` -> 38 tests passed.

### 2026-06-16 - REPL Routing Logic Order Fix & Test Regression Repairs

User-facing issue:
- REPL loop checked `should_delegate_to_worker` before intent classification, causing natural language preview requests containing coding keywords (e.g. "如果我直接说写一个日期转换器会发生什么") to trigger delegation and hang tests.
- Missing `re` import in `polyglot_cli.py` broke print formatting.
- `show_model` subcommand did not output the selected profile route description, failing model configuration tests.
- `show_report` subcommand formatted from state instead of reading the saved `final_report.md` when present, failing report-secret redaction tests.

Change:
- Reordered REPL loop in `polyglot_cli.py`: run `main_agent.classify_chat_intent(message)` first. If it matches a view, preview, info block, or help intent, handle it. Only delegate to worker if it falls through to fallback AND matches `should_delegate_to_worker`.
- Added `import re` in `polyglot_cli.py`.
- Updated `show_model` to print `main_agent.model_text(os.environ)` when called with no arguments.
- Updated `show_report` to display the saved `final_report.md` if it exists.
- Fixed `test_runtime_flow.py` test assertion mismatch for the missing model key help text case-sensitivity and terminal wrapping.

Verification:
- `python -m unittest discover -s polyglot_ai -p "test_*.py"` -> All 200 tests passed.

### 2026-06-17 - Minimal MCP Server Spec Added

User direction:

- Stop drifting in CLI-level detail and make the next real build target explicit.

Change:

- Added [docs/mcp-server-minimal-spec.md](file:///d:/Repository/polyglot-ai-team/docs/mcp-server-minimal-spec.md).
- Linked it from:
  - [docs/architecture-roadmap.md](file:///d:/Repository/polyglot-ai-team/docs/architecture-roadmap.md)
  - [docs/gemini-handoff.md](file:///d:/Repository/polyglot-ai-team/docs/gemini-handoff.md)

Why this matters:

- The repo now has a concrete spec for the next major build target instead of only a direction statement.
- It narrows the next implementation slice to the smallest useful MCP interface and reduces the risk of continuing to over-invest in CLI polish.

Current intended next implementation artifact:

- `polyglot_mcp_server.py`

### 2026-06-17 - Minimal `polyglot_mcp_server.py` Skeleton Implemented

Change:

- Added [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py).
- Implemented a minimal stdio JSON-RPC MCP-style server skeleton with:
  - `initialize`
  - `tools/list`
  - `tools/call`
  - `resources/list`
  - `resources/read`

Current minimal tool handlers:

- `polyglot_start_goal`
- `polyglot_status`
- `polyglot_get_task_board`
- `polyglot_steer`
- `polyglot_pause`
- `polyglot_resume`
- `polyglot_stop`
- `polyglot_get_report`
- `polyglot_list_models`

Current minimal resources:

- `polyglot://models`
- `polyglot://session/{session}/task-board`
- `polyglot://session/{session}/run-state`
- `polyglot://session/{session}/timeline`
- `polyglot://session/{session}/latest-packet`
- `polyglot://session/{session}/report`

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server` -> 7 tests passed.
- `python -B -m py_compile polyglot_mcp_server.py polyglot_ai\test_mcp_server.py` -> passed.

### 2026-06-17 - MCP Server Upgraded To Real stdio Framing + Prompt Surface

Change:

- Upgraded [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py) from line-oriented JSON handling to Content-Length stdio framing.
- Added prompt support:
  - `prompts/list`
  - `prompts/get`
- Added minimal built-in prompts:
  - `teamwork-preview`
  - `debug-runtime`
  - `review-task-board`
  - `continue-from-handoff`

Why this matters:

- The server is now much closer to a real MCP host-facing process instead of just a JSON-RPC sketch.
- Future host integration work can build on a protocol layer that already resembles expected stdio behavior.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server` -> 10 tests passed.
- `python -B -m py_compile polyglot_mcp_server.py polyglot_ai\test_mcp_server.py` -> passed.

### 2026-06-17 - MCP Tool And Resource Metadata Upgraded

Change:

- Added richer tool descriptors in [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py):
  - `description`
  - `inputSchema`
- Added resource descriptions.
- Added top-level server `instructions` in the `initialize` response so host clients can understand the role of the server more clearly.

Why this matters:

- The MCP layer is now easier for host agents to inspect and call correctly.
- This moves the server from "callable skeleton" toward "usable host-facing contract".

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server` -> 11 tests passed.
- `python -B -m py_compile polyglot_mcp_server.py polyglot_ai\test_mcp_server.py` -> passed.

### 2026-06-17 - MCP Initialize Now Includes Protocol Version

Change:

- Added `MCP_PROTOCOL_VERSION` in [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py).
- `initialize` now returns:
  - `protocolVersion`
  - `serverInfo`
  - `capabilities`
  - `instructions`

Why this matters:

- This is the smallest protocol-correctness improvement for host discovery.
- It keeps the MCP surface narrow while making the handshake less ambiguous for real hosts.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server` -> 17 tests passed.
- `python -B -m py_compile polyglot_mcp_server.py polyglot_ai\test_mcp_server.py` -> passed.

### 2026-06-17 - MCP Resource Typing Refined For Workspace Summary

Change:

- `polyglot://workspace-summary` now reads back as `text/plain`.
- Structured resources remain JSON-oriented.
- Report remains `text/markdown`.

Why this matters:

- Host clients can treat each resource more naturally instead of receiving everything as JSON.
- This keeps the contract closer to the intent of the resource surface without broadening scope.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server` -> 17 tests passed.

### 2026-06-17 - `polyglot_start_goal(force_run=true)` Now Returns Readable Follow-Up URIs

Change:

- Extended `polyglot_start_goal` force-run results in [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py).
- The response now includes:
  - `task_board_uri`
  - `run_state_uri`
  - `report_uri`

Why this matters:

- A host agent can now immediately know where to read the resulting state and report after starting a delegated run.
- This makes the minimal MCP contract more usable without widening scope.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server` -> 17 tests passed.

### 2026-06-17 - Handoff Added To The Minimal MCP Contract

Change:

- Added `polyglot_get_handoff` to [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py).
- Added `polyglot://session/{session}/handoff` resource support.
- Updated [docs/mcp-server-minimal-spec.md](file:///d:/Repository/polyglot-ai-team/docs/mcp-server-minimal-spec.md) so handoff is part of the minimal contract.

Why this matters:

- Report is not enough for long-running host workflows.
- Handoff is the durable continuation artifact that host agents need when work spans multiple turns or sessions.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server` -> 19 tests passed.

### 2026-06-17 - `continue-from-handoff` Prompt Now Includes Real Handoff Content

Change:

- Upgraded the `continue-from-handoff` MCP prompt in [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py).
- It now embeds the generated handoff markdown instead of only naming the session id.

Why this matters:

- Host agents can now use the prompt as a real continuation surface, not just a symbolic hint.
- This makes the prompt/resource/tool trio around handoff much more coherent.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server` -> 20 tests passed.

### 2026-06-17 - Codex Host Packaging Artifact Added

Change:

- Added [plugin.json](file:///d:/Repository/polyglot-ai-team/.codex-plugin/plugin.json) under `.codex-plugin/`.
- Added packaging coverage in [test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py).
- Updated:
  - [architecture-roadmap.md](file:///d:/Repository/polyglot-ai-team/docs/architecture-roadmap.md)
  - [host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md)
  - [gemini-handoff.md](file:///d:/Repository/polyglot-ai-team/docs/gemini-handoff.md)

Why this matters:

- The repo now contains an actual host-facing packaging artifact for Codex, not just abstract install guidance.
- This keeps the product direction anchored on host-first integration instead of fallback CLI growth.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging polyglot_ai.test_mcp_server` -> 16 tests passed.

Follow-up hardening:

- Updated [install_codex_host.ps1](file:///d:/Repository/polyglot-ai-team/scripts/install_codex_host.ps1) so `mcp.json` is written as UTF-8 **without BOM** using `System.IO.File.WriteAllText(..., UTF8Encoding(false))`.
- Added a merge-preservation test to ensure existing `mcpServers` entries and unrelated top-level keys survive install.
- Added a README install example for the Codex-first installer.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 8 tests passed.
- Dry-run installer still prints the expected install plan.

Follow-up:

- Added [install_codex_host.ps1](file:///d:/Repository/polyglot-ai-team/scripts/install_codex_host.ps1) as a first Codex-focused host install entrypoint.
- Updated:
  - [README.md](file:///d:/Repository/polyglot-ai-team/README.md)
  - [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md)
  - [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py)

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging polyglot_ai.test_mcp_server` -> 23 tests passed.
- PowerShell parser check for `scripts/install_codex_host.ps1` -> passed.

### 2026-06-17 - README Now Points To MCP Server Spec

Change:

- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) to point to:
  - `docs/architecture-roadmap.md`
  - `docs/vnext-host-runtime.md`
  - `docs/mcp-server-minimal-spec.md`

Why this matters:

- New readers now see the architectural roadmap, host/runtime boundary, and next implementation target in one place.

### 2026-06-17 - Host Install Flow And Future Protocol Notes Added

Change:

- Added [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md).
- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) to include that document in the canonical reading path.
- Updated [docs/architecture-roadmap.md](file:///d:/Repository/polyglot-ai-team/docs/architecture-roadmap.md) to:
  - reference the host install flow
  - explicitly record Claude Code Agent SDK as a future worker-adapter direction
  - explicitly record A2A as a future protocol worth tracking, not a current implementation target

Why this matters:

- The product shape is now documented not just as architecture, but as a concrete first-run user flow.
- Future contributors are less likely to confuse:
  - host model ownership
  - worker model ownership
  - runtime integration priorities

### 2026-06-17 - Codex Host Integration Guide Added

Change:

- Added [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md).
- Linked it from:
  - [README.md](file:///d:/Repository/polyglot-ai-team/README.md)
  - [docs/architecture-roadmap.md](file:///d:/Repository/polyglot-ai-team/docs/architecture-roadmap.md)
  - [docs/gemini-handoff.md](file:///d:/Repository/polyglot-ai-team/docs/gemini-handoff.md)

Why this matters:

- The repo now has a host-specific install and usage path for the most important first host.
- This reduces ambiguity between:
  - generic host-runtime architecture
  - concrete Codex-first install flow

### 2026-06-17 - Main Agent Owns Architecture Decisions, Sub-Agents Stay Sidecar

User correction:

- Core product shape, architecture, boundary-setting, and roadmap decisions should be made by the Main Agent directly.
- Sub-agents are welcome for cheap/fast sidecar work, but not for final architecture judgments.

Change:

- Updated:
  - [.clauderules](file:///d:/Repository/polyglot-ai-team/.clauderules)
  - [.cursorrules](file:///d:/Repository/polyglot-ai-team/.cursorrules)

New rule:

- the Main Agent owns final architecture and roadmap decisions
- sub-agents support with scanning, drift checks, and verification only

### 2026-06-17 - README Reframed Around Host-First Usage

Change:

- Reframed [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so it now:
  - presents the host-first install path before CLI usage
  - clearly marks the CLI as a fallback/debug/config shell
  - points readers to `docs/host-install-flow.md`

Why this matters:

- New readers now see the intended product shape earlier:
  - host client first
  - Polyglot runtime second
  - CLI as local fallback/config shell

### 2026-06-17 - Config TUI Now Defaults To Flash And Hides Pro In The First Menu

Change:

- Updated [polyglot_cli.py](file:///d:/Repository/polyglot-ai-team/polyglot_cli.py) so the first-run model preset menu only offers:
  - DeepSeek V4 Flash
  - Custom
- Removed the DeepSeek Pro preset from the default config TUI prompt path.
- Added a regression test in [polyglot_ai/test_config_tui.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_config_tui.py) to keep Pro out of the first visible menu.

Why this matters:

- The repo now follows the product rule from `docs/vnext-host-runtime.md` more closely:
  - Flash stays the cheap default path
  - Pro is not silently reintroduced through the main onboarding menu
- This also reduces accidental expensive model selection during dogfooding.

Verification:

- `python -B -m unittest polyglot_ai.test_config_tui polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 61 tests passed.

### 2026-06-17 - Config TUI Now Offers MiniMax And Stops Synthesizing Pro Defaults

Change:

- Updated [polyglot_cli.py](file:///d:/Repository/polyglot-ai-team/polyglot_cli.py) so the first-run model preset menu now offers:
  - DeepSeek V4 Flash
  - MiniMax M3
  - Custom
- Replaced the old non-Flash default-env branch that synthesized `deepseek-v4-pro[1m]` with a neutral worker-default helper that keeps the selected model name as the worker default instead of silently escalating to Pro.
- Added a regression test in [polyglot_ai/test_config_tui.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_config_tui.py) to verify MiniMax presets stay on MiniMax defaults and do not reintroduce Pro.

Why this matters:

- This now matches the repo docs that already describe Flash, MiniMax, and Custom as the small built-in set.
- It removes one of the easiest ways the runtime could drift back into expensive Pro usage during first-run configuration.

Verification:

- `python -B -m unittest polyglot_ai.test_config_tui polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 62 tests passed.

### 2026-06-17 - Custom MiniMax Profiles Now Infer Provider And Routing Metadata

Change:

- Updated [polyglot_cli.py](file:///d:/Repository/polyglot-ai-team/polyglot_cli.py) so the config TUI now infers routing metadata for custom profiles instead of leaving them as generic low-tier defaults.
- If the user enters a custom MiniMax-compatible profile, the CLI now infers:
  - `provider = minimax-openai`
  - `openai_base_url = https://api.minimax.io/v1`
  - `api_key_env = MINIMAX_API_KEY` when no encrypted key is supplied
  - `cost_tier = pro`
  - MiniMax-oriented worker capabilities
- The base URL prompt label is now generic (`Base URL`) instead of DeepSeek-specific.

Why this matters:

- Users can now configure a real backup worker through the same CLI flow even when they do not use the preset menu.
- The router no longer loses MiniMax metadata just because the profile was created in custom mode.

Verification:

- `python -B -m unittest polyglot_ai.test_config_tui polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 63 tests passed.

### 2026-06-17 - MCP Model Listing Now Exposes Routing Metadata

Change:

- Updated [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py) so `polyglot_list_models` now returns richer per-profile metadata:
  - `name`
  - `provider`
  - `base_url`
  - `capabilities`
- Updated [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) to verify the extra fields are preserved in the MCP response.
- Updated [docs/mcp-server-minimal-spec.md](file:///d:/Repository/polyglot-ai-team/docs/mcp-server-minimal-spec.md) to note that richer routing metadata is allowed and useful.

Why this matters:

- Host clients can now make smarter routing or display decisions from the MCP contract instead of inferring everything from the model string.
- This keeps the runtime more useful without expanding the tool catalog.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 54 tests passed.

### 2026-06-17 - Example Model Config Curated To Flash First And MiniMax Fallback

Change:

- Rewrote [polyglot_models.example.json](file:///d:/Repository/polyglot-ai-team/polyglot_models.example.json) into the new `default_model` / `configs` schema.
- Removed the disabled DeepSeek Pro profile from the checked-in example.
- Kept only the repo's intended sample profiles:
  - DeepSeek V4 Flash
  - MiniMax M3
- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) to say the checked-in example is curated for the Flash-first dogfood path and MiniMax fallback rather than mirroring an older DeepSeek Pro example.
- Added a packaging regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) so the example stays Flash-first.

Why this matters:

- The repo's user-facing example config now matches the actual product shape instead of advertising an expensive profile as the sample template.
- Future contributors are less likely to reintroduce Pro into the default example and confuse the onboarding story.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 33 tests passed.

### 2026-06-17 - Root Model Config Was Aligned To The Same Flash First Template

Change:

- Updated [polyglot_models.json](file:///d:/Repository/polyglot-ai-team/polyglot_models.json) so the repo root fallback config now matches the curated example template:
  - `default_model` is `deepseek-v4-flash`
  - only `deepseek-v4-flash` and `minimax-m3` profiles remain
  - the disabled DeepSeek Pro profile is removed from the checked-in fallback config

Why this matters:

- The repo no longer contains two different default stories for worker model setup.
- The file that runtime code falls back to when no workspace override exists now matches the same Flash-first, MiniMax-fallback shape as the example and README.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 34 tests passed.

### 2026-06-17 - Onboarding Copy Now Names Flash And MiniMax Directly

Change:

- Updated [polyglot_cli.py](file:///d:/Repository/polyglot-ai-team/polyglot_cli.py) so the setup hint now says `run /config to add encrypted Flash and MiniMax profiles`.
- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so the `/config` command directory entry now says `DeepSeek Flash, MiniMax, or custom profiles`.
- Updated the tests in [polyglot_ai/test_config_tui.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_config_tui.py) and [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to lock in the new wording.

Why this matters:

- The most visible configuration entrypoints now talk in the repo's actual cheap-default vocabulary instead of a generic DeepSeek catch-all.
- That reduces onboarding ambiguity for the user and keeps the first-use story consistent with the Flash-first runtime shape.

Verification:

- `python -B -m unittest polyglot_ai.test_config_tui polyglot_ai.test_skill_packaging` -> 44 tests passed.

### 2026-06-17 - Skill Docs Now Say To Use Model Listing Metadata For Routing

Change:

- Updated [skills/polyglot-team-os/references/runtime-capabilities.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/runtime-capabilities.md) to say that `polyglot_list_models` should be used when the host needs provider, base URL, or capability metadata before picking a worker profile.
- Added a packaging regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep that routing guidance in place.

Why this matters:

- The skill now teaches hosts not just how to call the runtime, but how to use the richer model listing output to make a better routing decision.
- This closes the loop between the MCP output shape and the host-facing skill instructions.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 36 tests passed.

### 2026-06-17 - MCP Minimal Spec Example Now Shows Rich Model Metadata

Change:

- Updated [docs/mcp-server-minimal-spec.md](file:///d:/Repository/polyglot-ai-team/docs/mcp-server-minimal-spec.md) so the `polyglot_list_models` example now includes:
  - `name`
  - `provider`
  - `base_url`
  - `capabilities`
- Added a packaging regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the richer metadata example documented.

Why this matters:

- The spec now matches the actual MCP server output shape more closely, so host implementers do not have to guess how to route between Flash and MiniMax.
- It keeps the host-facing contract consistent from code to docs to skills.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 37 tests passed.

### 2026-06-17 - VNext Host Runtime Model Listing Example Now Matches Rich Metadata

Change:

- Updated [docs/vnext-host-runtime.md](file:///d:/Repository/polyglot-ai-team/docs/vnext-host-runtime.md) so the `polyglot_list_models` example now includes the same richer metadata shape as the server:
  - `name`
  - `provider`
  - `base_url`
  - `capabilities`
  - `cost_tier`
- Added a packaging regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the central host-runtime doc aligned with the richer listing output.

Why this matters:

- `docs/vnext-host-runtime.md` is the main alignment target, so its example payload needs to match the actual MCP output shape instead of the older role-only sketch.
- Host implementers can now see the Flash vs MiniMax routing metadata directly in the central spec.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 38 tests passed.

### 2026-06-17 - CLI Help Example Now Uses Flash Instead Of Old Pro Label

Change:

- Updated the `/model` example in [polyglot_cli.py](file:///d:/Repository/polyglot-ai-team/polyglot_cli.py) so the command directory now shows `/model deepseek-v4-flash` instead of the stale `/model deepseek-pro` example.
- Added a packaging regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the CLI help example Flash-first.

Why this matters:

- The help output now matches the repo's current cheap-default model story instead of advertising the old Pro label.
- This is the kind of tiny user-facing drift that creates confusion even when the runtime itself is already correct.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 39 tests passed.

### 2026-06-17 - Models Resource Added To Host Quick Probes

Change:

- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so the host-side quick probe list now includes:
  - `polyglot://models`
  - `polyglot_list_models`
- Updated [docs/mcp-server-minimal-spec.md](file:///d:/Repository/polyglot-ai-team/docs/mcp-server-minimal-spec.md) to say that `polyglot://models` should mirror the richer `polyglot_list_models` output shape when available.
- Added a model-resource regression test in [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) and locked the README quick probes in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py).

Why this matters:

- Hosts now have a direct JSON resource to inspect when they need routing metadata before starting or resuming work.
- This is a cleaner fit for host-first integration than only exposing the list as a tool.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 62 tests passed.

### 2026-06-17 - Host Install Docs Now Verify Model Listing Alongside Workspace Summary And Handoff

Change:

- Updated [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md) so host install verification now includes the model listing surface alongside workspace summary and handoff.
- Updated [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) so the fast deterministic snapshot now points to `polyglot://models` and `polyglot_list_models` in addition to `polyglot://workspace-summary`.
- Added packaging regression tests in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the host-install and Codex-integration docs aligned with the richer model-routing probes.

Why this matters:

- Host agents now have an explicit install-time and verify-time path for checking routing metadata, not just handoff/state surfaces.
- This keeps the integration story consistent with the richer model-listing contract that the MCP server now exposes.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 39 tests passed.

### 2026-06-17 - Models Resource Now Mirrors The Full Model Listing Payload

Change:

- Updated [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py) so `polyglot://models` now returns the full `polyglot_list_models` payload instead of only the `profiles` array.
- Updated the resource-read test in [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) to assert that `default_model` is present alongside the richer routing metadata.

Why this matters:

- Hosts now get the same complete model-list object whether they call the tool or read the resource.
- This removes a subtle mismatch that would have made `polyglot://models` less useful for routing decisions than the docs suggested.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 62 tests passed.

### 2026-06-17 - Codex Integration Docs Now Lead With MCP Probes Instead Of CLI Model Checks

Change:

- Updated [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) so the primary recommended checks are now MCP probes:
  - `polyglot://models`
  - `polyglot_list_models`
  - `polyglot://workspace-summary`
  - `polyglot_get_task_board`
  - `polyglot_get_handoff`
  - `continue-from-handoff`
- Kept the CLI `model` / `route` checks only as fallback diagnostics.
- Added packaging regression coverage in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the doc MCP-first.

Why this matters:

- The Codex integration story now matches the repo's stated priority: MCP first, CLI fallback second.
- Host implementers are nudged toward the stable runtime contract instead of the older CLI inspection path.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 39 tests passed.

### 2026-06-17 - Task Board Was Added To The Host Quick Probes And Install Verification

Change:

- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so the host-side quick probes now include `polyglot_get_task_board`.
- Updated [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md) so install verification now explicitly mentions the task board alongside workspace summary, model listing, and handoff.
- Added packaging regression coverage in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the task-board probe and install verification wording in place.

Why this matters:

- Polyglot's structured task board is one of the core runtime surfaces, so it belongs in the host's first probe set.
- This keeps the integration story anchored on runtime state rather than only model selection and final handoff.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 39 tests passed.

### 2026-06-17 - Report Probe Was Added To The Host Quick Probes And Install Verification

Change:

- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so the host-side quick probes now include `polyglot://session/{session}/report` and `polyglot_get_report`.
- Updated [docs/host-install-flow.md](file:///d:/Repository/polyglot-ai-team/docs/host-install-flow.md) so install verification now mentions report alongside task board, workspace summary, model listing, and handoff.
- Updated [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) so the current recommended MCP probes include the report surface before handoff continuation.
- Added packaging regression coverage in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the report probe guidance in place.

Why this matters:

- The host-facing runtime story now includes the final result surface, not just the planning and in-progress surfaces.
- That gives the host a straight path from task board to final report without scraping logs.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 39 tests passed.

### 2026-06-17 - Start Goal Spec Now Documents Worker And Force-Run Controls

Change:

- Updated [docs/vnext-host-runtime.md](file:///d:/Repository/polyglot-ai-team/docs/vnext-host-runtime.md) so the `polyglot_start_goal` example now includes `worker` and `force_run` alongside `goal`, `workspace`, `model_profile`, and `mode`.
- Updated [docs/mcp-server-minimal-spec.md](file:///d:/Repository/polyglot-ai-team/docs/mcp-server-minimal-spec.md) so the minimal `polyglot_start_goal` example also shows `worker` and `force_run`.
- Added packaging regression coverage in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep those controls documented in both specs.
- Added a tool-schema assertion in [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) to ensure `worker` and `force_run` stay exposed by the MCP server.

Why this matters:

- The docs now show the same explicit control knobs that the server already supports.
- Host clients can intentionally force a worker or force execution without guessing at hidden runtime behavior.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 62 tests passed.

### 2026-06-17 - VNext Model List Example Now Includes Model And Enabled Fields

Change:

- Updated the `polyglot_list_models` example in [docs/vnext-host-runtime.md](file:///d:/Repository/polyglot-ai-team/docs/vnext-host-runtime.md) so it now includes the `model` and `enabled` fields that the MCP server actually returns.
- Added a packaging regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep those fields present in the main host-runtime spec.

Why this matters:

- The central host-runtime spec now mirrors the live MCP payload shape more closely.
- This reduces the chance that host implementers rely on an over-simplified example and miss fields that are actually returned by the server.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 39 tests passed.

### 2026-06-17 - First Implementation Slice Now Lists The Full MCP Resource Bundle

Change:

- Updated the `First Implementation Slice` section in [docs/vnext-host-runtime.md](file:///d:/Repository/polyglot-ai-team/docs/vnext-host-runtime.md) so the resource bundle now includes:
  - `task-board`
  - `run-state`
  - `timeline`
  - `latest-packet`
  - `report`
  - `handoff`
  - `models`
  - `workspace-summary`
- Added a packaging regression test in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep that slice aligned with the actual runtime surfaces.

Why this matters:

- The main host-runtime spec now describes the same resource surfaces that the MCP server already exposes.
- That keeps the first implementation slice from looking narrower than the runtime that was already built.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 40 tests passed.

### 2026-06-17 - Skill References Now Prefer MCP Before CLI Bridge Aliases

Change:

- Updated [skills/polyglot-team-os/references/runtime-capabilities.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/runtime-capabilities.md) to map host-facing MCP tools to their fallback CLI aliases and to state explicitly that MCP is the preferred surface when available.
- Updated [skills/polyglot-team-os/references/host-integration.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/host-integration.md) so the recommended MCP continuation path now starts with session/status/task-board inspection before handoff/report continuation.

Why this matters:

- The skill docs now teach the host agent to use the stable MCP contract first instead of defaulting to text bridge aliases.
- That keeps the product boundary consistent with `docs/vnext-host-runtime.md` and reduces the chance of a host implementation treating `/run` as the only entrypoint.

### 2026-06-17 - Host Quick Probes Now Include The Full Session Resource Bundle

Change:

- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so the host-side MCP quick probes now include the full session resource bundle:
  - `polyglot://session/{session}/task-board`
  - `polyglot://session/{session}/run-state`
  - `polyglot://session/{session}/timeline`
  - `polyglot://session/{session}/latest-packet`
  - `polyglot://session/{session}/report`
  - `polyglot://session/{session}/handoff`
- Updated [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) so the Codex-first MCP probe path now explicitly includes the session task board, run state, timeline, latest packet, report, and handoff.
- Added packaging regression coverage in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the README and Codex integration docs aligned with that session-level surface.

Why this matters:

- The host-facing docs now show the same session-scoped surfaces that the runtime already exposes through MCP.
- That makes it easier for a host agent to inspect a live run without slipping back into raw-log parsing.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 63 tests passed.

### 2026-06-17 - Session Status Probe Now Matches The Existing Runtime Template

Change:

- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so the host-side MCP quick probes now include `polyglot_status` and `polyglot://session/{session}/status` as the fast path for current session state.
- Updated [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) so the Codex-first MCP probe flow now begins with a dedicated session-state check before task-board inspection.
- Updated [docs/vnext-host-runtime.md](file:///d:/Repository/polyglot-ai-team/docs/vnext-host-runtime.md) and [docs/mcp-server-minimal-spec.md](file:///d:/Repository/polyglot-ai-team/docs/mcp-server-minimal-spec.md) so the recommended resource set now includes the session status resource template.
- Updated [skills/polyglot-team-os/SKILL.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/SKILL.md) and [skills/polyglot-team-os/references/host-integration.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/host-integration.md) so the portable skill and host reference both steer hosts toward the status probe first.
- Added packaging regression coverage in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the session status probe and resource template documented.

Why this matters:

- The host can now ask for the fastest possible current-state summary without jumping straight to the board or report.
- That lines up the docs with a runtime capability that was already present in `polyglot_mcp_server.py`.

Verification:

- `python -B -m unittest polyglot_ai.test_skill_packaging` -> 41 tests passed.

### 2026-06-17 - Session Status Resource Is Now Discoverable In Resources List

Change:

- Updated [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py) so `resources/list` now exposes `polyglot://session/{session}/status` alongside the other session resources.
- Added a regression assertion in [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) to ensure the status resource appears in the resource list and still uses a `uriTemplate`.

Why this matters:

- Hosts that discover capabilities from `resources/list` can now see the session status surface immediately instead of having to infer it from `resources/templates/list` or the tool list.
- That makes the MCP surface more complete and easier to render in a host-side status panel.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 64 tests passed.

### 2026-06-17 - Host Docs And Tests Now Cover The MCP Prompt Workflow Surface

Change:

- Updated [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md) to add a dedicated `Current Recommended MCP Prompts` section for `teamwork-preview`, `debug-runtime`, `review-task-board`, and `continue-from-handoff`.
- Added regression coverage in [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) to keep `review-task-board` present in `prompts/list` and to verify `prompts/get` returns the expected session-scoped instruction.
- Expanded [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) to verify the session task board, run state, timeline, and latest packet resources all render as JSON with representative live data.

Why this matters:

- The host-facing MCP story now covers not only state resources and tools, but also the workflow prompts that should guide the host agent through the common Polyglot paths.
- The task-board resource test now exercises a fresh heartbeat path instead of only the stale fallback, which is closer to how a user would actually inspect a live run.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 70 tests passed.

### 2026-06-17 - README Now Surfaces The MCP Prompt Workflow Entry Points

Change:

- Updated [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so the front-page host guidance now includes a dedicated `Host-side MCP prompts` block for `teamwork-preview`, `debug-runtime`, `review-task-board`, and `continue-from-handoff`.
- Added regression coverage in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep the README prompt entry points visible to future changes.

Why this matters:

- The README now gives a newcomer both the resource probes and the workflow starters in one place, which matches how a host agent should actually begin using Polyglot.
- That makes the repo a better first-run landing page for users who are also trying to learn the product shape while using it.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 71 tests passed.

### 2026-06-17 - MCP Prompt Workflow Surface Now Fully Covers Debug Runtime

Change:

- Added [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) coverage for the `debug-runtime` prompt so the session-scoped runtime inspection workflow is tested alongside `teamwork-preview`, `review-task-board`, and `continue-from-handoff`.

Why this matters:

- The prompt surface now has regression coverage for all four recommended workflow starters in `docs/vnext-host-runtime.md`.
- That makes the host-side entry points harder to accidentally trim during future refactors.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 72 tests passed.

### 2026-06-17 - MCP Tool Surface Now Has Direct Regression Coverage For The Core Actions

Change:

- Expanded [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) to assert the full core MCP tool surface in `tools/list`, including `polyglot_get_task_board`, `polyglot_steer`, `polyglot_pause`, `polyglot_resume`, `polyglot_stop`, `polyglot_get_report`, and `polyglot_list_models`.
- Added tool-call regression coverage for `polyglot_status`, `polyglot_get_task_board`, `polyglot_get_report`, `polyglot_steer`, `polyglot_pause`, `polyglot_resume`, and `polyglot_stop`.

Why this matters:

- The runtime now has direct tests for the main action surface that host agents are expected to use, not just the resource mirror of that state.
- That gives the MCP layer the same kind of contract coverage that the docs already imply.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 77 tests passed.

### 2026-06-17 - VNext Resources And Skill References Now Include Handoff And Workflow Prompts

Change:

- Updated [docs/vnext-host-runtime.md](file:///d:/Repository/polyglot-ai-team/docs/vnext-host-runtime.md) so the recommended MCP resource list now includes `polyglot://session/{session}/handoff` alongside the other session resources.
- Updated [skills/polyglot-team-os/references/runtime-capabilities.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/runtime-capabilities.md) to add a dedicated `MCP Prompts` section for `teamwork-preview`, `debug-runtime`, `review-task-board`, and `continue-from-handoff`.
- Added regression coverage in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep both the vnext resource block and the skill reference prompt block in place.

Why this matters:

- The host-facing documentation now treats handoff as a first-class resource in the main runtime spec instead of only in downstream guides.
- The reusable skill reference now explains the workflow starter prompts directly, which makes the MCP surface easier to use without spelunking into multiple docs.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 79 tests passed.

### 2026-06-17 - Host Integration Reference Now Documents MCP Prompt Starters

Change:

- Updated [skills/polyglot-team-os/references/host-integration.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/host-integration.md) to add a dedicated `MCP Prompts` section for `teamwork-preview`, `debug-runtime`, `review-task-board`, and `continue-from-handoff`.
- Added regression coverage in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep those prompt starters visible in the host integration reference.

Why this matters:

- The generic host wiring guide now teaches both the continuation path and the workflow starters, which makes it easier for external clients to use the runtime the way the vnext spec expects.
- That reduces the chance that a host integrator treats the bridge as the only entry point and misses the prompt surface entirely.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 80 tests passed.

### 2026-06-17 - Skill References Now Mirror The Full MCP Resource Surface

Change:

- Updated [skills/polyglot-team-os/references/runtime-capabilities.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/runtime-capabilities.md) to add a dedicated `MCP Resources` section covering `polyglot://session/{session}/status`, `polyglot://session/{session}/task-board`, `polyglot://session/{session}/run-state`, `polyglot://session/{session}/timeline`, `polyglot://session/{session}/latest-packet`, `polyglot://session/{session}/report`, `polyglot://session/{session}/handoff`, `polyglot://models`, and `polyglot://workspace-summary`.
- Updated [skills/polyglot-team-os/references/host-integration.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/references/host-integration.md) with the same `MCP Resources` list so host wiring guidance and capability guidance stay in sync.
- Added regression coverage in [polyglot_ai/test_skill_packaging.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_skill_packaging.py) to keep both reference docs aligned with the MCP resource contract.

Why this matters:

- The portable skill now reflects the same resource contract as the host-facing runtime spec instead of only describing prompts and tools.
- That makes the skill easier for host agents to consume without falling back to raw log parsing or extra prompting.

Verification:

- `python -B -m unittest polyglot_ai.test_mcp_server polyglot_ai.test_skill_packaging` -> 82 tests passed.

### 2026-06-17 - DPAPI Key Is Visible In Config But Still Fails Decryption In Doctor

Change:

- Verified that `setup` and model selection can read `C:\\Users\\ROG\\polyglot_models.json`, but `doctor` still reports `model key: decryption failed` for the encrypted API key.
- Confirmed the config file is present and the selected model is loaded, so the remaining blocker is specifically the decryption check in the current Windows execution context.

Why this matters:

- The config flow is close, but the runtime still needs the exact same session/user context for DPAPI to unlock the key cleanly.
- That means the next user-facing step is to re-save the API key in the same local CLI session that will launch Claude, or adjust the doctor wording to make this limitation explicit.

Verification:

- `setup` with `POLYGLOT_MODEL_CONFIG=C:\\Users\\ROG\\polyglot_models.json` -> ready: yes, key: encrypted.
- `doctor` with the same config -> `model key: decryption failed`.

### 2026-06-17 - DPAPI Failure Is Environment-Scoped In The Codex Sandbox

Change:

- Confirmed the Codex execution context reports `rog-strix\\codexsandboxoffline` even though it sees `C:\\Users\\ROG` as the profile directory.
- That explains why the user-level DPAPI blob cannot be decrypted here: the sandbox is not the same Windows logon context that created the secret.

Why this matters:

- It means the encrypted config can still be valid for the user's local PowerShell session while remaining unreadable from this sandbox.
- Any future diagnostics around encrypted keys should mention the same-user-context requirement explicitly so we do not mislabel a valid local config as broken.

### 2026-06-17 - Workspace Discovery Now Prefers Repo Script Location Over Current Directory

Change:

- Updated `polyglot_cli.py` so workspace detection now checks `POLYGLOT_WORKSPACE` first, then walks upward from the CLI script location, then walks upward from the current working directory.
- Added a regression test covering the common case where the user runs `polyglot doctor` from `C:\\Users\\ROG`, but the actual CLI lives in the repo root.

Why this matters:

- `polyglot doctor` and other workspace-aware commands now resolve the repo correctly even when the shell is opened elsewhere.
- This removes the earlier false failure where the CLI looked in `C:\\Users\\ROG` for `polyglot_ai` and `monitor.py`.

Verification:

- `python -m pytest polyglot_ai/test_encryption.py -q` -> 14 passed.
- `polyglot doctor` from `C:\\Users\\ROG` -> workspace resolves to `D:\\Repository\\polyglot-ai-team`, syntax ok, result ok.

### 2026-06-17 - Host MCP Now Exposes Model Registry Refresh And Snapshot Resources

Change:

- Added a new MCP tool, `polyglot_refresh_model_registry`, so host clients can force a SuperCLUE registry refresh without touching the CLI.
- Added a new MCP resource, `polyglot://model-registry`, so hosts can read the latest local registry snapshot directly.
- Updated the vnext host runtime spec and the minimal MCP spec to describe the new host-facing registry control surface.

Why this matters:

- Host agents now have a first-class way to keep model routing and price metadata fresh on demand.
- This keeps the model-price sync story on the host/MCP side instead of making the CLI the place where host integrations have to care.

Verification:

- `python -m pytest polyglot_ai/test_mcp_server.py polyglot_ai/test_config_tui.py -q` -> 45 passed.

### 2026-06-17 - Skill And Host Docs Now Surface Model Registry Refresh

Change:

- Updated [skills/polyglot-team-os/SKILL.md](file:///d:/Repository/polyglot-ai-team/skills/polyglot-team-os/SKILL.md) and the host integration references to include `polyglot_refresh_model_registry` and `polyglot://model-registry`.
- Updated [docs/codex-host-integration.md](file:///d:/Repository/polyglot-ai-team/docs/codex-host-integration.md), [docs/vnext-host-runtime.md](file:///d:/Repository/polyglot-ai-team/docs/vnext-host-runtime.md), [docs/mcp-server-minimal-spec.md](file:///d:/Repository/polyglot-ai-team/docs/mcp-server-minimal-spec.md), and [README.md](file:///d:/Repository/polyglot-ai-team/README.md) so host-facing guidance matches the new MCP surface.

Why this matters:

- The host contract now clearly shows how to refresh and inspect the model registry from MCP, which keeps pricing sync on the host side instead of burying it in CLI behavior.
- This closes the gap between the vnext host runtime spec and the reusable skill docs.

Verification:

- `python -m pytest polyglot_ai/test_skill_packaging.py polyglot_ai/test_mcp_server.py -q` -> 87 passed.

### 2026-06-17 - Host MCP And Skill Surface Are Now Coherent Enough For MVP Gap Assessment

Change:

- Re-audited the current host-facing contract against `docs/vnext-host-runtime.md`, `docs/mcp-server-minimal-spec.md`, `docs/host-install-flow.md`, `docs/codex-host-integration.md`, `README.md`, `skills/polyglot-team-os/SKILL.md`, and `polyglot_mcp_server.py`.
- Confirmed the current MCP surface already exposes the core host/runtime loop: `polyglot_start_goal`, `polyglot_status`, `polyglot_get_task_board`, `polyglot_steer`, `polyglot_pause`, `polyglot_resume`, `polyglot_stop`, `polyglot_get_report`, `polyglot_get_handoff`, `polyglot_list_models`, `polyglot_refresh_model_registry`, plus the `polyglot://model-registry` and `polyglot://workspace-summary` resources.
- Confirmed the reusable `polyglot-team-os` skill now points hosts at MCP first and the bridge script only as fallback.

Why this matters:

- The host-side product boundary is now coherent enough that the remaining work is mostly productization, install-flow polish, and end-to-end smoke rather than missing core runtime shape.
- The project can now be used to keep developing itself through its own host-facing MCP and skill surface instead of treating the CLI as the center.

Verification:

- `python -m pytest polyglot_ai/test_mcp_server.py polyglot_ai/test_skill_packaging.py -q` -> 87 passed.
- `python -m py_compile polyglot_mcp_server.py`

### 2026-06-17 - Host Status Surface Now Includes Team Plan, Control, Approval, And Lock Context

Change:

- Expanded `polyglot_status` and `polyglot://session/{session}/status` in [polyglot_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_mcp_server.py) so hosts can read the active `team_plan`, `next_action`, `selected_agent`, `complexity_level`, `steer`, `control`, `approval`, and `run_lock` context in one call.
- Updated [docs/mcp-server-minimal-spec.md](file:///d:/Repository/polyglot-ai-team/docs/mcp-server-minimal-spec.md) and [docs/vnext-host-runtime.md](file:///d:/Repository/polyglot-ai-team/docs/vnext-host-runtime.md) to show the richer status payload.
- Added regression coverage in [polyglot_ai/test_mcp_server.py](file:///d:/Repository/polyglot-ai-team/polyglot_ai/test_mcp_server.py) for the expanded tool and resource responses.

Why this matters:

- Host clients can now make control decisions from one MCP status read instead of stitching together state from multiple runtime files or extra resources.
- This is a concrete step toward the vNext promise that Polyglot should feel like a callable runtime behind the host rather than a separate CLI-centered system.

Verification:

- `python -m pytest polyglot_ai/test_mcp_server.py -q` -> 36 passed.
- `python -m pytest polyglot_ai/test_mcp_server.py polyglot_ai/test_skill_packaging.py -q` -> 87 passed.
- `python -m py_compile polyglot_mcp_server.py polyglot_ai/test_mcp_server.py`
