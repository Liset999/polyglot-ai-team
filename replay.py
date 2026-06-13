import argparse
from io import StringIO
import json
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

console = Console(legacy_windows=False)
ROOT = Path(__file__).resolve().parent
HISTORY_PATH = ROOT / "history.json"


STYLE_BY_ROLE = {
    "Boss": "bright_blue",
    "Planner": "yellow",
    "Coder": "turquoise2",
    "Harness": "green",
    "Tester": "purple",
}


def typewriter_print(text, delay):
    if delay <= 0:
        console.print(text)
        return
    for char in text:
        console.out(char, end="")
        time.sleep(delay)
    console.out()


def render_panel_to_text(panel):
    buffer = StringIO()
    temp_console = Console(file=buffer, width=console.width, force_terminal=False, legacy_windows=False)
    temp_console.print(panel)
    return buffer.getvalue()


def replay(history_path, delay, pause):
    if not history_path.exists():
        raise SystemExit(f"找不到 {history_path}，请先运行 python app.py \"你的任务\"")

    data = json.loads(history_path.read_text(encoding="utf-8"))
    console.print(
        Panel(
            f"任务: {data.get('task', '[未知]')}\n模式: {data.get('mode', '[未知]')}\n时间: {data.get('time', '[未知]')}",
            title="polyglot-ai-team 离线回放",
            border_style="cyan",
        )
    )

    for message in data.get("messages", []):
        role_key = message.get("role_key", "")
        border = STYLE_BY_ROLE.get(role_key, "white")
        title = f"[{message.get('at', '--:--:--')}] {message.get('from', role_key)}"
        if message.get("model"):
            title += f" ({message['model']})"

        content = message.get("content", "")
        panel = Panel(Text(content), title=title, border_style=border)
        if delay > 0:
            typewriter_print(render_panel_to_text(panel), delay)
        else:
            console.print(panel)
        time.sleep(pause)

    console.print(
        f"[bold cyan]💰 回放完成 | 原始开支: ¥{data.get('total_cost_cny', 0):.4f} | "
        f"Tokens: {data.get('total_tokens', 0)}[/]"
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Replay polyglot-ai-team history without API calls")
    parser.add_argument("--history", default=str(HISTORY_PATH), help="history.json 路径")
    parser.add_argument("--delay", type=float, default=0.0, help="保留给逐字输出的延迟参数")
    parser.add_argument("--pause", type=float, default=0.35, help="消息之间的停顿秒数")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    replay(Path(args.history), args.delay, args.pause)
