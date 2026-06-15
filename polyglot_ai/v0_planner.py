import os
import sys
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from polyglot_ai.runtime import Runtime

# 1. 核心常量定义
WORKSPACE_DIR = os.path.abspath(os.environ.get("POLYGLOT_WORKSPACE") or os.path.dirname(os.path.dirname(__file__)))
RUNTIME = Runtime(WORKSPACE_DIR, os.environ.get("POLYGLOT_SESSION", "default"))
# 三层目录结构：inputs（规划层）/ draft（草稿层）/ release（交付层）
INPUTS_DIR = os.path.abspath(RUNTIME.working_artifact_dir("inputs"))
DRAFT_DIR = os.path.abspath(RUNTIME.working_artifact_dir("draft"))
RELEASE_DIR = os.path.abspath(RUNTIME.working_artifact_dir("release"))
PLAN_JSON_PATH = os.path.abspath(os.path.join(INPUTS_DIR, "plan.json"))

def get_cli_goal():
    """
    获取用户的输入目标。优先从命令行参数读取，如果没有则提示用户进行交互式输入。
    """
    if len(sys.argv) > 1:
        return sys.argv[1].strip()
    
    print("请输入你的项目目标（例如: '用 Python 写一个带有单元测试的温度转换工具'）：")
    goal = input("> ").strip()
    if not goal:
        print("[ERROR] 目标不能为空！")
        sys.exit(1)
    return goal

def generate_mock_plan(goal):
    """
    Mock 模式：当无 API Key 或 API 请求失败时自动触发。根据目标生成对应的特定脚手架定义。
    这确保了在无网络/无 Key 时系统依然“能跑”。
    """
    print("[v0-Planner] 使用本地 Mock 模板生成规划...")
    goal_lower = goal.lower()
    
    if "string_processor" in goal_lower:
        # Task A: String Processor
        tasks = [
            {
                "filename": "string_processor.py",
                "path": "string_processor.py",
                "description": "Python 字符串处理工具，包含反转、大小写交替和驼峰命名转换功能。",
                "content": (
                    "# -*- coding: utf-8 -*-\n"
                    "def reverse_string(s: str) -> str:\n"
                    "    \"\"\"反转字符串\"\"\"\n"
                    "    raise NotImplementedError()\n\n"
                    "def alternate_case(s: str) -> str:\n"
                    "    \"\"\"字符串中字母大小写交替\"\"\"\n"
                    "    raise NotImplementedError()\n\n"
                    "def to_camel_case(s: str) -> str:\n"
                    "    \"\"\"下划线或空格分割字符串转换为驼峰式\"\"\"\n"
                    "    raise NotImplementedError()\n"
                )
            },
            {
                "filename": "test_string_processor.py",
                "path": "test_string_processor.py",
                "description": "String Processor 的单元测试文件。",
                "content": (
                    "# -*- coding: utf-8 -*-\n"
                    "import pytest\n"
                    "from string_processor import reverse_string, alternate_case, to_camel_case\n\n"
                    "class TestReverseString:\n"
                    "    def test_reverse_normal(self):\n"
                    "        assert reverse_string(\"hello\") == \"olleh\"\n\n"
                    "    def test_reverse_empty(self):\n"
                    "        assert reverse_string(\"\") == \"\"\n\n"
                    "    def test_reverse_single_char(self):\n"
                    "        assert reverse_string(\"a\") == \"a\"\n\n"
                    "    def test_reverse_palindrome(self):\n"
                    "        assert reverse_string(\"madam\") == \"madam\"\n\n"
                    "    def test_reverse_with_spaces(self):\n"
                    "        assert reverse_string(\"hello world\") == \"dlrow olleh\"\n\n"
                    "    def test_reverse_mixed_case(self):\n"
                    "        assert reverse_string(\"AbC\") == \"CbA\"\n\n"
                    "    def test_reverse_numeric(self):\n"
                    "        assert reverse_string(\"12345\") == \"54321\"\n\n"
                    "    def test_reverse_special_chars(self):\n"
                    "        assert reverse_string(\"!@#\") == \"#@!\"\n\n"
                    "class TestAlternateCase:\n"
                    "    def test_alternate_lower_basic(self):\n"
                    "        assert alternate_case(\"hello\") == \"HeLlO\"\n\n"
                    "    def test_alternate_upper_start(self):\n"
                    "        assert alternate_case(\"HELLO\") == \"HeLlO\"\n\n"
                    "    def test_alternate_empty(self):\n"
                    "        assert alternate_case(\"\") == \"\"\n\n"
                    "    def test_alternate_single_char(self):\n"
                    "        assert alternate_case(\"a\") == \"A\"\n\n"
                    "    def test_alternate_with_spaces(self):\n"
                    "        assert alternate_case(\"hello world\") == \"HeLlO wOrLd\"\n\n"
                    "    def test_alternate_non_alpha(self):\n"
                    "        assert alternate_case(\"h2l4o\") == \"H2l4O\"\n\n"
                    "    def test_alternate_mixed_case_input(self):\n"
                    "        assert alternate_case(\"HeLLo\") == \"HeLlO\"\n\n"
                    "    def test_alternate_all_uppercase(self):\n"
                    "        assert alternate_case(\"ABC\") == \"AbC\"\n\n"
                    "    def test_alternate_with_underscore(self):\n"
                    "        assert alternate_case(\"hello_world\") == \"HeLlO_wOrLd\"\n\n"
                    "class TestToCamelCase:\n"
                    "    def test_camel_snake_basic(self):\n"
                    "        assert to_camel_case(\"hello_world\") == \"helloWorld\"\n\n"
                    "    def test_camel_snake_multiple_underscores(self):\n"
                    "        assert to_camel_case(\"hello_world_python\") == \"helloWorldPython\"\n\n"
                    "    def test_camel_space_basic(self):\n"
                    "        assert to_camel_case(\"hello world\") == \"helloWorld\"\n\n"
                    "    def test_camel_empty(self):\n"
                    "        assert to_camel_case(\"\") == \"\"\n\n"
                    "    def test_camel_single_word(self):\n"
                    "        assert to_camel_case(\"hello\") == \"hello\"\n\n"
                    "    def test_camel_already_camel(self):\n"
                    "        assert to_camel_case(\"helloWorld\") == \"helloWorld\"\n\n"
                    "    def test_camel_leading_underscore(self):\n"
                    "        assert to_camel_case(\"_hello_world\") == \"helloWorld\"\n\n"
                    "    def test_camel_trailing_underscore(self):\n"
                    "        assert to_camel_case(\"hello_world_\") == \"helloWorld\"\n\n"
                    "    def test_camel_mixed_separators(self):\n"
                    "        assert to_camel_case(\"hello_world test\") == \"helloWorldTest\"\n\n"
                    "    def test_camel_numbers(self):\n"
                    "        assert to_camel_case(\"hello_2_world\") == \"hello2World\"\n\n"
                    "    def test_camel_multiple_spaces(self):\n"
                    "        assert to_camel_case(\"hello   world\") == \"helloWorld\"\n\n"
                    "    def test_camel_uppercase_word(self):\n"
                    "        assert to_camel_case(\"HELLO_WORLD\") == \"helloWorld\"\n\n"
                    "    def test_camel_only_separators(self):\n"
                    "        assert to_camel_case(\"_\") == \"\"\n"
                )
            },
            {
                "filename": "README.md",
                "path": "README.md",
                "description": "项目说明文档。",
                "content": f"# {goal}\n\n这是由 Polyglot AI Team OS v0 自动生成的脚手架项目。\n"
            }
        ]
    elif "date_converter" in goal_lower:
        # Task B: Date Converter
        tasks = [
            {
                "filename": "date_converter.py",
                "path": "date_converter.py",
                "description": "Python 日期转换工具，包含 ISO 格式转换及天数差计算。",
                "content": (
                    "# -*- coding: utf-8 -*-\n"
                    "def format_iso(date_str: str) -> str:\n"
                    "    \"\"\"将各种日期格式转换为标准 ISO 格式\"\"\"\n"
                    "    raise NotImplementedError()\n\n"
                    "def date_diff(date_str1: str, date_str2: str) -> int:\n"
                    "    \"\"\"计算两个日期之间的绝对天数差\"\"\"\n"
                    "    raise NotImplementedError()\n"
                )
            },
            {
                "filename": "test_date_converter.py",
                "path": "test_date_converter.py",
                "description": "Date Converter 的单元测试文件。",
                "content": (
                    "# -*- coding: utf-8 -*-\n"
                    "import pytest\n"
                    "from date_converter import format_iso, date_diff\n\n"
                    "class TestFormatIso:\n"
                    "    def test_format_standard(self):\n"
                    "        assert format_iso(\"2026-06-15\") == \"2026-06-15\"\n\n"
                    "    def test_format_slash(self):\n"
                    "        assert format_iso(\"2026/06/15\") == \"2026-06-15\"\n\n"
                    "    def test_format_dot(self):\n"
                    "        assert format_iso(\"2026.06.15\") == \"2026-06-15\"\n\n"
                    "    def test_format_invalid(self):\n"
                    "        with pytest.raises(ValueError):\n"
                    "            format_iso(\"invalid-date\")\n\n"
                    "class TestDateDiff:\n"
                    "    def test_diff_positive(self):\n"
                    "        assert date_diff(\"2026-06-15\", \"2026-06-10\") == 5\n\n"
                    "    def test_diff_negative(self):\n"
                    "        assert date_diff(\"2026-06-10\", \"2026-06-15\") == 5\n\n"
                    "    def test_diff_same(self):\n"
                    "        assert date_diff(\"2026-06-15\", \"2026-06-15\") == 0\n"
                )
            },
            {
                "filename": "README.md",
                "path": "README.md",
                "description": "项目说明文档。",
                "content": f"# {goal}\n\n这是由 Polyglot AI Team OS v0 自动生成的脚手架项目。\n"
            }
        ]
    elif "data_converter" in goal_lower:
        # Task C: CSV/JSON Parser (data_converter.py)
        tasks = [
            {
                "filename": "data_converter.py",
                "path": "data_converter.py",
                "description": "Python 数据转换工具，包含将 CSV 格式字符串解析并转化为标准 JSON 格式的工具。",
                "content": (
                    "# -*- coding: utf-8 -*-\n"
                    "def parse_csv_to_json(csv_str: str) -> str:\n"
                    "    \"\"\"将 CSV 格式字符串解析并转化为标准 JSON 格式的工具\"\"\"\n"
                    "    raise NotImplementedError()\n"
                )
            },
            {
                "filename": "test_data_converter.py",
                "path": "test_data_converter.py",
                "description": "CSV/JSON Parser 的单元测试文件。",
                "content": (
                    "# -*- coding: utf-8 -*-\n"
                    "import pytest\n"
                    "import json\n"
                    "from data_converter import parse_csv_to_json\n\n"
                    "class TestParseCsvToJson:\n"
                    "    def test_parse_simple(self):\n"
                    "        csv_data = \"name,age\\nAlice,30\\nBob,25\"\n"
                    "        json_data = parse_csv_to_json(csv_data)\n"
                    "        parsed = json.loads(json_data)\n"
                    "        assert len(parsed) == 2\n"
                    "        assert parsed[0][\"name\"] == \"Alice\"\n"
                    "        assert str(parsed[0][\"age\"]) == \"30\"\n"
                    "        assert parsed[1][\"name\"] == \"Bob\"\n"
                    "        assert str(parsed[1][\"age\"]) == \"25\"\n\n"
                    "    def test_parse_empty(self):\n"
                    "        csv_data = \"name,age\"\n"
                    "        json_data = parse_csv_to_json(csv_data)\n"
                    "        assert json.loads(json_data) == []\n"
                )
            },
            {
                "filename": "README.md",
                "path": "README.md",
                "description": "项目说明文档。",
                "content": f"# {goal}\n\n这是由 Polyglot AI Team OS v0 自动生成的脚手架项目。\n"
            }
        ]
    else:
        # Default fallback
        tasks = [
            {
                "filename": "app.py",
                "path": "app.py",
                "description": "项目主程序文件，包含核心逻辑。",
                "content": f"# -*- coding: utf-8 -*-\n# Project Goal: {goal}\n\ndef main():\n    print('Hello from SRE Scaffolding!')\n\nif __name__ == '__main__':\n    main()\n"
            },
            {
                "filename": "test_app.py",
                "path": "test_app.py",
                "description": "项目单元测试文件。",
                "content": "# -*- coding: utf-8 -*-\nimport unittest\nfrom app import main\n\nclass TestApp(unittest.TestCase):\n    def test_placeholder(self):\n        self.assertTrue(True)\n\nif __name__ == '__main__':\n    unittest.main()\n"
            },
            {
                "filename": "README.md",
                "path": "README.md",
                "description": "项目说明文档。",
                "content": f"# {goal}\n\n这是由 Polyglot AI Team OS v0 自动生成的脚手架项目。\n\n## 运行方式\n* 运行主程序: `python app.py`\n* 运行测试: `python test_app.py`\n"
            }
        ]
    
    return {"goal": goal, "tasks": tasks}

def generate_api_plan(goal, api_key):
    """
    API 模式：调用 DeepSeek API，强制模型返回 3~5 个文件的结构化 JSON 数据。
    """
    print("[v0-Planner] 正在请求 DeepSeek API 进行结构化文件拆解...")
    
    url = "https://api.deepseek.com/chat/completions"
    
    system_prompt = (
        "你是一个专业的项目脚手架拆解器。你必须根据用户的项目目标，"
        "将其合理拆解为 3 到 5 个核心文件（例如主逻辑文件、单元测试文件、README 说明文件或配置文件）。\n"
        "为了支持测试驱动开发(TDD)，你必须遵循以下规则：\n"
        "1. 所有的单元测试文件（文件名以 test_ 开头，如 test_calculator.py）必须包含完整且非常详尽的测试用例和断言逻辑，并且可以直接运行。\n"
        "2. 所有被测试的业务实现文件（如 calculator.py）必须仅包含类和函数的定义（骨架存根/Stub），但函数体内只能是 `pass`、`return None` 或 `raise NotImplementedError()`。绝对不能包含任何实际逻辑，确保测试运行时会失败。\n"
        "3. 其他非代码文件（如 README.md）必须包含完整的内容。\n"
        "你必须严格以下列 JSON 格式返回，不要包含任何 markdown 代码块标记（如 ```json），只返回纯 JSON 字符串：\n"
        "{\n"
        "  \"goal\": \"用户的原始目标\",\n"
        "  \"tasks\": [\n"
        "    {\n"
        "      \"filename\": \"文件名，例如 app.py\",\n"
        "      \"path\": \"文件相对路径，例如 app.py 或 src/app.py\",\n"
        "      \"description\": \"该文件的核心用途描述\",\n"
        "      \"content\": \"该文件的骨架存根或测试代码/文本内容\"\n"
        "    }\n"
        "  ]\n"
        "}"
    )
    
    payload = {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": goal}
        ],
        "response_format": {
            "type": "json_object"
        },
        "temperature": 0.2
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )
    
    try:
        # 加上 15 秒超时保护
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            choices = res_data.get("choices", [])
            if not choices:
                raise ValueError("API 返回内容中 choice 列表为空")
                
            text_response = choices[0].get("message", {}).get("content", "")
            return json.loads(text_response)
            
    except urllib.error.HTTPError as e:
        print(f"[WARNING] API 请求失败 (HTTP {e.code})。详细信息: {e.read().decode('utf-8')}", file=sys.stderr)
        print("[WARNING] 即将自动降级为本地 Mock 模式...", file=sys.stderr)
        return generate_mock_plan(goal)
    except Exception as e:
        print(f"[WARNING] 调用 API 发生异常: {e}。即将自动降级为本地 Mock 模式...", file=sys.stderr)
        return generate_mock_plan(goal)

def save_plan_and_files(plan_data):
    """
    保存 plan.json 到 inputs/ 层，并将骨架文件写入 draft/ 层（Claude 工作区）。
    三层目录语义：
      inputs/  ← Planner 产物（plan.json），只读，不在这里改代码
      draft/   ← Claude/Worker 工作区，所有代码在这里生成和修复
      release/ ← 仅在测试全部通过后，由 v1_worker 将代码复制到此处
    """
    # 1. 确保三层目录都存在
    os.makedirs(INPUTS_DIR, exist_ok=True)
    os.makedirs(DRAFT_DIR, exist_ok=True)
    os.makedirs(RELEASE_DIR, exist_ok=True)
    
    # 2. 写入 plan.json 到 inputs/ 层
    with open(PLAN_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2, ensure_ascii=False)
    print(f"[v0-Planner SUCCESS] 已保存规划元数据至: {PLAN_JSON_PATH}")
    
    # 3. 循环创建骨架文件到 draft/ 层（Claude 工作区）
    tasks = plan_data.get("tasks", [])
    print(f"[v0-Planner] 开始在 draft/ 层生成 {len(tasks)} 个骨架文件...")
    print("-" * 60)
    
    for task in tasks:
        rel_path = task.get("path")
        content = task.get("content", "")
        desc = task.get("description", "")
        
        # 计算该文件的本地绝对路径，防范目录穿越安全漏洞
        abs_file_path = os.path.abspath(os.path.join(DRAFT_DIR, rel_path))
        if not abs_file_path.startswith(DRAFT_DIR):
            print(f"[WARNING] 越界路径检测，已拒绝创建: {rel_path}", file=sys.stderr)
            continue
            
        # 确保文件的父目录存在
        os.makedirs(os.path.dirname(abs_file_path), exist_ok=True)
        
        # 写入文件
        with open(abs_file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"[draft] 创建文件: {abs_file_path}")
        print(f"文件描述: {desc}")
        print("-" * 60)

def main():
    goal = get_cli_goal()
    
    # 检测环境变量中的 API Key，若无则使用你提供的 DeepSeek Key 临时后备
    api_key = os.environ.get("DEEPSEEK_API_KEY") or "sk-cd82645e18de4805935439905db6fa79"
    
    force_mock = os.environ.get("FORCE_MOCK") == "1"
    
    if force_mock:
        print("[v0-Planner] 检测到 FORCE_MOCK=1，强制启动 Mock 模式。")
        plan_data = generate_mock_plan(goal)
    elif api_key and api_key != "YOUR_DEEPSEEK_API_KEY":
        plan_data = generate_api_plan(goal, api_key)
    else:
        plan_data = generate_mock_plan(goal)
        
    save_plan_and_files(plan_data)

if __name__ == "__main__":
    main()
