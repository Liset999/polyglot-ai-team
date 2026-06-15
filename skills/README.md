# Polyglot Skills Directory Contract

This directory contains two different kinds of skills. Keep them separate.

## 1. Runtime Pitfall Skills

Top-level `*.md` files are short execution notes for planner/worker prompts.

Current runtime pitfall skills:

- `date_diff_pitfalls.md`
- `cli_no_edit_recovery.md`
- `traceback_to_fix_prompt.md`

Contract:

- Keep each file short and action-oriented.
- Write in English unless a test fixture requires another language.
- Prefer concrete fixes over explanation.
- Avoid host-specific paths.
- Format each file as:

```markdown
# skill-name

- Trigger: when this pitfall appears.
- Symptom: what failure looks like.
- Fix strategy: the shortest concrete corrective move.
- Avoid: common wrong move.
```

These files are safe to inject into worker prompts because they are compact and predictable.

## 2. Host Integration Skills

Subdirectories are installable skills for external hosts.

Current host integration skill:

- `polyglot-team-os/`

Contract:

- `SKILL.md` explains when to use the skill and the routing contract.
- `scripts/` contains executable host bridge code.
- `references/` contains host-specific examples and deeper integration notes.
- `agents/openai.yaml` contains Codex UI metadata.
- Do not make machine-specific paths part of the contract.
- Prefer `POLYGLOT_WORKSPACE`, `--workspace`, and host-provided configuration.

Host integration skills are for Hermes, Lobster, Feishu, Codex, and other wrappers that need to route user text into Polyglot.
