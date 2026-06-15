# 技能：CLI 无修改静默失败恢复 (cli_no_edit_recovery)

## 适用场景
当 Claude CLI 退出码为 0，但目标文件内容实际上没有被修改时，属于"静默失败"（silent failure）。这是本地 CLI 执行 DeepSeek 模型时最常见的失败模式之一。

## 识别方法
在 CLI 调用前后对比目标文件的内容，如果内容未发生变化，则判断为静默失败，应在日志里记录 `failure_type: cli_no_edit`。

## 根本原因
本地 CLI 底层使用 DeepSeek 模型时，如果收到的执行指令过于复杂（例如包含大量 Traceback、冗长的业务描述、或中英文混排），模型可能退化为"聊天模式"：只在控制台输出解释性文字，而不实际调用文件写入/编辑工具。

## 恢复策略

### 策略 1：始终使用两步翻译法
不要把复杂上下文直接发给执行型 CLI。正确流程：
1. 先用无权限的查询模式（`claude -p`，不带 bypassPermissions）把复杂内容压缩成一句话指令；
2. 再把这句话发给带 bypassPermissions 权限的执行型 CLI，让它专注执行。

### 策略 2：执行指令必须包含触发工具调用的关键词
执行型指令必须明确包含以下关键词之一，才能稳定触发 DeepSeek 的文件工具调用：
- `"You MUST use your write/edit tool to modify the file directly."`
- `"Do not explain or ask for permission, just perform the edit."`

### 策略 3：保持指令极简
执行指令应当是一句话，绝对不超过 3 行。避免在执行指令里包含：
- 完整的测试代码内容
- 超过 5 行的错误 Traceback
- 多个改动要求（一次只改一件事）
