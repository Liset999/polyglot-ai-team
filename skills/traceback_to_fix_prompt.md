# 技能：Traceback 压缩为单句修复指令 (traceback_to_fix_prompt)

## 适用场景
当测试失败时，需要把 pytest 的错误输出（Traceback）转化为可供 CLI Worker 执行的单句修复指令。

## 核心规则

### 规则 1：单句指令格式（英文）
翻译后的修复指令必须是一句话，格式如下：

> Please fix the `[函数名]` function in `[文件名]` by [具体改动描述] so that [测试期望].

**示例：**
> Please fix the `date_diff` function in `date_converter.py` by wrapping the return value with `abs()` so that the difference is always a positive integer.

> Please fix the `reverse_words` function in `string_processor.py` so that it splits by whitespace and rejoins with single spaces, stripping leading/trailing spaces.

### 规则 2：指令中必须包含的三要素
1. **文件名**（在哪个文件里改）
2. **函数名**（改哪个函数）
3. **具体改动**（改什么，不允许使用"修复 Bug"这种模糊描述）

### 规则 3：关于语言
- 指令必须用**英文**写，不使用中文。
- 原因：DeepSeek CLI 在收到英文指令时，工具调用的成功率更高，不容易退化为聊天模式。

### 规则 4：禁止事项
- ❌ 不要把完整的 Traceback 塞入执行指令
- ❌ 不要使用 "Fix the bug" 这种模糊指令（必须说清楚怎么改）
- ❌ 不要在指令里包含 "请确认"、"是否同意"、"Can you please" 等请求批准的措辞
- ❌ 不要在一条指令里要求改动多个函数（拆成多步）

## 常见 Traceback 模式与对应指令模板

| 错误模式 | 生成指令模板 |
|---------|-------------|
| `AssertionError: assert -5 == 5` (日期差) | `Please fix ... by wrapping return value with abs()` |
| `AssertionError: assert 'hello  world' == 'hello world'` (空格) | `Please fix ... to normalize whitespace using split() and join()` |
| `IndexError` (越界访问) | `Please fix ... to add boundary check before accessing index` |
| `KeyError` (CSV/JSON 字段不存在) | `Please fix ... to use .get() with a default value or check key existence` |
| `TypeError` (类型不匹配) | `Please fix ... to ensure return type matches expected type` |
