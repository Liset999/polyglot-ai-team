import os
import sys
import shutil
import json
import subprocess

WORKSPACE_DIR = r"d:\Repository\polyglot-ai-team"
# 三层目录结构
DRAFT_DIR = os.path.join(WORKSPACE_DIR, "artifacts", "draft")
INPUTS_DIR = os.path.join(WORKSPACE_DIR, "artifacts", "inputs")
RELEASE_DIR = os.path.join(WORKSPACE_DIR, "artifacts", "release")
RUN_STATE_PATH = os.path.join(WORKSPACE_DIR, "artifacts", "run_state.json")

def clear_draft_directory():
    """
    清空 artifacts/draft/ 中的所有文件，保留 .claude 目录（包含权限绕过配置）。
    """
    print("[Harness] Clearing draft directory...")
    if not os.path.exists(DRAFT_DIR):
        os.makedirs(DRAFT_DIR, exist_ok=True)
        return
        
    for item in os.listdir(DRAFT_DIR):
        item_path = os.path.join(DRAFT_DIR, item)
        if item == ".claude":
            continue
        if os.path.isdir(item_path):
            shutil.rmtree(item_path, ignore_errors=True)
        else:
            try:
                os.remove(item_path)
            except Exception:
                pass

def run_command(cmd, cwd=WORKSPACE_DIR):
    print(f"[Harness] Running: {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    output = []
    for line in process.stdout:
        try:
            sys.stdout.buffer.write(("  " + line).encode(sys.stdout.encoding or "utf-8", errors="replace"))
            sys.stdout.flush()
        except Exception:
            pass
        output.append(line)
    process.wait()
    return process.returncode, "".join(output)

def inject_bug(file_rel_path, target_str, replacement_str):
    abs_path = os.path.join(DRAFT_DIR, file_rel_path)
    if not os.path.exists(abs_path):
        print(f"[Harness] [ERROR] Target file not found for bug injection: {abs_path}")
        return False
        
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if target_str not in content:
        print(f"[Harness] [ERROR] Target string '{target_str}' not found in {file_rel_path}!")
        print("File content was:")
        print(content)
        return False
        
    new_content = content.replace(target_str, replacement_str)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"[Harness] Successfully injected bug into {file_rel_path}!")
    return True

def verify_run_state(expected_status=None, check_attempt=False):
    if not os.path.exists(RUN_STATE_PATH):
        print("[Harness] [ERROR] run_state.json not found!")
        return False
        
    with open(RUN_STATE_PATH, "r", encoding="utf-8") as f:
        state = json.load(f)
        
    print(f"[Harness] Current run_state.json: {json.dumps(state, indent=2, ensure_ascii=False)}")
    
    if expected_status and state.get("status") != expected_status:
        print(f"[Harness] [ERROR] Expected status '{expected_status}', got '{state.get('status')}'")
        return False
        
    if check_attempt and state.get("attempt", 0) <= 0:
        print("[Harness] [ERROR] Expected attempt > 0 for self-healing, got 0")
        return False
        
    return True

def run_task_suite(task_name, goal, impl_file, target_bug_str, replacement_bug_str):
    print("=" * 80)
    print(f" STARTING TASK: {task_name}")
    print(f" Goal: {goal}")
    print("=" * 80)
    
    result = {
        "name": task_name,
        "planner_success": False,
        "initial_fill_success": False,
        "bug_injected": False,
        "self_healing_success": False,
        "exit_code": -1,
        "run_state_exists": False,
        "run_state_status": None,
        "failure_type": None,
    }
    
    # 1. Clear draft sandbox (keeping .claude settings for bypassPermissions)
    clear_draft_directory()
    
    # Clean up state from previous runs
    if os.path.exists(RUN_STATE_PATH):
        try:
            os.remove(RUN_STATE_PATH)
        except Exception:
            pass
    
    # 2. Run Planner
    print(f"[Harness] [Step 1] Running Planner...")
    planner_cmd = [sys.executable, os.path.join(WORKSPACE_DIR, "polyglot_ai", "v0_planner.py"), goal]
    code, _ = run_command(planner_cmd)
    if code != 0:
        print(f"[Harness] [ERROR] Planner failed with exit code: {code}")
        return result
        
    result["planner_success"] = True
    
    # 3. Run Worker for initial fill
    print(f"[Harness] [Step 2] Running Worker for initial fill...")
    worker_cmd = [sys.executable, os.path.join(WORKSPACE_DIR, "polyglot_ai", "v1_worker.py")]
    code, _ = run_command(worker_cmd)
    result["exit_code"] = code
    
    # Check state after initial fill
    if os.path.exists(RUN_STATE_PATH):
        result["run_state_exists"] = True
        try:
            with open(RUN_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
                result["run_state_status"] = state.get("status")
                result["failure_type"] = state.get("failure_type")
        except Exception:
            pass
            
    if code != 0:
        print(f"[Harness] [ERROR] Worker initial fill failed with exit code: {code}")
        return result
        
    if result["run_state_status"] != "success":
        print(f"[Harness] [ERROR] Worker initial fill returned 0 but state status is {result['run_state_status']}")
        return result
        
    result["initial_fill_success"] = True
    
    # 4. Inject bug
    print(f"[Harness] [Step 3] Injecting bug into {impl_file}...")
    if not inject_bug(impl_file, target_bug_str, replacement_bug_str):
        print(f"[Harness] [ERROR] Failed to inject bug into {impl_file}")
        return result
        
    result["bug_injected"] = True
    
    # 5. Run Worker again to trigger self-healing
    print(f"[Harness] [Step 4] Running Worker for self-healing...")
    code, _ = run_command(worker_cmd)
    result["exit_code"] = code
    
    # Check state after self-healing
    if os.path.exists(RUN_STATE_PATH):
        result["run_state_exists"] = True
        try:
            with open(RUN_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
                result["run_state_status"] = state.get("status")
                result["failure_type"] = state.get("failure_type")
        except Exception:
            pass
            
    if code != 0:
        print(f"[Harness] [ERROR] Worker self-healing failed with exit status: {code}")
        return result
        
    if result["run_state_status"] != "success":
        print(f"[Harness] [ERROR] Worker self-healing returned 0 but state status is {result['run_state_status']}")
        return result
        
    result["self_healing_success"] = True
    print(f"[Harness] TASK {task_name} COMPLETED SUCCESSFULLY!\n")
    return result

def main():
    os.environ["FORCE_MOCK"] = "1"
    tasks = [
        {
            "name": "Task A: String Processor",
            "goal": "写一个带有单元测试的 Python 字符串处理工具，在 string_processor.py 中包含 reverse_string、alternate_case、to_camel_case 三个函数",
            "impl_file": "string_processor.py",
            "target": "[::-1]",
            "replacement": "[::]"  # disables reversal
        },
        {
            "name": "Task B: Date Converter",
            "goal": "写一个带有单元测试的 Python 日期转换工具，在 date_converter.py 中包含 format_iso、date_diff 两个函数",
            "impl_file": "date_converter.py",
            "target": "abs(",
            "replacement": "("  # breaks absolute calculation for negative date differences
        },
        {
            "name": "Task C: CSV/JSON Parser",
            "goal": "写一个带有单元测试的 Python 数据转换工具，在 data_converter.py 中包含 parse_csv_to_json 函数",
            "impl_file": "data_converter.py",
            "target": "json.dumps(",
            "replacement": "'[' + json.dumps("  # corrupts JSON format
        }
    ]
    
    results = []
    for task in tasks:
        res = run_task_suite(
            task["name"],
            task["goal"],
            task["impl_file"],
            task["target"],
            task["replacement"]
        )
        results.append(res)
            
    print("\n" + "=" * 80)
    print(" PHASE 3.5 VERIFICATION SUMMARY")
    print("=" * 80)
    
    passed_count = 0
    explainable_failures = 0
    unexplainable_failures = 0
    
    for res in results:
        task_name = res["name"]
        print(f"Task: {task_name}")
        print(f"  - Planner Success: {res['planner_success']}")
        print(f"  - Initial Fill Success: {res['initial_fill_success']}")
        print(f"  - Bug Injected: {res['bug_injected']}")
        print(f"  - Self-Healing Success: {res['self_healing_success']}")
        print(f"  - Worker Exit Code: {res['exit_code']}")
        print(f"  - Run State Saved: {res['run_state_exists']}")
        print(f"  - Run State Status: {res['run_state_status']}")
        print(f"  - Failure Type: {res['failure_type']}")
        
        if res["self_healing_success"]:
            passed_count += 1
            print("  --> Result: PASS")
        else:
            # Check if failure is explainable
            # Criteria: run_state.json exists and failure_type is correctly categorized (not "none")
            if res["run_state_exists"] and res["failure_type"] not in (None, "none", ""):
                explainable_failures += 1
                print("  --> Result: FAIL (Explainable)")
            else:
                unexplainable_failures += 1
                print("  --> Result: FAIL (Unexplainable)")
        print("-" * 60)
        
    print("\n" + "=" * 80)
    print(" METRIC VALIDATION")
    print("=" * 80)
    print(f"Total Tasks Run: {len(results)}/3")
    print(f"Passed Tasks: {passed_count}")
    print(f"Explainable Failures: {explainable_failures}")
    print(f"Unexplainable Failures: {unexplainable_failures}")
    
    validation_ok = True
    
    # 1. 3 个任务都能完整跑完流程
    if len(results) < 3:
        print("[FAIL] Did not run all 3 tasks.")
        validation_ok = False
        
    # 2. 至少 2/3 任务能在当前策略下自愈成功
    if passed_count < 2:
        print("[FAIL] Less than 2/3 tasks succeeded.")
        validation_ok = False
        
    # 3. 失败的任务能正确写出 run_state.json 并正确归类
    if unexplainable_failures > 0:
        print("[FAIL] There are unexplainable failures without proper run_state.json or category.")
        validation_ok = False
        
    if validation_ok:
        print("\n[SUCCESS] Engineering validation PASSED! (All criteria met)")
        sys.exit(0)
    else:
        print("\n[FAILURE] Engineering validation FAILED! (Some criteria not met)")
        sys.exit(1)

if __name__ == "__main__":
    main()
