import os
import subprocess
import sys
from datetime import datetime

from polyglot_ai.agents import discover_agents, read_agent_config, select_agent
from polyglot_ai.task_board import build_task_board, render_compact_task_board, render_task_board


class MainAgent:
    """Shared control layer for terminal and IM interfaces."""

    def __init__(self, workspace_dir, runtime):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.runtime = runtime

    def discover_agent_paths(self, env=None):
        return [agent.to_dict() for agent in discover_agents(env)]

    def release_files(self):
        return self.runtime.release_files()

    def parse_env_and_goal(self, words):
        env = {}
        goal_parts = []
        for word in words:
            if "=" in word:
                key, value = word.split("=", 1)
                if key.isupper():
                    env[key] = value
                    continue
            goal_parts.append(word)
        return env, " ".join(goal_parts).strip()

    def estimate_complexity(self, goal):
        text = goal.lower()
        score = 0
        markers = (
            "api", "database", "db", "jwt", "login", "frontend", "backend",
            "multi-file", "refactor", "crawler", "dashboard",
        )
        for marker in markers:
            if marker in text:
                score += 1
        if len(goal) > 80:
            score += 1
        if score >= 3:
            return "medium"
        if score >= 1:
            return "small"
        return "tiny"

    def build_team_plan(self, goal, env=None):
        agents = self.discover_agent_paths(env)
        selected_agent = select_agent(env)
        selected = selected_agent.name
        complexity = self.estimate_complexity(goal)
        execution_mode = "single-agent" if complexity in ("tiny", "small") else "single-agent-with-self-heal"
        roles = ["meta_planner", "runtime_orchestrator", "coder", "test_runner"]
        if complexity == "medium":
            roles.append("reviewer")

        return {
            "goal": goal,
            "task_name": goal[:48],
            "complexity_level": complexity,
            "execution_mode": execution_mode,
            "roles_needed": roles,
            "selected_agent": selected,
            "routing": self.route_decision(goal, env),
            "available_agents": agents,
            "issue_graph": [
                {"id": "plan", "title": "Generate testable task scaffold", "depends_on": []},
                {"id": "implement", "title": "Delegate implementation to local CLI worker", "depends_on": ["plan"]},
                {"id": "verify", "title": "Run tests and self-heal if needed", "depends_on": ["implement"]},
                {"id": "report", "title": "Summarize artifacts, status, and next action", "depends_on": ["verify"]},
            ],
            "budget": {
                "max_worker_calls": 4,
                "max_self_heal_attempts": 3,
                "coordination_style": "structured-state-not-chat",
            },
            "product_strategy": {
                "clawswarm_takeaway": "preserve visible team collaboration without defaulting to free-form agent group chat",
                "multica_takeaway": "preserve managed-agent lifecycle and squads without becoming a heavy platform first",
                "polyglot_differentiator": "local-first workers, human steering, Feishu-ready sessions, and low-token structured coordination",
            },
            "approval_points": ["before_destructive_changes", "before_network_or_external_side_effects"],
            "next_action": "run local planner, then delegate current task to selected worker",
            "created_at": datetime.now().isoformat(),
        }

    def route_decision(self, goal, env=None):
        env = env or os.environ
        selected = select_agent(env)
        selected_data = selected.to_dict()
        requested = env.get("POLYGLOT_AGENT", "auto").strip()
        reason = "auto-selected first available local coding worker"
        if requested and requested.lower() not in ("", "auto"):
            reason = f"POLYGLOT_AGENT={requested} override"
        if selected.is_mock:
            reason = "offline/mock fallback selected"
        complexity = self.estimate_complexity(goal)
        approval_points = ["before_destructive_changes", "before_network_or_external_side_effects"]
        if selected_data.get("permission_profile") in ("high-trust-local", "ask-before-use"):
            approval_points.append("before_high_trust_worker_actions")
        return {
            "goal": goal,
            "selected_agent": selected.name,
            "backend": selected.backend_name,
            "adapter": selected.adapter,
            "permission_profile": selected_data.get("permission_profile", ""),
            "best_for": selected_data.get("best_for", []),
            "routing_hint": selected_data.get("routing_hint", ""),
            "reason": reason,
            "complexity": complexity,
            "approval_points": approval_points,
        }

    def route_text(self, goal, env=None):
        decision = self.route_decision(goal, env)
        lines = ["Route Decision"]
        lines.append(f"  goal:       {decision['goal']}")
        lines.append(f"  agent:      {decision['selected_agent']} ({decision['backend']})")
        lines.append(f"  adapter:    {decision['adapter']}")
        lines.append(f"  permission: {decision['permission_profile']}")
        lines.append(f"  complexity: {decision['complexity']}")
        lines.append(f"  reason:     {decision['reason']}")
        if decision.get("routing_hint"):
            lines.append(f"  hint:       {decision['routing_hint']}")
        if decision.get("best_for"):
            lines.append(f"  best for:   {', '.join(decision['best_for'])}")
        lines.append(f"  approvals:  {', '.join(decision['approval_points'])}")
        return "\n".join(lines)

    def approval_required(self, decision):
        permission = decision.get("permission_profile", "")
        if permission in ("high-trust-local", "ask-before-use", "sandbox-preferred"):
            return True
        if decision.get("adapter") in ("openclaw", "openhands", "autogpt"):
            return True
        return False

    def request_run_approval_text(self, goal, env=None):
        decision = self.route_decision(goal, env)
        payload = self.runtime.request_approval({
            "kind": "run",
            "goal": goal,
            "env": env or {},
            "decision": decision,
            "reason": "worker requires explicit approval before execution",
        })
        lines = ["[APPROVAL REQUIRED]"]
        lines.append(f"  id:         {payload.get('approval_id')}")
        lines.append(f"  goal:       {goal}")
        lines.append(f"  agent:      {decision.get('selected_agent')} ({decision.get('backend')})")
        lines.append(f"  permission: {decision.get('permission_profile')}")
        lines.append(f"  reason:     {payload.get('reason')}")
        lines.append("  next:       use /approve to run, or /deny to cancel")
        return "\n".join(lines)

    def approval_text(self):
        approval = self.runtime.read_approval()
        if not approval:
            return "No pending approval."
        if approval.get("_error"):
            return f"Could not read approval file: {approval['_error']}"
        decision = approval.get("decision") or {}
        lines = ["", "[approval]"]
        lines.append(f"  id:         {approval.get('approval_id', '')}")
        lines.append(f"  kind:       {approval.get('kind', '')}")
        lines.append(f"  goal:       {approval.get('goal', '')}")
        lines.append(f"  agent:      {decision.get('selected_agent', '')} ({decision.get('backend', '')})")
        lines.append(f"  permission: {decision.get('permission_profile', '')}")
        lines.append(f"  reason:     {approval.get('reason', '')}")
        lines.append(f"  created:    {approval.get('created_at', '')}")
        lines.append("  next:       /approve or /deny")
        return "\n".join(lines)

    def approve_text(self):
        approval = self.runtime.read_approval()
        if not approval:
            return "No pending approval."
        if approval.get("_error"):
            return f"Could not read approval file: {approval['_error']}"
        if approval.get("kind") != "run":
            return f"Unsupported approval kind: {approval.get('kind')}"
        goal = approval.get("goal", "")
        env = approval.get("env") or {}
        self.runtime.clear_approval(status="approved", reason=f"Approved run: {goal}")
        exit_code, text = self.run_goal(goal, env, require_approval=False)
        return f"[OK] approval accepted; run exited {exit_code}\n\n{text}"

    def deny_text(self, reason=""):
        approval = self.runtime.clear_approval(status="denied", reason=reason or "Denied by user")
        if not approval:
            return "No pending approval."
        return f"[OK] approval denied: {approval.get('goal', '')}"

    def save_team_plan(self, plan):
        self.runtime.save_team_plan(plan)

    def render_team_plan(self, plan):
        lines = ["", "Team Plan"]
        lines.append(f"  task:       {plan['task_name']}")
        lines.append(f"  complexity: {plan['complexity_level']}")
        lines.append(f"  mode:       {plan['execution_mode']}")
        lines.append(f"  agent:      {plan['selected_agent']}")
        lines.append(f"  roles:      {', '.join(plan['roles_needed'])}")
        lines.append("  graph:      plan -> implement -> verify -> report")
        lines.append(f"  next:       {plan['next_action']}")
        return "\n".join(lines)

    def plan_goal(self, goal, env=None):
        plan = self.build_team_plan(goal, env)
        self.save_team_plan(plan)
        return plan, self.render_team_plan(plan)

    def run_monitor(self, goal, extra_env=None):
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        env["POLYGLOT_WORKSPACE"] = self.workspace_dir
        cmd = [sys.executable, os.path.join(self.workspace_dir, "monitor.py"), goal]
        return subprocess.call(cmd, cwd=self.workspace_dir, env=env)

    def run_goal(self, goal, env=None, require_approval=True):
        decision = self.route_decision(goal, env)
        if require_approval and self.approval_required(decision):
            return 2, self.request_run_approval_text(goal, env)
        acquired, lock = self.runtime.acquire_run_lock(goal)
        if not acquired:
            if lock.get("_error"):
                return 3, f"[BUSY] could not acquire run lock: {lock.get('_error')}"
            return 3, self.format_run_lock_busy(lock)
        try:
            _plan, plan_text = self.plan_goal(goal, env)
            exit_code = self.run_monitor(goal, env or None)
            self.runtime.snapshot_artifacts()
            report = self.format_run_report(exit_code)
            self.runtime.write_final_report(report)
            return exit_code, f"{plan_text}\n{report}"
        finally:
            self.runtime.release_run_lock(f"run finished: {goal}")

    def format_run_lock_busy(self, lock):
        lines = ["[BUSY] session already has an active run."]
        lines.append(f"  session: {lock.get('session_id', self.runtime.session_id)}")
        lines.append(f"  goal:    {lock.get('goal', '')}")
        lines.append(f"  owner:   {lock.get('owner', '')}")
        lines.append(f"  pid:     {lock.get('pid', '')}")
        lines.append(f"  since:   {lock.get('created_at', '')}")
        lines.append("  next:    use status to inspect, or unlock only if the run is stale")
        return "\n".join(lines)

    def read_final_report(self):
        if not os.path.exists(self.runtime.final_report_path):
            return "No final_report.md found for this session."
        with open(self.runtime.final_report_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def format_run_report(self, exit_code=None):
        state = self.runtime.read_run_state() or {}
        team_plan = self.runtime.read_team_plan() or {}
        if state.get("_error"):
            return f"I could not read the run state: {state['_error']}"

        status = state.get("status", "unknown")
        goal = state.get("goal", "")
        attempt = state.get("attempt", 0)
        backend = state.get("backend", "unknown")
        failure = state.get("failure_type", "none")
        error = state.get("last_error_summary", "")
        files = self.release_files()

        lines = ["Run report:"]
        if goal:
            lines.append(f"  goal: {goal}")
        if team_plan and not team_plan.get("_error"):
            lines.append(f"  plan: {team_plan.get('execution_mode', 'unknown')} via {team_plan.get('selected_agent', 'unknown')}")
        lines.append(f"  status: {status}")
        lines.append(f"  backend: {backend}")
        if attempt:
            lines.append(f"  self-heal attempts: {attempt}")
        if exit_code is not None:
            lines.append(f"  process exit: {exit_code}")
        if files:
            lines.append(f"  artifacts: {', '.join(files)}")
        if failure and failure != "none":
            lines.append(f"  failure: {failure}")
        if error:
            lines.append(f"  last error: {error}")
        return "\n".join(lines)

    def status_text(self):
        state = self.runtime.read_run_state()
        pending = self.runtime.read_steer()
        control = self.runtime.read_control()
        approval = self.runtime.read_approval()
        run_lock = self.runtime.read_run_lock()
        team_plan = self.runtime.read_team_plan()
        lines = ["", "[team plan]"]
        if not team_plan:
            lines.append("  No team_plan.json found.")
        elif team_plan.get("_error"):
            lines.append(f"  Could not read team plan: {team_plan['_error']}")
        else:
            lines.append(f"  task:       {team_plan.get('task_name', '')}")
            lines.append(f"  complexity: {team_plan.get('complexity_level', '')}")
            lines.append(f"  mode:       {team_plan.get('execution_mode', '')}")
            lines.append(f"  agent:      {team_plan.get('selected_agent', '')}")
            lines.append(f"  next:       {team_plan.get('next_action', '')}")

        lines.append("")
        lines.append("[run]")
        if not state:
            lines.append("  No run_state.json found.")
        elif state.get("_error"):
            lines.append(f"  Could not read state: {state['_error']}")
        else:
            lines.append(f"  goal:    {state.get('goal', '')}")
            lines.append(f"  status:  {state.get('status', 'unknown')}")
            lines.append(f"  attempt: {state.get('attempt', 0)}")
            lines.append(f"  backend: {state.get('backend', 'unknown')}")
            if state.get("failure_type") and state.get("failure_type") != "none":
                lines.append(f"  failure: {state.get('failure_type')}")
            if state.get("last_error_summary"):
                lines.append(f"  error:   {state.get('last_error_summary')}")

        lines.append("")
        lines.append("[run lock]")
        if not run_lock:
            lines.append("  No active run lock.")
        elif run_lock.get("_error"):
            lines.append(f"  Could not read run lock: {run_lock['_error']}")
        else:
            lines.append(f"  goal:  {run_lock.get('goal', '')}")
            lines.append(f"  owner: {run_lock.get('owner', '')}")
            lines.append(f"  pid:   {run_lock.get('pid', '')}")
            lines.append(f"  since: {run_lock.get('created_at', '')}")

        lines.append("")
        lines.append("[steer]")
        if not pending:
            lines.append("  No pending steer instruction.")
        elif pending.get("_error"):
            lines.append(f"  Could not read steer file: {pending['_error']}")
        else:
            lines.append(f"  message: {pending.get('message', '')}")
            lines.append(f"  sent:    {pending.get('timestamp', '')}")

        lines.append("")
        lines.append("[control]")
        if not control:
            lines.append("  No control signal.")
        elif control.get("_error"):
            lines.append(f"  Could not read control file: {control['_error']}")
        else:
            lines.append(f"  action:  {control.get('action', '')}")
            if control.get("message"):
                lines.append(f"  message: {control.get('message', '')}")
            lines.append(f"  sent:    {control.get('timestamp', '')}")

        lines.append("")
        lines.append("[approval]")
        if not approval:
            lines.append("  No pending approval.")
        elif approval.get("_error"):
            lines.append(f"  Could not read approval file: {approval['_error']}")
        else:
            decision = approval.get("decision") or {}
            lines.append(f"  goal:       {approval.get('goal', '')}")
            lines.append(f"  agent:      {decision.get('selected_agent', '')}")
            lines.append(f"  permission: {decision.get('permission_profile', '')}")
            lines.append("  next:       /approve or /deny")
        return "\n".join(lines)

    def lock_text(self):
        lock = self.runtime.read_run_lock()
        if not lock:
            return "No active run lock."
        if lock.get("_error"):
            return f"Could not read run lock: {lock['_error']}"
        return self.format_run_lock_busy(lock)

    def unlock_text(self, reason="manual unlock"):
        lock = self.runtime.release_run_lock(reason)
        if not lock:
            return "No active run lock."
        if lock.get("_error"):
            return f"Could not read run lock before unlock: {lock['_error']}"
        return f"[OK] run lock released: {lock.get('goal', '')}"

    def board_text(self):
        return render_task_board(build_task_board(self.runtime))

    def compact_board_text(self):
        return render_compact_task_board(build_task_board(self.runtime))

    def latest_packet_text(self):
        packets = self.runtime.read_task_packets(limit=1)
        if not packets:
            return "No task packet found for this session."
        packet = packets[-1]
        lines = ["Latest Task Packet"]
        lines.append(f"  id:      {packet.get('packet_id', '')}")
        lines.append(f"  phase:   {packet.get('phase', '')}")
        lines.append(f"  target:  {packet.get('target_file', '')}")
        lines.append(f"  test:    {packet.get('test_file', '')}")
        lines.append(f"  backend: {packet.get('backend', '')}")
        lines.append(f"  permission: {packet.get('permission_profile', '')}")
        lines.append(f"  attempt: {packet.get('attempt', 0)}")
        constraints = packet.get("constraints") or []
        if constraints:
            lines.append("  constraints:")
            for item in constraints:
                lines.append(f"    - {item.get('source', '')}: {item.get('text', '')}")
        preview = packet.get("prompt_preview", "")
        if preview:
            lines.append("")
            lines.append("Prompt Preview")
            lines.append(preview)
        return "\n".join(lines)

    def history_text(self, limit=12):
        messages = self.runtime.read_messages(limit=limit)
        lines = ["", "[conversation]"]
        if not messages:
            lines.append("  No conversation messages yet.")
            return "\n".join(lines)
        for message in messages:
            content = (message.get("content") or "").replace("\n", " ").strip()
            if len(content) > 120:
                content = content[:117].rstrip() + "..."
            lines.append(
                "  {ts}  {role:<9} {content}".format(
                    ts=message.get("ts", ""),
                    role=message.get("role", "")[:9],
                    content=content,
                )
            )
        return "\n".join(lines)

    def session_brief_text(self):
        state = self.runtime.read_run_state() or {}
        team_plan = self.runtime.read_team_plan() or {}
        files = self.release_files()
        selected = select_agent()
        lines = ["Session Brief"]
        lines.append(f"  session: {self.runtime.session_id}")
        lines.append(f"  worker:  {selected.name} ({selected.backend_name})")
        if team_plan and not team_plan.get("_error"):
            lines.append(f"  plan:    {team_plan.get('task_name', '')}")
            lines.append(f"  mode:    {team_plan.get('execution_mode', '')}")
        if state and not state.get("_error"):
            lines.append(f"  run:     {state.get('status', 'unknown')} via {state.get('backend', 'unknown')}")
            if state.get("goal"):
                lines.append(f"  goal:    {state.get('goal')}")
        if files:
            lines.append(f"  release: {', '.join(files)}")
        return "\n".join(lines)

    def sessions_text(self):
        sessions = self.runtime.list_sessions()
        lines = ["", "[sessions]"]
        if not sessions:
            lines.append("  No sessions found.")
            return "\n".join(lines)
        lines.append("  id          status    events  updated")
        lines.append("  ----------  --------  ------  -------")
        for item in sessions:
            marker = "*" if item.get("session_id") == self.runtime.session_id else " "
            lines.append(
                "{marker} {sid:<10}  {status:<8}  {events:<6}  {updated}".format(
                    marker=marker,
                    sid=item.get("session_id", "")[:10],
                    status=item.get("status", "")[:8],
                    events=item.get("events", 0),
                    updated=item.get("updated_at", ""),
                )
            )
        return "\n".join(lines)

    def create_session_text(self, session_id, title=""):
        runtime_cls = self.runtime.__class__
        new_runtime = runtime_cls(self.workspace_dir, session_id)
        meta = new_runtime.create_session(title=title)
        return f"[OK] session created: {meta.get('session_id')} ({meta.get('title')})"

    def events_text(self, limit=12):
        events = self.runtime.read_events(limit=limit)
        lines = ["", "[events]"]
        if not events:
            lines.append("  No events yet.")
            return "\n".join(lines)
        for event in events:
            lines.append(f"  {event.get('ts', '')}  {event.get('type', '')}  {event.get('summary', '')}")
        return "\n".join(lines)

    def timeline_text(self, limit=16):
        items = self.runtime.read_timeline(limit=limit)
        lines = ["", "[timeline]"]
        if not items:
            lines.append("  No timeline items yet.")
            return "\n".join(lines)
        lines.append("  time                 status    actor             action           observation")
        lines.append("  -------------------  --------  ----------------  ---------------  -----------")
        for item in items:
            observation = (item.get("observation") or "").replace("\n", " ").strip()
            if len(observation) > 88:
                observation = observation[:85].rstrip() + "..."
            lines.append(
                "  {time:<19}  {status:<8}  {actor:<16}  {action:<15}  {observation}".format(
                    time=item.get("ts", "")[:19],
                    status=item.get("status", "")[:8],
                    actor=item.get("actor", "")[:16],
                    action=item.get("action", "")[:15],
                    observation=observation,
                )
            )
        return "\n".join(lines)

    def build_handoff(self):
        plan = self.runtime.read_team_plan() or {}
        state = self.runtime.read_run_state() or {}
        packets = self.runtime.read_task_packets(limit=3)
        timeline = [
            item for item in self.runtime.read_timeline(limit=24)
            if item.get("action") != "handoff.written"
        ][-12:]
        files = self.release_files()
        control = self.runtime.read_control() or {}
        steer = self.runtime.read_steer() or {}

        data = {
            "session_id": self.runtime.session_id,
            "workspace_dir": self.workspace_dir,
            "session_dir": self.runtime.session_dir,
            "artifact_dir": self.runtime.snapshot_dir,
            "goal": plan.get("goal") or state.get("goal", ""),
            "status": state.get("status", "idle"),
            "backend": state.get("backend", plan.get("selected_agent", "")),
            "attempt": state.get("attempt", 0),
            "failure_type": state.get("failure_type", "none"),
            "last_error_summary": state.get("last_error_summary", ""),
            "release_files": files,
            "team_plan": plan if not plan.get("_error") else {},
            "latest_task_packets": packets,
            "recent_timeline": timeline,
            "control": control if not control.get("_error") else {},
            "pending_steer": steer if not steer.get("_error") else {},
        }
        markdown = self.render_handoff(data)
        paths = self.runtime.write_handoff(markdown, data)
        return data, markdown, paths

    def render_handoff(self, data):
        lines = ["# Polyglot Session Handoff", ""]
        lines.append(f"- session: {data.get('session_id', '')}")
        lines.append(f"- workspace: {data.get('workspace_dir', '')}")
        lines.append(f"- session_dir: {data.get('session_dir', '')}")
        lines.append(f"- artifacts: {data.get('artifact_dir', '')}")
        lines.append("")
        lines.append("## Current State")
        lines.append(f"- goal: {data.get('goal', '')}")
        lines.append(f"- status: {data.get('status', '')}")
        lines.append(f"- backend: {data.get('backend', '')}")
        lines.append(f"- attempt: {data.get('attempt', 0)}")
        if data.get("failure_type") and data.get("failure_type") != "none":
            lines.append(f"- failure_type: {data.get('failure_type')}")
        if data.get("last_error_summary"):
            lines.append(f"- last_error: {data.get('last_error_summary')}")
        control = data.get("control") or {}
        if control.get("action") and control.get("action") != "resume":
            lines.append(f"- control: {control.get('action')} {control.get('message', '')}".rstrip())
        steer = data.get("pending_steer") or {}
        if steer.get("message"):
            lines.append(f"- pending_steer: {steer.get('message')}")
        lines.append("")
        lines.append("## Released Files")
        files = data.get("release_files") or []
        if files:
            for name in files:
                lines.append(f"- {name}")
        else:
            lines.append("- none")

        plan = data.get("team_plan") or {}
        if plan:
            lines.append("")
            lines.append("## Plan")
            lines.append(f"- mode: {plan.get('execution_mode', '')}")
            lines.append(f"- selected_agent: {plan.get('selected_agent', '')}")
            routing = plan.get("routing") or {}
            if routing:
                lines.append(f"- permission: {routing.get('permission_profile', '')}")
                lines.append(f"- route_reason: {routing.get('reason', '')}")
            graph = plan.get("issue_graph") or []
            if graph:
                lines.append("- graph: " + " -> ".join(item.get("id", "") for item in graph))

        packets = data.get("latest_task_packets") or []
        if packets:
            lines.append("")
            lines.append("## Recent Task Packets")
            for packet in packets:
                lines.append(
                    "- {phase} attempt {attempt} via {backend}: {target}".format(
                        phase=packet.get("phase", ""),
                        attempt=packet.get("attempt", 0),
                        backend=packet.get("backend", ""),
                        target=packet.get("target_file", ""),
                    )
                )

        timeline = data.get("recent_timeline") or []
        if timeline:
            lines.append("")
            lines.append("## Recent Timeline")
            for item in timeline:
                lines.append(
                    "- {status} {actor}.{action}: {observation}".format(
                        status=item.get("status", ""),
                        actor=item.get("actor", ""),
                        action=item.get("action", ""),
                        observation=(item.get("observation") or "").replace("\n", " "),
                    )
                )

        lines.append("")
        lines.append("## Suggested Next Step")
        status = data.get("status", "")
        if status == "success":
            lines.append("- Review release files and ask the main agent follow-up questions before delegating more work.")
        elif status in ("failed", "stopped"):
            lines.append("- Inspect the last error, then use /steer or /run with a narrower goal to re-plan.")
        elif status == "paused":
            lines.append("- Use /resume to continue or /stop to end the active worker.")
        else:
            lines.append("- Use /status, /timeline, and /packet to decide whether to continue, steer, or re-run.")
        lines.append("")
        return "\n".join(lines)

    def handoff_text(self):
        _data, markdown, paths = self.build_handoff()
        return (
            f"[OK] handoff written\n"
            f"  markdown: {paths.get('markdown')}\n"
            f"  json:     {paths.get('json')}\n\n"
            f"{markdown}"
        )

    def agents_text(self, env=None):
        lines = ["", "[agents]"]
        config = read_agent_config(env)
        lines.append(f"  config: {config.get('path', '')}")
        if config.get("_error"):
            lines.append(f"  config error: {config.get('_error')}")
        elif config.get("default"):
            lines.append(f"  default: {config.get('default')}")
        found = False
        custom = os.environ.get("POLYGLOT_CLAUDE_CMD")
        if custom:
            found = True
            lines.append(f"  configured claude: {custom}")
        for agent in self.discover_agent_paths(env):
            found = True
            lines.append(
                "  {name} CLI: {path} [{adapter}, {permission}, {source}]".format(
                    name=agent.get("name", ""),
                    path=agent.get("path", ""),
                    adapter=agent.get("adapter", ""),
                    permission=agent.get("permission_profile", ""),
                    source=agent.get("source", ""),
                )
            )
        if not found:
            lines.append("  No known agent CLI found on PATH.")
        lines.append("  mock-agent: built-in offline fallback for verification")
        return "\n".join(lines)

    def about_text(self):
        selected = select_agent()
        agents = self.discover_agent_paths()
        config = read_agent_config()
        lines = ["Polyglot AI Team OS"]
        lines.append("  terminal-first, local-agent-first, steerable team runtime")
        lines.append("")
        lines.append("Current Session")
        lines.append(f"  id:        {self.runtime.session_id}")
        lines.append(f"  path:      {self.runtime.session_dir}")
        lines.append(f"  artifacts: {self.runtime.snapshot_dir}")
        lines.append(f"  workspace: {self.workspace_dir}")
        lines.append("")
        lines.append("Interfaces")
        lines.append("  terminal: polyglot_cli.py")
        lines.append("  monitor:  monitor.py")
        lines.append("  steer:    steer.py / /steer")
        lines.append("  feishu:   feishu_bridge.py with FEISHU_WEBHOOK_URL")
        lines.append("  listener: feishu_listener.py --dry-run")
        lines.append("")
        lines.append("Selected Worker")
        lines.append(f"  {selected.name} ({selected.backend_name})")
        lines.append(f"  adapter: {selected.adapter}")
        lines.append(f"  source: {selected.source}")
        lines.append(f"  permission: {selected.to_dict().get('permission_profile', '')}")
        lines.append(f"  agent_config: {config.get('path', '')}")
        lines.append("")
        lines.append("Discovered Workers")
        if not agents:
            lines.append("  none on PATH; mock-agent remains available")
        for agent in agents:
            lines.append(
                "  - {name}: {adapter} | {permission} | {hint}".format(
                    name=agent.get("name", ""),
                    adapter=agent.get("adapter", ""),
                    permission=agent.get("permission_profile", ""),
                    hint=agent.get("routing_hint", ""),
                )
            )
        lines.append("  - mock-agent: mock | no-external-side-effects | fallback for development and CI")
        lines.append("")
        lines.append("State Files")
        lines.append("  team_plan.json, run_state.json, events.jsonl, timeline.jsonl, messages.jsonl, task_packets.jsonl, final_report.md, handoff.md")
        lines.append("")
        lines.append("Common Commands")
        lines.append("  /run <goal>       delegate work")
        lines.append("  /approve          approve a pending high-trust run")
        lines.append("  /deny             deny a pending high-trust run")
        lines.append("  /chat <message>   ask the main agent without delegating")
        lines.append("  /steer <message>  interrupt the active run")
        lines.append("  /pause            pause at the next worker checkpoint")
        lines.append("  /resume           resume a paused worker")
        lines.append("  /stop             stop at the next worker checkpoint")
        lines.append("  /board            inspect task lifecycle")
        lines.append("  /packet           inspect latest worker packet")
        lines.append("  /timeline         replay recent action/observation flow")
        lines.append("  /handoff          write a compact session handoff pack")
        lines.append("  /history          inspect recent main-agent conversation")
        lines.append("  /sessions         list local sessions")
        return "\n".join(lines)

    def send_steer(self, message):
        self.runtime.send_steer(message)
        return f"[OK] steer sent: {message}"

    def cancel_steer(self):
        if self.runtime.cancel_steer():
            return "[OK] pending steer cancelled."
        return "No pending steer instruction."

    def set_control_text(self, action, message=""):
        payload = self.runtime.set_control(action, message)
        suffix = f": {payload.get('message')}" if payload.get("message") else ""
        return f"[OK] control set: {payload.get('action')}{suffix}"

    def compact_status(self):
        state = self.runtime.read_run_state() or {}
        pending = self.runtime.read_steer()
        control = self.runtime.read_control() or {}
        run_lock = self.runtime.read_run_lock()
        status = state.get("status", "idle")
        attempt = state.get("attempt", 0)
        backend = state.get("backend", "auto")
        steer = "pending steer" if pending and not pending.get("_error") else "no steer"
        control_action = control.get("action", "none") if not control.get("_error") else "control-error"
        lock_label = "locked" if run_lock and not run_lock.get("_error") else "unlocked"
        return f"{status} | attempt {attempt} | {backend} | {steer} | control {control_action} | {lock_label}"

    def should_delegate_to_worker(self, message):
        text = message.strip().lower()
        if not text:
            return False
        task_words = ("write", "make", "implement", "create", "generate", "fix", "change", "refactor", "test", "build")
        artifact_words = (".py", "unit test", "code", "function", "script", "project", "api", "cli", "pytest", "unittest", "bug")
        return any(word in text for word in task_words) and any(word in text for word in artifact_words)

    def chat_reply(self, message, channel="terminal"):
        text = message.strip().lower()
        self.runtime.append_message("user", message, channel=channel)
        self.runtime.append_event("main_agent.message", message, {"channel": "main"})
        if text in ("hello", "hi", "hey"):
            reply = "Hello. I am the main agent. Ask normally, or use /run <goal> when you want a local worker to execute."
            self.runtime.append_message("assistant", reply, channel=channel)
            return reply
        if any(word in text for word in ("brief", "where are we", "当前", "现在", "session")):
            reply = self.session_brief_text()
            self.runtime.append_message("assistant", reply, channel=channel)
            return reply
        if any(word in text for word in ("status", "progress", "done", "finished", "last run", "what did you", "刚才", "做了什么", "上次")):
            reply = self.format_run_report()
            self.runtime.append_message("assistant", reply, channel=channel)
            return reply
        if any(word in text for word in ("result", "report", "summary")):
            reply = self.format_run_report()
            self.runtime.append_message("assistant", reply, channel=channel)
            return reply
        if any(word in text for word in ("artifact", "file", "产物", "文件")):
            files = self.release_files()
            reply = "Released files: " + (", ".join(files) if files else "none yet")
            self.runtime.append_message("assistant", reply, channel=channel)
            return reply
        if any(word in text for word in ("agent", "worker", "claude", "codex", "谁在做")):
            reply = self.route_text(message)
            self.runtime.append_message("assistant", reply, channel=channel)
            return reply
        reply = (
            "I will not call a worker for this. Keep chatting here for lightweight questions, "
            "or use /run <goal> to delegate engineering work to the selected local agent."
        )
        self.runtime.append_message("assistant", reply, channel=channel)
        return reply
