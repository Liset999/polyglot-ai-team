import os
from datetime import datetime


TASK_EVENT_PREFIX = {
    "plan": ("team_plan.created", "planner.started", "planner.completed", "planner.failed"),
    "implement": ("worker.status.filling", "worker.adapter.query", "worker.adapter.write"),
    "verify": ("worker.status.testing", "worker.status.healing", "worker.status.success", "worker.status.failed"),
    "report": ("report.written",),
}


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _seconds_between(first, last):
    start = _parse_ts(first)
    end = _parse_ts(last)
    if not start or not end:
        return ""
    return f"{max(0, int((end - start).total_seconds()))}s"


def _line_count(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _event_index(events):
    index = {}
    for event in events:
        event_type = event.get("type", "")
        index.setdefault(event_type, []).append(event)
    return index


def _current_run_events(events):
    last_plan = -1
    for index, event in enumerate(events):
        if event.get("type") == "team_plan.created":
            last_plan = index
    if last_plan < 0:
        return events
    return events[last_plan:]


def _task_status(task_id, event_types, state):
    run_status = (state or {}).get("status", "")
    if task_id == "plan":
        if event_types.get("planner.failed"):
            return "failed"
        if event_types.get("planner.completed") or event_types.get("team_plan.created"):
            return "done"
        if event_types.get("planner.started"):
            return "running"
        return "pending"
    if task_id == "implement":
        if event_types.get("worker.adapter.write"):
            return "done"
        if event_types.get("worker.status.filling") or event_types.get("worker.adapter.query"):
            return "running"
        if run_status in ("failed", "error"):
            return "blocked"
        return "pending"
    if task_id == "verify":
        if event_types.get("worker.status.success"):
            return "done"
        if event_types.get("worker.status.failed"):
            return "failed"
        if event_types.get("worker.status.healing"):
            return "healing"
        if event_types.get("worker.status.testing"):
            return "running"
        return "pending"
    if task_id == "report":
        if event_types.get("report.written"):
            return "done"
        if run_status == "success":
            return "pending"
        return "pending"
    return "pending"


def _task_timing(task_id, event_types):
    names = TASK_EVENT_PREFIX.get(task_id, ())
    matched = []
    for name in names:
        matched.extend(event_types.get(name, []))
    if not matched:
        return "", ""
    first = matched[0].get("ts", "")
    last = matched[-1].get("ts", "")
    return first, _seconds_between(first, last)


def _task_errors(task_id, events, state):
    if task_id == "verify":
        failures = [event for event in events if event.get("type") in ("worker.status.failed", "worker.status.healing")]
        last_error = (state or {}).get("last_error_summary", "")
        return len(failures), last_error
    failed_events = [event for event in events if event.get("type", "").endswith(".failed")]
    return len(failed_events), ""


def _artifact_rows(runtime):
    rows = []
    for kind, dirname in (("draft", "draft"), ("release", "release")):
        root = runtime.artifact_dir(dirname) if hasattr(runtime, "artifact_dir") else os.path.join(runtime.artifacts_dir, dirname)
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if not os.path.isfile(path):
                continue
            rows.append({
                "kind": kind,
                "name": name,
                "lines": _line_count(path) if name.endswith(".py") else "",
                "bytes": os.path.getsize(path),
            })
    return rows


def build_task_board(runtime):
    plan = runtime.read_team_plan() or {}
    state = runtime.read_run_state() or {}
    all_events = runtime.read_events()
    packets = runtime.read_task_packets()
    control = runtime.read_control() or {}
    events = _current_run_events(all_events)
    event_types = _event_index(events)
    issue_graph = plan.get("issue_graph") or []

    tasks = []
    for item in issue_graph:
        task_id = item.get("id", "")
        first_seen, elapsed = _task_timing(task_id, event_types)
        errors, last_error = _task_errors(task_id, events, state)
        tasks.append({
            "id": task_id,
            "title": item.get("title", ""),
            "status": _task_status(task_id, event_types, state),
            "depends_on": item.get("depends_on", []),
            "first_seen": first_seen,
            "elapsed": elapsed,
            "errors": errors,
            "last_error": last_error,
        })

    has_session_work = bool(plan and not plan.get("_error")) or bool(state and not state.get("_error"))
    return {
        "session_id": runtime.session_id,
        "goal": plan.get("goal") or state.get("goal", ""),
        "agent": plan.get("selected_agent") or state.get("backend", ""),
        "run_status": state.get("status", "idle"),
        "attempt": state.get("attempt", 0),
        "control": control if not control.get("_error") else {"action": "error", "message": control.get("_error", "")},
        "tasks": tasks,
        "artifacts": _artifact_rows(runtime) if has_session_work else [],
        "task_packets": packets[-5:],
        "task_packets_count": len(packets),
        "events_count": len(events),
        "events_total": len(all_events),
        "product_strategy": plan.get("product_strategy", {}),
    }


def render_task_board(board):
    lines = []
    lines.append("Task Board")
    lines.append(f"  session: {board.get('session_id', '')}")
    lines.append(f"  goal:    {board.get('goal', '')}")
    lines.append(f"  agent:   {board.get('agent', '')}")
    lines.append(f"  status:  {board.get('run_status', 'idle')} | attempts {board.get('attempt', 0)} | events {board.get('events_count', 0)}")
    control = board.get("control") or {}
    if control.get("action") and control.get("action") != "resume":
        message = f" | {control.get('message')}" if control.get("message") else ""
        lines.append(f"  control: {control.get('action')}{message}")
    lines.append("")

    lines.append("Tasks")
    if not board.get("tasks"):
        lines.append("  No task graph found.")
    else:
        lines.append("  id         status    errors  elapsed  title")
        lines.append("  ---------  --------  ------  -------  -----")
        for task in board["tasks"]:
            lines.append(
                "  {id:<9}  {status:<8}  {errors:<6}  {elapsed:<7}  {title}".format(
                    id=task.get("id", "")[:9],
                    status=task.get("status", "")[:8],
                    errors=task.get("errors", 0),
                    elapsed=task.get("elapsed", ""),
                    title=task.get("title", ""),
                )
            )
            if task.get("last_error"):
                lines.append(f"             error: {task['last_error']}")

    lines.append("")
    lines.append("Artifacts")
    if not board.get("artifacts"):
        lines.append("  No artifacts found.")
    else:
        lines.append("  kind     lines   bytes   name")
        lines.append("  -------  ------  ------  ----")
        for artifact in board["artifacts"]:
            lines.append(
                "  {kind:<7}  {lines:<6}  {bytes:<6}  {name}".format(
                    kind=artifact.get("kind", ""),
                    lines=artifact.get("lines", ""),
                    bytes=artifact.get("bytes", ""),
                    name=artifact.get("name", ""),
                )
            )

    strategy = board.get("product_strategy") or {}
    packets = board.get("task_packets") or []
    if packets:
        lines.append("")
        lines.append("Recent Task Packets")
        lines.append("  phase    attempt  backend       target")
        lines.append("  -------  -------  ------------  ------")
        for packet in packets:
            lines.append(
                "  {phase:<7}  {attempt:<7}  {backend:<12}  {target}".format(
                    phase=packet.get("phase", "")[:7],
                    attempt=packet.get("attempt", 0),
                    backend=packet.get("backend", "")[:12],
                    target=packet.get("target_file", ""),
                )
            )

    if strategy:
        lines.append("")
        lines.append("Product Strategy")
        for key, value in strategy.items():
            lines.append(f"  {key}: {value}")

    return "\n".join(lines)


def render_compact_task_board(board):
    lines = []
    goal = board.get("goal", "")
    if len(goal) > 90:
        goal = goal[:87].rstrip() + "..."
    lines.append("Polyglot Task Board")
    lines.append(f"session: {board.get('session_id', '')}")
    lines.append(f"status: {board.get('run_status', 'idle')} | agent: {board.get('agent', '')} | attempts: {board.get('attempt', 0)}")
    control = board.get("control") or {}
    if control.get("action") and control.get("action") != "resume":
        lines.append(f"control: {control.get('action')}")
    if goal:
        lines.append(f"goal: {goal}")

    tasks = board.get("tasks") or []
    if tasks:
        task_bits = []
        for task in tasks:
            task_bits.append(f"{task.get('id', '')}:{task.get('status', '')}")
        lines.append("tasks: " + " -> ".join(task_bits))

    packets = board.get("task_packets") or []
    if packets:
        packet = packets[-1]
        lines.append(
            "last packet: {phase} attempt {attempt} -> {target} via {backend}".format(
                phase=packet.get("phase", ""),
                attempt=packet.get("attempt", 0),
                target=packet.get("target_file", ""),
                backend=packet.get("backend", ""),
            )
        )

    artifacts = board.get("artifacts") or []
    release_files = [item for item in artifacts if item.get("kind") == "release"]
    if release_files:
        names = ", ".join(item.get("name", "") for item in release_files[:8])
        suffix = "" if len(release_files) <= 8 else f", +{len(release_files) - 8} more"
        lines.append(f"release: {names}{suffix}")

    lines.append("commands: /status, /report, /steer <message>, /pause, /resume, /stop, /run <goal>")
    return "\n".join(lines)
