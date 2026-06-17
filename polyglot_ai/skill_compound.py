"""Skill Compounding — track skill usage and build cross-session indices.
No LLM calls. Pure functions only.
"""

import json
import math
import os
from datetime import datetime


def _session_skill_usage_path(session_dir):
    return os.path.join(str(session_dir), "skill_usage.json")


def _skill_index_path(artifacts_dir):
    return os.path.join(str(artifacts_dir), "skill_index.json")


def _read_json(path, default):
    """Read a JSON file, returning default on any error."""
    if not path or not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    """Write data atomically-ish — write to tmp then rename."""
    dir_path = os.path.dirname(os.path.abspath(str(path)))
    os.makedirs(dir_path, exist_ok=True)
    tmp_path = str(path) + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(path))
        return True
    except OSError:
        return False


def record_skill_usage(session_dir, skill_name, phase="fill", outcome="unknown"):
    """Record that a skill was used in a session.

    Args:
        session_dir: directory where session state lives
        skill_name: string skill file name
        phase: "fill" | "verify" | "plan" | "report"
        outcome: "success" | "failure" | "unknown"

    Returns:
        True if recorded successfully
    """
    if not session_dir or not skill_name:
        return False

    path = _session_skill_usage_path(session_dir)
    current = _read_json(path, [])
    if not isinstance(current, list):
        current = []

    entry = {
        "skill": str(skill_name),
        "phase": str(phase),
        "outcome": str(outcome),
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    current.append(entry)
    return _write_json(path, current)


def read_skill_usage(session_dir):
    """Read all skill usage entries for a session. Returns list."""
    if not session_dir:
        return []
    path = _session_skill_usage_path(session_dir)
    data = _read_json(path, [])
    return data if isinstance(data, list) else []


def update_skill_index(artifacts_dir, session_dir):
    """Merge session skill usage into the artifact-level skill index.

    The skill index tracks per-skill statistics across sessions:
        - total_uses: int
        - success_count: int
        - failure_count: int
        - success_rate: float or None
        - last_used_at: ISO timestamp
        - last_outcome: str
        - triggers: list of str (skill names that were used alongside this one)

    Returns:
        The updated skill_index dict (also written to disk).
    """
    if not session_dir or not artifacts_dir:
        return {}

    usage = read_skill_usage(session_dir)
    if not usage:
        return read_skill_index(artifacts_dir)

    index_path = _skill_index_path(artifacts_dir)
    index = _read_json(index_path, {})
    if not isinstance(index, dict):
        index = {}

    skills_in_session = {entry.get("skill") for entry in usage}

    for entry in usage:
        skill = entry.get("skill")
        if not skill:
            continue
        outcome = str(entry.get("outcome", "unknown"))
        ts = entry.get("ts", datetime.now().isoformat(timespec="seconds"))

        stats = index.get(skill, {
            "total_uses": 0,
            "success_count": 0,
            "failure_count": 0,
            "success_rate": None,
            "last_used_at": "",
            "last_outcome": "",
            "triggers": [],
        })

        stats["total_uses"] = int(stats.get("total_uses", 0)) + 1
        if outcome == "success":
            stats["success_count"] = int(stats.get("success_count", 0)) + 1
        elif outcome == "failure":
            stats["failure_count"] = int(stats.get("failure_count", 0)) + 1

        total = stats["success_count"] + stats["failure_count"]
        stats["success_rate"] = (
            round(stats["success_count"] / total, 3) if total > 0 else None
        )
        stats["last_used_at"] = ts
        stats["last_outcome"] = outcome

        triggers = set(stats.get("triggers") or [])
        for other in skills_in_session:
            if other and other != skill:
                triggers.add(str(other))
        stats["triggers"] = sorted(triggers)[:10]

        index[skill] = stats

    _write_json(index_path, index)
    return index


def read_skill_index(artifacts_dir):
    """Read the skill index. Returns dict (empty if none exists)."""
    if not artifacts_dir:
        return {}
    path = _skill_index_path(artifacts_dir)
    data = _read_json(path, {})
    return data if isinstance(data, dict) else {}


def recommend_by_history(skill_index, top_n=5):
    """Return top-n skill names ordered by success_rate * log(uses+1).

    Pure function — takes index dict, returns sorted list.
    """
    if not skill_index or not isinstance(skill_index, dict):
        return []
    scored = []
    for skill, stats in skill_index.items():
        if not isinstance(stats, dict):
            continue
        sr = stats.get("success_rate")
        uses = int(stats.get("total_uses", 0) or 0)
        if sr is None:
            weight = 0.5
        else:
            weight = float(sr) * math.log(uses + 1, 2)
        scored.append((skill, weight))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in scored[:top_n]]


if __name__ == "__main__":
    import sys
    artifacts = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "artifacts")
    idx = read_skill_index(artifacts)
    if idx:
        print(json.dumps(idx, indent=2, ensure_ascii=False))
        print("\nTop recommendations:", recommend_by_history(idx, top_n=3))
    else:
        print("No skill index yet. Skills are tracked across sessions as workers run.")
