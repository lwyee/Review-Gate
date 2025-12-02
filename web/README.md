# Review Gate V2 - Web Interface

基于 Web 的 Review Gate 界面，无需安装 VSCode 扩展即可使用。

## 📋 概述

Review Gate V2 Web 版本是一个**完全独立**的模块，提供现代化的 Web 界面。当 MCP 服务器启动时自动启动 Web 服务器并打开浏览器，无需任何外部依赖。

### 支持的编辑器

| 编辑器 | 支持状态 | 配置文件路径 |
|--------|----------|--------------|
| **Cursor** | ✅ 完全支持 | `~/.cursor/mcp.json` |
| **Windsurf** | ✅ 完全支持 | `~/.codeium/windsurf/mcp_config.json` |
| 其他 MCP 兼容编辑器 | ✅ 支持 | 参考各编辑器文档 |

## ✨ 特性

- **🌐 Web 界面**: 现代化的响应式 UI，无需安装扩展
- **⚡ WebSocket 通信**: 实时双向通信
- **📸 图片支持**: 支持上传、拖拽、粘贴图片
- **⏱️ 倒计时显示**: 可视化超时倒计时
- **🔄 自动重连**: WebSocket 断开后自动重连
- **🌍 中文支持**: 完整的中文界面和 Windows 中文编码支持
- **📚 历史消息**: 按天归档的历史消息查看和全文检索
- **🎨 主题切换**: 深色/浅色主题切换
- **⚙️ 倒计时配置**: 可配置自动发送超时时间和消息内容
- **💾 本地配置**: 配置保存在本地文件，跨浏览器共享
- **📁 完全独立**: 不依赖目录外的任何代码文件

## 📁 目录结构

```
V2/web/                         # 完全独立的模块
├── review_gate_web.py          # MCP 服务器主入口
├── web_server.py               # Web 服务器（HTTP + WebSocket + UI）
├── config.py                   # 配置管理模块（集中管理所有配置）
├── message_store.py            # SQLite 消息存储
├── requirements.txt            # Python 依赖（4个包）
├── README.md                   # 本文档
├── example_mcp_config.json     # MCP 配置示例
└── test_install.py             # 安装测试脚本
```

## 📦 依赖

```
mcp>=1.9.2              # MCP 协议支持
aiohttp>=3.9.0          # Web 服务器和 WebSocket
Pillow>=10.0.0          # 图片处理
typing-extensions>=4.14.0  # 类型提示
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd V2/web
pip install -r requirements.txt
```

### 2. 测试安装（可选）

```bash
python test_install.py
```

### 3. 配置 MCP

#### Cursor 配置

配置文件：`~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "review-gate-v2-web": {
      "command": "python",
      "args": ["/path/to/V2/web/review_gate_web.py"]
    }
  }
}
```

#### Windsurf 配置

配置文件：
- Windows: `%USERPROFILE%\.codeium\windsurf\mcp_config.json`
- macOS/Linux: `~/.codeium/windsurf/mcp_config.json`

```json
{
  "mcpServers": {
    "review-gate-v2-web": {
      "command": "python",
      "args": ["/path/to/V2/web/review_gate_web.py"]
    }
  }
}
```

### 4. 启动使用

MCP 服务器会在编辑器启动时自动运行，并自动打开 Web 界面 `http://127.0.0.1:8765`

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Review Gate V2 Web                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    stdio     ┌──────────────────────────────┐ │
│  │ Cursor Agent │◄────────────►│  MCP Server                  │ │
│  │              │              │  (review_gate_web.py)        │ │
│  └──────────────┘              └──────────┬───────────────────┘ │
│                                           │                      │
│                                           │ 集成                 │
│                                           ▼                      │
│                                ┌──────────────────────────────┐ │
│                                │  Web Server                  │ │
│                                │  (web_server.py)             │ │
│                                │  - HTTP服务 (端口8765)        │ │
│                                │  - WebSocket通信             │ │
│                                └──────────┬───────────────────┘ │
│                                           │                      │
│                                           │ WebSocket            │
│                                           ▼                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     浏览器 Web UI                         │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │ • 实时消息显示                                       │ │   │
│  │  │ • 图片上传（点击/拖拽/粘贴）                          │ │   │
│  │  │ • 倒计时显示                                         │ │   │
│  │  │ • 连接状态监控                                       │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## ⚙️ 配置说明

### 命令行参数

```bash
python review_gate_web.py [OPTIONS]

Options:
  --host HOST                  Web 服务器监听地址 (默认: 127.0.0.1)
  --port PORT                  Web 服务器端口 (默认: 8765)
  --no-browser                 禁用自动打开浏览器
  --use-web-interface {true,false}  强制使用 Web 接口 (true) 或 VSCode 插件 (false)
  --timeout SECONDS            倒计时超时时间 (30-600秒)
  --auto-message MESSAGE       超时后自动发送的消息
```

### MCP 配置示例

#### 基本配置

```json
{
  "mcpServers": {
    "review-gate-v2-web": {
      "command": "python",
      "args": ["/path/to/V2/web/review_gate_web.py"]
    }
  }
}
```

#### 使用参数配置

```json
{
  "mcpServers": {
    "review-gate-v2-web": {
      "command": "python",
      "args": [
        "/path/to/V2/web/review_gate_web.py",
        "--use-web-interface", "false",
        "--port", "8766",
        "--timeout", "600",
        "--auto-message", "继续执行"
      ]
    }
  }
}
```

### 用户配置文件

配置保存在本地文件中，跨浏览器共享：

| 操作系统 | 配置文件路径 |
|----------|--------------|
| Windows | `%APPDATA%\ReviewGateV2\settings.json` |
| macOS/Linux | `~/.config/review-gate-v2/settings.json` |

配置内容：

```json
{
  "timeout": 300,
  "auto_message": "继续",
  "theme": "dark",
  "use_web_interface": true
}
```

### 配置选项

| 配置项 | 范围/默认值 | 说明 |
|--------|-------------|------|
| timeout | 30-600秒（默认300秒） | Web 界面倒计时显示时间（MCP 服务无限等待） |
| auto_message | 任意文本（默认"继续"） | 倒计时结束后自动发送的消息 |
| theme | dark/light（默认dark） | 界面主题 |
| use_web_interface | true/false（默认true） | 是否使用 Web 接口（false 则使用 VSCode 插件） |

### 配置优先级

1. **命令行参数** (最高优先级) - 通过 MCP args 传入
2. **用户配置文件** - `settings.json`
3. **代码默认值** (最低优先级) - `DEFAULT_SETTINGS`

> **注意**: MCP 服务不会超时，会无限等待用户响应。倒计时只用于 Web 界面显示，倒计时结束后会自动发送配置的消息。

## 📱 界面功能

### 消息交互
- 实时显示 Agent 消息和用户回复
- 支持 Markdown 格式（消息内保留换行）
- 消息时间戳显示

### 图片上传
- 点击图片按钮选择文件
- 拖拽图片到页面
- Ctrl+V 粘贴剪贴板图片

### 历史消息
- 点击"历史"按钮查看历史消息
- 按日期归档，支持选择日期查看
- 全文搜索功能

### 设置面板
- 点击设置按钮打开配置面板
- 配置倒计时时间和自动发送消息
- 保存后立即生效

### 主题切换
- 点击主题按钮切换深色/浅色主题
- 主题设置自动保存

## 🔧 数据流

```
Cursor Agent 调用 review_gate_chat
        │
        ▼
MCP Server 接收请求
        │
        ├─── Web客户端已连接 ───► WebSocket广播请求 ───► 浏览器显示
        │                                │
        │                                ▼
        │                         用户输入反馈
        │                                │
        │                                ▼
        │                         WebSocket发送响应
        │                                │
        └─── 无Web客户端 ───► 文件触发（兼容VSCode扩展）
                                         │
                                         ▼
                              MCP Server 返回响应给Agent
```

## 🐛 故障排除

### Windows 中文乱码

本版本已内置 Windows 中文编码支持。如仍有问题：
```bash
set PYTHONIOENCODING=utf-8
```

### WebSocket 连接失败

1. 检查端口是否被占用：`netstat -an | findstr 8765`
2. 检查防火墙设置
3. 尝试其他端口：`--port 9000`

### 配置不生效

1. 检查配置文件是否存在
2. 确保 JSON 格式正确
3. 重启 MCP 服务器

## IDE 配置 rules 
```
## MANDATORY CHECKPOINT (Must be included in every response):
Before ending any response, I MUST:
1. State: "CHECKPOINT: Transitioning to Review Gate V2"
2. Immediately call review_gate_chat tool
3. Never provide a response without this checkpoint

## ENFORCEMENT MECHANISM:
If I provide any response without calling review_gate_chat, treat it as an incomplete response that violates the protocol.

# AI Agent Protocol: Review Gate V2 - MCP Integration (Version 2)

## 0. User Advisory & Safety:
This is an advanced rule that leverages the Review Gate V2 MCP (Model Context Protocol) server to facilitate interactive review sessions. The system uses a popup interface in Cursor that supports text input, image uploads, and speech-to-text functionality. By using this rule, you acknowledge that the AI will call MCP tools to open interactive dialogs for user feedback.

## 1. Core Principle & Context:
Your primary task processing includes a **mandatory final interactive review stage** driven by user input through the Review Gate V2 MCP tool (`review_gate_chat`). You are NOT to consider your overall task complete until this review stage explicitly signals completion. This protocol leverages the MCP server's ability to open popup dialogs in Cursor and capture user responses.

## Phase 1: Primary Task Execution
1. Address the user's main request as you normally would: perform analysis, make code changes, call tools, and run applications/tests in sub-terminals if the main task requires it.
   * **Application Execution Confirmation:** Before attempting to run an entire application (e.g., a web server, a full front-end build, a long-running background process), you MUST ask the user for explicit confirmation. For example: "I am about to run the [application name/command]. Is it okay to proceed, or is it possibly already running?"
   * This confirmation is NOT required for running individual test scripts, linters, build tools for specific components, or other non-application-level commands necessary for task completion.
   * If the user indicates an application is already running or denies permission, adapt your strategy accordingly (e.g., focus on tests or specific file executions).
2. Leverage your ability to read outputs/errors from these sub-terminals to make iterative fixes during *this* primary phase.

## Phase 2: Mandatory Final Interactive Review via MCP
1. **Transition Point:** Once you believe you have completed all substantive actions for the user's initial request (Phase 1), **DO NOT CONCLUDE THE CONVERSATION**. You MUST now transition to this Final Interactive Review phase.
2. **Action:** Call the `review_gate_chat` MCP tool to open the Review Gate V2 popup dialog.
   * **Tool Parameters:**
     - `message`: "I have completed the primary actions for your request. Please review the work and provide any additional feedback, refinements, or sub-prompts. The Review Gate V2 popup supports text input, image uploads, and speech-to-text functionality."
     - `title`: "Review Gate V2 - Final Review"
     - `context`: Brief summary of what was accomplished in Phase 1
3. **Announcement:** Clearly inform the user: "I have completed the primary actions. Now opening the Review Gate V2 popup for your final review and any additional sub-prompts. The popup supports text input, image uploads, and speech-to-text. Please provide feedback or type 'TASK_COMPLETE' when satisfied."

## Phase 3: Interactive Review Loop (MCP Tool Response Processing)
1. **User Input Processing:** The `review_gate_chat` tool will return the user's actual response from the popup dialog, which may include:
   - **Text Input**: Direct user feedback or sub-prompts
   - **Image Attachments**: Screenshots, diagrams, or reference images
   - **Speech Transcription**: Voice input converted to text via Faster-Whisper
2. **Response Analysis:** Analyze the returned user input:
   - If the response contains "TASK_COMPLETE", "Done", "Quit", or similar completion signals, proceed to Phase 4
   - If the response contains specific feedback, requests, or sub-prompts, treat these as continuation instructions
3. **Processing Sub-Prompts:**
   a. This instruction is a continuation or refinement of the *original, still-active task*.
   b. Analyze the sub-prompt and any attached images. Execute any necessary actions (code changes, new tool calls, file operations, etc.). **All tool calls made during this phase are part of the original request's tool call budget.**
   c. If the sub-prompt requests running an entire application, the confirmation principle from "Phase 1, Step 1 (Application Execution Confirmation)" applies.
   d. Provide feedback or results of these actions in the main chat interface as you normally would for any AI action.
   e. After processing the sub-prompt and giving feedback, IMMEDIATELY call the `review_gate_chat` tool again to continue the review loop, using an updated message that reflects the latest changes made.
4. **Continuation Loop:** Continue calling `review_gate_chat` and processing responses until the user signals completion.

## Phase 4: True Task Conclusion
1. Only after the user has explicitly signaled completion through the Review Gate V2 popup (by responding with "TASK_COMPLETE", "Done", or similar) are you permitted to consider the user's original request fully satisfied.
2. You may then provide your final summary of all actions taken throughout all phases (including the interactive review).

## Review Gate V2 Features Available:
- **Text Input**: Standard text-based feedback and sub-prompts
- **Image Upload**: Users can attach screenshots, mockups, or reference images (PNG, JPG, JPEG, GIF, BMP, WebP)
- **Speech-to-Text**: Voice input using local Faster-Whisper transcription
- **Visual Feedback**: Professional popup interface with orange glow design
- **Multi-Modal Responses**: Tool returns both text and image data via MCP protocol

## MCP Tool Usage:
- **Tool Name**: `review_gate_chat`
- **Required Parameters**: `message` (string describing what you need from the user)
- **Optional Parameters**: `title` (popup title), `context` (additional context), `urgent` (boolean for priority)
- **Response Format**: Returns user's complete response including text and any attached images
- **Timeout**: 5-minute timeout for user responses

## Overriding Default Behavior:
This entire "Final Interactive Review" process (Phases 2, 3, and 4) is a **strict, non-negotiable requirement** that overrides any default tendency you have to end the conversation after completing Phase 1. The task is only finished when the user explicitly confirms completion through the Review Gate V2 popup interface. Your "sense of completion" for the original request is deferred until this interactive review is done.

## Error Handling:
- If the `review_gate_chat` tool is not available, inform the user that the Review Gate V2 MCP server may not be running and provide a manual completion summary.
- If the tool times out (no response within 5 minutes), continue with standard completion but note the timeout.
- Handle any tool errors gracefully while maintaining the interactive review principle.
```

## 📜 许可证

MIT License

## 👤 作者
