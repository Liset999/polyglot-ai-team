import os
import json
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from polyglot_ai.runtime import Runtime

# 1. 核心路径定义
WORKSPACE_DIR = os.path.abspath(os.environ.get("POLYGLOT_WORKSPACE") or os.path.dirname(os.path.dirname(__file__)))
RUNTIME = Runtime(WORKSPACE_DIR, os.environ.get("POLYGLOT_SESSION", "default"))
# 三层目录语义：inputs（规划）/ draft（草稿）/ release（交付）
INPUTS_DIR = os.path.abspath(RUNTIME.working_artifact_dir("inputs"))
DRAFT_DIR = os.path.abspath(RUNTIME.working_artifact_dir("draft"))
PLAN_JSON_PATH = os.path.abspath(os.path.join(INPUTS_DIR, "plan.json"))
TEST_LOG_PATH = os.path.abspath(RUNTIME.working_artifact_path("test_run.log"))

def read_plan():
    """
    读取并解析 plan.json
    """
    if not os.path.exists(PLAN_JSON_PATH):
        print(f"[ERROR] 找不到规划文件: {PLAN_JSON_PATH}", file=sys.stderr)
        sys.exit(1)
        
    with open(PLAN_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def run_single_test(test_rel_path):
    """
    启动子进程运行单个测试文件，并将输出捕获写到控制台和日志文件中。
    """
    abs_test_path = os.path.abspath(os.path.join(DRAFT_DIR, test_rel_path))
    
    print("=" * 60)
    print(f"[Worker] 开始执行测试文件: {test_rel_path}")
    print(f"[Worker] 执行命令: python {abs_test_path}")
    print("=" * 60)
    
    # 操作系统层面的进程启动
    # cwd=GENERATED_DIR: 必须在该目录下执行，保证 test 寻找 temperature 模块的导入路径正确
    try:
        process = subprocess.Popen(
            [sys.executable, abs_test_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # 合并标准错误到标准输出（2>&1）
            cwd=DRAFT_DIR,       # 设定子进程工作目录（draft 层）
            text=True,
            errors="replace",
            bufsize=1                 # 行缓冲实时读取
        )
        
        test_output = []
        # 实时流式读取子进程输出并在控制台回显
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            test_output.append(line)
            
        process.wait()
        exit_code = process.returncode
        
        # 将日志写入本地 artifacts/test_run.log 进行归盘
        os.makedirs(os.path.dirname(TEST_LOG_PATH), exist_ok=True)
        with open(TEST_LOG_PATH, "w", encoding="utf-8") as log_file:
            log_file.writelines(test_output)
            
        return exit_code
        
    except Exception as e:
        print(f"[ERROR] 执行测试进程异常: {e}", file=sys.stderr)
        return -1

def main():
    plan_data = read_plan()
    tasks = plan_data.get("tasks", [])
    
    # 2. 扫描过滤出所有以 test_ 开头且以 .py 结尾的测试文件
    test_files = []
    for task in tasks:
        filename = task.get("filename", "")
        path = task.get("path", "")
        if filename.startswith("test_") and filename.endswith(".py"):
            test_files.append(path)
            
    if not test_files:
        print("[Worker] 规划中没有检测到需要运行的测试文件。")
        sys.exit(0)
        
    # 3. 执行我们找到的第一个测试文件
    test_to_run = test_files[0]
    exit_code = run_single_test(test_to_run)
    
    # 4. 根据子进程退出状态码判断整个项目构建是否成功
    print("=" * 60)
    if exit_code == 0:
        print("[Worker SUCCESS] Project is healthy. All tests passed! (Exit Code: 0)")
        sys.exit(0)
    else:
        print(f"[Worker FAILURE] Project build failed. Tests failed! (Exit Code: {exit_code})", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
