/**
 * TypeScript type definitions for doc-agent frontend.
 * Mirrors the backend Pydantic models.
 */

// --- Document ---

export interface Document {
  id: string;
  title: string;
  content: string;
  branch: string;
  created_at: string;
  updated_at: string;
}

// --- Unified Document (cross-branch) ---

export interface UnifiedDocument {
  id: string;
  title: string;
  branches: string[];
  format: string;
}

// --- Branch ---

export interface BranchInfo {
  name: string;
  is_active: boolean;
  created_at: string;
  commit_count: number;
}

// --- Edit ---

export interface EditRequest {
  document_id: string;
  instruction: string;
  branch?: string;
}

export interface EditResponse {
  document_id: string;
  original_content: string;
  new_content: string;
  diff: string;
  branch: string;
  status?: "success" | "error";
  message?: string;
  commit_hash?: string | null;
}

// --- Version / History ---

export interface VersionInfo {
  id: string;
  document_id: string;
  branch: string;
  message: string;
  author: string;
  timestamp: string;
  content_snapshot?: string;
}

// --- Diff ---

export interface DiffResult {
  document_id: string;
  branch_a: string;
  branch_b: string;
  old_content: string;
  new_content: string;
  unified_diff: string;
}

// --- Merge ---

export interface MergeResult {
  success: boolean;
  merged_content?: string;
  conflicts?: string[];
  message: string;
}

// --- Config ---

export interface AppConfig {
  llm_provider: string;
  llm_model: string;
  temperature: number;
  style_enabled: boolean;
  auto_save: boolean;
}

// --- Task Status (mirrors backend enum) ---

export type TaskStatus = "pending" | "in_progress" | "completed" | "failed";

// --- WebSocket Messages ---

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface WsMessage {
  type: string;
  [key: string]: unknown;
}

export interface WsEditRequest {
  type: "edit";
  document_id: string;
  instruction: string;
  branch?: string;
  selection?: string;
  style_template?: string;
}

export interface WsTokenMessage {
  type: "token";
  content: string;
}

export interface WsCompleteMessage {
  type: "complete";
  edit_response: {
    document_id: string;
    original_content: string;
    edited_content: string;
    diff_summary: string;
    branch: string;
    commit_hash: string | null;
  };
}

export interface WsErrorMessage {
  type: "error";
  message: string;
}

// --- Agent Loop WebSocket Messages (/ws/agent) ---

export interface WsAgentRequest {
  type: "agent";
  document_id: string;
  instruction: string;
  branch?: string;
  selection?: string;
  style_template?: string;
}

export interface WsStepMessage {
  type: "step";
  step: number;
}

export interface WsToolCallMessage {
  type: "tool_call";
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface WsToolResultMessage {
  type: "tool_result";
  id: string;
  name: string;
  result: string;
}

// A single entry rendered in the agent activity timeline.
export interface AgentTimelineEvent {
  id: string;                          // unique key
  kind: "step" | "tool_call" | "tool_result";
  timestamp: string;                   // ISO time
  label: string;                       // short human-readable summary
  detail?: string;                     // optional expanded detail (args / result)
}

// --- Style Template ---

export interface StyleTemplateDTO {
  name: string;
  description: string;
  tone: string;
  vocabulary_level: string;
  formatting_rules: string[];
  forbidden_patterns: string[];
}

// --- Interaction Record ---

export interface InteractionRecord {
  id: string;           // 唯一ID（时间戳+随机数）
  timestamp: string;    // ISO 时间字符串
  documentId: string;   // 关联的文档
  branch: string;       // 当时所在分支
  instruction: string;  // 用户输入的编辑指令
  selection?: string;   // 选中文本（如果有）
  status: 'pending' | 'streaming' | 'completed' | 'accepted' | 'rejected' | 'error';
  resultSummary?: string;  // AI 结果摘要（如 "修改了3处" 或错误信息）
  editedContent?: string;  // AI 生成的内容（用于回溯）
}
