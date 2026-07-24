/**
 * API client for doc-agent backend.
 */

import type {
  Document,
  UnifiedDocument,
  BranchInfo,
  EditRequest,
  EditResponse,
  VersionInfo,
  DiffResult,
  MergeResult,
  AppConfig,
  InteractionRecord,
  StyleTemplateDTO,
} from "../types";

const API_BASE = "/api";

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorBody = await response.text().catch(() => "");
    throw new Error(
      `API error ${response.status}: ${response.statusText}${errorBody ? ` - ${errorBody}` : ""}`
    );
  }

  return response.json();
}

export const api = {
  // --- Documents ---

  async listAllDocuments(): Promise<{ documents: UnifiedDocument[]; branch_map: Record<string, string[]> }> {
    return request<{ documents: UnifiedDocument[]; branch_map: Record<string, string[]> }>('/documents/all');
  },

  async getDocumentBranches(docId: string): Promise<string[]> {
    const data = await request<{ document_id: string; branches: string[] }>(`/documents/${docId}/branches`);
    return data.branches || [];
  },

  async listDocuments(branch?: string): Promise<Document[]> {
    const params = branch ? `?branch=${encodeURIComponent(branch)}` : "";
    const data = await request<{ documents: string[]; branch: string }>(`/documents${params}`);
    // Backend returns a list of file paths (strings), map to Document objects
    const docs: Document[] = (data.documents || []).map((filePath: string) => {
      const title = filePath.replace(/\.(md|txt|rst)$/i, "").replace(/-/g, " ");
      return {
        id: filePath,
        title,
        content: "",
        branch: data.branch || "",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    });
    return docs;
  },

  async getDocument(id: string, branch?: string): Promise<Document> {
    const params = branch ? `?branch=${encodeURIComponent(branch)}` : "";
    const data = await request<{ document_id: string; content: string; branch: string }>(
      `/documents/${id}${params}`
    );
    // Map backend fields to frontend Document interface
    return {
      id: data.document_id,
      title: data.document_id,
      content: data.content,
      branch: data.branch,
      created_at: "",
      updated_at: "",
    };
  },

  async createDocument(title: string, content?: string, branch?: string): Promise<Document> {
    const data = await request<{ document_id: string; title: string; format: string; commit_hash: string }>(
      "/documents",
      {
        method: "POST",
        body: JSON.stringify({ title, content: content ?? "", branch: branch || undefined }),
      }
    );
    // Map backend response to frontend Document interface
    return {
      id: data.document_id,
      title: data.title,
      content: content ?? "",
      branch: branch || "",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  },

  // --- Edit ---

  submitEdit(editRequest: EditRequest): Promise<EditResponse> {
    return request<EditResponse>("/edit", {
      method: "POST",
      body: JSON.stringify(editRequest),
    });
  },

  // --- Assets (image upload) ---

  async uploadAsset(file: File): Promise<{ url: string; filename: string }> {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${API_BASE}/assets`, { method: "POST", body: form });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(`Upload failed ${response.status}: ${body}`);
    }
    return response.json();
  },

  // --- Diagram (code -> mermaid) ---

  async generateDiagram(code: string, language?: string): Promise<string> {
    const data = await request<{ mermaid: string }>("/diagram/from-code", {
      method: "POST",
      body: JSON.stringify({ code, language }),
    });
    return data.mermaid || "";
  },

  // --- Export ---

  async exportDocument(docId: string, format: "html", branch?: string): Promise<Blob> {
    const params = new URLSearchParams({ format });
    if (branch) params.set("branch", branch);
    const response = await fetch(`${API_BASE}/export/${docId}?${params.toString()}`);
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(`Export failed ${response.status}: ${body}`);
    }
    return response.blob();
  },

  // --- Save/Commit ---

  async saveDocument(documentId: string, content: string, branch?: string, message?: string): Promise<{ commit_hash: string }> {
    return request<{ commit_hash: string; document_id: string }>("/edit/commit", {
      method: "POST",
      body: JSON.stringify({
        document_id: documentId,
        content,
        branch: branch || undefined,
        message: message || `Update ${documentId}`,
      }),
    });
  },

  // --- Branches ---

  async listBranches(): Promise<BranchInfo[]> {
    const data = await request<{ branches: BranchInfo[] }>("/branches");
    return data.branches || [];
  },

  createBranch(name: string, deliveryTarget: string): Promise<void> {
    return request<void>("/branches", {
      method: "POST",
      body: JSON.stringify({ name, delivery_target: deliveryTarget }),
    });
  },

  renameBranch(oldName: string, newName: string): Promise<void> {
    const encodedName = oldName.split('/').map(encodeURIComponent).join('/');
    return request<void>(`/branches/${encodedName}`, {
      method: "PUT",
      body: JSON.stringify({ new_name: newName }),
    });
  },

  mergeBranches(source: string, target: string): Promise<MergeResult> {
    return request<MergeResult>("/branches/merge", {
      method: "POST",
      body: JSON.stringify({ source, target }),
    });
  },

  // --- History ---

  async getHistory(docId: string): Promise<VersionInfo[]> {
    const data = await request<{ document_id: string; history: Array<{ commit_hash: string; message: string; author: string; timestamp: string }> }>(
      `/history/${docId}`
    );
    return (data.history || []).map(item => ({
      id: item.commit_hash,
      document_id: docId,
      branch: '',
      message: item.message,
      author: item.author,
      timestamp: item.timestamp,
    }));
  },

  async getDiff(docId: string, branchA?: string, branchB?: string): Promise<DiffResult> {
    const params = new URLSearchParams();
    if (branchA) params.set("branch_a", branchA);
    if (branchB) params.set("branch_b", branchB);
    const qs = params.toString();
    const data = await request<{ document_id: string; diff: DiffResult }>(
      `/diff/${docId}${qs ? `?${qs}` : ""}`
    );
    return data.diff;
  },

  // --- Config ---

  async getConfig(): Promise<AppConfig> {
    // Backend returns nested Pydantic model; map to flat frontend AppConfig
    const data = await request<Record<string, unknown>>("/config");
    const model = (data?.model ?? {}) as Record<string, unknown>;
    const cloud = (model?.cloud ?? {}) as Record<string, unknown>;
    const local = (model?.local ?? {}) as Record<string, unknown>;
    const style = (data?.style ?? {}) as Record<string, unknown>;
    const provider = (model?.provider as string) || "cloud";
    const temp = model?.temperature;
    return {
      llm_provider: provider,
      llm_model: provider === "local"
        ? (local?.model as string) || ""
        : (cloud?.model as string) || "",
      temperature: typeof temp === "number" ? temp : 0.7,
      style_enabled: style?.default_template != null,
      auto_save: true,
    };
  },

  async updateConfig(config: Partial<AppConfig>): Promise<void> {
    // Map flat frontend config back to nested backend format
    const payload: Record<string, unknown> = {};
    if (config.llm_provider !== undefined || config.llm_model !== undefined) {
      const modelPayload: Record<string, unknown> = {};
      if (config.llm_provider !== undefined) {
        modelPayload.provider = config.llm_provider;
      }
      if (config.llm_model !== undefined) {
        if (config.llm_provider === "local") {
          modelPayload.local = { model: config.llm_model };
        } else {
          modelPayload.cloud = { model: config.llm_model };
        }
      }
      if (config.temperature !== undefined) {
        modelPayload.temperature = config.temperature;
      }
      payload.model = modelPayload;
    } else if (config.temperature !== undefined) {
      payload.model = { temperature: config.temperature };
    }
    if (config.style_enabled !== undefined) {
      payload.style = {
        default_template: config.style_enabled ? "default" : null,
      };
    }
    await request<unknown>("/config", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  // --- Style ---

  learnStyle(): Promise<{ status: string; doc_count?: number; summary?: string }> {
    return request<{ status: string; doc_count?: number; summary?: string }>('/styles/learn', { method: 'POST' });
  },

  getHabitProfile(): Promise<{ exists: boolean; summary: string; profile: Record<string, unknown> }> {
    return request<{ exists: boolean; summary: string; profile: Record<string, unknown> }>('/styles/habit');
  },

  clearHabitProfile(): Promise<{ status: string }> {
    return request<{ status: string }>('/styles/habit', { method: 'DELETE' });
  },

  async listStyleTemplates(): Promise<StyleTemplateDTO[]> {
    const data = await request<{ templates: StyleTemplateDTO[] }>('/styles/templates');
    return data.templates || [];
  },

  async getStyleTemplate(name: string): Promise<StyleTemplateDTO> {
    return request<StyleTemplateDTO>(`/styles/templates/${encodeURIComponent(name)}`);
  },

  async createStyleTemplate(data: Omit<StyleTemplateDTO, 'name'> & { name: string }): Promise<void> {
    await request<{ status: string; name: string }>('/styles/templates', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async updateStyleTemplate(name: string, data: Partial<StyleTemplateDTO>): Promise<void> {
    await request<{ status: string }>(`/styles/templates/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  async deleteStyleTemplate(name: string): Promise<void> {
    await request<{ status: string }>(`/styles/templates/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    });
  },

  // --- Interactions ---

  async listInteractions(documentId?: string, branch?: string): Promise<InteractionRecord[]> {
    const params = new URLSearchParams();
    if (documentId) params.set('document_id', documentId);
    if (branch) params.set('branch', branch);
    const query = params.toString() ? `?${params.toString()}` : '';
    const data = await request<{ interactions: InteractionRecord[] }>(`/interactions${query}`);
    return data.interactions || [];
  },

  async addInteraction(record: InteractionRecord): Promise<void> {
    await request<{ status: string }>("/interactions", {
      method: "POST",
      body: JSON.stringify(record),
    });
  },

  async updateInteraction(id: string, update: Partial<InteractionRecord>): Promise<void> {
    await request<{ status: string }>(`/interactions/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(update),
    });
  },
};
