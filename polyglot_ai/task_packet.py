import hashlib


def _short_hash(text):
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:10]


def build_task_packet(
    *,
    goal,
    phase,
    target_file,
    test_file,
    backend,
    prompt,
    permission_profile="",
    description="",
    attempt=0,
    error_summary="",
    steer_message="",
    max_attempts=3,
):
    packet_id = _short_hash("|".join([
        goal or "",
        phase or "",
        target_file or "",
        str(attempt),
        prompt or "",
    ]))
    constraints = []
    if steer_message:
        constraints.append({"source": "human_steer", "text": steer_message})
    if error_summary:
        constraints.append({"source": "test_failure", "text": error_summary})

    return {
        "packet_id": packet_id,
        "phase": phase,
        "goal": goal,
        "target_file": target_file,
        "test_file": test_file,
        "description": description or "",
        "backend": backend,
        "permission_profile": permission_profile or "unknown",
        "attempt": attempt,
        "budget": {
            "max_self_heal_attempts": max_attempts,
            "coordination_style": "task-packet-not-chat",
        },
        "context": {
            "verification_command": "python polyglot_ai/v0_worker.py",
            "workspace_scope": "artifacts/draft",
            "release_scope": "artifacts/release",
        },
        "constraints": constraints,
        "prompt_preview": (prompt or "")[:1000],
    }
