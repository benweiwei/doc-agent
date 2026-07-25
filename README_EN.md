# Doc-Agent

[中文文档](README.md) | English

An AI-powered document editing assistant that delivers a Cursor-like intelligent editing experience.

## Features

- **AI-assisted document editing** — Natural language instructions with intelligent edit-intent understanding
- **Zero-to-document generation** — No document open? Just type your requirement; a new document is created automatically and the AI drafts the content for you
- **Markdown source editing** — Visual / Source dual-mode, edit raw Markdown directly in source mode
- **Version management + multi-branch** — Multiple delivery targets with independent branches edited in parallel
- **Document–branch decoupled view** — Documents as first-class entities, branches as filters, unified cross-branch view
- **Personal writing-style learning** — Automatically learns and reuses your writing habits
- **Style template management** — Import, create, edit and apply writing-style templates; pick a style per AI edit
- **Built-in reference style library** — Multiple built-in document style templates, one-click switching
- **Real-time diff preview** — Compare before/after edits in real time, every change at a glance
- **Document-level context management** — Interaction history linked per document+branch, automatically injected into AI edits
- **Persistent interaction history** — All AI interactions persisted, filterable by document/branch
- **Document export** — Export to .md / .txt
- **Chinese / English i18n** — One-click UI language switching, auto-detects browser preference
- **Cloud / local model switching** — Supports Anthropic, OpenAI (and OpenAI-compatible endpoints), Ollama and more
- **Cross-platform** — macOS / Linux / Windows

## Screenshots

| Main editor (type a requirement directly) | Settings: style learning & templates |
|-------------------------------------------|--------------------------------------|
| ![Main editor](docs/images/screenshot-main.jpg) | ![Settings](docs/images/screenshot-settings.jpeg) |

## Demo

Requirement → auto-created document → Agent web search + full draft (37s):

![Demo](docs/images/demo.gif)

> 📼 [Watch the high-quality MP4 version](docs/images/demo.mp4)
>
> 📸 More screenshots coming: AI edit diff preview, Agent tool-call timeline, multi-branch view.

## Quick Start

```bash
# 1. Clone & install
git clone https://github.com/<your-username>/doc-agent.git
cd doc-agent
pip install -e .

# 2. Configure
cp config.example.yaml config.yaml
# Edit config.yaml and set your model provider & API key

# 3. Run
doc-agent serve
```

The editor UI opens automatically in your browser at `http://127.0.0.1:3966`.

## Configuration

Configuration is loaded from `./config.yaml` (current directory) or `~/.doc-agent/config.yaml`:

| Section | Description |
|---------|-------------|
| `server.host` / `server.port` | Bind address & port (default `127.0.0.1:3966`) |
| `model.provider` | `cloud` / `local` |
| `model.cloud.service` | `anthropic` / `openai` (OpenAI-compatible endpoints supported via `base_url`) |
| `model.cloud.model` | Model name |
| `model.cloud.api_key_env` | Env var holding the API key (default `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) |
| `model.local.endpoint` | Ollama endpoint (default `http://localhost:11434`) |
| `workspace.path` | Workspace root for documents |
| `agent.max_steps` | Max tool-use iterations per agent run (default 10) |
| `agent.enable_web_search` | Enable web-search tool (default true) |
| `agent.search.provider` | `duckduckgo` (no key) / `tavily` / `brave` / `bocha` |

> ⚠️ **Never commit API keys.** `config.yaml` is gitignored by default — keep it that way. Prefer environment variables or the `api_key_env` indirection.

## CLI

```bash
doc-agent serve              # Start the server (main entry)
doc-agent init [--path DIR]  # Initialize a workspace
doc-agent config set KEY VAL # Set a config value
doc-agent config get [KEY]   # Read config value(s)
doc-agent config show        # Show full config
doc-agent --version          # Version info
```

## Development

```bash
# Backend
pip install -e ".[dev]"
pytest tests/ -v
python3 -m uvicorn doc_agent.server:app --host 127.0.0.1 --port 3966

# Frontend
cd frontend && npm install
npx vite --port 5173 --strictPort
```

The Vite dev server runs at `http://localhost:5173` and proxies API requests to the backend.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI + Uvicorn |
| AI integration | Anthropic / OpenAI-compatible / Ollama |
| Version control | GitPython |
| Frontend | React 18 + TypeScript |
| State management | useReducer + Context API |
| Rich-text editing | Tiptap + tiptap-markdown |
| i18n | React Context + localStorage |
| Build | Vite |
| Packaging | pip (setuptools) / npm |

## License

MIT
