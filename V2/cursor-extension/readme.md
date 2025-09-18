# Review Gate V2 ゲート - Cursor Extension

[![Version](https://img.shields.io/badge/version-2.7.3-orange.svg)](https://github.com/your-repo/review-gate-v2)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Cursor](https://img.shields.io/badge/Cursor-Extension-brightgreen.svg)](https://cursor.sh)

> 高级审查门系统，集成MCP (Model Context Protocol) 为Cursor IDE提供智能交互体验

## 🚀 项目简介

Review Gate V2 是一个为 Cursor IDE 设计的高级扩展，通过 MCP (Model Context Protocol) 集成提供智能的代码审查和反馈系统。该扩展支持多模态输入，包括文本、图像上传和语音转文字功能，为开发者提供无缝的AI交互体验。

### ✨ 核心特性

- **🎯 MCP集成**: 与Cursor AI Agent深度集成，支持实时通信
- **💬 智能聊天界面**: 现代化的聊天UI，支持消息历史和状态指示
- **🖼️ 多媒体支持**: 
  - 图像拖拽上传
  - 剪贴板图像粘贴
  - 多种图像格式支持 (PNG, JPG, JPEG, GIF, BMP, WebP)
- **🎤 语音转文字**: 基于SoX和Faster-Whisper的本地语音识别
- **⚡ 实时状态监控**: MCP服务器状态实时显示
- **🔄 自动化工作流**: 支持多种工具调用和响应模式

## 📦 安装使用

### 前提条件

- **Cursor IDE** (版本 >= 1.60.0)
- **Node.js** (推荐版本 >= 16.x)
- **SoX** (语音功能所需)
  ```bash
  # macOS
  brew install sox
  
  # Ubuntu/Debian
  sudo apt-get install sox
  
  # Windows
  # 下载并安装 SoX from https://sox.sourceforge.net/
  ```

### 安装扩展

1. **从VSIX文件安装**:
   ```bash
   # 在Cursor中打开命令面板 (Cmd+Shift+P / Ctrl+Shift+P)
   # 输入: Extensions: Install from VSIX...
   # 选择 review-gate-v2-2.7.3.vsix 文件
   ```

2. **手动安装**:
   - 下载 `review-gate-v2-2.7.3.vsix` 文件
   - 在Cursor中: 扩展 → 从VSIX安装
   - 选择下载的文件

### 快速开始

1. **激活扩展**: 安装后扩展会自动激活
2. **打开Review Gate**: 
   - 使用快捷键: `Cmd+Shift+R` (Mac) / `Ctrl+Shift+R` (Windows/Linux)
   - 或通过命令面板: `Review Gate: Open Review Gate v2`
3. **开始使用**: 在聊天界面中输入消息或使用语音功能

## 🔧 功能详解

### MCP消息展示功能

Review Gate V2 在聊天窗口中展示MCP相关的消息和状态，当前支持以下消息展示：

#### 当前消息展示功能

1. **用户发送的消息**: 
   ```
   👤 用户: "微积分证明"
   👤 用户: "cursor聊天窗口输出"
   👤 用户: "现在时间是多少"
   ```

2. **系统确认消息** (发送后的随机确认):
   ```
   🍕 Delivered faster than pizza on a Friday night!
   🤖 Your wisdom has been transmitted to the digital overlords!
   📁 Message received and filed under 'Probably Important'!
   ⚡ Message delivered! Agent is probably doing agent things now...
   🧠 Your input is now part of the agent's master plan!
   ```

3. **MCP状态指示**:
   ```
   🟢 MCP Active - 绿色圆点表示MCP服务器连接正常
   🟠 MCP Inactive - 橙色圆点表示MCP服务器未连接
   ```

4. **语音和图像处理消息**:
   ```
   🎤 Recording started...
   📝 Speech transcription completed
   🖼️ Image uploaded: filename.png (125.4 KB)
   ```

#### 消息接收展示说明

**注意**: 当前版本主要展示**发送给MCP的消息**和**系统状态**，而**来自MCP服务器的响应消息**需要在Cursor主聊天界面中查看。

#### 消息流向图示

```
用户输入 → Review Gate界面 → MCP服务器 → Cursor Agent → Cursor主界面
   ↑                ↓
显示确认消息    显示发送状态     (Agent响应在主界面显示)
```

**为什么不能看到接收的消息？**

1. **架构设计**: Review Gate主要作为**输入工具**，专注于收集用户反馈
2. **MCP协议**: 服务器响应直接返回给Cursor Agent，不会回传到Review Gate
3. **界面分离**: Agent的处理结果和回复显示在Cursor主聊天界面
4. **单向通信**: 当前实现为单向发送模式，确保消息准确传递给Agent

**如何查看Agent的回复？**
- 在Cursor主界面的聊天窗口中查看Agent的回复
- Review Gate发送消息后，切换到Cursor主界面查看处理结果

#### 增强消息接收显示 (未来版本)

为了更好地展示接收到的MCP消息，可以考虑添加：

```javascript
// 示例：未来可能的消息接收显示
🔄 MCP Request: "请审查这段代码"
📨 Agent Message: "我需要你的反馈..."
⚡ Tool Call: review_gate_chat
✅ Response Sent: "代码看起来不错，但建议添加错误处理"
```

#### 消息展示配置

消息在聊天窗口中按以下方式展示：

- **实时状态指示器**: 橙色/绿色圆点显示MCP连接状态
- **消息分类**: 系统消息、用户消息、错误消息使用不同样式
- **时间戳**: 每条消息都带有精确的时间戳
- **交互反馈**: 发送消息后显示有趣的确认信息

### 语音功能

- **一键录音**: 点击麦克风图标开始/停止录音
- **实时反馈**: 录音状态实时显示
- **自动转录**: 使用Faster-Whisper进行本地转录
- **错误处理**: 详细的错误提示和故障排除建议

### 图像处理

- **多种上传方式**: 
  - 拖拽文件到聊天窗口
  - 从剪贴板粘贴图像
  - 点击附件按钮选择文件
- **预览功能**: 上传的图像支持预览和删除
- **格式支持**: PNG, JPG, JPEG, GIF, BMP, WebP

## 💡 功能增强建议

### 增强MCP消息接收显示

如果需要在Review Gate聊天窗口中显示更多来自MCP的消息，可以考虑以下技术方案：

#### 1. 监听MCP响应文件
```javascript
// 在extension.js中添加响应文件监听
function watchMcpResponses() {
    const responsePattern = getTempPath('mcp_agent_response_*.json');
    // 监听Agent响应文件并在聊天窗口显示
}
```

#### 2. 解析工具调用内容
```javascript
// 显示更详细的工具调用信息
function displayToolCallDetails(toolData) {
    const message = `
🔧 工具调用: ${toolData.tool}
📝 消息: ${toolData.message}
⚡ 触发ID: ${toolData.trigger_id}
    `;
    // 发送到聊天窗口显示
}
```

#### 3. 双向消息同步
```javascript
// 实现Agent消息的实时同步显示
function syncAgentMessages() {
    // 监听Cursor Agent的消息并在Review Gate中显示
    // 实现真正的双向消息展示
}
```

#### 当前限制说明

- **单向显示**: 目前主要显示用户输入和系统确认
- **MCP协议限制**: MCP响应直接返回给Cursor Agent
- **界面分离**: Review Gate作为输入工具，主要聊天在Cursor界面

## 🛠️ 开发与构建

### 开发环境设置

```bash
# 克隆项目
git clone <repository-url>
cd cursor-extension

# 安装依赖
npm install

# 安装VSCE工具 (如果还没安装)
npm install -g @vscode/vsce
```

### VSIX打包命令

使用以下命令打包扩展为VSIX文件：

```bash
# 基础打包命令
npm run package

# 或者直接使用vsce
vsce package

# 指定版本打包
vsce package --version 2.7.4

# 打包并忽略某些文件
vsce package --out review-gate-v2.vsix

# 详细输出打包过程
vsce package --verbose

# 预发布版本打包
vsce package --pre-release
```

### 打包配置说明

在 `package.json` 中已配置的打包脚本：

```json
{
  "scripts": {
    "package": "vsce package"
  },
  "devDependencies": {
    "@vscode/vsce": "^2.32.0"
  }
}
```

### 打包前检查

```bash
# 检查扩展包内容
vsce ls

# 验证扩展配置
vsce verify

# 发布前测试 (不实际发布)
vsce publish --dry-run
```

## 📋 使用示例

### 基本工作流

1. **启动Review Gate**:
   ```
   Cmd+Shift+R → 打开Review Gate界面
   ```

2. **MCP工具调用**:
   ```
   Cursor Agent → 调用 review_gate_chat → 弹出Review Gate
   ```

3. **多模态输入**:
   ```
   文本输入 + 图像附件 + 语音输入 → 发送给Agent
   ```

4. **响应处理**:
   ```
   Agent接收响应 → 处理反馈 → 继续对话
   ```

### 高级用法

- **批量图像上传**: 同时拖拽多个图像文件
- **语音命令**: 使用语音输入复杂的代码审查意见
- **MCP状态监控**: 实时查看MCP服务器连接状态

## 🔍 故障排除

### 常见问题

1. **MCP连接失败**:
   - 检查MCP服务器是否运行
   - 查看临时文件目录权限

2. **语音功能不工作**:
   ```bash
   # 检查SoX安装
   sox --version
   
   # 测试麦克风
   sox -d test.wav trim 0 3
   ```

3. **图像上传失败**:
   - 检查图像文件格式
   - 确认文件大小限制

### 日志查看

- **扩展日志**: Cursor → 输出 → Review Gate V2 ゲート
- **MCP日志**: 临时目录中的 `review_gate_v2.log`
- **用户输入日志**: `review_gate_user_inputs.log`

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

### 开发流程

1. Fork 项目
2. 创建功能分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'feat: 添加amazing功能'`
4. 推送到分支: `git push origin feature/amazing-feature`
5. 提交Pull Request

### 代码规范

- 使用中文编写commit message
- 遵循JavaScript标准代码风格
- 添加适当的注释和文档

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 👤 作者

**Lakshman Turlapati**

- GitHub: [@LakshmanTurlapati](https://github.com/LakshmanTurlapati)
- Email: lakshman@example.com

## 🙏 致谢

- Cursor团队提供的优秀IDE平台
- MCP协议的开发者们
- SoX和Faster-Whisper项目
- 所有贡献者和用户

---

<div align="center">

**[⬆ 回到顶部](#review-gate-v2-ゲート---cursor-extension)**

Made with ❤️ for the Cursor community

</div>
