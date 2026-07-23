"""FastAPI application for doc-agent."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from doc_agent import __version__
from doc_agent.agent import DocumentEditor
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


@app.websocket("/ws/edit")
async def websocket_edit(ws: WebSocket):
    """WebSocket endpoint for streaming document edits.

    Client sends: {"type": "edit", "document_id": "...", "instruction": "...", "branch": "...", "selection": "..."}
    Server streams: {"type": "token", "content": "..."}
    Server completes: {"type": "complete", "edit_response": {...}}
    Server error: {"type": "error", "message": "..."}
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

            if msg_type != "edit":
                await ws.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})
                continue

            # Build EditRequest
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
                continue

            # Stream tokens
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

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket connection error: %s", e)


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
