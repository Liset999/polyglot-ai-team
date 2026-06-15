# 📝 SRE & 自动化引擎学习笔记

这个文件夹专门用于记录你在开发 `polyglot-ai-team` 过程中学到的 SRE 核心知识、操作系统底层原理、高频经典命令行细节以及大厂面试复盘。

## 🗂️ 目录索引

* [x] **2026-06-14**: Phase 1 最小内核核心地基（Exit Code 与标准流管道重定向机制）
* [x] **2026-06-15**: Polyglot AI Team OS v2 核心设计主张归档 与 v0 拆解器开发核心地基

---

## 📌 核心知识归档

### 1. 操作系统错误码与 Exit Code
* **Errno 2 (ENOENT)**: 文件或路径不存在。排查路径配置时的第一警示。
* **Exit Code 0**: 进程执行成功。
* **Exit Code 非 0 (1-255)**: 进程异常退出。
  * `137` (128 + 9): 代表进程被信号 `SIGKILL` (9) 强行杀死。最典型的场景是 **OOM (Out Of Memory) 内存耗尽**。

### 2. 标准输入/输出与管道机制
* **FD 0**: `stdin` (标准输入)
* **FD 1**: `stdout` (标准输出)
* **FD 2**: `stderr` (标准错误)
* **管道 (Pipe)**: 在内存中连接两个进程的缓冲区。父进程通过读管道，流式读取子进程输出，防止内存溢出。

### 3. API 安全设计：为什么无权限会返回 404？
* **HTTP 403 vs 404**: 
  * `403 Forbidden` 明确告诉客户端“资源存在，但你没有访问权限”。
  * `404 Not Found` 告诉客户端“资源不存在”。
  * **SRE 安全设计原则**：对于未授权的敏感资源，安全要求高的 API（如 Notion API）会故意返回 `404` 而不是 `403`。这样可以防止恶意攻击者通过暴力枚举（Brute-force）ID 来确认系统中存在哪些资源。

### 4. SRE 健壮性设计：为什么网络请求必须设置超时（Timeout）？
* **无限等待挂起**：Python 内置的 `urlopen` 如果不传 `timeout` 参数，在网络遇到半开连接（Half-Open Connection）或慢速攻击时，进程会无限期阻塞挂起。
* **SRE 最佳实践**：在生产环境中，任何对外网络请求、数据库查询、RPC 调用都**必须显式设置超时时间（如 `timeout=10`）**。这能防止单点堵塞导致整个系统的调用链路雪崩。

### 5. Notion API 块结构与行内 Markdown 解析
* **结构化 Block**：Notion API 不把页面当成一个大文本，而是当成一个由 **Block Objects** 组成的数组（如 `heading_1`, `paragraph`, `code` 等）。
* **富文本行内格式**：Notion 无法直接解析 `**加粗**` 这种 Markdown 语法。要实现加粗或行内代码框，必须在 API 请求中将文本拆解为多个富文本段，并设置 `annotations: {"bold": true, "code": true}`。我们为此在 `sync_notion.py` 中实现了一个**行内 Markdown 编译器**。

### 6. Polyglot AI Team OS v2 核心设计主张 (SRE & Architecture)
* **本地 Worker 优先 (Local-first Workforce)**：不强制云端托管或昂贵的第三方 API，直接自动发现并复用本地运行的 `Claude Code`、`Codex`、`OpenClaw` 等 CLI Agent，将其作为子进程调度。这与 SRE 监控和管理本地守护进程（Daemons）的逻辑一致。
* **活性人类干预 (Human Steering)**：中途打断（Interrupt）、转向（Reroute）、暂停（Pause）是一等公民，而不是异常。系统需支持父进程捕获用户输入，动态调整下发的 Task Graph。
* **低 Token 结构化协调**：摒弃高成本、易发散的多 Agent 自由群聊（Chatroom），使用类似 Git Issue Lifecycle 和结构化任务板（Task Board）的形式传递上下文，每个 Worker 仅分配当前任务所需的最小上游摘要，防止上下文膨胀。

### 7. 越界路径与目录穿越安全防护 (Directory Traversal Defense)
* **安全漏洞根源**：如果程序允许使用外部输入（或大模型动态生成的路径）来落盘写入文件，攻击者可以通过传入 `../../etc/passwd` 或 `../../../../windows/system32/cmd.exe` 等相对路径，跳出目标存放目录，恶意篡改或覆盖系统关键文件。
* **SRE 安全防御**：在 `v0_planner.py` 中，我们计算绝对路径并利用 `startswith()` 进行白名单前缀检查：
  ```python
  abs_file_path = os.path.abspath(os.path.join(GENERATED_DIR, rel_path))
  if not abs_file_path.startswith(GENERATED_DIR):
      # 越界防范，拒绝写入
  ```
  这确保了不论大模型生成了什么路径，写入操作永远被死死锁在指定的 `artifacts/generated/` 文件夹中。这是任何资产管理和自动化部署平台的必备安全红线。

### 8. API 结构化控制与降级容灾设计 (Graceful Degradation)
* **JSON Mode 强校验**：调用 DeepSeek 等大模型（如新一代 `deepseek-v4-flash`，旧版 `deepseek-chat` 已于 2026 年废弃）时，通过传入 `"response_format": {"type": "json_object"}` 并在 System Prompt 中描述输出格式，强制要求 API 响应格式完全契合我们定义的 JSON 架构，无需编写繁琐的正则表达式或字符串清洗，极大降低了解析的复杂度。
* **离线降级方案（Fallback）**：当网络波动或无 Key 时，系统自动触发 Mock 降级策略，输出预设的文件骨架。在生产环境 SRE 架构中，任何第三方 API 依赖都**必须配备 Fallback 逻辑**以保证业务不因单点依赖断裂而彻底中断。
