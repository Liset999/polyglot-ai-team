import os
import sys
import json
import subprocess
import shutil
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from polyglot_ai.agents import select_agent
from polyglot_ai.runtime import Runtime
from polyglot_ai.task_packet import build_task_packet
from polyglot_ai.worker_adapters import create_worker_adapter

# 1. 核心路径定义
WORKSPACE_DIR = os.path.abspath(os.environ.get("POLYGLOT_WORKSPACE") or os.path.dirname(os.path.dirname(__file__)))
INSTALL_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
RUNTIME = Runtime(WORKSPACE_DIR, os.environ.get("POLYGLOT_SESSION", "default"))
# 三层目录结构：inputs（规划层）/ draft（草稿层）/ release（交付层）
INPUTS_DIR = os.path.abspath(RUNTIME.working_artifact_dir("inputs"))
DRAFT_DIR = os.path.abspath(RUNTIME.working_artifact_dir("draft"))
RELEASE_DIR = os.path.abspath(RUNTIME.working_artifact_dir("release"))
PLAN_JSON_PATH = os.path.abspath(os.path.join(INPUTS_DIR, "plan.json"))
TEST_LOG_PATH = os.path.abspath(RUNTIME.working_artifact_path("test_run.log"))
CLAUDE_LOG_PATH = os.path.abspath(RUNTIME.working_artifact_path("claude_run.log"))
RUN_STATE_PATH = os.path.abspath(RUNTIME.working_artifact_path("run_state.json"))
SKILLS_DIR = os.path.abspath(os.path.join(WORKSPACE_DIR, "skills"))
STEER_PATH = os.path.abspath(os.path.join(WORKSPACE_DIR, "artifacts", "steer.json"))

def _configure_stdio():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


_configure_stdio()

AGENT_BACKEND = select_agent()
WORKER_ADAPTER = create_worker_adapter(AGENT_BACKEND, WORKSPACE_DIR, DRAFT_DIR, CLAUDE_LOG_PATH, RUNTIME)

# Skill compounding helpers — additive, cross-session skill index updates.
def _finalize_skill_outcome(success):
    """Update cross-session skill index with run outcome."""
    try:
        from polyglot_ai.skill_compound import update_skill_index
        session_dir = RUNTIME.session_dir
        parent_artifacts = os.path.dirname(os.path.abspath(session_dir))
        update_skill_index(parent_artifacts, session_dir)
    except Exception:
        pass


def _check_and_apply_budget(attempt):
    """If attempt exceeds budget, record a downgrade event. Returns True if exceeded."""
    try:
        plan = RUNTIME.read_team_plan() or {}
        if isinstance(plan, dict):
            budget = plan.get("budget") or {}
            if isinstance(budget, dict):
                max_attempts = int(budget.get("max_total_attempts") or 3)
            else:
                max_attempts = 3
        else:
            max_attempts = 3
        if attempt > max_attempts:
            reason = f"attempt {attempt} exceeds budget max_total_attempts={max_attempts}"
            state = RUNTIME.read_run_state() or {}
            if isinstance(state, dict):
                events = list(state.get("budget_downgrade_events") or [])
                events.append(reason)
                state["budget_downgrade_events"] = events
                state["budget_exceeded"] = True
                RUNTIME.save_run_state(state)
            return True
    except Exception:
        pass
    return False

def update_run_state(goal, target_file, test_file, status, attempt=0, last_error_summary="", last_exit_code=0, failure_type="none"):
    state = {
        "goal": goal,
        "target_file": target_file,
        "test_file": test_file,
        "status": status,
        "attempt": attempt,
        "last_error_summary": last_error_summary,
        "backend": AGENT_BACKEND.backend_name,
        "last_exit_code": last_exit_code,
        "failure_type": failure_type
    }
    try:
        os.makedirs(os.path.dirname(RUN_STATE_PATH), exist_ok=True)
        with open(RUN_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        RUNTIME.save_run_state(state)
        RUNTIME.append_event(
            f"worker.status.{status}",
            f"Worker status: {status}",
            {
                "target_file": target_file,
                "test_file": test_file,
                "attempt": attempt,
                "last_exit_code": last_exit_code,
                "failure_type": failure_type,
                "last_error_summary": last_error_summary,
                "backend": AGENT_BACKEND.backend_name,
            },
        )
    except Exception as e:
        print(f"[WARNING] 无法更新运行状态文件: {e}", file=sys.stderr)

def read_plan():
    if not os.path.exists(PLAN_JSON_PATH):
        print(f"[ERROR] 找不到规划文件: {PLAN_JSON_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(PLAN_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def run_v0_worker():
    print("[v1-Worker] [INFO] 正在启动 v0_worker 执行测试...")
    cmd = [sys.executable, os.path.join(INSTALL_DIR, "polyglot_ai", "v0_worker.py")]
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=WORKSPACE_DIR,
            text=True,
            errors="replace",
            bufsize=1
        )
        output = []
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            output.append(line)
        process.wait()
        return process.returncode
    except Exception as e:
        print(f"[ERROR] 执行 v0_worker 失败: {e}", file=sys.stderr)
        return -1

def _copy_to_release(impl_tasks):
    print("[v1-Worker] [INFO] 正在将代码同步至 release 目录...")
    os.makedirs(RELEASE_DIR, exist_ok=True)
    for task in impl_tasks:
        path = task.get("path")
        src = os.path.join(DRAFT_DIR, path)
        dst = os.path.join(RELEASE_DIR, path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(src):
            shutil.copy2(src, dst)

def call_claude_cli(prompt):
    return WORKER_ADAPTER.write(prompt)

def query_claude_cli(prompt):
    return WORKER_ADAPTER.query(prompt)

def cli_failure_type(exit_code, default="generation_failed"):
    if exit_code == 130:
        return "user_stopped"
    if exit_code == -4:
        return "worker_timeout"
    if exit_code == -3:
        return "profile_not_runnable"
    if exit_code == -2:
        return "subprocess_start_failed"
    return default

def process_exit_code(exit_code):
    if exit_code == 0:
        return 0
    if exit_code == 130:
        return 130
    return 1

def record_task_packet(goal, phase, path, test_file, prompt, desc="", attempt=0, error_summary="", steer_message=""):
    packet = build_task_packet(
        goal=goal,
        phase=phase,
        target_file=path,
        test_file=test_file,
        backend=AGENT_BACKEND.backend_name,
        permission_profile=AGENT_BACKEND.to_dict().get("permission_profile", ""),
        prompt=prompt,
        description=desc or "",
        attempt=attempt,
        error_summary=error_summary or "",
        steer_message=steer_message or "",
    )
    RUNTIME.append_task_packet(packet)
    return packet

def is_stub_code(code):
    clean = code.strip()
    if not clean:
        return True
    if "raise NotImplementedError" in clean or "NotImplementedError()" in clean:
        return True
    # 如果代码行数很少，且包含 pass
    lines = [line.strip() for line in clean.splitlines() if line.strip() and not line.strip().startswith("#")]
    if len(lines) < 15 and any("pass" in line for line in lines):
        return True
    return False

def load_relevant_skills(context_text):
    """
    扫描 skills/ 目录，找到与 context_text（目标描述或报错信息）相关的技能文件并加载。
    使用简单的关键词匹配：技能文件名中的关键词若出现在 context_text 中，则认为相关。
    返回格式化好的技能上下文字符串，可直接注入到 Prompt 中。
    """
    if not os.path.exists(SKILLS_DIR):
        return ""

    # 关键词映射表：文件名关键词 -> context_text 中用于匹配的词
    keyword_map = {
        "date": ["date", "datetime", "day", "month", "year", "iso", "diff", "calendar"],
        "cli": ["cli", "claude", "no edit", "silent", "exit code", "tool call"],
        "traceback": ["traceback", "assertionerror", "assert", "fail", "error", "fix", "bug"],
    }

    context_lower = context_text.lower()
    relevant_skills = []

    for filename in sorted(os.listdir(SKILLS_DIR)):
        if not filename.endswith(".md"):
            continue
        filepath = os.path.join(SKILLS_DIR, filename)
        # 检查文件名中的关键词是否和上下文匹配
        name_base = filename.replace(".md", "").lower()
        matched = False
        for key, triggers in keyword_map.items():
            if key in name_base:
                if any(t in context_lower for t in triggers):
                    matched = True
                    break
        # 如果匹配，也直接检查 context 里有没有文件名本身的字眼
        if not matched and name_base.split("_")[0] in context_lower:
            matched = True

        if matched:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                relevant_skills.append(f"### [{filename}]\n{content}")
                print(f"[v1-Worker] [SKILL] 已加载技能文件: {filename}")
            except Exception as e:
                print(f"[WARNING] 无法读取技能文件 {filename}: {e}", file=sys.stderr)

    # Skill compounding: record which skills were used (additive only)
    try:
        import re
        names = re.findall(r'### \[([^\]]+\.md)\]', " ".join(relevant_skills))
        for name in set(names):
            from polyglot_ai.skill_compound import record_skill_usage
            record_skill_usage(RUNTIME.session_dir, name, "context", "unknown")
    except Exception:
        pass

    if not relevant_skills:
        return ""

    header = "\n=== MANDATORY SKILL FILES (Read before proceeding) ===\n"
    footer = "\n=== END OF SKILL FILES ===\n"
    return header + "\n\n".join(relevant_skills) + footer

def check_for_steer():
    """
    检查是否有人工打断信号（artifacts/steer.json）。
    如果存在，读取并删除文件，返回消息内容。
    如果不存在，返回空字符串。
    """
    data = RUNTIME.read_steer()
    if not data or data.get("_error"):
        return ""
    try:
        for path in (RUNTIME.steer_path, STEER_PATH):
            if os.path.exists(path):
                os.remove(path)
        message = data.get("message", "").strip()
        if message:
            print(f"[v1-Worker] [STEER] 检测到人工打断指令：{message}")
            print(f"[v1-Worker] [STEER] 已将人工指令合并进本次修复上下文")
            RUNTIME.append_event("worker.steer_consumed", message, {"message": message})
        return message
    except Exception as e:
        print(f"[WARNING] 读取 steer.json 失败: {e}", file=sys.stderr)
        return ""


def honor_control_signal(goal, target_file="", test_file="", current_status="running", attempt=0):
    control = RUNTIME.read_control()
    if not control or control.get("_error"):
        return

    action = (control.get("action") or "").strip().lower()
    message = control.get("message", "")
    if action == "stop":
        print(f"[v1-Worker] [CONTROL] stop requested. {message}".rstrip())
        update_run_state(
            goal,
            target_file,
            test_file,
            "stopped",
            attempt=attempt,
            last_error_summary=message or "Stopped by user control signal.",
            failure_type="user_stopped",
        )
        RUNTIME.append_event("worker.control.stopped", message or "Stopped by user")
        sys.exit(130)

    if action != "pause":
        return

    print(f"[v1-Worker] [CONTROL] pause requested. {message}".rstrip())
    update_run_state(
        goal,
        target_file,
        test_file,
        "paused",
        attempt=attempt,
        last_error_summary=message or "Paused by user control signal.",
        failure_type="user_paused",
    )
    RUNTIME.append_event("worker.control.paused", message or "Paused by user")

    while True:
        time.sleep(2)
        control = RUNTIME.read_control() or {}
        action = (control.get("action") or "").strip().lower()
        message = control.get("message", "")
        if action == "stop":
            print(f"[v1-Worker] [CONTROL] stop requested while paused. {message}".rstrip())
            update_run_state(
                goal,
                target_file,
                test_file,
                "stopped",
                attempt=attempt,
                last_error_summary=message or "Stopped by user control signal.",
                failure_type="user_stopped",
            )
            RUNTIME.append_event("worker.control.stopped", message or "Stopped by user")
            sys.exit(130)
        if action == "resume":
            print(f"[v1-Worker] [CONTROL] resume requested. {message}".rstrip())
            update_run_state(goal, target_file, test_file, current_status, attempt=attempt)
            RUNTIME.append_event("worker.control.resumed", message or "Resumed by user")
            return

def main():
    plan_data = read_plan()
    goal = plan_data.get("goal", "")
    tasks = plan_data.get("tasks", [])
    
    # 清理旧的 claude_run.log
    if os.path.exists(CLAUDE_LOG_PATH):
        try:
            os.remove(CLAUDE_LOG_PATH)
        except Exception:
            pass
            
    # 提取测试文件内容作为上下文
    test_files_context = {}
    impl_tasks = []
    
    for task in tasks:
        filename = task.get("filename", "")
        path = task.get("path", "")
        
        abs_path = os.path.abspath(os.path.join(DRAFT_DIR, path))
        
        if not abs_path.startswith(DRAFT_DIR):
            continue
            
        if filename.startswith("test_") and filename.endswith(".py"):
            # 读取测试用例内容
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    test_files_context[path] = f.read()
        elif filename.endswith(".py"):
            # 需要填充的实现任务
            impl_tasks.append(task)
            
    target_file = ""
    test_file = ""
    for task in tasks:
        filename = task.get("filename", "")
        path = task.get("path", "")
        if filename.startswith("test_") and filename.endswith(".py") and not test_file:
            test_file = path
        elif filename.endswith(".py") and not target_file:
            target_file = path

    honor_control_signal(goal, target_file, test_file, current_status="starting")

    if not impl_tasks:
        print("[v1-Worker] [INFO] 未找到需要填充的 Python 实现文件，直接运行测试。")
        record_task_packet(
            goal,
            "verify",
            target_file,
            test_file,
            "No implementation stub was found. Run verification against the current draft artifacts.",
            desc="Verification-only task packet for an already-populated draft.",
        )
        update_run_state(goal, target_file, test_file, "testing")
        honor_control_signal(goal, target_file, test_file, current_status="testing")
        exit_code = run_v0_worker()
        if exit_code == 0:
            update_run_state(goal, target_file, test_file, "success", last_exit_code=0)
        else:
            update_run_state(goal, target_file, test_file, "failed", last_exit_code=exit_code, failure_type="test_execution_failed")
        sys.exit(exit_code)
        
    # 第一步：首次填充所有实现桩文件
    for task in impl_tasks:
        path = task.get("path")
        desc = task.get("description")
        
        abs_path = os.path.abspath(os.path.join(DRAFT_DIR, path))
        
        # 读取当前 Stub
        stub_code = ""
        if os.path.exists(abs_path):
            with open(abs_path, "r", encoding="utf-8") as f:
                stub_code = f.read()
                
        # 如果不是 Stub，说明可能已经由别处编写，或者有待自愈修复的 bug，跳过初始生成
        if os.path.exists(abs_path) and not is_stub_code(stub_code):
            print(f"[v1-Worker] [INFO] 检测到 {path} 已经包含实现代码（非空桩），跳过初始生成，直接进入测试和自愈阶段。")
            record_task_packet(
                goal,
                "verify",
                path,
                test_file,
                f"Existing implementation detected in '{path}'. Skip initial fill and verify it against '{test_file}'.",
                desc=desc or "Existing implementation; verify before self-heal.",
            )
            continue
            
        update_run_state(goal, path, test_file, "filling")
        honor_control_signal(goal, path, test_file, current_status="filling")
        # 加载与当前任务相关的技能文件，注入到翻译指令的上下文中
        skills_context = load_relevant_skills(f"{goal} {desc}")
        # 使用两步翻译指令法：先翻译为一行动作指令，以防模型卡死或请求审批
        query_prompt = (
            f"You are an assistant translating a programming task into a single direct sentence instruction for another developer to write the implementation of a file.\n"
            f"Write a single-sentence direct instruction to implement the file '{path}' based on the project goal and description.\n"
            f"Your instruction MUST start with 'Please write the implementation of {path} containing...' or 'Please implement the functions in {path}...' and describe the functions/classes to implement.\n"
            f"Do not include any chat formatting, notes, markdown blocks, or explanation. Output ONLY the single sentence.\n"
            f"{skills_context}\n"
            f"Project Goal: {goal}\n"
            f"File Description: {desc}"
        )
        print(f"[v1-Worker] [INFO] Generating direct fill instruction for {path}...")
        direct_instruction = query_claude_cli(query_prompt)
        honor_control_signal(goal, path, test_file, current_status="filling")
        
        clean_lines = []
        for line in direct_instruction.splitlines():
            if "Warning: no stdin data" in line or "proceeding without it" in line:
                continue
            if line.strip():
                clean_lines.append(line.strip())
        action_prompt = " ".join(clean_lines)
        
        if not action_prompt:
            action_prompt = f"Please write the implementation code for '{path}' to achieve the project goal: {goal}."
        else:
            action_prompt += f" You must use your write/edit tool to write this code directly to '{path}'. Do not explain or ask for confirmation."
            
        record_task_packet(goal, "fill", path, test_file, action_prompt, desc=desc)
        print(f"[v1-Worker] [INFO] Generated action prompt: {action_prompt}")
        print(f"[v1-Worker] [INFO] Launching local Claude CLI to fill: {path}...")
        exit_code = call_claude_cli(action_prompt)
        print(f"[v1-Worker] [INFO] Claude CLI completed with exit code: {exit_code}")
        if exit_code != 0:
            update_run_state(goal, path, test_file, "failed", last_exit_code=exit_code, failure_type=cli_failure_type(exit_code))
            sys.exit(process_exit_code(exit_code))
        
    # 第二步：外部运行测试，评估健康度
    update_run_state(goal, target_file, test_file, "testing")
    honor_control_signal(goal, target_file, test_file, current_status="testing")
    exit_code = run_v0_worker()
    if exit_code == 0:
        print("[v1-Worker SUCCESS] 所有测试均已通过！无须开启自愈。")
        update_run_state(goal, target_file, test_file, "success", last_exit_code=0)
        _copy_to_release(impl_tasks)
        _finalize_skill_outcome(True)
        sys.exit(0)
        
    # 第三步：外部控制的自愈修复循环
    max_attempts = 3
    attempt = 1
    while exit_code != 0 and attempt <= max_attempts:
        # Budget check — record a downgrade event if this attempt exceeds the configured budget.
        _check_and_apply_budget(attempt)
        print(f"\n[v1-Worker] [TRY] 开启第 {attempt}/{max_attempts} 次自愈尝试...")
        honor_control_signal(goal, target_file, test_file, current_status="healing", attempt=attempt)
        
        # ✨ 检查人工打断信号：如果用户在另一个终端发出了指令，在这里读取
        steer_message = check_for_steer()
        
        # 读取测试失败的日志
        error_logs = ""
        if os.path.exists(TEST_LOG_PATH):
            with open(TEST_LOG_PATH, "r", encoding="utf-8") as f:
                error_logs = f.read()
                
        # 逐个修复实现文件
        for task in impl_tasks:
            path = task.get("path")
            abs_path = os.path.abspath(os.path.join(DRAFT_DIR, path))
            
            # 读取当前失败的代码
            failed_code = ""
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    failed_code = f.read()
                    
            # 提取具体的失败行与断言错误，构造极简的报错信息，避免长文本干扰大模型工具调用
            lines = error_logs.splitlines()
            failure_msg = ""
            assertion_line = ""
            for line in reversed(lines):
                if "AssertionError:" in line:
                    failure_msg = line.strip()
                elif ("self.assert" in line or "assertEqual" in line) and not assertion_line:
                    assertion_line = line.strip()
                    
            error_summary = f"{assertion_line} -> {failure_msg}" if assertion_line and failure_msg else failure_msg or "Tests failed."
            update_run_state(goal, path, test_file, "healing", attempt=attempt, last_error_summary=error_summary, last_exit_code=exit_code)
            honor_control_signal(goal, path, test_file, current_status="healing", attempt=attempt)

            # 加载与报错信息相关的技能文件，注入到翻译指令的上下文中
            skills_context = load_relevant_skills(f"{error_summary} {goal}")
            # 构造人工打断指令的上下文
            steer_context = (
                f"\nIMPORTANT - User steering instruction (highest priority):\n"
                f"\"{steer_message}\"\n"
                f"Incorporate this instruction into your fix. It may modify the requirement or approach.\n"
            ) if steer_message else ""
            # 先通过无权限的 query 模式把 Traceback 翻译为一层简短直接的指令，逼迫 DeepSeek 调用 edit 工具而不会退化为寻求授权
            query_prompt = (
                f"You are an assistant translating Python test failures into a single direct sentence instruction for another developer to edit a file.\n"
                f"Analyze this failure and write a single-sentence direct instruction to fix the bug in '{path}'.\n"
                f"Your instruction MUST start with 'Please fix...' or 'Please modify...' and describe the exact code change needed to pass the test.\n"
                f"Do not include any chat formatting, notes, markdown blocks, or explanation. Output ONLY the single sentence.\n"
                f"{skills_context}\n"
                f"{steer_context}"
                f"Failure Details:\n"
                f"{error_summary}"
            )
            print(f"[v1-Worker] [INFO] Analyzing failure and generating direct instruction for {path}...")
            direct_instruction = query_claude_cli(query_prompt)
            honor_control_signal(goal, path, test_file, current_status="healing", attempt=attempt)
            
            clean_lines = []
            for line in direct_instruction.splitlines():
                if "Warning: no stdin data" in line or "proceeding without it" in line:
                    continue
                if line.strip():
                    clean_lines.append(line.strip())
            action_prompt = " ".join(clean_lines)
            
            if not action_prompt:
                action_prompt = f"Please fix the bug in '{path}' so it passes tests. You must use your edit tool to modify the file directly."
                update_run_state(goal, path, test_file, "healing", attempt=attempt, last_error_summary=error_summary, failure_type="fix_instruction_invalid")
            else:
                action_prompt += f" You must use your edit tool to modify '{path}' directly. Do not explain or ask for permission."

            record_task_packet(
                goal,
                "heal",
                path,
                test_file,
                action_prompt,
                desc=task.get("description", ""),
                attempt=attempt,
                error_summary=error_summary,
                steer_message=steer_message,
            )
            print(f"[v1-Worker] [INFO] Generated action prompt: {action_prompt}")
            print(f"[v1-Worker] [WARNING] Tests failed. Requesting Claude CLI to heal: {path}...")
            cli_exit = call_claude_cli(action_prompt)
            print(f"[v1-Worker] [INFO] Claude CLI completed with exit code: {cli_exit}")
            if cli_exit != 0:
                update_run_state(goal, path, test_file, "healing", attempt=attempt, last_error_summary=error_summary, last_exit_code=cli_exit, failure_type=cli_failure_type(cli_exit, "cli_no_edit"))
            
        # 重新在外部运行测试
        honor_control_signal(goal, target_file, test_file, current_status="testing", attempt=attempt)
        exit_code = run_v0_worker()
        if exit_code == 0:
            print(f"[v1-Worker SUCCESS] 自愈成功！在第 {attempt} 次尝试中测试全部通过。")
            update_run_state(goal, target_file, test_file, "success", attempt=attempt, last_exit_code=0)
            _copy_to_release(impl_tasks)
            _finalize_skill_outcome(True)
            sys.exit(0)
            
        attempt += 1
        
    print(f"[v1-Worker FAILURE] 自愈失败。已达到最大尝试次数 {max_attempts}。测试仍然未通过。", file=sys.stderr)
    update_run_state(goal, target_file, test_file, "failed", attempt=max_attempts, last_error_summary=error_summary, last_exit_code=exit_code, failure_type="max_retries_reached")
    _finalize_skill_outcome(False)
    sys.exit(1)

if __name__ == "__main__":
    main()
