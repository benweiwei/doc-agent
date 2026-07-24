# 更新日志

## v1.2.2 (2026-07-24)

### 修复

- 导出/预览图片无法显示：资源接口按扩展名返回正确图片 MIME（原为 text/plain 导致浏览器拒绝渲染）；HTML 导出将图片内联为 base64 data URI，使导出完全自包含

### 变更

- 默认开启 Agent 模式（前端打开即为多步工具调用模式，仍可手动切回单发编辑）

### 文档

- `docs/architecture.md` 新增“数据存储与持久化”（历史文档/交互记录/习惯画像/风格模板/图片资源）与“编辑模式：Agent vs 单发”说明

## v1.2.1 (2026-07-24)

### 编辑器增强

- Mermaid 代码块渲染：光标在 ```mermaid 块内显示可编辑源码，光标离开（结束编辑）时自动渲染为 SVG 图；渲染失败保留源码并提示错误，点击图可重新编辑
- 插入流程图：工具栏新增「插入流程图」按钮，直接插入带起始模板的 Mermaid 源码块供手写
- 图片缩放：选中图片可拖拽右下角手柄调整大小，宽度经 `<img width>` 持久化到 Markdown
- 全屏编辑：工具栏新增全屏切换按钮，覆盖视口编辑，Esc 退出

### 依赖

- 新增前端依赖：`mermaid`

## v1.2.0 (2026-07-24)

### 新增功能

- 编辑器图片导入：接入 `@tiptap/extension-image`，工具栏「插入图片」上传到后端并插入文档
- 代码转架构图：选中代码经 LLM 生成 Mermaid 定义并插入代码块
- 丰富导出：导出菜单新增 HTML（自包含，内嵌样式 + mermaid CDN 渲染，相对图片转绝对）
- 编辑自动保存：停止输入约 2s 防抖自动提交，工具条含开关（localStorage 持久化，审阅 AI diff 期间不触发）

### 后端新增端点

- `POST /api/assets` + `GET /api/assets/{name}`：图片上传/服务（类型与大小校验、防路径穿越）
- `GET /api/export/{doc_id}?format=html`：Markdown 转自包含 HTML
- `POST /api/diagram/from-code`：代码转 Mermaid 定义

### 依赖

- 新增运行时依赖：`markdown`、`python-multipart`

## v1.1.0 (2026-07-24)

### 新增功能

- Agent 多步工具调用循环（Agent Loop）：AI 可自主读取、列出、搜索、编辑文档，并联网检索资料，多步迭代完成复杂编辑任务
- 工具系统（`doc_agent/tools/`）：文档读写工具 + 可插拔联网搜索工具，统一注册与调度
- 联网搜索多后端支持：DuckDuckGo（默认，免密钥）/ Tavily / Brave / 博查（Bocha），可通过配置切换
- LLM 工具调用能力：抽象层新增 `chat()` 接口与 `ToolSpec`/`ToolCall`/`ChatResult` 结构，Anthropic、OpenAI 均支持 function calling
- OpenAI 兼容模式：支持自定义 `base_url`，可对接阿里云百炼 MaaS 等 OpenAI 兼容端点
- 前端 Agent 模式：交互面板实时展示每一步工具调用、结果与最终编辑
- API 密钥直填：`config.yaml` 支持直接填写云模型与搜索后端密钥（优先于环境变量）

### 修复

- 修复 Agent/编辑模式切换时 WebSocket 重连竞态导致的“无输出 / Accept 后空白 / Unknown message type”问题：两个 WebSocket 端点改为按消息 `type` 统一分发，前端固定连接 URL

### 技术架构

- 新增配置：`agent`（max_steps / token_budget / enable_web_search / search 后端）
- WebSocket 共享分发循环 `_ws_dispatch_loop`，端点与消息类型解耦

## v1.0.0 (2026-07-23)

### 核心功能

- AI 辅助文档编辑：自然语言指令驱动，智能理解编辑意图
- Markdown 源码编辑：Visual/Source 双模式切换
- 版本管理 + 多分支：支持多交付对象，独立分支并行编辑
- 文档-分支解耦视图：文档作为一等实体，分支作为筛选条件
- 个人行文风格学习：自动学习并复用写作习惯
- 文风模板管理：支持导入、创建、编辑和应用文风模板
- 实时 Diff 对比预览：编辑前后实时对比
- 文档级上下文管理：交互记录按文档+分支关联，AI 编辑时注入历史上下文
- 交互记录持久化：全部 AI 交互记录持久化存储，支持按文档/分支筛选
- 文档导出：支持导出为 .md / .txt 格式
- 中英文国际化：界面中英文切换，自动检测浏览器语言偏好
- 云端/本地模型切换：支持 Anthropic、OpenAI、Ollama 等多种后端

### 技术架构

- 后端：FastAPI + Uvicorn + GitPython
- 前端：React 18 + TypeScript + Tiptap + Vite
- 状态管理：useReducer + Context API
- 国际化：React Context + localStorage + navigator.language 检测
