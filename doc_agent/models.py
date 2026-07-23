"""Pydantic models for doc-agent."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Document(BaseModel):
    """A managed document."""

    id: str  # 文件名作为ID
    title: str
    content: str
    format: str = "md"  # md | txt | rst
    branch: str = "main"
    created_at: datetime
    updated_at: datetime


class EditRequest(BaseModel):
    """Request to edit a document via natural language instruction."""

    document_id: str
    instruction: str  # 自然语言编辑指令
    branch: Optional[str] = None  # 目标分支
    selection: Optional[str] = None  # 选中的文本（部分编辑）
    style_template: Optional[str] = None


class EditResponse(BaseModel):
    """Response after applying an edit."""

    document_id: str
    original_content: str
    edited_content: str
    diff_summary: str
    branch: str
    commit_hash: Optional[str] = None


class BranchInfo(BaseModel):
    """Information about a document branch."""

    name: str
    delivery_target: str  # 交付对象描述
    created_at: datetime
    head_commit: str
    is_current: bool = False


class VersionInfo(BaseModel):
    """A single version/commit entry."""

    commit_hash: str
    message: str
    author: str
    timestamp: datetime


class StyleTemplate(BaseModel):
    """A writing style template."""

    name: str
    description: str
    tone: str  # 语气
    vocabulary_level: str  # 用词层次
    formatting_rules: list[str] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)


class ConflictDetail(BaseModel):
    """Three-way conflict content for a document."""

    doc_id: str
    base: str  # 共同祖先版本
    ours: str  # 当前分支版本
    theirs: str  # 要合并的分支版本
    has_conflict: bool
    source_branch: str
    target_branch: str


class ConflictResolveRequest(BaseModel):
    """Request to resolve a merge conflict."""

    resolution: str  # "manual" | "llm"
    content: Optional[str] = None  # 手动解决时提供的内容
    instruction: Optional[str] = None  # LLM 辅助合并时的用户指令
    source_branch: str
    target_branch: str


class ConflictResolveResponse(BaseModel):
    """Response after resolving a conflict."""

    doc_id: str
    commit_hash: str
    resolution: str  # 使用的解决方式
    merged_content: str


class DiffResult(BaseModel):
    """Result of comparing two versions of content."""

    old_content: str
    new_content: str
    unified_diff: str  # unified diff 格式文本
    stats: dict = Field(default_factory=dict)  # additions, deletions等统计
