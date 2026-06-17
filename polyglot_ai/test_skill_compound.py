"""Tests for skill_compound (Task 4/5), budget control (Task 6), and handoff (Task 7)."""

import json
import os
import tempfile
import unittest

from polyglot_ai.skill_compound import (
    record_skill_usage, read_skill_usage,
    update_skill_index, read_skill_index,
    recommend_by_history,
)


class TestSkillCompound(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.session_dir = os.path.join(self.tmp, "session_1")
        os.makedirs(self.session_dir, exist_ok=True)
        self.artifacts_dir = self.tmp
        self.nested_session = os.path.join(self.tmp, "artifacts", "session_x")
        os.makedirs(self.nested_session, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_record_skill_usage_writes_json(self):
        ok = record_skill_usage(self.session_dir, "date_diff_pitfalls.md", "fill", "success")
        self.assertTrue(ok)
        path = os.path.join(self.session_dir, "skill_usage.json")
        self.assertTrue(os.path.isfile(path))
        with open(path, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["skill"], "date_diff_pitfalls.md")
        self.assertEqual(data[0]["outcome"], "success")

    def test_record_multiple_append(self):
        for i in range(3):
            record_skill_usage(self.session_dir, f"skill_{i}.md", "verify", "success")
        data = read_skill_usage(self.session_dir)
        self.assertEqual(len(data), 3)

    def test_read_skill_usage_empty_dir(self):
        result = read_skill_usage(os.path.join(self.tmp, "does_not_exist"))
        self.assertEqual(result, [])

    def test_update_skill_index_tracks_counts(self):
        record_skill_usage(self.nested_session, "date_diff_pitfalls.md", "fill", "success")
        record_skill_usage(self.nested_session, "traceback_to_fix_prompt.md", "verify", "failure")
        artifacts_parent = os.path.dirname(os.path.abspath(self.nested_session))
        index = update_skill_index(artifacts_parent, self.nested_session)
        self.assertIn("date_diff_pitfalls.md", index)
        self.assertIn("traceback_to_fix_prompt.md", index)
        self.assertEqual(index["date_diff_pitfalls.md"]["total_uses"], 1)
        self.assertEqual(index["date_diff_pitfalls.md"]["success_count"], 1)
        self.assertEqual(index["traceback_to_fix_prompt.md"]["failure_count"], 1)
        self.assertIsNotNone(index["date_diff_pitfalls.md"]["success_rate"])
        self.assertEqual(index["date_diff_pitfalls.md"]["success_rate"], 1.0)

    def test_update_skill_index_aggregates_across_sessions(self):
        artifacts_parent = os.path.dirname(os.path.abspath(self.nested_session))
        record_skill_usage(self.nested_session, "date_diff_pitfalls.md", "fill", "success")
        update_skill_index(artifacts_parent, self.nested_session)

        session2 = os.path.join(artifacts_parent, "session_2")
        os.makedirs(session2, exist_ok=True)
        record_skill_usage(session2, "date_diff_pitfalls.md", "fill", "failure")
        update_skill_index(artifacts_parent, session2)

        idx = read_skill_index(artifacts_parent)
        self.assertEqual(idx["date_diff_pitfalls.md"]["total_uses"], 2)
        self.assertEqual(idx["date_diff_pitfalls.md"]["success_count"], 1)
        self.assertEqual(idx["date_diff_pitfalls.md"]["failure_count"], 1)
        self.assertEqual(idx["date_diff_pitfalls.md"]["success_rate"], 0.5)

    def test_recommend_by_history_prefers_high_success_rate(self):
        idx = {
            "date_diff_pitfalls.md": {"total_uses": 10, "success_rate": 0.9},
            "traceback_to_fix_prompt.md": {"total_uses": 10, "success_rate": 0.5},
            "cli_no_edit_recovery.md": {"total_uses": 5, "success_rate": None},
        }
        recs = recommend_by_history(idx, top_n=3)
        self.assertEqual(recs[0], "date_diff_pitfalls.md")
        self.assertEqual(recs[1], "traceback_to_fix_prompt.md")

    def test_recommend_by_history_empty(self):
        self.assertEqual(recommend_by_history({}), [])
        self.assertEqual(recommend_by_history(None), [])


class TestBudgetRuntime(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_record_budget_downgrade(self):
        from polyglot_ai.runtime import Runtime
        rt = Runtime(self.tmp, "default")
        rt.ensure()
        state = rt.record_budget_downgrade("attempt 4 exceeds budget of 3")
        self.assertTrue(state.get("budget_exceeded"))
        self.assertIn("budget_downgrade_events", state)
        self.assertEqual(len(state.get("budget_downgrade_events", [])), 1)
        self.assertIn("exceeds budget", state.get("budget_downgrade_events", [])[0])

    def test_record_multiple_downgrades_append(self):
        from polyglot_ai.runtime import Runtime
        rt = Runtime(self.tmp, "default")
        rt.ensure()
        rt.record_budget_downgrade("first")
        rt.record_budget_downgrade("second")
        rt.record_budget_downgrade("third")
        state = rt.read_run_state() or {}
        self.assertEqual(len(state.get("budget_downgrade_events", [])), 3)

    def test_read_budget_state_defaults(self):
        from polyglot_ai.runtime import Runtime
        rt = Runtime(self.tmp, "default")
        rt.ensure()
        bs = rt.read_budget_state()
        self.assertIn("attempts_used", bs)
        self.assertIn("max_total_attempts", bs)
        self.assertIn("budget_exceeded", bs)
        self.assertIn("downgrade_events", bs)
        self.assertIn("model_tier", bs)

    def test_read_budget_state_from_team_plan(self):
        from polyglot_ai.runtime import Runtime
        rt = Runtime(self.tmp, "default")
        rt.ensure()
        rt.save_team_plan({"goal": "x", "budget": {"max_total_attempts": 5, "preferred_cost_tier": "pro"}})
        bs = rt.read_budget_state()
        self.assertEqual(bs["max_total_attempts"], 5)
        self.assertEqual(bs["model_tier"], "pro")


class TestHandoff(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_handoff_pack_basic(self):
        from polyglot_ai.runtime import Runtime
        from polyglot_ai.handoff import build_handoff_pack, build_handoff_markdown
        rt = Runtime(self.tmp, "default")
        rt.ensure()
        rt.save_team_plan({
            "goal": "build a simple utility",
            "complexity_level": "simple",
            "task_graph": [
                {"id": "fill_main", "phase": "fill", "description": "implement code",
                 "depends_on": [], "status": "pending", "max_attempts": 3, "model_preference": "cheap"},
                {"id": "verify_main", "phase": "verify", "description": "run tests",
                 "depends_on": ["fill_main"], "status": "pending", "max_attempts": 3, "model_preference": "cheap"},
            ],
            "budget": {"max_total_attempts": 3, "preferred_cost_tier": "cheap"},
            "next_action": "implement code",
        })
        rt.save_run_state({"status": "running", "attempt": 1, "goal": "build a simple utility",
                            "backend": "test_backend"})

        pack = build_handoff_pack(rt, "default")
        self.assertIn("session_state", pack)
        self.assertIn("completed_tasks", pack)
        self.assertIn("remaining_tasks", pack)
        self.assertIn("key_context_refs", pack)
        self.assertIn("next_action", pack)
        self.assertIn("budget_remaining", pack)
        self.assertIn("metadata", pack)
        self.assertEqual(pack["session_state"]["status"], "running")
        self.assertEqual(len(pack["remaining_tasks"]), 2)
        self.assertEqual(len(pack["completed_tasks"]), 0)

        md = build_handoff_markdown(pack)
        self.assertIn("Session Handoff", md)
        self.assertIn("Next Action", md)
        self.assertIn("simple utility", md)

    def test_build_handoff_pack_mixed_status(self):
        from polyglot_ai.runtime import Runtime
        from polyglot_ai.handoff import build_handoff_pack
        rt = Runtime(self.tmp, "default")
        rt.ensure()
        rt.save_team_plan({
            "goal": "test",
            "task_graph": [
                {"id": "a", "phase": "plan", "description": "A", "depends_on": [],
                 "status": "done", "max_attempts": 1, "model_preference": "cheap"},
                {"id": "b", "phase": "fill", "description": "B", "depends_on": ["a"],
                 "status": "pending", "max_attempts": 3, "model_preference": "cheap"},
            ],
            "budget": {"max_total_attempts": 3, "preferred_cost_tier": "cheap"},
            "next_action": "do B",
        })
        pack = build_handoff_pack(rt, "default")
        self.assertEqual(len(pack["completed_tasks"]), 1)
        self.assertEqual(len(pack["remaining_tasks"]), 1)
        self.assertEqual(pack["completed_tasks"][0]["id"], "a")

    def test_handoff_markdown_has_budget_warning_when_exceeded(self):
        from polyglot_ai.runtime import Runtime
        from polyglot_ai.handoff import build_handoff_pack, build_handoff_markdown
        rt = Runtime(self.tmp, "default")
        rt.ensure()
        rt.save_team_plan({
            "goal": "test",
            "task_graph": [],
            "budget": {"max_total_attempts": 3, "preferred_cost_tier": "cheap"},
        })
        rt.save_run_state({"status": "failed", "attempt": 5, "goal": "test",
                            "budget_exceeded": True,
                            "budget_downgrade_events": ["exceeded"]})
        pack = build_handoff_pack(rt, "default")
        md = build_handoff_markdown(pack)
        self.assertIn("Budget Exceeded", md)


if __name__ == "__main__":
    unittest.main()
