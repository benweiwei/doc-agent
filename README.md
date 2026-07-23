# Doc-Agent

AI 驱动的文档编辑助手，提供类 Cursor 的智能编辑体验。

## 功能特性

- **AI 辅助文档编辑** — 自然语言指令驱动，智能理解编辑意图
- **Markdown 源码编辑** — 支持 Visual/Source 双模式切换，源码模式直接编辑 Markdown
- **版本管理 + 多分支** — 支持多交付对象，独立分支并行编辑
- **文档-分支解耦视图** — 文档作为一等实体，分支作为筛选条件，跨分支统一视图
- **个人行文风格学习** — 自动学习并复用你的写作习惯
- **文风模板管理** — 支持导入、创建、编辑和应用文风模板，AI 编辑时可选择风格
- **参考文库风格模板** — 内置多种文档风格模板，一键切换
- **实时 Diff 对比预览** — 编辑前后实时对比，改动一目了然
- **文档级上下文管理** — 交互记录按文档+分支关联，AI 编辑时自动注入历史对话上下文
- **交互记录持久化** — 全部 AI 交互记录持久化存储，支持按文档/分支筛选查看
- **文档导出** — 支持导出为 .md / .txt 格式
- **中英文国际化** — 界面支持中英文一键切换，自动检测浏览器语言偏好
- **云端/本地模型自由切换** — 支持 Anthropic、OpenAI、Ollama 等多种后端
- **跨平台** — 支持 Mac / Linux / Windows

## 快速开始

```bash
# 1. 安装
pip install -e .

# 2. 初始化配置
cp config.example.yaml ~/.doc-agent/config.yaml
# 编辑配置文件设置 API key

# 3. 启动服务
doc-agent serve
```

启动后浏览器会自动打开编辑器界面。

## 配置说明

配置文件位于 `~/.doc-agent/config.yaml`，主要配置项：

| 配置段 | 说明 |
|--------|------|
| `server.host` / `server.port` | 服务绑定地址与端口（默认 127.0.0.1:3966） |
| `model.provider` | 模型提供方：`anthropic` / `openai` / `ollama` |
| `model.name` | 模型名称 |
| `model.temperature` | 生成温度 |
| `style.tone` | 行文风格（professional / casual 等） |
| `style.language` | 文档语言（zh-CN / en 等） |
| `workspace.root` | 文档工作区根目录 |
| `workspace.branch_prefix` | 分支命名前缀（默认 `target/`） |

## CLI 命令

```bash
doc-agent serve              # 启动服务（主入口）
doc-agent init [--path DIR]  # 初始化工作区
doc-agent config set KEY VAL # 设置配置项
doc-agent config get [KEY]   # 查看配置
doc-agent config show        # 显示完整配置
doc-agent --version          # 版本信息
```

## 开发者指南

```bash
# 后端
pip install -e ".[dev]"
pytest tests/ -v
python3 -m uvicorn doc_agent.server:app --host 127.0.0.1 --port 3966

# 前端
cd frontend && npm install
npx vite --port 5173 --strictPort
```

前端开发服务器默认运行在 `http://localhost:5173`，会自动代理 API 请求到后端。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI + Uvicorn |
| AI 接入 | Anthropic / OpenAI / Ollama |
| 版本控制 | GitPython |
| 前端框架 | React 18 + TypeScript |
| 状态管理 | useReducer + Context API |
| 富文本编辑 | Tiptap + tiptap-markdown |
| 国际化 | React Context + localStorage |
| 构建工具 | Vite |
| 包管理 | pip (setuptools) / npm |

## License

MIT
