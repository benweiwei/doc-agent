import { useCallback, useEffect, useState, useRef } from "react";
import { Editor } from "./components/Editor";
import { InstructionBar } from "./components/InstructionBar";
import { BranchPanel } from "./components/BranchPanel";
import { DiffView } from "./components/DiffView";
import { HistoryPanel } from "./components/HistoryPanel";
import { InteractionPanel } from "./components/InteractionPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { TabBar } from "./components/TabBar";
import { useAppContext } from "./context/AppContext";
import { useI18n } from "./context/I18nContext";
import { PanelLeftClose, PanelRightClose, FileText, Settings, Save, Download } from "lucide-react";
import { api } from "./api/client";
import type { EditResponse, InteractionRecord, UnifiedDocument } from "./types";

// --- Style constants ---
const colors = {
  bg: "#1e1e2e",
  sidebar: "#181825",
  text: "#cdd6f4",
  textMuted: "#a6adc8",
  border: "#313244",
  accent: "#89b4fa",
  surface: "#1e1e2e",
};

const styles = {
  app: {
    display: "flex",
    flexDirection: "column" as const,
    height: "100vh",
    width: "100vw",
    backgroundColor: colors.bg,
    color: colors.text,
    fontFamily: "system-ui, -apple-system, sans-serif",
    fontSize: "14px",
    overflow: "hidden",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    height: "40px",
    minHeight: "40px",
    padding: "0 12px",
    borderBottom: `1px solid ${colors.border}`,
    backgroundColor: colors.sidebar,
  },
  headerTitle: {
    fontSize: "13px",
    fontWeight: 600,
    color: colors.text,
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  headerActions: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
  },
  iconBtn: {
    background: "none",
    border: "none",
    color: colors.textMuted,
    cursor: "pointer",
    padding: "4px 6px",
    borderRadius: "4px",
    display: "flex",
    alignItems: "center",
  },
  langBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    padding: "2px 10px",
    borderRadius: "4px",
    fontSize: "11px",
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    minWidth: "32px",
  },
  langBtnActive: {
    color: colors.accent,
  },
  langBtnInactive: {
    color: "#6c7086",
  },
  langGroup: {
    display: "flex",
    alignItems: "center",
    border: `1px solid ${colors.border}`,
    borderRadius: "4px",
    overflow: "hidden",
  },
  main: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
  },
  leftPanel: {
    width: "240px",
    minWidth: "240px",
    backgroundColor: colors.sidebar,
    borderRight: `1px solid ${colors.border}`,
    display: "flex",
    flexDirection: "column" as const,
    overflow: "hidden",
  },
  leftPanelHidden: {
    width: 0,
    minWidth: 0,
    overflow: "hidden",
    border: "none",
  },
  center: {
    flex: 1,
    display: "flex",
    flexDirection: "column" as const,
    overflow: "hidden",
    minWidth: 0,
  },
  editorArea: {
    flex: 1,
    overflow: "auto",
    padding: "16px 24px",
  },
  instructionArea: {
    borderTop: `1px solid ${colors.border}`,
    padding: "8px 16px",
    backgroundColor: colors.sidebar,
  },
  rightPanel: {
    width: "280px",
    minWidth: "280px",
    backgroundColor: colors.sidebar,
    borderLeft: `1px solid ${colors.border}`,
    display: "flex",
    flexDirection: "column" as const,
    overflow: "hidden",
  },
  rightPanelHidden: {
    width: 0,
    minWidth: 0,
    overflow: "hidden",
    border: "none",
  },
  panelSection: {
    padding: "12px",
    borderBottom: `1px solid ${colors.border}`,
  },
  panelTitle: {
    fontSize: "11px",
    fontWeight: 600,
    textTransform: "uppercase" as const,
    color: colors.textMuted,
    marginBottom: "8px",
    letterSpacing: "0.5px",
  },
};

function App() {
  const { state, dispatch } = useAppContext();
  const { t, locale, setLocale } = useI18n();
  const [selectedText, setSelectedText] = useState("");
  const [diffMode, setDiffMode] = useState(false);
  const [originalContent, setOriginalContent] = useState("");
  const [editedContent, setEditedContent] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [saveToast, setSaveToast] = useState(false);
  const [rightTab, setRightTab] = useState<"history" | "interactions">("interactions");
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const saveToastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [historyDiff, setHistoryDiff] = useState<{
    oldContent: string;
    newContent: string;
    oldTitle: string;
    newTitle: string;
  } | null>(null);

  const toggleLeft = useCallback(
    () => dispatch({ type: "TOGGLE_LEFT_PANEL" }),
    [dispatch]
  );
  const toggleRight = useCallback(
    () => dispatch({ type: "TOGGLE_RIGHT_PANEL" }),
    [dispatch]
  );

  // --- Data loading ---

  // Load branches on mount
  useEffect(() => {
    api
      .listBranches()
      .then((branches) => dispatch({ type: "SET_BRANCHES", payload: branches }))
      .catch((err) => console.error("Failed to load branches:", err));
  }, [dispatch]);

  // Load all documents (cross-branch) on mount
  useEffect(() => {
    api.listAllDocuments().then(data => {
      dispatch({ type: "SET_ALL_DOCUMENTS", documents: data.documents });
    }).catch((err) => console.error("Failed to load all documents:", err));
  }, [dispatch]);

  // Load documents on mount and when branch changes
  useEffect(() => {
    api
      .listDocuments(state.currentBranch)
      .then((docs) => {
        dispatch({ type: "SET_DOCUMENTS", payload: docs });
        // Auto-select first document if none selected
        if (!state.currentDocument && docs.length > 0) {
          api.getDocument(docs[0]!.id, state.currentBranch).then((fullDoc) => {
            dispatch({ type: "SET_CURRENT_DOCUMENT", payload: fullDoc });
            dispatch({ type: "OPEN_TAB", payload: { docId: fullDoc.id, title: fullDoc.title } });
          }).catch((err) => console.error("Failed to load first doc:", err));
        }
      })
      .catch((err) => console.error("Failed to load documents:", err));
  }, [state.currentBranch, dispatch]);

  // --- Load persisted interactions on mount ---

  useEffect(() => {
    api
      .listInteractions()
      .then((records) => {
        // Restore in reverse so newest are first in state
        for (const record of records.reverse()) {
          dispatch({ type: "ADD_INTERACTION", payload: record });
        }
      })
      .catch((err) => console.error("Failed to load interactions:", err));
  }, [dispatch]);

  // --- Load interactions for current document ---

  useEffect(() => {
    if (state.currentDocument?.id) {
      api.listInteractions(state.currentDocument.id, state.currentBranch).then(records => {
        dispatch({ type: "SET_INTERACTION_HISTORY", history: records });
      });
    } else {
      dispatch({ type: "SET_INTERACTION_HISTORY", history: [] });
    }
  }, [state.currentDocument?.id, state.currentBranch, dispatch]);

  // --- Branch handlers ---

  const handleSwitchBranch = useCallback(
    async (branchName: string) => {
      dispatch({ type: "SET_CURRENT_BRANCH", payload: branchName });
      dispatch({ type: "SET_BRANCH_FILTER", branch: branchName });
    },
    [dispatch]
  );

  const handleCreateBranch = useCallback(
    async (name: string, target: string) => {
      try {
        await api.createBranch(name, target);
        const branches = await api.listBranches();
        dispatch({ type: "SET_BRANCHES", payload: branches });
      } catch (err) {
        console.error("Failed to create branch:", err);
      }
    },
    [dispatch]
  );

  const handleRenameBranch = useCallback(
    async (oldName: string, newName: string) => {
      try {
        await api.renameBranch(oldName, newName);
        const branches = await api.listBranches();
        dispatch({ type: "SET_BRANCHES", payload: branches });
        if (state.currentBranch === oldName) {
          dispatch({ type: "SET_CURRENT_BRANCH", payload: newName });
        }
      } catch (err) {
        console.error("Failed to rename branch:", err);
      }
    },
    [dispatch, state.currentBranch]
  );

  // --- Document handlers ---

  const handleSetBranchFilter = useCallback(
    (branch: string | null) => {
      dispatch({ type: "SET_BRANCH_FILTER", branch });
    },
    [dispatch]
  );

  // Compute filtered documents based on branch filter
  const filteredDocuments: UnifiedDocument[] = state.branchFilter
    ? state.allDocuments.filter(d => d.branches.includes(state.branchFilter!))
    : state.allDocuments;

  const handleSelectDocument = useCallback(
    async (docId: string) => {
      // Find the document in allDocuments to determine which branch to load from
      const unifiedDoc = state.allDocuments.find(d => d.id === docId);
      let branch = state.currentBranch;
      if (unifiedDoc && !unifiedDoc.branches.includes(branch)) {
        // Auto-switch to the first available branch for this document
        branch = unifiedDoc.branches[0] || branch;
        dispatch({ type: "SET_CURRENT_BRANCH", payload: branch });
      }
      try {
        const doc = await api.getDocument(docId, branch);
        dispatch({ type: "SET_CURRENT_DOCUMENT", payload: doc });
        dispatch({ type: "OPEN_TAB", payload: { docId: doc.id, title: doc.title } });
        setHistoryDiff(null);
      } catch (err) {
        console.error("Failed to load document:", err);
      }
    },
    [state.currentBranch, state.allDocuments, dispatch]
  );

  const handleCreateDocument = useCallback(
    async (title: string) => {
      try {
        const newDoc = await api.createDocument(title, undefined, state.currentBranch);
        // Refresh both per-branch and unified document lists so the new doc appears in the sidebar
        const docs = await api.listDocuments(state.currentBranch);
        dispatch({ type: "SET_DOCUMENTS", payload: docs });
        const allDocs = await api.listAllDocuments();
        dispatch({ type: "SET_ALL_DOCUMENTS", documents: allDocs.documents });
        const fullDoc = await api.getDocument(newDoc.id, state.currentBranch);
        dispatch({ type: "SET_CURRENT_DOCUMENT", payload: fullDoc });
        dispatch({ type: "OPEN_TAB", payload: { docId: fullDoc.id, title: fullDoc.title } });
      } catch (err) {
        console.error("Failed to create document:", err);
      }
    },
    [state.currentBranch, dispatch]
  );

  // --- Tab handlers ---

  const handleSwitchTab = useCallback(
    async (docId: string) => {
      dispatch({ type: "SWITCH_TAB", payload: docId });
      try {
        const doc = await api.getDocument(docId, state.currentBranch);
        dispatch({ type: "SET_CURRENT_DOCUMENT", payload: doc });
        setHistoryDiff(null);
      } catch (err) {
        console.error("Failed to load document for tab:", err);
      }
    },
    [state.currentBranch, dispatch]
  );

  const handleCloseTab = useCallback(
    async (docId: string) => {
      dispatch({ type: "CLOSE_TAB", payload: docId });
      // If closing the active tab, load the next active document
      if (state.activeTabId === docId) {
        const remaining = state.openTabs.filter((t) => t.docId !== docId);
        if (remaining.length > 0) {
          const closedIdx = state.openTabs.findIndex((t) => t.docId === docId);
          const nextIdx = Math.min(closedIdx, remaining.length - 1);
          const nextDocId = remaining[nextIdx]!.docId;
          try {
            const doc = await api.getDocument(nextDocId, state.currentBranch);
            dispatch({ type: "SET_CURRENT_DOCUMENT", payload: doc });
          } catch (err) {
            console.error("Failed to load next doc:", err);
          }
        } else {
          dispatch({ type: "SET_CURRENT_DOCUMENT", payload: null });
        }
      }
      setHistoryDiff(null);
    },
    [state.activeTabId, state.openTabs, state.currentBranch, dispatch]
  );

  // --- History diff handler ---

  const handleViewDiff = useCallback(
    async (commitHash: string) => {
      if (!state.currentDocument) return;
      try {
        const history = await api.getHistory(state.currentDocument.id);
        const version = history.find((v) => v.id === commitHash);
        if (version && version.content_snapshot != null) {
          setHistoryDiff({
            oldContent: version.content_snapshot,
            newContent: state.currentDocument.content,
            oldTitle: commitHash.slice(0, 7),
            newTitle: "Current",
          });
        }
      } catch (err) {
        console.error("Failed to load diff:", err);
      }
    },
    [state.currentDocument]
  );

  const handleCloseDiff = useCallback(() => {
    setHistoryDiff(null);
  }, []);

  // --- Editor content change handler ---

  const handleContentChange = useCallback(
    (newContent: string) => {
      if (state.currentDocument) {
        dispatch({
          type: "SET_CURRENT_DOCUMENT",
          payload: { ...state.currentDocument, content: newContent },
        });
        dispatch({ type: "MARK_UNSAVED", payload: state.currentDocument.id });
      }
    },
    [state.currentDocument, dispatch]
  );

  // --- Save handler ---

  const handleSave = useCallback(async () => {
    if (!state.currentDocument) return;
    try {
      const filename = state.currentDocument.id.split("/").pop() || state.currentDocument.id;
      await api.saveDocument(
        state.currentDocument.id,
        state.currentDocument.content,
        state.currentBranch,
        `Update ${filename}`
      );
      dispatch({ type: "MARK_SAVED", payload: state.currentDocument.id });
      setSaveToast(true);
      if (saveToastTimer.current) clearTimeout(saveToastTimer.current);
      saveToastTimer.current = setTimeout(() => setSaveToast(false), 2000);
    } catch (err) {
      console.error("Failed to save document:", err);
    }
  }, [state.currentDocument, state.currentBranch, dispatch]);

  // Ctrl/Cmd+S shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleSave]);

  // --- Interaction record helper ---

  const currentInteractionId = useRef<string | null>(null);

  function generateInteractionId(): string {
    return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  }

  // --- Edit flow handlers ---

  const handleEditStart = useCallback(() => {
    dispatch({ type: "SET_EDITING", payload: true });
  }, [dispatch]);

  const handleEditComplete = useCallback(
    (response: EditResponse) => {
      dispatch({ type: "SET_EDITING", payload: false });
      dispatch({ type: "SET_EDIT_RESULT", payload: response });
      setOriginalContent(response.original_content);
      setEditedContent(response.new_content);
      setDiffMode(true);

      // Update interaction record to completed
      if (currentInteractionId.current) {
        const lines = response.diff ? response.diff.split("\n").length : 0;
        const summary = lines > 0
          ? (locale === "zh" ? `修改了 ${lines} 行` : `${lines} lines modified`)
          : response.new_content.slice(0, 50);
        const updatePayload = {
          id: currentInteractionId.current,
          status: "completed" as const,
          resultSummary: summary,
          editedContent: response.new_content,
        };
        dispatch({
          type: "UPDATE_INTERACTION",
          payload: updatePayload,
        });
        api.updateInteraction(updatePayload.id, { status: "completed", resultSummary: summary, editedContent: response.new_content }).catch((err) => console.error("Failed to update interaction:", err));
      }
    },
    [dispatch, locale]
  );

  const handleAcceptEdit = useCallback(async () => {
    if (state.currentDocument && editedContent) {
      const updatedDoc = { ...state.currentDocument, content: editedContent };
      dispatch({
        type: "SET_CURRENT_DOCUMENT",
        payload: updatedDoc,
      });
      try {
        await api.saveDocument(
          state.currentDocument.id,
          editedContent,
          state.currentBranch,
          `AI edit: ${state.currentDocument.title}`
        );
      } catch (err) {
        console.error("Failed to commit edit:", err);
      }
    }
    // Update interaction record to accepted
    if (currentInteractionId.current) {
      dispatch({
        type: "UPDATE_INTERACTION",
        payload: { id: currentInteractionId.current, status: "accepted" },
      });
      api.updateInteraction(currentInteractionId.current, { status: "accepted" }).catch((err) => console.error("Failed to update interaction:", err));
      currentInteractionId.current = null;
    }
    setDiffMode(false);
    setOriginalContent("");
    setEditedContent("");
    dispatch({ type: "SET_EDIT_RESULT", payload: null });
  }, [state.currentDocument, state.currentBranch, editedContent, dispatch]);

  const handleRejectEdit = useCallback(() => {
    // Update interaction record to rejected
    if (currentInteractionId.current) {
      dispatch({
        type: "UPDATE_INTERACTION",
        payload: { id: currentInteractionId.current, status: "rejected" },
      });
      api.updateInteraction(currentInteractionId.current, { status: "rejected" }).catch((err) => console.error("Failed to update interaction:", err));
      currentInteractionId.current = null;
    }
    setDiffMode(false);
    setOriginalContent("");
    setEditedContent("");
    dispatch({ type: "SET_EDIT_RESULT", payload: null });
  }, [dispatch]);

  const handleSelectionChange = useCallback((text: string) => {
    setSelectedText(text);
  }, []);

  // --- Instruction submit handler (creates interaction record) ---

  const handleInstructionSubmit = useCallback(
    (instruction: string, selection?: string) => {
      const id = generateInteractionId();
      currentInteractionId.current = id;
      const record: InteractionRecord = {
        id,
        timestamp: new Date().toISOString(),
        documentId: state.currentDocument?.id || "",
        branch: state.currentBranch,
        instruction,
        selection: selection || undefined,
        status: "pending",
      };
      dispatch({ type: "ADD_INTERACTION", payload: record });
      // Persist to backend
      api.addInteraction(record).catch((err) => console.error("Failed to persist interaction:", err));
    },
    [state.currentDocument, state.currentBranch, dispatch]
  );

  // --- Track streaming status for interaction record ---

  useEffect(() => {
    if (state.isStreaming && currentInteractionId.current) {
      const update = { id: currentInteractionId.current, status: "streaming" as const };
      dispatch({
        type: "UPDATE_INTERACTION",
        payload: update,
      });
      api.updateInteraction(update.id, { status: "streaming" }).catch((err) => console.error("Failed to update interaction:", err));
    }
  }, [state.isStreaming, dispatch]);

  // --- Edit error handler ---

  const handleEditError = useCallback(
    (errorMessage: string) => {
      if (currentInteractionId.current) {
        dispatch({
          type: "UPDATE_INTERACTION",
          payload: {
            id: currentInteractionId.current,
            status: "error",
            resultSummary: errorMessage,
          },
        });
        api.updateInteraction(currentInteractionId.current, { status: "error", resultSummary: errorMessage }).catch((err) => console.error("Failed to update interaction:", err));
        currentInteractionId.current = null;
      }
    },
    [dispatch]
  );

  // Determine whether to show history diff view in center
  const showHistoryDiff = historyDiff !== null;
  const { streamingContent, isStreaming } = state;

  // --- Export handler ---

  const handleExport = useCallback((format: 'md' | 'txt') => {
    const content = state.currentDocument?.content || '';
    const title = state.currentDocument?.title || 'document';
    const safeName = title.replace(/\.[^.]+$/, ''); // strip existing extension
    const ext = format === 'md' ? '.md' : '.txt';
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${safeName}${ext}`;
    a.click();
    URL.revokeObjectURL(url);
    setExportMenuOpen(false);
  }, [state.currentDocument]);

  return (
    <div style={styles.app}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerTitle}>
          <FileText size={14} color={colors.accent} />
          <span>doc-agent</span>
        </div>
        <div style={styles.headerActions}>
          {/* Language toggle */}
          <div style={styles.langGroup}>
            <button
              style={{
                ...styles.langBtn,
                ...(locale === "zh" ? styles.langBtnActive : styles.langBtnInactive),
              }}
              onClick={() => setLocale("zh")}
              title="中文"
            >
              ZH
            </button>
            <button
              style={{
                ...styles.langBtn,
                ...(locale === "en" ? styles.langBtnActive : styles.langBtnInactive),
              }}
              onClick={() => setLocale("en")}
              title="English"
            >
              EN
            </button>
          </div>
          <button
            style={styles.iconBtn}
            onClick={() => setSettingsOpen(true)}
            title={t("app.settings")}
          >
            <Settings size={16} />
          </button>
          <button
            style={styles.iconBtn}
            onClick={toggleLeft}
            title="Toggle left panel"
          >
            <PanelLeftClose size={16} />
          </button>
          <button
            style={styles.iconBtn}
            onClick={toggleRight}
            title="Toggle right panel"
          >
            <PanelRightClose size={16} />
          </button>
        </div>
      </header>

      {/* Main layout */}
      <div style={styles.main}>
        {/* Left sidebar — BranchPanel */}
        <aside
          style={
            state.leftPanelOpen
              ? styles.leftPanel
              : { ...styles.leftPanel, ...styles.leftPanelHidden }
          }
        >
          <BranchPanel
            branches={state.branches}
            currentBranch={state.currentBranch}
            branchFilter={state.branchFilter}
            documents={filteredDocuments}
            currentDocId={state.currentDocument?.id ?? null}
            onSwitchBranch={handleSwitchBranch}
            onSetBranchFilter={handleSetBranchFilter}
            onCreateBranch={handleCreateBranch}
            onRenameBranch={handleRenameBranch}
            onSelectDocument={handleSelectDocument}
            onCreateDocument={handleCreateDocument}
          />
        </aside>

        {/* Center: TabBar + editor or diff view + instruction bar */}
        <section style={styles.center}>
          {/* Tab Bar */}
          <div style={{ display: "flex", alignItems: "center" }}>
            <div style={{ flex: 1, overflow: "hidden" }}>
              <TabBar
                tabs={state.openTabs}
                activeTabId={state.activeTabId}
                unsavedDocIds={state.unsavedChanges}
                onSwitchTab={handleSwitchTab}
                onCloseTab={handleCloseTab}
              />
            </div>
            {/* Save button + Export button + toast */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "0 8px", height: "32px", backgroundColor: colors.sidebar, borderBottom: `1px solid ${colors.border}` }}>
              {saveToast && (
                <span style={{ fontSize: "11px", color: "#a6e3a1", whiteSpace: "nowrap" }}>
                  {t("document.saveSuccess")}
                </span>
              )}
              <button
                style={{
                  ...styles.iconBtn,
                  opacity: state.currentDocument && state.unsavedChanges.has(state.currentDocument.id) ? 1 : 0.4,
                }}
                onClick={handleSave}
                title={`${t("document.save")} (${navigator.platform.includes("Mac") ? "⌘" : "Ctrl"}+S)`}
              >
                <Save size={15} color={state.currentDocument && state.unsavedChanges.has(state.currentDocument.id) ? colors.accent : colors.textMuted} />
              </button>
              {/* Export dropdown */}
              <div style={{ position: "relative" }}>
                <button
                  style={{
                    ...styles.iconBtn,
                    opacity: state.currentDocument ? 1 : 0.4,
                  }}
                  onClick={() => setExportMenuOpen(!exportMenuOpen)}
                  title={t("document.export")}
                  disabled={!state.currentDocument}
                >
                  <Download size={15} color={colors.textMuted} />
                </button>
                {exportMenuOpen && (
                  <div style={{
                    position: "absolute",
                    top: "100%",
                    right: 0,
                    marginTop: "4px",
                    backgroundColor: colors.sidebar,
                    border: `1px solid ${colors.border}`,
                    borderRadius: "6px",
                    padding: "4px 0",
                    zIndex: 100,
                    minWidth: "160px",
                    boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
                  }}>
                    <button
                      onClick={() => handleExport('md')}
                      style={{
                        display: "block",
                        width: "100%",
                        padding: "6px 12px",
                        fontSize: "12px",
                        color: colors.text,
                        backgroundColor: "transparent",
                        border: "none",
                        cursor: "pointer",
                        textAlign: "left",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = colors.border)}
                      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                    >
                      {t("document.exportMd")}
                    </button>
                    <button
                      onClick={() => handleExport('txt')}
                      style={{
                        display: "block",
                        width: "100%",
                        padding: "6px 12px",
                        fontSize: "12px",
                        color: colors.text,
                        backgroundColor: "transparent",
                        border: "none",
                        cursor: "pointer",
                        textAlign: "left",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = colors.border)}
                      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
                    >
                      {t("document.exportTxt")}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div style={styles.editorArea}>
            {showHistoryDiff ? (
              <DiffView
                oldContent={historyDiff.oldContent}
                newContent={historyDiff.newContent}
                oldTitle={historyDiff.oldTitle}
                newTitle={historyDiff.newTitle}
                onClose={handleCloseDiff}
              />
            ) : (
              <>
                <Editor
                  content={state.currentDocument?.content || ""}
                  onChange={handleContentChange}
                  editable={!state.isEditing}
                  diffMode={diffMode}
                  originalContent={originalContent}
                  editedContent={editedContent}
                  onAcceptEdit={handleAcceptEdit}
                  onRejectEdit={handleRejectEdit}
                  onSelectionChange={handleSelectionChange}
                />
                {isStreaming && (
                  <div style={{
                    marginTop: "12px",
                    padding: "12px 16px",
                    backgroundColor: "#1e1e2e",
                    borderLeft: "3px solid #89b4fa",
                    borderRadius: "0 6px 6px 0",
                    fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace",
                    fontSize: "13px",
                    lineHeight: "1.7",
                    color: "#cdd6f4",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    maxHeight: "200px",
                    overflow: "auto",
                    position: "relative",
                  }}>
                    <div style={{
                      fontSize: "11px",
                      color: "#89b4fa",
                      marginBottom: "6px",
                      fontFamily: "system-ui, -apple-system, sans-serif",
                      fontWeight: 600,
                    }}>
                      {streamingContent ? t('editor.aiWriting') : t('editor.aiThinking')}
                    </div>
                    <div>
                      {streamingContent || "\u00A0"}
                      <span style={{
                        display: "inline-block",
                        width: "2px",
                        height: "14px",
                        backgroundColor: "#89b4fa",
                        marginLeft: "1px",
                        verticalAlign: "text-bottom",
                        animation: "blink 1s step-end infinite",
                      }} />
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
          <div style={styles.instructionArea}>
            <InstructionBar
              documentId={state.currentDocument?.id || ""}
              branch={state.currentBranch}
              selectedText={selectedText}
              contextCount={state.interactionHistory.length}
              onEditStart={handleEditStart}
              onEditComplete={handleEditComplete}
              onAccept={handleAcceptEdit}
              onReject={handleRejectEdit}
              onInstructionSubmit={handleInstructionSubmit}
              onEditError={handleEditError}
            />
          </div>
        </section>

        {/* Right sidebar — History + Interactions */}
        <aside
          style={
            state.rightPanelOpen
              ? styles.rightPanel
              : { ...styles.rightPanel, ...styles.rightPanelHidden }
          }
        >
          {/* Tab buttons */}
          <div style={{ display: "flex", borderBottom: `1px solid ${colors.border}` }}>
            <button
              onClick={() => setRightTab("interactions")}
              style={{
                flex: 1,
                padding: "8px 0",
                fontSize: "11px",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                backgroundColor: rightTab === "interactions" ? colors.bg : "transparent",
                color: rightTab === "interactions" ? colors.accent : colors.textMuted,
                borderBottom: rightTab === "interactions" ? `2px solid ${colors.accent}` : "2px solid transparent",
              }}
            >
              {t("interaction.title")}
            </button>
            <button
              onClick={() => setRightTab("history")}
              style={{
                flex: 1,
                padding: "8px 0",
                fontSize: "11px",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                backgroundColor: rightTab === "history" ? colors.bg : "transparent",
                color: rightTab === "history" ? colors.accent : colors.textMuted,
                borderBottom: rightTab === "history" ? `2px solid ${colors.accent}` : "2px solid transparent",
              }}
            >
              {t("history.title")}
            </button>
          </div>
          <div style={{ ...styles.panelSection, flex: 1, overflow: "auto" }}>
            {rightTab === "history" ? (
              <HistoryPanel
                docId={state.currentDocument?.id || ""}
                branch={state.currentBranch}
                onViewDiff={handleViewDiff}
              />
            ) : (
              <InteractionPanel />
            )}
          </div>
        </aside>
      </div>

      {/* Settings modal */}
      <SettingsPanel isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

export default App;
