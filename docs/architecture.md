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
| Agent | `doc_agent/agent.py` | 核心编辑引擎，协调 LLM 完成文档编辑任务 |
| VCS | `doc_agent/vcs.py` | 版本控制层，封装 Git 操作（分支、提交、Diff） |
| LLM | `doc_agent/llm/` | LLM 抽象层，支持多 Provider 切换 |
| Style | `doc_agent/style/` | 行文风格引擎（模板管理 + 个人习惯学习） |
| Config | `doc_agent/config.py` | 配置加载与管理 |
| Frontend | `frontend/src/` | React SPA，提供编辑器 UI |

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
| `/ws` | 实时编辑通道（发送指令、接收 diff 结果和状态更新） |
