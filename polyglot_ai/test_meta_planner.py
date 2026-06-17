import os
import json
import tempfile
import unittest

from polyglot_ai.runtime import Runtime, normalize_team_plan


class TestTeamPlanNormalization(unittest.TestCase):
    """Test normalize_team_plan handles all input formats."""

    def test_none_plan_returns_default(self):
        result = normalize_team_plan(None)
        self.assertIsInstance(result, dict)
        self.assertIn("complexity_level", result)
        self.assertIn("task_graph", result)
        self.assertIn("roles_needed", result)
        self.assertIn("budget", result)
        self.assertIn("approval_points", result)
        self.assertIn("recommended_skills", result)

    def test_empty_dict_plan(self):
        result = normalize_team_plan({})
        self.assertEqual(result["complexity_level"], "simple")
        self.assertIsInstance(result["task_graph"], list)

    def test_minimal_test_format_preserves_fields(self):
        """Tests create team plans like {task_name, next_action, selected_agent, complexity_level}."""
        plan = {"task_name": "demo", "next_action": "apply focused fix",
                "selected_agent": "Claude Code", "complexity_level": "small"}
        result = normalize_team_plan(plan)
        # Preserved
        self.assertEqual(result["task_name"], "demo")
        self.assertEqual(result["next_action"], "apply focused fix")
        self.assertEqual(result["selected_agent"], "Claude Code")
        # Added
        self.assertIn("task_graph", result)
        self.assertIn("roles_needed", result)
        self.assertIn("budget", result)
        # complexity mapping: small -> simple
        self.assertEqual(result["complexity_level"], "simple")

    def test_v0_planner_format_gets_task_graph(self):
        """v0_planner format: {goal, tasks:[{filename,path,description,content}]}"""
        plan = {
            "goal": "build a date converter",
            "tasks": [
                {"filename": "date_converter.py", "path": "date_converter.py",
                 "description": "date conversion", "content": "..."},
                {"filename": "test_date_converter.py", "path": "test_date_converter.py",
                 "description": "tests", "content": "..."},
            ],
        }
        result = normalize_team_plan(plan)
        self.assertIsInstance(result["task_graph"], list)
        self.assertGreater(len(result["task_graph"]), 0)
        phases = [t["phase"] for t in result["task_graph"]]
        self.assertIn("fill", phases)
        self.assertIn("verify", phases)

    def test_main_agent_format_preserves_fields(self):
        """main_agent creates rich plans with issue_graph, budget, etc."""
        plan = {
            "goal": "build a multi-module code generator",
            "task_name": "code generator",
            "complexity_level": "medium",
            "execution_mode": "single-agent-with-self-heal",
            "roles_needed": ["meta_planner", "runtime_orchestrator", "coder", "test_runner", "reviewer"],
            "selected_agent": "Claude Code",
            "budget": {"max_worker_calls": 4, "max_self_heal_attempts": 3,
                       "coordination_style": "structured-state-not-chat"},
            "issue_graph": [
                {"id": "plan", "title": "Plan the work", "depends_on": []},
                {"id": "code", "title": "Write code", "depends_on": ["plan"]},
                {"id": "verify", "title": "Run tests", "depends_on": ["code"]},
            ],
            "approval_points": ["before_destructive_changes"],
            "next_action": "run local planner",
            "created_at": "2025-01-01T00:00:00",
        }
        result = normalize_team_plan(plan)
        # All original fields preserved
        self.assertEqual(result["goal"], "build a multi-module code generator")
        self.assertEqual(result["complexity_level"], "medium")
        self.assertEqual(result["execution_mode"], "single-agent-with-self-heal")
        self.assertEqual(len(result["roles_needed"]), 5)
        self.assertEqual(result["next_action"], "run local planner")
        self.assertEqual(result["created_at"], "2025-01-01T00:00:00")
        # issue_graph-derived task_graph
        self.assertGreater(len(result["task_graph"]), 0)
        ids = [t["id"] for t in result["task_graph"]]
        self.assertIn("plan", ids)

    def test_goal_only_generates_simple_graph(self):
        plan = {"goal": "write a quick utility"}
        result = normalize_team_plan(plan)
        self.assertEqual(result["complexity_level"], "simple")
        self.assertIsInstance(result["task_graph"], list)
        self.assertGreater(len(result["task_graph"]), 0)

    def test_task_node_schema(self):
        """Every task node must have required fields."""
        plan = {
            "goal": "build something",
            "tasks": [{"filename": "app.py", "path": "app.py", "description": "main file", "content": ""}],
        }
        result = normalize_team_plan(plan)
        for node in result["task_graph"]:
            self.assertIn("id", node)
            self.assertIn("phase", node)
            self.assertIn("description", node)
            self.assertIn("depends_on", node)
            self.assertIn("status", node)
            self.assertIn("max_attempts", node)
            self.assertIn("model_preference", node)
            self.assertIsInstance(node["depends_on"], list)

    def test_budget_structure(self):
        # default budget
        result = normalize_team_plan({"goal": "x"})
        self.assertIn("max_total_attempts", result["budget"])
        self.assertIn("preferred_cost_tier", result["budget"])
        # existing budget not overwritten
        plan = {"goal": "x", "budget": {"max_total_attempts": 7,
                 "preferred_cost_tier": "pro", "fallback_cost_tier": "cheap"}}
        result = normalize_team_plan(plan)
        self.assertEqual(result["budget"]["max_total_attempts"], 7)
        self.assertEqual(result["budget"]["preferred_cost_tier"], "pro")

    def test_estimated_complexity_score_present(self):
        result = normalize_team_plan({"goal": "x"})
        self.assertIn("estimated_complexity_score", result)
        self.assertIsInstance(result["estimated_complexity_score"], int)
        self.assertGreaterEqual(result["estimated_complexity_score"], 0)
        self.assertLessEqual(result["estimated_complexity_score"], 100)

    def test_runtime_save_read_roundtrip(self):
        """save_team_plan -> read_team_plan preserves normalized structure."""
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Runtime(tmp, "default")
            runtime.ensure()
            plan = {"goal": "build demo", "task_name": "demo",
                    "complexity_level": "small", "next_action": "run worker"}
            runtime.save_team_plan(plan)
            read_back = runtime.read_team_plan()
            self.assertIsNotNone(read_back)
            self.assertEqual(read_back["goal"], "build demo")
            self.assertIn("task_graph", read_back)
            self.assertIn("roles_needed", read_back)
            self.assertIn("budget", read_back)

    def test_complexity_level_scoring(self):
        for level, expected in [("simple", 20), ("medium", 55), ("complex", 85)]:
            plan = normalize_team_plan({"goal": "x", "complexity_level": level})
            self.assertEqual(plan["estimated_complexity_score"], expected)

    def test_tasks_length_infers_complexity(self):
        # 6 tasks should imply complex
        plan = normalize_team_plan({
            "goal": "build many files",
            "tasks": [{"filename": f"file{i}.py", "path": f"file{i}.py",
                       "description": f"file {i}", "content": ""} for i in range(6)],
        })
        self.assertEqual(plan["complexity_level"], "complex")
        self.assertGreaterEqual(plan["estimated_complexity_score"], 80)


from polyglot_ai.meta_planner import (
    assess_complexity,
    generate_task_graph,
    recommend_skills,
    build_team_plan,
    score_complexity_text,
    complexity_level_from_score,
)


class TestComplexityAssessment(unittest.TestCase):

    def test_simple_goal_scores_low(self):
        result = assess_complexity("write a quick date diff utility")
        self.assertEqual(result["level"], "simple")
        self.assertLess(result["score"], 60)

    def test_complex_goal_scores_high(self):
        result = assess_complexity(
            "build a multi-module async API framework with JWT authentication, "
            "dashboard, ORM integration, and plugin extension system"
        )
        self.assertEqual(result["level"], "complex")
        self.assertGreaterEqual(result["score"], 60)

    def test_hint_override_forces_level(self):
        result = assess_complexity("write a hello script", complexity_hint="complex")
        self.assertEqual(result["level"], "complex")
        self.assertGreaterEqual(result["score"], 60)

    def test_task_count_hint_boosts_score(self):
        r1 = assess_complexity("build tool", task_count_hint=0)
        r2 = assess_complexity("build tool", task_count_hint=6)
        self.assertGreater(r2["score"], r1["score"])

    def test_reasons_list_non_empty(self):
        result = assess_complexity("build a JWT auth API with tests")
        self.assertTrue(len(result["reasons"]) > 0)

    def test_testing_keywords_detected(self):
        result = assess_complexity("write tool with unit tests and pytest integration")
        self.assertGreater(result["testing_score"], 0)

    def test_score_always_0_to_100(self):
        for goal in ["", "hello", "write " * 50, "async framework " * 10]:
            r = assess_complexity(goal)
            self.assertGreaterEqual(r["score"], 0)
            self.assertLessEqual(r["score"], 100)


class TestTaskGraphGeneration(unittest.TestCase):

    def test_simple_graph_has_2_nodes(self):
        nodes = generate_task_graph("write a utility", "simple")
        self.assertEqual(len(nodes), 2)
        phases = [n["phase"] for n in nodes]
        self.assertIn("fill", phases)
        self.assertIn("verify", phases)

    def test_medium_graph_has_more_than_simple(self):
        nodes = generate_task_graph("build an API backend", "medium",
                                    file_hints=["server.py", "auth.py", "test.py"])
        self.assertGreaterEqual(len(nodes), 3)
        phases = set(n["phase"] for n in nodes)
        self.assertIn("plan", phases)
        self.assertIn("verify", phases)
        self.assertIn("report", phases)

    def test_complex_graph_has_pro_model_preference(self):
        nodes = generate_task_graph("build a complex framework", "complex",
                                    file_hints=["core.py", "io.py", "utils.py", "test.py"])
        self.assertGreaterEqual(len(nodes), 5)
        model_prefs = [n.get("model_preference", "") for n in nodes]
        self.assertIn("pro", model_prefs)

    def test_each_node_has_required_fields(self):
        for level in ["simple", "medium", "complex"]:
            nodes = generate_task_graph("x", level)
            for n in nodes:
                self.assertIn("id", n)
                self.assertIn("phase", n)
                self.assertIn("description", n)
                self.assertIn("depends_on", n)
                self.assertIn("status", n)
                self.assertIn("max_attempts", n)
                self.assertIn("model_preference", n)
                self.assertIsInstance(n["depends_on"], list)

    def test_dependency_dag_no_cycles(self):
        nodes = generate_task_graph("x", "complex", file_hints=["a.py", "b.py", "c.py"])
        ids = {n["id"] for n in nodes}
        for n in nodes:
            for dep in n["depends_on"]:
                self.assertIn(dep, ids, f"{n['id']} depends on unknown {dep}")

    def test_file_hints_reflected_in_graph(self):
        nodes = generate_task_graph("x", "medium", file_hints=["server.py", "client.py"])
        descriptions = " ".join(n.get("description", "") for n in nodes)
        self.assertIn("server.py", descriptions)
        self.assertIn("client.py", descriptions)


class TestSkillRecommendation(unittest.TestCase):

    def test_date_goal_recommends_date_skill(self):
        result = recommend_skills("build a date diff utility that computes days between dates")
        self.assertTrue(any("date" in s for s in result))

    def test_traceback_goal_recommends_traceback_skill(self):
        result = recommend_skills("fix traceback error assertion bug exception")
        self.assertTrue(any("traceback" in s for s in result))

    def test_no_matching_skills_returns_empty(self):
        result = recommend_skills("build a quantum computer")
        self.assertEqual(result, [])

    def test_skill_index_with_history_boosts_order(self):
        index = {
            "date_diff_pitfalls.md": {"total_uses": 10, "success_rate": 0.9},
            "traceback_to_fix_prompt.md": {"total_uses": 0, "success_rate": None},
        }
        result = recommend_skills(
            "fix date diff utility that throws traceback error exception",
            skill_index=index,
        )
        # date should come before traceback due to history
        date_idx = next(i for i, s in enumerate(result) if "date" in s)
        tb_idx = next(i for i, s in enumerate(result) if "traceback" in s)
        self.assertLess(date_idx, tb_idx)

    def test_skill_index_none_works_like_keyword_only(self):
        goal = "write a date utility with bug fixes"
        r1 = recommend_skills(goal)
        r2 = recommend_skills(goal, skill_index=None)
        self.assertEqual(r1, r2)


class TestBuildTeamPlanIntegration(unittest.TestCase):

    def test_full_plan_structure(self):
        plan = build_team_plan("write a date diff utility with tests")
        self.assertIsInstance(plan, dict)
        required = ["goal", "task_name", "complexity_level",
                    "estimated_complexity_score", "roles_needed",
                    "task_graph", "budget", "recommended_skills",
                    "next_action", "team_plan_version"]
        for field in required:
            self.assertIn(field, plan, f"missing field: {field}")

    def test_simple_plan_has_small_task_graph(self):
        plan = build_team_plan("write a quick utility")
        self.assertLessEqual(len(plan["task_graph"]), 5)

    def test_complex_plan_has_approval_points(self):
        plan = build_team_plan(
            "build a distributed async API framework with dashboard, "
            "JWT auth, ORM, and plugin system"
        )
        self.assertIsInstance(plan["approval_points"], list)

    def test_budget_reflects_complexity(self):
        simple_plan = build_team_plan("write a quick utility")
        complex_plan = build_team_plan(
            "build a distributed async framework with JWT auth dashboard plugin"
        )
        self.assertEqual(simple_plan["budget"]["preferred_cost_tier"], "cheap")
        self.assertEqual(complex_plan["budget"]["preferred_cost_tier"], "pro")


if __name__ == "__main__":
    unittest.main()
