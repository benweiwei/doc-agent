# 系统架构

## 架构概览

```
┌─────────────────────────────────────────────────┐
│                  Frontend (React)                │
│  Editor │ DiffView │ BranchPanel │ HistoryPanel │
└────────────────────┬────────────────────────────┘
                     │ HTTP / WebSocket
┌────────────────────▼────────────────────────────┐
│               FastAPI Server                     │
│  REST API  │  WebSocket Handler  │  Static Files │
└─────┬──────────────┬──────────────────┬─────────┘
      │              │                  │
┌─────▼─────┐ ┌─────▼──────┐ ┌────────▼────────┐
│   Agent   │ │    VCS     │ │  Style Engine   │
│(LLM 调度) │ │(Git 版本控制)│ │(风格模板+习惯)  │
└─────┬─────┘ └────────────┘ └─────────────────┘
      │
┌─────▼─────────────────────┐
│      LLM Providers        │
│ Anthropic│OpenAI│Ollama   │
└───────────────────────────┘
```

## 模块职责

| 模块 | 路径 | 职责 |
|------|------|------|
| CLI | `doc_agent/cli.py` | 命令行入口，启动服务、初始化工作区、管理配置 |
| Server | `doc_agent/server.py` | FastAPI 应用，REST API + WebSocket + 静态文件托管 |
| Agent | `doc_agent/agent.py` | 核心编辑引擎，协调 LLM 完成单发文档编辑任务 |
| Agent Loop | `doc_agent/agent_loop.py` | 多步工具调用会话，驱动 LLM 迭代调用工具完成复杂编辑 |
| Tools | `doc_agent/tools/` | 工具系统：文档读写工具 + 联网搜索工具（可插拔后端） |
| VCS | `doc_agent/vcs.py` | 版本控制层，封装 Git 操作（分支、提交、Diff） |
| LLM | `doc_agent/llm/` | LLM 抽象层，支持多 Provider 切换与工具调用（function calling） |
| Style | `doc_agent/style/` | 行文风格引擎（模板管理 + 个人习惯学习） |
| Config | `doc_agent/config.py` | 配置加载与管理（模型 / 工作区 / Agent / 搜索后端） |
| Frontend | `frontend/src/` | React SPA，提供编辑器 UI（含 Agent 模式） |

## 数据流：编辑请求链路

```
1. 用户在 Editor 输入自然语言指令
       │
2. InstructionBar 通过 WebSocket 发送 EditRequest
       │
3. Server 接收请求，创建 Agent 实例
       │
4. Agent 组装 prompt（文档内容 + 用户指令 + 风格约束）
       │
5. Agent 调用 LLM Provider 生成编辑结果
       │
6. Agent 返回 diff，Server 通过 WebSocket 推送给前端
       │
7. 前端 DiffView 展示对比，用户确认后提交
       │
8. VCS 层创建 commit，记录变更历史
```

## API 概览

### REST

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/documents` | 文档列表 |
| GET | `/api/documents/{id}` | 获取文档内容 |
| POST | `/api/documents` | 创建文档 |
| GET | `/api/branches` | 分支列表 |
| POST | `/api/branches` | 创建分支 |
| GET | `/api/history` | 提交历史 |
| GET | `/api/styles/templates` | 风格模板列表 |

### WebSocket

| 端点 | 说明 |
|------|------|
| `/ws/edit` | 实时编辑通道（按消息 `type` 分发：`edit` 单发流式编辑 / `agent` 多步循环） |
| `/ws/agent` | Agent 通道（与 `/ws/edit` 共享分发逻辑，推送 step / tool_call / tool_result / token / complete / error 事件） |

> 两个端点均使用共享的 `_ws_dispatch_loop`，实际行为由消息 `type` 决定，与连接的 URL 解耦，避免模式切换时的重连竞态。

## Agent Loop：多步工具调用

```
1. 用户开启 Agent 模式并输入指令
       │
2. AgentSession 组装 system prompt + 工具声明（读/列/搜/编辑文档 + 联网搜索）
       │
3. LLM 迭代决策：调用工具 → 执行 → 结果回灌，直到产出最终编辑（受 max_steps 限制）
       │
4. 每一步以事件流经 WebSocket 推送前端（time line 实时展示）
       │
5. apply_edit 仅修改内存工作副本并生成 diff；用户确认后走既有 commit 流程落盘
```

| 工具 | 说明 |
|------|------|
| `read_document` / `list_documents` / `search_documents` | 读取、列出、检索工作区文档 |
| `apply_edit` | 写入完整新内容到内存工作副本（不立即提交） |
| `web_search` | 联网搜索，后端可选 duckduckgo / tavily / brave / bocha |

## 数据存储与持久化

均为本地文件存储，无数据库。以下路径以默认工作区 `~/.doc-agent` 为例。

| 数据 | 位置 | 说明 |
|------|------|------|
| 历史文档 / 版本 | `~/.doc-agent/workspace`（Git 仓库） | 文档为 `.md` 文件，每次保存/Accept 产生一次 commit，多分支隔离；历史面板读取 git log |
| AI 交互记录 | `~/.doc-agent/workspace/.doc-agent/interactions.json` | 经 `/api/interactions` 增改查，仅保留最近 200 条；同时作为 AI 编辑时注入的“文档+分支”历史上下文（取最近 5 条 completed） |
| 个人习惯画像 | `~/.doc-agent/habit_profile.json` | 由 `HabitAnalyzer` 从历史文档统计（句长/段长、高频词、标点、句首/段首、连接词等）；`/api/styles/learn` 触发，支持增量更新（旧0.7/新0.3 加权） |
| 风格模板（含导入） | 用户：`~/.doc-agent/styles/*.yaml`；内置：`doc_agent/style/templates/*.yaml` | YAML 格式；内置 3 个（casual_blog / formal_report / technical_doc，只读），用户创建/导入的存用户目录，同名时用户优先 |
| 上传图片资源 | `~/.doc-agent/assets/` | 位于 Git 工作区之外，不进文档 git 历史；经 `/api/assets` 上传/服务 |

> 习惯画像、风格模板、图片资源均在工作区之外的 `~/.doc-agent/` 下，不会被纳入文档的 Git 版本历史；而交互记录位于工作区内的 `.doc-agent/`。

## 编辑模式：Agent vs 单发

- **单发编辑**（消息 `type=edit`，`DocumentEditor.edit_document_stream`）：一次 prompt → 流式生成，适合直接改写。
- **Agent 模式**（消息 `type=agent`，`AgentSession.run`，前端默认开启）：多步工具调用循环（最多 `max_steps` 步），可读取其他文档、联网检索后再动笔；模型不支持 function calling 时自动回退到单发路径。
- 两者共享同一 system prompt 组装（风格模板 + 习惯画像 + 该文档历史上下文），且均不自动提交，由用户 Accept 后走 `/api/edit/commit` 落盘。
