#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monitor.py — Polyglot AI Team OS 实时监控 CLI

参考 Claude Code 的 AgentProgressLine + StatusLine 设计理念：
- 实时流式显示 Planner → Worker → 自愈 全流程日志（带颜色分类）
- 顶部固定 Header：状态、阶段、耗时、尝试次数、最近错误
- 底部固定 Footer：成本估算、Steer 提示
- 随时输入打断指令（不需要停止程序）

用法：
    python monitor.py "写一个带单元测试的日期转换工具 date_converter.py"
    python monitor.py  （不带参数则交互式输入目标）
"""

import os
import sys
import json
import time
import shutil
import locale
import threading
import subprocess
from datetime import datetime

from polyglot_ai.runtime import Runtime

def _configure_stdio():
    """Never let a console code page crash the monitor render loop."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def _output_encoding():
    return (
        getattr(sys.stdout, "encoding", None)
        or locale.getpreferredencoding(False)
        or "utf-8"
    )


def _is_utf8_console():
    return "utf" in _output_encoding().lower()


def safe_text(value, limit=None):
    text = "" if value is None else str(value)
    if limit is not None:
        text = text[:limit]
    encoding = _output_encoding()
    try:
        return text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    except Exception:
        return text.encode("ascii", errors="replace").decode("ascii")


_configure_stdio()
ASCII_SAFE_RENDER = os.name == "nt" and not _is_utf8_console()

# ── 依赖检测 ──────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("[WARNING] rich 未安装，使用纯 ANSI 模式。建议 pip install rich", file=sys.stderr)

# ── 路径配置 ──────────────────────────────────────────────────────────────────
WORKSPACE_DIR = os.path.abspath(os.environ.get("POLYGLOT_WORKSPACE") or os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS_DIR = os.path.join(WORKSPACE_DIR, "artifacts")
RUNTIME = Runtime(WORKSPACE_DIR, os.environ.get("POLYGLOT_SESSION", "default"))
RUN_STATE_PATH = RUNTIME.working_artifact_path("run_state.json")
STEER_PATH = RUNTIME.steer_path
INPUTS_DIR = RUNTIME.working_artifact_dir("inputs")
DRAFT_DIR = RUNTIME.working_artifact_dir("draft")
RELEASE_DIR = RUNTIME.working_artifact_dir("release")

# ── 日志行分类规则（参考 AgentProgressLine 的颜色策略）────────────────────────
LOG_RULES = [
    ("[SUCCESS]",   "bold green",    "[OK]"),
    ("SUCCESS]",    "bold green",    "[OK]"),
    ("All tests passed", "bold green", "[OK]"),
    ("FAILURE]",    "bold red",      "[XX]"),
    ("[ERROR]",     "bold red",      "[!!]"),
    ("ERROR]",      "red",           "[!!]"),
    ("NameError",   "red",           "[!!]"),
    ("Traceback",   "red",           "[!!]"),
    ("[WARNING]",   "yellow",        "[~~]"),
    ("WARNING]",    "yellow",        "[~~]"),
    ("[STEER]",     "bold magenta",  "[!]"),
    ("[SKILL]",     "magenta",       "[S]"),
    ("[TRY]",       "bold yellow",   "[>>]"),
    ("[HEAL]",      "yellow",        "[>>]"),
    ("[PLAN]",      "bold cyan",     "[P]"),
    ("Planner",     "cyan",          "[P]"),
    ("[draft]",     "blue",          "[->"),
    ("draft]",      "blue",          "[->"),
    ("[Worker]",    "cyan",          "[W]"),
    ("[v1-Worker]", "cyan",          "[W]"),
    ("[Harness]",   "dim",           "[ ]"),
]

STATUS_COLORS = {
    "filling":  ("bold cyan",    "FILLING "),
    "testing":  ("bold blue",    "TESTING "),
    "healing":  ("bold yellow",  "HEALING "),
    "success":  ("bold green",   "SUCCESS "),
    "failed":   ("bold red",     "FAILED  "),
    "planning": ("bold cyan",    "PLANNING"),
    "starting": ("dim",          "STARTING"),
}

SPINNERS = {
    "filling":  "dots",
    "testing":  "line",
    "healing":  "bouncingBar",
    "success":  None,
    "failed":   None,
    "planning": "dots2",
}

# ── 全局状态 ──────────────────────────────────────────────────────────────────
class MonitorState:
    def __init__(self, goal):
        self.goal = goal
        self.start_time = time.time()
        self.log_lines = []          # (timestamp, styled_text)
        self.run_state = {}
        self.lock = threading.Lock()
        self.worker_done = False
        self.worker_exit_code = None
        self.estimated_calls = 0     # 粗略估算 CLI 调用次数（用于 cost 估算）
        self.steer_history = []

    def elapsed(self):
        s = int(time.time() - self.start_time)
        return f"{s//60:02d}:{s%60:02d}"

    def add_log(self, line):
        ts = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.log_lines.append((ts, line.rstrip()))
            if "Launching local Claude CLI" in line:
                self.estimated_calls += 1

    def read_run_state(self):
        try:
            if os.path.exists(RUN_STATE_PATH):
                with open(RUN_STATE_PATH, "r", encoding="utf-8") as f:
                    self.run_state = json.load(f)
        except Exception:
            pass

    def send_steer(self, message):
        payload = {
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        RUNTIME.send_steer(message)
        self.steer_history.append(message)

    def release_files(self):
        """检查 release/ 目录里有哪些最终产物"""
        if not os.path.exists(RELEASE_DIR):
            return []
        return [f for f in os.listdir(RELEASE_DIR) if f.endswith(".py")]

# ── 日志着色 ──────────────────────────────────────────────────────────────────
def classify_line(line):
    """根据行内容返回 (rich_style, prefix_icon)"""
    for keyword, style, icon in LOG_RULES:
        if keyword in line:
            return style, icon
    return "white", " "


def panel_box():
    return box.ASCII if ASCII_SAFE_RENDER else box.ROUNDED

# ── Rich 模式渲染 ──────────────────────────────────────────────────────────────
def make_header_panel(state: MonitorState) -> Panel:
    """顶部状态面板（类比 Claude Code 的 AgentProgressLine）"""
    rs = state.run_state
    status = rs.get("status", "starting")
    attempt = rs.get("attempt", 0)
    max_attempts = 3
    last_error = rs.get("last_error_summary", "")
    failure_type = rs.get("failure_type", "")

    color, label = STATUS_COLORS.get(status, ("dim", "UNKNOWN "))

    # status_text
    spinner_name = SPINNERS.get(status)
    status_text = Text()
    if spinner_name and status not in ("success", "failed"):
        status_text.append(f" [{label}] ", style=color)
    else:
        marker = "[OK]" if status == "success" else ("[XX]" if status == "failed" else "[ ]")
        status_text.append(f" {marker} {label} ", style=color)

    status_text.append(f"  {state.elapsed()}  ", style="dim")

    if attempt > 0:
        status_text.append(f" Attempt {attempt}/{max_attempts} ", style="yellow bold")

    # 目标行
    goal_text = Text()
    goal_text.append("  Goal: ", style="dim")
    goal_text.append(safe_text(state.goal, 70), style="white bold")

    # 错误行
    error_text = Text()
    if last_error:
        error_text.append("  Error: ", style="red dim")
        error_text.append(safe_text(last_error, 80), style="red")
    if failure_type and failure_type != "none":
        error_text.append(f"  [{failure_type}]", style="red dim")

    # 产物行
    release_files = state.release_files()
    artifact_text = Text()
    if release_files:
        artifact_text.append("  Release: ", style="green dim")
        artifact_text.append("  ".join(f"[OK] {f}" for f in release_files), style="green")

    content = Text.assemble(status_text, "\n", goal_text)
    if error_text.plain:
        content = Text.assemble(content, "\n", error_text)
    if artifact_text.plain:
        content = Text.assemble(content, "\n", artifact_text)

    return Panel(
        content,
        title="[bold cyan] Polyglot AI Team OS [/bold cyan]",
        border_style="cyan" if status not in ("success", "failed") else ("green" if status == "success" else "red"),
        padding=(0, 1),
        box=panel_box(),
    )

def make_footer_text(state: MonitorState) -> Text:
    """底部提示行（类比 StatusLine）"""
    t = Text()
    t.append("  CLI calls: ", style="dim")
    t.append(str(state.estimated_calls), style="cyan")
    t.append("  |  ", style="dim")
    t.append("  [i] Interrupt/Steer", style="bold yellow")
    t.append("  |  ", style="dim")
    t.append("[q] Quit", style="dim")
    if state.steer_history:
        t.append(f"  |  Last steer: {safe_text(state.steer_history[-1], 30)}", style="magenta dim")
    return t

def make_log_table(state: MonitorState, max_rows=20) -> Table:
    """日志面板"""
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 0),
        expand=True,
    )
    table.add_column("ts", style="dim", width=10, no_wrap=True)
    table.add_column("icon", width=3, no_wrap=True)
    table.add_column("line", no_wrap=False)

    with state.lock:
        recent = state.log_lines[-max_rows:]

    for ts, line in recent:
        # 过滤掉空行和纯点行
        if not line.strip() or line.strip() == "•":
            continue
        style, icon = classify_line(line)
        table.add_row(ts, icon, Text(safe_text(line, 120), style=style))

    return table

# ── 子进程启动 ────────────────────────────────────────────────────────────────
def run_pipeline(goal: str, state: MonitorState, env_override: dict = None):
    """后台线程：依次运行 Planner → Worker，实时收集输出"""
    runtime = Runtime(WORKSPACE_DIR, os.environ.get("POLYGLOT_SESSION", "default"))
    runtime.append_event("run.started", f"Run started: {goal}", {"goal": goal})
    runtime.append_timeline("monitor", "run.start", f"Run started: {goal}", "running", {"goal": goal})

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    env["PYTHONUTF8"] = "1"
    env["POLYGLOT_WORKSPACE"] = WORKSPACE_DIR
    env["POLYGLOT_SESSION"] = runtime.session_id
    if env_override:
        env.update(env_override)

    if env.get("FORCE_MOCK") == "1":
        state.add_log("[monitor] Planner mode: FORCE_MOCK=1 (local mock plan)")
    elif env.get("DEEPSEEK_API_KEY"):
        state.add_log("[monitor] Planner mode: DeepSeek API (DEEPSEEK_API_KEY detected)")
    else:
        state.add_log("[monitor] Planner mode: auto (planner may use its configured fallback)")

    def stream(proc):
        for line in proc.stdout:
            state.add_log(line)
        proc.wait()
        return proc.returncode

    # Step 1: Planner
    state.add_log("[monitor] === Step 1: Running Planner ===")
    runtime.append_event("planner.started", "Planner started", {"goal": goal})
    runtime.append_timeline("planner", "planner.run", "Planner started", "running", {"goal": goal})
    planner_cmd = [sys.executable, os.path.join(WORKSPACE_DIR, "polyglot_ai", "v0_planner.py"), goal]
    try:
        proc = subprocess.Popen(
            planner_cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=WORKSPACE_DIR, text=True, encoding="utf-8",
            errors="replace", bufsize=1, env=env
        )
        stream(proc)
        runtime.append_event("planner.completed", f"Planner exited with {proc.returncode}", {"exit_code": proc.returncode})
        runtime.append_timeline(
            "planner",
            "planner.run",
            f"Planner exited with {proc.returncode}",
            "success" if proc.returncode == 0 else "failed",
            {"exit_code": proc.returncode},
        )
        if proc.returncode != 0:
            state.add_log(f"[ERROR] Planner failed (exit {proc.returncode})")
            runtime.append_event("planner.failed", f"Planner failed with {proc.returncode}", {"exit_code": proc.returncode})
            state.worker_done = True
            state.worker_exit_code = proc.returncode
            return
    except Exception as e:
        state.add_log(f"[ERROR] Failed to launch Planner: {e}")
        runtime.append_event("planner.failed", f"Failed to launch Planner: {e}", {"error": str(e)})
        state.worker_done = True
        state.worker_exit_code = -1
        return

    # Step 2: Worker (v1_worker.py - handles fill + test + self-healing)
    state.add_log("[monitor] === Step 2: Running Worker (fill + test + self-heal) ===")
    runtime.append_event("worker.started", "Worker started", {"worker": "polyglot_ai.v1_worker"})
    runtime.append_timeline("orchestrator", "worker.run", "Worker started", "running", {"worker": "polyglot_ai.v1_worker"})
    worker_cmd = [sys.executable, os.path.join(WORKSPACE_DIR, "polyglot_ai", "v1_worker.py")]
    try:
        proc = subprocess.Popen(
            worker_cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=WORKSPACE_DIR, text=True, encoding="utf-8",
            errors="replace", bufsize=1, env=env
        )
        stream(proc)
        state.worker_exit_code = proc.returncode
        runtime.append_event("worker.completed", f"Worker exited with {proc.returncode}", {"exit_code": proc.returncode})
        runtime.append_timeline(
            "orchestrator",
            "worker.run",
            f"Worker exited with {proc.returncode}",
            "success" if proc.returncode == 0 else "failed",
            {"exit_code": proc.returncode},
        )
    except Exception as e:
        state.add_log(f"[ERROR] Failed to launch Worker: {e}")
        state.worker_exit_code = -1
        runtime.append_event("worker.failed", f"Failed to launch Worker: {e}", {"error": str(e)})

    state.worker_done = True
    runtime.mirror_legacy_artifact("run_state.json")
    try:
        runtime.snapshot_artifacts()
    except Exception as exc:
        runtime.append_event("artifacts.snapshot_failed", f"Artifact snapshot failed: {exc}", {"error": str(exc)})
    runtime.append_event("run.completed", f"Run completed with {state.worker_exit_code}", {"exit_code": state.worker_exit_code})
    runtime.append_timeline(
        "monitor",
        "run.complete",
        f"Run completed with {state.worker_exit_code}",
        "success" if state.worker_exit_code == 0 else "failed",
        {"exit_code": state.worker_exit_code},
    )

# ── 状态轮询线程 ──────────────────────────────────────────────────────────────
def poll_state(state: MonitorState, interval=1.0):
    while not state.worker_done:
        state.read_run_state()
        time.sleep(interval)
    state.read_run_state()  # 最后读一次

# ── 用户输入线程 ──────────────────────────────────────────────────────────────
def handle_input(state: MonitorState, console):
    """在后台持续等待用户输入，'i' 发送打断，'q' 退出"""
    while not state.worker_done:
        try:
            cmd = input()
            if cmd.lower() == "q":
                console.print(f"\n[yellow]User requested exit...[/yellow]")
                state.worker_done = True
                break
            elif cmd.lower() == "i" or cmd == "":
                console.print("\n[bold yellow]>>> 输入打断指令（回车发送）：[/bold yellow]", end="")
                msg = input()
                if msg.strip():
                    state.send_steer(msg.strip())
                    console.print(f"[magenta][STEER] 已发送：\"{msg}\"[/magenta]")
            elif cmd.lower() == "s":
                state.read_run_state()
                rs = state.run_state
                console.print(f"\n[cyan]当前状态: {rs.get('status')} | 尝试: {rs.get('attempt', 0)} | 耗时: {state.elapsed()}[/cyan]")
        except (EOFError, KeyboardInterrupt):
            state.worker_done = True
            break

# ── 主函数（Rich 模式）────────────────────────────────────────────────────────
def run_rich(goal: str, env_override: dict = None):
    console = Console(
        legacy_windows=ASCII_SAFE_RENDER,
        highlight=False,
        safe_box=True,
        emoji=False,
    )
    state = MonitorState(goal)

    # 启动后台线程
    pipeline_thread = threading.Thread(target=run_pipeline, args=(goal, state, env_override), daemon=True)
    pipeline_thread.start()

    poll_thread = threading.Thread(target=poll_state, args=(state,), daemon=True)
    poll_thread.start()

    if sys.stdin.isatty():
        input_thread = threading.Thread(target=handle_input, args=(state, console), daemon=True)
        input_thread.start()

    if ASCII_SAFE_RENDER:
        console.print("\n[dim]Keys: [bold]i[/bold] steer, [bold]q[/bold] quit, [bold]s[/bold] status[/dim]\n")
    else:
        console.print("\n[dim]提示：输入 [bold]i[/bold] 发送打断指令，[bold]q[/bold] 退出，[bold]s[/bold] 查看状态[/dim]\n")

    # Live 显示循环
    with Live(console=console, refresh_per_second=2, screen=False) as live:
        while not state.worker_done:
            layout = Layout()
            layout.split_column(
                Layout(make_header_panel(state), size=6),
                Layout(Panel(make_log_table(state, max_rows=25),
                             title="[dim]Logs[/dim]" if ASCII_SAFE_RENDER else "[dim]实时日志[/dim]",
                             border_style="dim", padding=(0,1), box=panel_box())),
                Layout(Panel(make_footer_text(state), border_style="dim", padding=(0,1), box=panel_box()), size=3),
            )
            live.update(layout)
            time.sleep(0.5)

        # 最后更新一次
        state.read_run_state()
        layout = Layout()
        layout.split_column(
            Layout(make_header_panel(state), size=6),
            Layout(Panel(make_log_table(state, max_rows=30),
                         title="[dim]Logs[/dim]" if ASCII_SAFE_RENDER else "[dim]完整日志[/dim]",
                         border_style="dim", padding=(0,1), box=panel_box())),
        )
        live.update(layout)

    # 最终摘要
    console.rule("[bold]Done[/bold]" if ASCII_SAFE_RENDER else "[bold]运行结束[/bold]")
    rs = state.run_state
    status = rs.get("status", "unknown")
    if status == "success":
        console.print(f"\n[bold green][OK] Task complete![/bold green] Elapsed {state.elapsed()}")
        release = state.release_files()
        if release:
            console.print(f"[green]Released: {', '.join(release)}[/green]")
    else:
        console.print(f"\n[bold red][FAIL] Task failed[/bold red] (exit {state.worker_exit_code})")
        if rs.get("last_error_summary"):
            console.print(f"[red]Last error: {safe_text(rs['last_error_summary'])}[/red]")

    console.print(f"\n[dim]CLI calls estimated: {state.estimated_calls}[/dim]")
    if state.steer_history:
        console.print(f"[dim]Steer history: {safe_text(state.steer_history)}[/dim]")

# ── 纯 ANSI 回退模式 ──────────────────────────────────────────────────────────
def run_ansi(goal: str, env_override: dict = None):
    CYAN, GREEN, RED, YELLOW, DIM, RESET = '\033[96m','\033[92m','\033[91m','\033[93m','\033[2m','\033[0m'
    state = MonitorState(goal)

    pipeline_thread = threading.Thread(target=run_pipeline, args=(goal, state, env_override), daemon=True)
    pipeline_thread.start()

    poll_thread = threading.Thread(target=poll_state, args=(state,), daemon=True)
    poll_thread.start()

    print(f"[Polyglot AI Team OS] Goal: {goal}")
    print(f"[i=steer  q=quit]\n")

    last_count = 0
    while not state.worker_done:
        # 打印新增的日志行
        with state.lock:
            new_lines = state.log_lines[last_count:]
            last_count = len(state.log_lines)
        for ts, line in new_lines:
            if not line.strip() or line.strip() == "•":
                continue
            style, icon = classify_line(line)
            color = {
                "bold green": GREEN, "bold red": RED, "bold yellow": YELLOW,
                "yellow": YELLOW, "red": RED, "green": GREEN, "cyan": CYAN,
                "bold cyan": CYAN, "dim": DIM, "magenta": YELLOW,
            }.get(style, RESET)
            print(f"  {DIM}{ts}{RESET} {icon} {color}{line.rstrip()[:120]}{RESET}")

        # 非阻塞检查输入（简化版）
        time.sleep(0.3)

    # 打印剩余
    with state.lock:
        new_lines = state.log_lines[last_count:]
    for ts, line in new_lines:
        if line.strip() and line.strip() != "•":
            print(f"  {DIM}{ts}{RESET}   {line.rstrip()[:120]}")

    rs = state.run_state
    if rs.get("status") == "success":
        print(f"\n{GREEN}[OK] 任务完成！耗时 {state.elapsed()}{RESET}")
    else:
        print(f"\n{RED}[FAIL] 任务失败 (exit {state.worker_exit_code}){RESET}")

# ── 入口 ──────────────────────────────────────────────────────────────────────
def main():
    # 解析 env 覆盖（简单支持 KEY=VALUE 形式附加参数）
    args = sys.argv[1:]
    env_override = {}
    goal_parts = []

    for a in args:
        if "=" in a and a.split("=")[0].isupper():
            k, v = a.split("=", 1)
            env_override[k] = v
        else:
            goal_parts.append(a)

    goal = " ".join(goal_parts).strip()

    if not goal:
        if HAS_RICH:
            from rich.console import Console
            Console().print("[bold cyan]Polyglot AI Team OS[/bold cyan] — 实时监控")
        print("请输入任务目标：")
        goal = input("> ").strip()

    if not goal:
        print("[ERROR] 目标不能为空！")
        sys.exit(1)

    if HAS_RICH:
        run_rich(goal, env_override if env_override else None)
    else:
        run_ansi(goal, env_override if env_override else None)

if __name__ == "__main__":
    main()
