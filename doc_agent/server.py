"""FastAPI application for doc-agent."""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from doc_agent import __version__
from doc_agent.agent import DocumentEditor
from doc_agent.agent_loop import AgentSession
from doc_agent.config import AppConfig, load_config
from doc_agent.llm import LLMError
from doc_agent.models import ConflictResolveRequest, EditRequest
from doc_agent.style import HabitTracker, TemplateManager
from doc_agent.vcs import (
    BranchNotFoundError,
    DocumentNotFoundError,
    VCSError,
    VersionControl,
)

logger = logging.getLogger(__name__)

# ─── Global State ─────────────────────────────────────────────────────────────

_config: Optional[AppConfig] = None
_vcs: Optional[VersionControl] = None
_editor: Optional[DocumentEditor] = None
_template_manager: Optional[TemplateManager] = None
_habit_tracker: Optional[HabitTracker] = None


def _get_config() -> AppConfig:
    assert _config is not None, "App not initialized"
    return _config


def _get_vcs() -> VersionControl:
    assert _vcs is not None, "App not initialized"
    return _vcs


def _get_editor() -> DocumentEditor:
    assert _editor is not None, "App not initialized"
    return _editor


def _get_assets_dir() -> Path:
    """Directory holding uploaded images/assets (outside the git workspace)."""
    workspace = Path(_get_config().workspace.path).expanduser()
    assets = workspace.parent / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    return assets


# ─── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize config, vcs, editor on startup."""
    global _config, _vcs, _editor, _template_manager, _habit_tracker

    _config = load_config()
    workspace_path = Path(_config.workspace.path).expanduser()

    _vcs = VersionControl(workspace_path)
    _vcs.init_workspace()

    _editor = DocumentEditor(_config)
    _template_manager = TemplateManager()
    _habit_tracker = HabitTracker()

    logger.info("doc-agent server started, workspace: %s", workspace_path)
    yield
    logger.info("doc-agent server shutting down")


# ─── App Creation ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="doc-agent",
    version=__version__,
    description="AI-powered documentation agent",
    lifespan=lifespan,
)

# CORS — allow Vite dev server in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Exception Handlers ──────────────────────────────────────────────────────


@app.exception_handler(DocumentNotFoundError)
async def document_not_found_handler(request, exc: DocumentNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(BranchNotFoundError)
async def branch_not_found_handler(request, exc: BranchNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(VCSError)
async def vcs_error_handler(request, exc: VCSError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(LLMError)
async def llm_error_handler(request, exc: LLMError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


# ─── Request/Response Models ─────────────────────────────────────────────────


class CreateDocumentRequest(BaseModel):
    title: str
    content: Optional[str] = ""
    format: Optional[str] = "md"
    branch: Optional[str] = None


class CommitRequest(BaseModel):
    document_id: str
    content: str
    branch: Optional[str] = None
    message: Optional[str] = None


class CreateBranchRequest(BaseModel):
    name: str
    delivery_target: str = ""


class MergeBranchRequest(BaseModel):
    source: str
    target: str


class RenameBranchRequest(BaseModel):
    new_name: str


class SwitchBranchRequest(BaseModel):
    name: str


class DiagramRequest(BaseModel):
    code: str
    language: Optional[str] = None
    instruction: Optional[str] = None


# ─── Health ───────────────────────────────────────────────────────────────────


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}


# ─── Document Management ─────────────────────────────────────────────────────


@app.post("/api/documents")
async def create_document(req: CreateDocumentRequest):
    """Create a new document."""
    vcs = _get_vcs()

    # Build doc_id from title and format
    safe_title = req.title.replace(" ", "-").replace("/", "-")
    doc_id = f"{safe_title}.{req.format}"
    content = req.content or f"# {req.title}\n"

    commit_hash = vcs.save_document(
        doc_id=doc_id,
        content=content,
        message=f"Create document: {req.title}",
        branch=req.branch,
    )

    return {
        "document_id": doc_id,
        "title": req.title,
        "format": req.format,
        "commit_hash": commit_hash,
    }


@app.get("/api/documents")
async def list_documents(branch: Optional[str] = None):
    """List all documents on a branch."""
    vcs = _get_vcs()
    documents = vcs.list_documents(branch=branch)
    return {"documents": documents, "branch": branch or vcs.get_current_branch()}


@app.get("/api/documents/all")
async def list_all_documents():
    """Return a unified document list across all branches + per-doc branch mapping."""
    vcs = _get_vcs()
    branch_docs = vcs.get_all_documents()

    # Merge all documents (deduplicate)
    doc_branch_map: dict[str, list[str]] = {}  # {doc_id: [branches]}
    for branch, docs in branch_docs.items():
        for doc_id in docs:
            if doc_id not in doc_branch_map:
                doc_branch_map[doc_id] = []
            doc_branch_map[doc_id].append(branch)

    # Build response structure
    documents = []
    for doc_id, branches in sorted(doc_branch_map.items()):
        title = doc_id.replace(".md", "").replace(".txt", "").replace(".rst", "")
        documents.append({
            "id": doc_id,
            "title": title,
            "branches": branches,
            "format": doc_id.rsplit(".", 1)[-1] if "." in doc_id else "md",
        })

    return {
        "documents": documents,
        "branch_map": {b: docs for b, docs in branch_docs.items()},
    }


@app.get("/api/documents/{doc_id:path}/branches")
async def get_document_branches(doc_id: str):
    """Return list of branches that contain the given document."""
    vcs = _get_vcs()
    branches = vcs.get_document_branches(doc_id)
    return {"document_id": doc_id, "branches": branches}


@app.get("/api/documents/{doc_id:path}")
async def get_document(doc_id: str, branch: Optional[str] = None):
    """Get a single document's content."""
    vcs = _get_vcs()
    content, resolved_branch = vcs.load_document(doc_id, branch)
    return {
        "document_id": doc_id,
        "content": content,
        "branch": resolved_branch,
    }


# ─── Edit ─────────────────────────────────────────────────────────────────────


@app.post("/api/edit")
async def edit_document(req: EditRequest):
    """Submit an edit instruction (non-streaming). Returns EditResponse."""
    editor = _get_editor()
    response = await editor.edit_document(req)
    return response.model_dump()


@app.post("/api/edit/commit")
async def commit_edit(req: CommitRequest):
    """Confirm and commit an edit."""
    editor = _get_editor()
    commit_hash = await editor.commit_edit(
        document_id=req.document_id,
        content=req.content,
        branch=req.branch,
        message=req.message,
    )
    return {"commit_hash": commit_hash, "document_id": req.document_id}


@app.post("/api/agent")
async def run_agent(req: EditRequest):
    """Run the multi-step agent loop (non-streaming).

    Executes tool-use iterations and returns the final edit_response
    (structure aligned with /api/edit). Does not commit.
    """
    config = _get_config()
    session = AgentSession(config, editor=_get_editor())
    edit_response: Optional[dict] = None
    error: Optional[str] = None
    async for event in session.run(req):
        if event.get("type") == "complete":
            edit_response = event.get("edit_response")
        elif event.get("type") == "error":
            error = event.get("message")
    if edit_response is None:
        raise HTTPException(status_code=502, detail=error or "Agent produced no result")
    return {"edit_response": edit_response, "error": error}


# ─── Assets (image upload) ────────────────────────────────────────────────────

_ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


@app.post("/api/assets")
async def upload_asset(file: UploadFile = File(...)):
    """Upload an image; store it under the assets dir and return its URL."""
    original = file.filename or "image"
    ext = Path(original).suffix.lower()
    if ext not in _ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {ext}")
    data = await file.read()
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 10 MB)")
    name = f"{uuid.uuid4().hex}{ext}"
    (_get_assets_dir() / name).write_bytes(data)
    return {"url": f"/api/assets/{name}", "filename": name}


@app.get("/api/assets/{name}")
async def get_asset(name: str):
    """Serve a previously uploaded asset."""
    # Prevent path traversal — only a bare filename is allowed.
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid asset name")
    path = _get_assets_dir() / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(path)


# ─── Export ───────────────────────────────────────────────────────────────────


def _render_markdown_html(doc_id: str, md_text: str, base_url: str) -> str:
    """Render markdown to a standalone HTML document.

    - Fenced ```mermaid blocks are turned into <pre class="mermaid"> and rendered
      client-side via the mermaid CDN.
    - Relative /api/assets URLs are rewritten to absolute so images load while
      the server is running.
    """
    import markdown

    body = markdown.markdown(
        md_text or "",
        extensions=["fenced_code", "tables", "toc", "sane_lists"],
    )
    # Rewrite relative asset URLs to absolute.
    body = body.replace('src="/api/assets/', f'src="{base_url.rstrip("/")}/api/assets/')
    # Convert highlighted mermaid code blocks into mermaid containers.
    body = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        lambda m: f'<pre class="mermaid">{html_lib.unescape(m.group(1))}</pre>',
        body,
        flags=re.DOTALL,
    )
    title = html_lib.escape(Path(doc_id).stem or doc_id)
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ max-width: 820px; margin: 40px auto; padding: 0 20px;
         font-family: -apple-system, system-ui, "Segoe UI", sans-serif;
         line-height: 1.7; color: #24292f; }}
  h1, h2, h3 {{ line-height: 1.3; }}
  pre {{ background: #f6f8fa; padding: 12px 16px; border-radius: 6px; overflow-x: auto; }}
  code {{ background: #f6f8fa; padding: .2em .4em; border-radius: 3px;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .9em; }}
  pre code {{ background: none; padding: 0; }}
  pre.mermaid {{ background: none; text-align: center; }}
  blockquote {{ border-left: 3px solid #d0d7de; padding-left: 12px; color: #57606a; margin-left: 0; }}
  table {{ border-collapse: collapse; }}
  th, td {{ border: 1px solid #d0d7de; padding: 6px 12px; }}
  img {{ max-width: 100%; height: auto; }}
</style>
</head>
<body>
{body}
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: true }});
</script>
</body>
</html>
"""


@app.get("/api/export/{doc_id:path}")
async def export_document(doc_id: str, request: Request, branch: Optional[str] = None, format: str = "html"):
    """Export a document. Currently supports format=html (self-contained)."""
    vcs = _get_vcs()
    content, _resolved = vcs.load_document(doc_id, branch)
    if format != "html":
        raise HTTPException(status_code=400, detail=f"Unsupported export format: {format}")
    rendered = _render_markdown_html(doc_id, content, str(request.base_url))
    filename = f"{Path(doc_id).stem or 'document'}.html"
    return HTMLResponse(
        content=rendered,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Diagram (code → mermaid) ──────────────────────────────────────────────────


@app.post("/api/diagram/from-code")
async def diagram_from_code(req: DiagramRequest):
    """Convert a code snippet into a Mermaid diagram definition via the LLM."""
    if not (req.code or "").strip():
        raise HTTPException(status_code=400, detail="code is required")
    lang = req.language or ""
    extra = f"\n额外要求：{req.instruction}" if req.instruction else ""
    system = (
        "你是软件架构分析专家。阅读用户提供的代码，提炼其模块、调用关系与数据流，"
        "输出一张 Mermaid 图来描述其架构。"
        "只输出 Mermaid 源码本身，不要任何解释文字，不要用 ``` 代码围栏包裹。"
        "优先使用 flowchart 或 graph 语法，节点标签用中文。"
    )
    prompt = f"代码语言：{lang or '未知'}\n\n代码：\n{req.code}{extra}"
    editor = _get_editor()
    raw = await editor.llm.generate(prompt, system=system, temperature=0.2)
    mermaid = raw.strip()
    # Strip accidental code fences if the model added them anyway.
    if mermaid.startswith("```"):
        mermaid = re.sub(r"^```[a-zA-Z]*\n?", "", mermaid)
        mermaid = re.sub(r"\n?```$", "", mermaid).strip()
    return {"mermaid": mermaid}


# ─── Branch Management ────────────────────────────────────────────────────────


@app.get("/api/branches")
async def list_branches():
    """List all branches."""
    vcs = _get_vcs()
    branches = vcs.list_branches()
    return {"branches": branches}


@app.post("/api/branches")
async def create_branch(req: CreateBranchRequest):
    """Create a new branch."""
    vcs = _get_vcs()
    vcs.create_branch(branch_name=req.name, delivery_target=req.delivery_target)
    return {"name": req.name, "delivery_target": req.delivery_target, "status": "created"}


@app.put("/api/branches/{branch_name:path}")
async def rename_branch(branch_name: str, req: RenameBranchRequest):
    """Rename a branch."""
    vcs = _get_vcs()
    vcs.rename_branch(old_name=branch_name, new_name=req.new_name)
    return {"old_name": branch_name, "new_name": req.new_name, "status": "renamed"}


@app.post("/api/branches/merge")
async def merge_branches(req: MergeBranchRequest):
    """Merge source branch into target branch."""
    vcs = _get_vcs()
    result = vcs.merge_branches(source_branch=req.source, target_branch=req.target)
    return result


@app.post("/api/branches/switch")
async def switch_branch(req: SwitchBranchRequest):
    """Switch to another branch."""
    vcs = _get_vcs()
    vcs.switch_branch(req.name)
    return {"current_branch": req.name}


# ─── Conflict Resolution ───────────────────────────────────────────────────


@app.get("/api/conflicts/{doc_id:path}")
async def get_conflict_details(
    doc_id: str,
    source_branch: str,
    target_branch: str,
):
    """Get three-way conflict details (base/ours/theirs) for a document."""
    vcs = _get_vcs()
    details = vcs.get_conflict_details(
        doc_id=doc_id,
        source_branch=source_branch,
        target_branch=target_branch,
    )
    return details


@app.post("/api/conflicts/{doc_id:path}/resolve")
async def resolve_conflict(doc_id: str, req: ConflictResolveRequest):
    """Resolve a merge conflict.

    resolution='manual': use the provided content directly.
    resolution='llm': invoke LLM to intelligently merge base/ours/theirs.
    """
    vcs = _get_vcs()
    editor = _get_editor()

    if req.resolution == "llm":
        # Get conflict details for LLM merge
        details = vcs.get_conflict_details(
            doc_id=doc_id,
            source_branch=req.source_branch,
            target_branch=req.target_branch,
        )
        # Call LLM to resolve
        merged_content = await editor.resolve_merge_conflict(
            base=details["base"],
            ours=details["ours"],
            theirs=details["theirs"],
            instruction=req.instruction or "",
        )
    elif req.resolution == "manual":
        if not req.content:
            raise HTTPException(
                status_code=400,
                detail="content is required for manual resolution",
            )
        merged_content = req.content
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid resolution type: '{req.resolution}'. Must be 'manual' or 'llm'.",
        )

    # Apply the resolution via VCS
    commit_hash = vcs.resolve_conflict(
        doc_id=doc_id,
        resolution=merged_content,
        source_branch=req.source_branch,
        target_branch=req.target_branch,
    )

    return {
        "doc_id": doc_id,
        "commit_hash": commit_hash,
        "resolution": req.resolution,
        "merged_content": merged_content,
    }


# ─── Version History ──────────────────────────────────────────────────────────


@app.get("/api/history/{doc_id:path}")
async def get_history(doc_id: str, branch: Optional[str] = None, limit: int = 50):
    """Get commit history for a document."""
    vcs = _get_vcs()
    history = vcs.get_history(doc_id=doc_id, branch=branch, limit=limit)
    return {"document_id": doc_id, "history": history}


@app.get("/api/diff/{doc_id:path}")
async def get_diff(
    doc_id: str,
    branch_a: Optional[str] = None,
    branch_b: Optional[str] = None,
    commit_a: Optional[str] = None,
    commit_b: Optional[str] = None,
):
    """Get diff for a document between branches or commits."""
    vcs = _get_vcs()
    diff = vcs.get_diff(
        doc_id=doc_id,
        branch_a=branch_a,
        branch_b=branch_b,
        commit_a=commit_a,
        commit_b=commit_b,
    )
    return {"document_id": doc_id, "diff": diff}


# ─── Configuration ────────────────────────────────────────────────────────────

_SENSITIVE_KEYS = {"api_key", "api_key_env", "secret", "token", "password"}


def _sanitize_config(data: dict) -> dict:
    """Recursively mask sensitive fields in config dict."""
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, dict):
            sanitized[key] = _sanitize_config(value)
        elif any(s in key.lower() for s in _SENSITIVE_KEYS):
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


@app.get("/api/config")
async def get_config():
    """Get current configuration (sensitive fields masked)."""
    config = _get_config()
    raw = config.model_dump()
    return _sanitize_config(raw)


@app.put("/api/config")
async def update_config(updates: dict):
    """Update configuration at runtime.

    Note: Only updates in-memory config. Does not persist to disk.
    """
    global _config, _editor
    config = _get_config()

    # Merge updates into current config
    current = config.model_dump()
    _deep_merge(current, updates)
    _config = AppConfig(**current)

    # Reinitialize editor with new config
    _editor = DocumentEditor(_config)

    return {"status": "updated", "config": _sanitize_config(_config.model_dump())}


def _deep_merge(base: dict, override: dict) -> None:
    """Deep merge override into base dict (in-place)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


# ─── Interactions ─────────────────────────────────────────────────────────────


def _get_interactions_file() -> Path:
    vcs = _get_vcs()
    interactions_dir = Path(vcs.workspace_path) / ".doc-agent"
    interactions_dir.mkdir(parents=True, exist_ok=True)
    return interactions_dir / "interactions.json"


@app.get("/api/interactions")
async def list_interactions(document_id: str = None, branch: str = None):
    """Get all stored interaction records, optionally filtered by document_id and/or branch."""
    f = _get_interactions_file()
    if f.exists():
        data = json.loads(f.read_text(encoding="utf-8"))
        interactions = data.get("interactions", [])
    else:
        interactions = []
    if document_id:
        interactions = [r for r in interactions if r.get("document_id") == document_id or r.get("documentId") == document_id]
    if branch:
        interactions = [r for r in interactions if r.get("branch") == branch]
    return {"interactions": interactions}


@app.post("/api/interactions")
async def add_interaction(record: dict):
    """Add a new interaction record."""
    f = _get_interactions_file()
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"interactions": []}
    data["interactions"].append(record)
    # Keep only the latest 200 records
    data["interactions"] = data["interactions"][-200:]
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok"}


@app.put("/api/interactions/{interaction_id}")
async def update_interaction(interaction_id: str, update: dict):
    """Update an existing interaction record."""
    f = _get_interactions_file()
    if not f.exists():
        return {"status": "not_found"}
    data = json.loads(f.read_text(encoding="utf-8"))
    for item in data["interactions"]:
        if item.get("id") == interaction_id:
            item.update(update)
            break
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok"}


# ─── Styles ───────────────────────────────────────────────────────────────────


@app.get("/api/styles/templates")
async def list_style_templates():
    """List all style templates with full details."""
    templates = _template_manager.list_templates() if _template_manager else []
    return {
        "templates": [
            {
                "name": t.name,
                "description": t.description or "",
                "tone": t.tone or "",
                "vocabulary_level": t.vocabulary_level or "",
                "formatting_rules": t.formatting_rules or [],
                "forbidden_patterns": t.forbidden_patterns or [],
            }
            for t in templates
        ]
    }


@app.get("/api/styles/templates/{name}")
async def get_style_template(name: str):
    """Get a single style template by name."""
    if not _template_manager:
        raise HTTPException(status_code=500, detail="Style manager not initialized")
    try:
        template = _template_manager.load_template(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
    return {
        "name": template.name,
        "description": template.description or "",
        "tone": template.tone or "",
        "vocabulary_level": template.vocabulary_level or "",
        "formatting_rules": template.formatting_rules or [],
        "forbidden_patterns": template.forbidden_patterns or [],
    }


@app.post("/api/styles/templates")
async def create_style_template(data: dict):
    """Create a new style template."""
    from doc_agent.models import StyleTemplate

    if not _template_manager:
        raise HTTPException(status_code=500, detail="Style manager not initialized")
    template = StyleTemplate(**data)
    _template_manager.save_template(template)
    return {"status": "ok", "name": template.name}


@app.put("/api/styles/templates/{name}")
async def update_style_template(name: str, data: dict):
    """Update an existing style template."""
    from doc_agent.models import StyleTemplate

    if not _template_manager:
        raise HTTPException(status_code=500, detail="Style manager not initialized")
    data["name"] = name
    template = StyleTemplate(**data)
    _template_manager.save_template(template)
    return {"status": "ok"}


@app.delete("/api/styles/templates/{name}")
async def delete_style_template(name: str):
    """Delete a style template."""
    if not _template_manager:
        raise HTTPException(status_code=500, detail="Style manager not initialized")
    try:
        _template_manager.delete_template(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
    return {"status": "ok"}


@app.post("/api/styles/learn")
async def learn_style_from_docs():
    """Learn writing habits from workspace documents."""
    vcs = _get_vcs()
    branch = vcs.get_current_branch()
    doc_ids = vcs.list_documents(branch)
    workspace = Path(vcs.workspace_path)
    doc_files = [workspace / d for d in doc_ids if (workspace / d).exists()]
    if not doc_files:
        return {"status": "no_documents"}
    profile = _habit_tracker.learn_from_documents(doc_files)
    _habit_tracker.save_profile(profile)
    return {"status": "ok"}


# ─── WebSocket ────────────────────────────────────────────────────────────────


async def _handle_edit_message(ws: WebSocket, msg: dict) -> None:
    """Run the classic single-shot streaming edit for one message."""
    try:
        request = EditRequest(
            document_id=msg["document_id"],
            instruction=msg["instruction"],
            branch=msg.get("branch"),
            selection=msg.get("selection"),
            style_template=msg.get("style_template"),
        )
    except (KeyError, Exception) as e:
        await ws.send_json({"type": "error", "message": f"Invalid edit request: {e}"})
        return

    editor = _get_editor()
    collected_tokens: list[str] = []
    try:
        async for token in editor.edit_document_stream(request):
            collected_tokens.append(token)
            await ws.send_json({"type": "token", "content": token})

        # After streaming completes, build full response
        full_content = "".join(collected_tokens)

        # Post-process: strip code block wrappers and preambles
        full_content = editor._post_process(full_content, editor._detect_format(request.document_id))

        # Load original for diff
        vcs = _get_vcs()
        branch = request.branch or vcs.get_current_branch()
        original_content, resolved_branch = vcs.load_document(request.document_id, branch)

        edit_response = {
            "document_id": request.document_id,
            "original_content": original_content,
            "edited_content": full_content,
            "diff_summary": editor._generate_diff(original_content, full_content).unified_diff,
            "branch": resolved_branch,
            "commit_hash": None,
        }

        await ws.send_json({"type": "complete", "edit_response": edit_response})

    except (VCSError, LLMError) as e:
        await ws.send_json({"type": "error", "message": str(e)})
    except Exception as e:
        logger.exception("Unexpected error in WebSocket edit stream")
        await ws.send_json({"type": "error", "message": f"Internal error: {e}"})


async def _handle_agent_message(ws: WebSocket, msg: dict) -> None:
    """Run the multi-step agent loop for one message."""
    try:
        request = EditRequest(
            document_id=msg["document_id"],
            instruction=msg["instruction"],
            branch=msg.get("branch"),
            selection=msg.get("selection"),
            style_template=msg.get("style_template"),
        )
    except (KeyError, Exception) as e:
        await ws.send_json({"type": "error", "message": f"Invalid agent request: {e}"})
        return

    config = _get_config()
    session = AgentSession(config, editor=_get_editor())
    try:
        async for event in session.run(request):
            await ws.send_json(event)
    except (VCSError, LLMError) as e:
        await ws.send_json({"type": "error", "message": str(e)})
    except Exception as e:
        logger.exception("Unexpected error in WebSocket agent loop")
        await ws.send_json({"type": "error", "message": f"Internal error: {e}"})


async def _ws_dispatch_loop(ws: WebSocket) -> None:
    """Shared receive loop that dispatches each message by its ``type``.

    Both /ws/edit and /ws/agent use this loop, so a message routed to either
    endpoint is handled by its declared type. This removes any dependency on
    which URL the client happened to connect to (avoiding reconnect races when
    the client toggles between edit and agent modes).
    """
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type")
            # Handle heartbeat ping/pong silently
            if msg_type in ("ping", "pong"):
                if msg_type == "ping":
                    await ws.send_json({"type": "pong"})
                continue

            if msg_type == "edit":
                await _handle_edit_message(ws, msg)
            elif msg_type == "agent":
                await _handle_agent_message(ws, msg)
            else:
                await ws.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket connection error: %s", e)


@app.websocket("/ws/edit")
async def websocket_edit(ws: WebSocket):
    """WebSocket endpoint accepting both edit and agent messages (dispatched by type)."""
    await _ws_dispatch_loop(ws)


@app.websocket("/ws/agent")
async def websocket_agent(ws: WebSocket):
    """WebSocket endpoint accepting both agent and edit messages (dispatched by type).

    Client sends: {"type": "agent", "document_id": "...", "instruction": "...",
                   "branch": "...", "selection": "...", "style_template": "..."}
    Server streams agent events: step / tool_call / tool_result / token / complete / error.
    """
    await _ws_dispatch_loop(ws)


# ─── Static Files & SPA Fallback ─────────────────────────────────────────────

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    # Mount static assets (js, css, images, etc.)
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="static-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """Serve frontend SPA — fallback all non-API routes to index.html."""
        # Exclude API and WebSocket paths
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404, detail="Not found")

        # Try to serve the exact file first
        file_path = _FRONTEND_DIST / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)

        # Fallback to index.html for SPA routing
        index = _FRONTEND_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)

        raise HTTPException(status_code=404, detail="Frontend not built")
