# 更新日志

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
