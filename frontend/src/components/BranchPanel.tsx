import { useState, useRef, useEffect, useCallback } from "react";
import { GitBranch, Plus, File, ChevronDown, Pencil, Check, Trash2 } from "lucide-react";
import type { BranchInfo, UnifiedDocument } from "../types";
import { useI18n } from "../context/I18nContext";

// --- Types ---

interface BranchPanelProps {
  branches: BranchInfo[];
  currentBranch: string;
  branchFilter: string | null;
  documents: UnifiedDocument[];
  currentDocId: string | null;
  onSwitchBranch: (branch: string) => void;
  onSetBranchFilter: (branch: string | null) => void;
  onCreateBranch: (name: string, target: string) => void;
  onRenameBranch: (oldName: string, newName: string) => void;
  onSelectDocument: (docId: string) => void;
  onCreateDocument: (title: string) => void;
  onRenameDocument: (docId: string, newId: string) => void;
  onDeleteDocument: (docId: string) => void;
}

// --- Style constants ---

const colors = {
  sidebar: "#181825",
  text: "#cdd6f4",
  textMuted: "#a6adc8",
  border: "#313244",
  accent: "#89b4fa",
  hover: "#313244",
  surface: "#1e1e2e",
  badge: "#45475a",
  dropdownBg: "#11111b",
};

// --- Component ---

export function BranchPanel({
  branches,
  currentBranch,
  branchFilter,
  documents,
  currentDocId,
  onSwitchBranch,
  onSetBranchFilter,
  onCreateBranch,
  onRenameBranch,
  onSelectDocument,
  onCreateDocument,
  onRenameDocument,
  onDeleteDocument,
}: BranchPanelProps) {
  const { t } = useI18n();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [showNewBranch, setShowNewBranch] = useState(false);
  const [newBranchName, setNewBranchName] = useState("");
  const [newBranchTarget, setNewBranchTarget] = useState("");
  const [showNewDoc, setShowNewDoc] = useState(false);
  const [newDocTitle, setNewDocTitle] = useState("");
  const [renamingBranch, setRenamingBranch] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renamingDoc, setRenamingDoc] = useState<string | null>(null);
  const [docRenameValue, setDocRenameValue] = useState("");
  const docRenameInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  // Close dropdown on outside click
  const handleClickOutside = useCallback((e: MouseEvent) => {
    if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
      setDropdownOpen(false);
    }
  }, []);

  useEffect(() => {
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [dropdownOpen, handleClickOutside]);

  useEffect(() => {
    if (renamingBranch && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingBranch]);

  const handleCreateBranch = () => {
    if (newBranchName.trim()) {
      onCreateBranch(newBranchName.trim(), newBranchTarget.trim());
      setNewBranchName("");
      setNewBranchTarget("");
      setShowNewBranch(false);
    }
  };

  const handleCreateDoc = () => {
    if (newDocTitle.trim()) {
      onCreateDocument(newDocTitle.trim());
      setNewDocTitle("");
      setShowNewDoc(false);
    }
  };

  const startRename = (branchName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingBranch(branchName);
    setRenameValue(branchName);
  };

  const submitRename = () => {
    if (renamingBranch && renameValue.trim() && renameValue.trim() !== renamingBranch) {
      onRenameBranch(renamingBranch, renameValue.trim());
    }
    setRenamingBranch(null);
    setRenameValue("");
  };

  const cancelRename = () => {
    setRenamingBranch(null);
    setRenameValue("");
  };

  useEffect(() => {
    if (renamingDoc && docRenameInputRef.current) {
      docRenameInputRef.current.focus();
      docRenameInputRef.current.select();
    }
  }, [renamingDoc]);

  const startDocRename = (docId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingDoc(docId);
    setDocRenameValue(docId);
  };

  const submitDocRename = () => {
    const next = docRenameValue.trim();
    if (renamingDoc && next && next !== renamingDoc) {
      onRenameDocument(renamingDoc, next);
    }
    setRenamingDoc(null);
    setDocRenameValue("");
  };

  const cancelDocRename = () => {
    setRenamingDoc(null);
    setDocRenameValue("");
  };

  const handleDeleteDoc = (docId: string, title: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm(t("document.deleteConfirm").replace("{name}", title))) {
      onDeleteDocument(docId);
    }
  };

  const handleSelectBranch = (branchName: string | null) => {
    if (branchName === null) {
      onSetBranchFilter(null);
    } else {
      onSwitchBranch(branchName);
      onSetBranchFilter(branchName);
    }
    setDropdownOpen(false);
  };

  const displayBranch = branchFilter || t("branch.all");

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100%",
      overflow: "hidden",
    }}>
      {/* Branch selector area */}
      <div ref={dropdownRef} style={{
        padding: "8px 12px",
        backgroundColor: colors.sidebar,
        borderBottom: `1px solid ${colors.border}`,
        position: "relative",
      }}>
        {/* Selector button */}
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            width: "100%",
            padding: "6px 10px",
            backgroundColor: colors.surface,
            border: `1px solid ${colors.border}`,
            borderRadius: "6px",
            color: colors.text,
            fontSize: "12px",
            cursor: "pointer",
            textAlign: "left",
          }}
        >
          <GitBranch size={13} color={colors.accent} />
          <span style={{
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}>
            {displayBranch}
          </span>
          <ChevronDown
            size={12}
            color={colors.textMuted}
            style={{
              transform: dropdownOpen ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.15s",
            }}
          />
        </button>

        {/* Dropdown overlay */}
        {dropdownOpen && (
          <div style={{
            position: "absolute",
            top: "100%",
            left: "8px",
            right: "8px",
            marginTop: "4px",
            backgroundColor: colors.dropdownBg,
            border: `1px solid ${colors.border}`,
            borderRadius: "8px",
            zIndex: 1000,
            boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
            maxHeight: "280px",
            overflow: "auto",
          }}>
            {/* All documents option */}
            <div
              onClick={() => handleSelectBranch(null)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "7px 12px",
                fontSize: "12px",
                color: !branchFilter ? colors.accent : colors.text,
                cursor: "pointer",
                backgroundColor: !branchFilter ? "rgba(137,180,250,0.08)" : "transparent",
                borderBottom: `1px solid ${colors.border}`,
              }}
              onMouseEnter={(e) => {
                if (branchFilter) e.currentTarget.style.backgroundColor = colors.hover;
              }}
              onMouseLeave={(e) => {
                if (branchFilter) e.currentTarget.style.backgroundColor = "transparent";
              }}
            >
              <File size={12} color={!branchFilter ? colors.accent : colors.textMuted} />
              <span style={{ flex: 1 }}>{t("branch.all")}</span>
              {!branchFilter && <Check size={12} color={colors.accent} />}
            </div>

            {/* Branch items */}
            {branches.map((branch) => (
              <div
                key={branch.name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "7px 12px",
                  fontSize: "12px",
                  color: branch.name === branchFilter ? colors.accent : colors.text,
                  cursor: "pointer",
                  backgroundColor: branch.name === branchFilter ? "rgba(137,180,250,0.08)" : "transparent",
                }}
                onClick={() => {
                  if (renamingBranch !== branch.name) {
                    handleSelectBranch(branch.name);
                  }
                }}
                onMouseEnter={(e) => {
                  if (branch.name !== branchFilter) e.currentTarget.style.backgroundColor = colors.hover;
                }}
                onMouseLeave={(e) => {
                  if (branch.name !== branchFilter) e.currentTarget.style.backgroundColor = "transparent";
                }}
              >
                <GitBranch size={12} color={branch.name === branchFilter ? colors.accent : colors.textMuted} />
                {renamingBranch === branch.name ? (
                  <input
                    ref={renameInputRef}
                    style={{
                      flex: 1,
                      backgroundColor: colors.surface,
                      border: `1px solid ${colors.border}`,
                      borderRadius: "4px",
                      padding: "2px 6px",
                      color: colors.text,
                      fontSize: "12px",
                      outline: "none",
                    }}
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submitRename();
                      if (e.key === "Escape") cancelRename();
                    }}
                    onBlur={submitRename}
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {branch.name}
                  </span>
                )}
                {branch.name === currentBranch && (
                  <span style={{ fontSize: "9px", color: colors.accent, fontWeight: 600 }}>●</span>
                )}
                <span style={{ fontSize: "10px", color: colors.textMuted }}>
                  {branch.commit_count}c
                </span>
                {branch.name === branchFilter && renamingBranch !== branch.name && (
                  <Check size={12} color={colors.accent} />
                )}
                {renamingBranch !== branch.name && (
                  <button
                    style={{
                      background: "none",
                      border: "none",
                      padding: "2px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      borderRadius: "3px",
                    }}
                    onClick={(e) => startRename(branch.name, e)}
                    title={t("branch.rename")}
                  >
                    <Pencil size={10} color={colors.textMuted} />
                  </button>
                )}
              </div>
            ))}

            {/* New branch button */}
            <div style={{ borderTop: `1px solid ${colors.border}`, padding: "4px" }}>
              {!showNewBranch ? (
                <button
                  onClick={(e) => { e.stopPropagation(); setShowNewBranch(true); }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    width: "100%",
                    padding: "6px 8px",
                    fontSize: "11px",
                    color: colors.textMuted,
                    backgroundColor: "transparent",
                    border: "none",
                    cursor: "pointer",
                    borderRadius: "4px",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = colors.hover; }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
                >
                  <Plus size={12} />
                  {t("branch.create")}
                </button>
              ) : (
                <div style={{ padding: "4px 4px", display: "flex", flexDirection: "column", gap: "4px" }}>
                  <input
                    style={{
                      backgroundColor: colors.surface,
                      border: `1px solid ${colors.border}`,
                      borderRadius: "4px",
                      padding: "5px 8px",
                      color: colors.text,
                      fontSize: "11px",
                      outline: "none",
                      width: "100%",
                      boxSizing: "border-box",
                    }}
                    placeholder={t("branch.name")}
                    value={newBranchName}
                    onChange={(e) => setNewBranchName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleCreateBranch()}
                    autoFocus
                  />
                  <input
                    style={{
                      backgroundColor: colors.surface,
                      border: `1px solid ${colors.border}`,
                      borderRadius: "4px",
                      padding: "5px 8px",
                      color: colors.text,
                      fontSize: "11px",
                      outline: "none",
                      width: "100%",
                      boxSizing: "border-box",
                    }}
                    placeholder={t("branch.target")}
                    value={newBranchTarget}
                    onChange={(e) => setNewBranchTarget(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleCreateBranch()}
                  />
                  <div style={{ display: "flex", gap: "4px", justifyContent: "flex-end" }}>
                    <button
                      onClick={() => setShowNewBranch(false)}
                      style={{
                        padding: "3px 8px",
                        borderRadius: "4px",
                        border: `1px solid ${colors.border}`,
                        backgroundColor: "transparent",
                        color: colors.text,
                        fontSize: "10px",
                        cursor: "pointer",
                      }}
                    >
                      {t("settings.cancel")}
                    </button>
                    <button
                      onClick={handleCreateBranch}
                      style={{
                        padding: "3px 8px",
                        borderRadius: "4px",
                        border: "none",
                        backgroundColor: colors.accent,
                        color: "#1e1e2e",
                        fontSize: "10px",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      {t("branch.create")}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Document area */}
      <div style={{
        flex: 1,
        overflow: "auto",
        backgroundColor: colors.surface,
        display: "flex",
        flexDirection: "column",
      }}>
        {/* Document header */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 12px 6px",
        }}>
          <span style={{
            fontSize: "11px",
            fontWeight: 600,
            textTransform: "uppercase",
            color: colors.textMuted,
            letterSpacing: "0.5px",
          }}>
            {t("document.title")}
          </span>
          <button
            style={{
              background: "none",
              border: "none",
              color: colors.textMuted,
              cursor: "pointer",
              padding: "2px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
            }}
            onClick={() => setShowNewDoc(!showNewDoc)}
            title={t("document.create")}
          >
            <Plus size={14} />
          </button>
        </div>

        {/* New document form */}
        {showNewDoc && (
          <div style={{ padding: "4px 12px 8px", display: "flex", flexDirection: "column", gap: "6px" }}>
            <input
              style={{
                backgroundColor: colors.sidebar,
                border: `1px solid ${colors.border}`,
                borderRadius: "6px",
                padding: "6px 10px",
                color: colors.text,
                fontSize: "12px",
                outline: "none",
                width: "100%",
                boxSizing: "border-box",
              }}
              placeholder={t("document.untitled")}
              value={newDocTitle}
              onChange={(e) => setNewDocTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreateDoc()}
              autoFocus
            />
            <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
              <button
                style={{
                  padding: "4px 12px",
                  borderRadius: "5px",
                  border: `1px solid ${colors.border}`,
                  backgroundColor: "transparent",
                  color: colors.text,
                  fontSize: "11px",
                  cursor: "pointer",
                }}
                onClick={() => setShowNewDoc(false)}
              >
                {t("settings.cancel")}
              </button>
              <button
                style={{
                  padding: "4px 12px",
                  borderRadius: "5px",
                  border: "none",
                  backgroundColor: colors.accent,
                  color: "#1e1e2e",
                  fontWeight: 600,
                  fontSize: "11px",
                  cursor: "pointer",
                }}
                onClick={handleCreateDoc}
              >
                {t("document.create")}
              </button>
            </div>
          </div>
        )}

        {/* Document list */}
        <div style={{ padding: "0 4px" }}>
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="doc-row"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "6px 10px",
                margin: "1px 0",
                fontSize: "13px",
                color: colors.text,
                cursor: "pointer",
                borderRadius: "5px",
                borderLeft: doc.id === currentDocId ? `3px solid ${colors.accent}` : "3px solid transparent",
                backgroundColor: doc.id === currentDocId ? "rgba(137,180,250,0.08)" : "transparent",
                transition: "background-color 0.1s",
              }}
              onClick={() => { if (renamingDoc !== doc.id) onSelectDocument(doc.id); }}
              onMouseEnter={(e) => {
                if (doc.id !== currentDocId) {
                  (e.currentTarget as HTMLElement).style.backgroundColor = colors.hover;
                }
              }}
              onMouseLeave={(e) => {
                if (doc.id !== currentDocId) {
                  (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
                }
              }}
            >
              <File size={13} color={doc.id === currentDocId ? colors.accent : colors.textMuted} />
              {renamingDoc === doc.id ? (
                <input
                  ref={docRenameInputRef}
                  style={{
                    flex: 1,
                    backgroundColor: colors.sidebar,
                    border: `1px solid ${colors.border}`,
                    borderRadius: "4px",
                    padding: "2px 6px",
                    color: colors.text,
                    fontSize: "12px",
                    outline: "none",
                    minWidth: 0,
                  }}
                  value={docRenameValue}
                  onChange={(e) => setDocRenameValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") submitDocRename();
                    if (e.key === "Escape") cancelDocRename();
                  }}
                  onBlur={submitDocRename}
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                    {doc.title}
                  </span>
                  {!branchFilter && doc.branches.length > 0 && (
                    <span style={{
                      display: "inline-flex",
                      alignItems: "center",
                      padding: "1px 5px",
                      borderRadius: "3px",
                      fontSize: "10px",
                      fontWeight: 500,
                      backgroundColor: colors.badge,
                      color: colors.textMuted,
                      marginLeft: "4px",
                      whiteSpace: "nowrap",
                    }}>
                      {doc.branches.length > 1
                        ? `${doc.branches.length}`
                        : doc.branches[0]?.replace("target/", "")}
                    </span>
                  )}
                  <button
                    className="doc-action"
                    style={{ background: "none", border: "none", padding: "2px", cursor: "pointer", display: "flex", alignItems: "center", borderRadius: "3px" }}
                    onClick={(e) => startDocRename(doc.id, e)}
                    title={t("document.rename")}
                  >
                    <Pencil size={11} color={colors.textMuted} />
                  </button>
                  <button
                    className="doc-action"
                    style={{ background: "none", border: "none", padding: "2px", cursor: "pointer", display: "flex", alignItems: "center", borderRadius: "3px" }}
                    onClick={(e) => handleDeleteDoc(doc.id, doc.title, e)}
                    title={t("document.delete")}
                  >
                    <Trash2 size={11} color={colors.textMuted} />
                  </button>
                </>
              )}
            </div>
          ))}

          {documents.length === 0 && (
            <div style={{ padding: "12px", fontSize: "12px", color: colors.textMuted, textAlign: "center" }}>
              {t("document.empty")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
