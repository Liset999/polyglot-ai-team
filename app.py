import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

console = Console(legacy_windows=False)
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
HISTORY_PATH = ROOT / "history.json"
OUTPUT_DIR = ROOT / "outputs"
AUTO_RUN_PATH = OUTPUT_DIR / "auto_run.py"


DEFAULT_CONFIG = {
    "base_url": "https://your-gateway.example.com/v1",
    "api_key_env": "DEEPSEEK_API_KEY",
    "temperature": 0.3,
    "request_timeout_seconds": 30,
    "runtime_timeout_seconds": 5,
    "typing_delay_seconds": 0.004,
    "max_fix_rounds": 2,
    "offline_mode": "auto",
    "roles": {
        "Planner": {
            "name": "项目经理 (DeepSeek)",
            "model": "deepseek-v4-flash",
            "prompt": "你是PM，拆解需求。请用2句话以内概括，并明确指定@Coder执行。",
            "border": "yellow",
        },
        "Coder": {
            "name": "程序员 (DeepSeek)",
            "model": "deepseek-v4-flash",
            "prompt": "你是Coder，用Python实现需求。代码必须放在 ```python ... ``` 块中。代码应尽量可直接运行。",
            "border": "turquoise2",
        },
        "Tester": {
            "name": "测试员 (DeepSeek)",
            "model": "deepseek-v4-flash",
            "prompt": "你是QA。检查代码逻辑，输出 ✓ 完美 或 ✗ 缺陷，并简述原因。",
            "border": "purple",
        },
    },
    "pricing_cny_per_1k_tokens": {
        "deepseek-v4-flash": 0.0015,
    },
}


def load_config():
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    return deep_merge(DEFAULT_CONFIG, loaded)


def deep_merge(base, override):
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def api_ready(config, forced_offline):
    if forced_offline:
        return False
    if config.get("offline_mode") == "always":
        return False

    api_key = get_api_key(config)
    base_url = os.getenv("BASE_URL") or os.getenv("OPENAI_BASE_URL") or config.get("base_url", "")
    if not api_key:
        return False
    return "your-gateway" not in base_url and "你的" not in base_url


def build_client(config):
    api_key = get_api_key(config)
    base_url = os.getenv("BASE_URL") or os.getenv("OPENAI_BASE_URL") or config.get("base_url")
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=config.get("request_timeout_seconds", 30),
    )


def get_api_key(config):
    names = [
        config.get("api_key_env", "API_KEY"),
        "DEEPSEEK_API_KEY",
        "API_KEY",
        "OPENAI_API_KEY",
    ]
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def format_api_error(exc):
    parts = [f"{type(exc).__name__}: {exc}"]
    cause = getattr(exc, "__cause__", None)
    context = getattr(exc, "__context__", None)
    if cause:
        parts.append(f"cause={type(cause).__name__}: {cause}")
    if context and context is not cause:
        parts.append(f"context={type(context).__name__}: {context}")
    return " | ".join(parts)


def now_stamp():
    return datetime.now().strftime("%H:%M:%S")


def estimate_tokens(text):
    return max(16, len(text) // 2)


def role_cost(config, model, tokens):
    rate = config.get("pricing_cny_per_1k_tokens", {}).get(model, 0.002)
    return tokens / 1000 * rate


def extract_python_code(text):
    match = re.search(r"```(?:python|py)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip() + "\n"


def save_code_artifact(code):
    OUTPUT_DIR.mkdir(exist_ok=True)
    AUTO_RUN_PATH.write_text(code, encoding="utf-8")
    return AUTO_RUN_PATH


def run_python_artifact(timeout_seconds):
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, str(AUTO_RUN_PATH)],
            input="",
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(ROOT),
        )
        elapsed = time.perf_counter() - start
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "duration_seconds": round(elapsed, 3),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - start
        return {
            "ok": False,
            "returncode": "timeout",
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": f"TimeoutExpired: execution exceeded {timeout_seconds}s",
            "duration_seconds": round(elapsed, 3),
        }


def print_banner(task, mode):
    line = "━" * min(console.width, 72)
    console.print(f"[bold cyan]{line}[/]")
    console.print(
        f"[bold cyan]      polyglot-ai-team 指挥中心 | 模式: [{mode}][/]\n"
        f"[bold white]      任务: {task}[/]"
    )
    console.print(f"[bold cyan]{line}[/]\n")


def render_message(title, body, border_style="cyan", subtitle=None):
    panel_title = title if subtitle is None else f"{title} [dim]{subtitle}[/]"
    console.print(Panel(Text(body), title=panel_title, border_style=border_style))


def fake_typing(label, delay):
    console.print(f"\n[dim]● {label} 正在输入...[/]")
    if delay > 0:
        time.sleep(min(0.7, delay * 80))


def offline_reply(role_key, task, shared_history, fix_round):
    if role_key == "Planner":
        content = (
            f"任务拆解：先生成一个可直接运行的 Python 构件，再由系统沙箱执行并回填结果。"
            f"@Coder 立即实现「{task}」的核心逻辑，避免交互式卡死。"
        )
        return content, estimate_tokens(content)

    if role_key == "Coder":
        code = offline_code_for_task(task, fix_round)
        content = (
            "收到，下面给出可直接运行的 Python 实现，已避免阻塞式输入。\n\n"
            f"```python\n{code}```\n"
            f"📎 构件将自动导出至: {AUTO_RUN_PATH.as_posix()}"
        )
        return content, estimate_tokens(content)

    content = (
        "✓ 完美：构件具备直接运行入口，系统沙箱已经反馈运行结果；"
        "若接入真实模型，可继续让 Coder 根据 stderr 进行最多 2 轮自动修复。"
    )
    return content, estimate_tokens(content)


def offline_code_for_task(task, fix_round):
    lower_task = task.lower()
    if "bmi" in lower_task or "体重" in task or "身高" in task:
        return '''def calculate_bmi(height_m, weight_kg):
    if height_m <= 0:
        raise ValueError("height_m must be greater than 0")
    if weight_kg <= 0:
        raise ValueError("weight_kg must be greater than 0")
    return weight_kg / (height_m ** 2)


def roast(bmi):
    if bmi < 18.5:
        return "能量库存告急，先补给再上线。"
    if bmi < 24:
        return "系统负载漂亮，继续保持。"
    if bmi < 28:
        return "碳水进程偏多，建议手动限流。"
    return "警告：负载过高，不换习惯就换告警等级。"


if __name__ == "__main__":
    height_m = 1.75
    weight_kg = 70
    bmi = calculate_bmi(height_m, weight_kg)
    print(f"BMI: {bmi:.1f}")
    print(roast(bmi))
'''

    if "内存" in task or "memory" in lower_task:
        return '''import os
import platform
import subprocess


def memory_usage_percent():
    system = platform.system().lower()
    if system == "windows":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return float(status.dwMemoryLoad)

    if os.path.exists("/proc/meminfo"):
        values = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                key, value = line.split(":", 1)
                values[key] = int(value.strip().split()[0])
        total = values["MemTotal"]
        available = values.get("MemAvailable", values.get("MemFree", 0))
        return (total - available) / total * 100

    if system == "darwin":
        output = subprocess.check_output(["vm_stat"], text=True)
        pages = {}
        for line in output.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                pages[key] = int(value.strip().strip("."))
        used = pages.get("Pages active", 0) + pages.get("Pages wired down", 0)
        free = pages.get("Pages free", 0) + pages.get("Pages inactive", 0)
        return used / max(used + free, 1) * 100

    raise RuntimeError(f"Unsupported platform: {platform.system()}")


if __name__ == "__main__":
    print(f"Memory usage: {memory_usage_percent():.1f}%")
'''

    return f'''def main():
    task = {task!r}
    print("polyglot-ai-team artifact executed")
    print(f"Task: {{task}}")


if __name__ == "__main__":
    main()
'''


def ask_ai(role_key, task, shared_history, config, client, offline, fix_round=0):
    role = config["roles"][role_key]
    if offline:
        return offline_reply(role_key, task, shared_history, fix_round)

    messages = [{"role": "system", "content": role["prompt"]}] + shared_history
    try:
        response = client.chat.completions.create(
            model=role["model"],
            messages=messages,
            temperature=config.get("temperature", 0.3),
        )
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        tokens = getattr(usage, "total_tokens", None) or estimate_tokens(content)
        return content, tokens
    except Exception as exc:
        content = f"🔴 [集群链路故障]: {format_api_error(exc)}"
        return content, 0


def append_log(log_artifact, role_key, name, model, content, tokens, cost, duration, extra=None):
    item = {
        "at": now_stamp(),
        "role_key": role_key,
        "from": name,
        "model": model,
        "content": content,
        "tokens": tokens,
        "cost_cny": round(cost, 6),
        "duration_seconds": round(duration, 3),
    }
    if extra:
        item.update(extra)
    log_artifact["messages"].append(item)


def run_coder_once(task, shared_history, config, client, offline, log_artifact, fix_round=0):
    role_key = "Coder"
    role = config["roles"][role_key]
    label = f"{role['name']}" if fix_round == 0 else f"{role['name']} 修复轮次 #{fix_round}"
    fake_typing(label, config.get("typing_delay_seconds", 0.004))

    start = time.perf_counter()
    reply, tokens = ask_ai(role_key, task, shared_history, config, client, offline, fix_round)
    duration = time.perf_counter() - start
    cost = role_cost(config, role["model"], tokens)

    subtitle = f"| {role['model']} | {duration:.1f}s | Tokens {tokens} | ¥{cost:.4f}"
    render_message(label, reply, role.get("border", "turquoise2"), subtitle)
    shared_history.append({"role": "assistant", "content": f"[{role_key}] {reply}"})
    append_log(log_artifact, role_key, label, role["model"], reply, tokens, cost, duration)

    code = extract_python_code(reply)
    if "🔴 [集群链路故障]" in reply:
        return False, "API_FAILURE"
    if not code:
        feedback = "[系统反馈] Coder 未输出 Python Markdown 代码块，无法生成构件。"
        shared_history.append({"role": "user", "content": feedback})
        return False, feedback

    artifact_path = save_code_artifact(code)
    console.print(Syntax(code, "python", theme="monokai", line_numbers=False))

    result = run_python_artifact(config.get("runtime_timeout_seconds", 5))
    if result["ok"]:
        body = (
            f"✓ Runtime 成功 | returncode={result['returncode']} | {result['duration_seconds']}s\n"
            f"stdout:\n{result['stdout'] or '[无输出]'}"
        )
        border = "green"
    else:
        body = (
            f"✗ Runtime 失败 | returncode={result['returncode']} | {result['duration_seconds']}s\n"
            f"stdout:\n{result['stdout'] or '[无输出]'}\n\nstderr:\n{result['stderr'] or '[无错误输出]'}"
        )
        border = "red"

    render_message("系统沙箱 (Harness 运行时)", body, border, f"| {artifact_path.as_posix()}")
    append_log(
        log_artifact,
        "Harness",
        "系统沙箱",
        "subprocess.run",
        body,
        0,
        0.0,
        result["duration_seconds"],
        extra={
            "artifact": artifact_path.as_posix(),
            "runtime_ok": result["ok"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "returncode": result["returncode"],
        },
    )

    if not result["ok"]:
        feedback = (
            "[系统反馈] 运行失败，请修复后重新输出完整 Python 代码块。\n"
            f"returncode={result['returncode']}\nstdout={result['stdout']}\nstderr={result['stderr']}"
        )
        shared_history.append({"role": "user", "content": feedback})
        return False, feedback

    return True, body


def run_role(role_key, task, shared_history, config, client, offline, log_artifact):
    role = config["roles"][role_key]
    fake_typing(role["name"], config.get("typing_delay_seconds", 0.004))
    start = time.perf_counter()
    reply, tokens = ask_ai(role_key, task, shared_history, config, client, offline)
    duration = time.perf_counter() - start
    cost = role_cost(config, role["model"], tokens)
    subtitle = f"| {role['model']} | {duration:.1f}s | Tokens {tokens} | ¥{cost:.4f}"
    render_message(role["name"], reply, role.get("border", "cyan"), subtitle)
    shared_history.append({"role": "assistant", "content": f"[{role_key}] {reply}"})
    append_log(log_artifact, role_key, role["name"], role["model"], reply, tokens, cost, duration)
    return tokens, cost


def run_team_chat(task, force_offline=False, no_run=False):
    config = load_config()
    offline = not api_ready(config, force_offline)
    mode = "Offline Mock" if offline else "Pipeline"
    client = None if offline else build_client(config)

    shared_history = [{"role": "user", "content": f"[老板提示] {task}"}]
    log_artifact = {
        "task": task,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "artifact": AUTO_RUN_PATH.as_posix(),
        "total_tokens": 0,
        "total_cost_cny": 0.0,
        "messages": [
            {
                "at": now_stamp(),
                "role_key": "Boss",
                "from": "老板",
                "model": "user",
                "content": task,
                "tokens": 0,
                "cost_cny": 0.0,
                "duration_seconds": 0,
            }
        ],
    }

    print_banner(task, mode)
    render_message("老板 (用户输入)", f"任务: {task}", "bright_blue")

    run_role("Planner", task, shared_history, config, client, offline, log_artifact)

    if no_run:
        run_role("Coder", task, shared_history, config, client, offline, log_artifact)
    else:
        ok, _ = run_coder_once(task, shared_history, config, client, offline, log_artifact)
        max_fix_rounds = int(config.get("max_fix_rounds", 2))
        fix_round = 1
        while not ok and _ != "API_FAILURE" and fix_round <= max_fix_rounds:
            ok, _ = run_coder_once(
                task,
                shared_history,
                config,
                client,
                offline,
                log_artifact,
                fix_round=fix_round,
            )
            fix_round += 1

    run_role("Tester", task, shared_history, config, client, offline, log_artifact)

    total_tokens = sum(item.get("tokens", 0) for item in log_artifact["messages"])
    total_cost = sum(item.get("cost_cny", 0.0) for item in log_artifact["messages"])

    log_artifact["total_tokens"] = total_tokens
    log_artifact["total_cost_cny"] = round(total_cost, 6)
    HISTORY_PATH.write_text(json.dumps(log_artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    console.print(
        f"\n[bold green]✓ 状态持久化成功：{HISTORY_PATH.as_posix()}[/]\n"
        f"[bold cyan]💰 本次总开支: ¥{total_cost:.4f} | Tokens: {total_tokens} | 🔄 构件资产: {AUTO_RUN_PATH.as_posix()}[/]"
    )
    return log_artifact


def parse_args():
    parser = argparse.ArgumentParser(description="polyglot-ai-team CLI pipeline")
    parser.add_argument("task", nargs="*", help="老板任务，例如：写个BMI计算器")
    parser.add_argument("--offline", action="store_true", help="强制使用本地 mock，不调用 API")
    parser.add_argument("--no-run", action="store_true", help="只展示群聊，不执行 Coder 产物")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    task = " ".join(args.task).strip() or "写一段获取当前系统内存使用率的Python代码。"
    run_team_chat(task, force_offline=args.offline, no_run=args.no_run)
