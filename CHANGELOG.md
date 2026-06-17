# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2026-06-18

### Added

**Meta Planner (Team Plan 2.0)**
- `polyglot_ai/meta_planner.py` — keyword-based complexity scoring (no LLM needed)
- `assess_complexity(goal)` — scores 0–100, returns level (simple/medium/complex) + reasoning
- `generate_task_graph(goal, complexity_level)` — generates structured task graph with phases, dependencies, and per-node model preferences
- `build_team_plan(goal)` — full Team Plan 2.0 composer
- `normalize_team_plan(plan)` — auto-upgrades old-format team plans to 2.0 schema with backwards compatibility
- `polyglot_preview_plan` MCP tool — read-only plan preview without starting any worker

**Skill Compounding**
- `polyglot_ai/skill_compound.py` — cross-session skill usage tracking
- `record_skill_usage()` — records skill loads per session
- `update_skill_index()` — aggregates into global skill statistics (total_uses, success_rate, triggers)
- `recommend_by_history()` — returns top-N skills sorted by success_rate × log(uses+1)
- Worker automatically tracks which skills are loaded and records outcomes

**Budget Control**
- `Runtime.record_budget_downgrade(reason)` — logs budget-exceeded events to run_state
- `Runtime.read_budget_state()` — exposes attempts_used / max_total_attempts / budget_exceeded
- `budget_state` field added to `polyglot_status` response
- Worker self-heal loop checks budget before each attempt; downgrades gracefully when exceeded

**Structured Handoff**
- `polyglot_ai/handoff.py` — structured continuation packs
- `build_handoff_pack()` — returns {session_state, completed_tasks, remaining_tasks, key_context_refs, next_action, budget_remaining, metadata}
- `build_handoff_markdown()` — human-readable handoff rendering
- `polyglot_get_handoff` upgraded to return structured handoff pack + handoff.json written to session dir

### Changed

- `Runtime.save_team_plan()` and `Runtime.read_team_plan()` now auto-normalize through `normalize_team_plan()`
- `polyglot_mcp_server.py` — `session_status_payload()` includes `budget_state` from runtime
- `v1_worker.py` — additive changes only; skill tracking and budget checks are non-invasive

### Fixed

- `normalize_team_plan()` maps tiny/small → simple correctly; infers complexity from tasks length when not specified
- Budget downgrade events correctly appended to `run_state.json` budget_downgrade_events list

### Documentation

- `skills/polyglot-team-os/SKILL.md` — `polyglot_preview_plan` added to MCP Tools table
- `docs/development-log.md` — full feature batch documented

---

## [1.x] - Previous versions

See git history for earlier changelog entries.
