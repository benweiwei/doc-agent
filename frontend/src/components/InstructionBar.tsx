import { useState, useRef, useEffect, useCallback } from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import { useI18n } from "../context/I18nContext";
import { useAppContext } from "../context/AppContext";
import type { EditResponse, WsCompleteMessage } from "../types";

// --- Types ---

interface InstructionBarProps {
  documentId: string;
  branch: string;
  selectedText?: string;
  contextCount?: number;
  onEditStart: () => void;
  onEditComplete: (response: EditResponse) => void;
  onAccept: () => void;
  onReject: () => void;
  onInstructionSubmit?: (instruction: string, selection?: string) => void;
  onEditError?: (errorMessage: string) => void;
}

// --- Style constants ---

const colors = {
  bg: "#181825",
  inputBg: "#1e1e2e",
  text: "#cdd6f4",
  textMuted: "#a6adc8",
  border: "#313244",
  accent: "#89b4fa",
  accentHover: "#a6c8ff",
  surface: "#11111b",
};

const barStyles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  styleRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "12px",
    color: colors.textMuted,
  },
  styleSelect: {
    backgroundColor: colors.inputBg,
    border: `1px solid ${colors.border}`,
    borderRadius: "6px",
    padding: "4px 8px",
    color: colors.text,
    fontSize: "12px",
    outline: "none",
    cursor: "pointer",
    maxWidth: "180px",
  },
  selectionHint: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    fontSize: "12px",
    color: colors.textMuted,
    padding: "4px 0",
  },
  selectionBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: "4px",
    backgroundColor: "rgba(137,180,250,0.15)",
    color: colors.accent,
    padding: "2px 8px",
    borderRadius: "4px",
    fontSize: "11px",
    maxWidth: "300px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  inputRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  input: {
    flex: 1,
    backgroundColor: colors.inputBg,
    border: `1px solid ${colors.border}`,
    borderRadius: "8px",
    padding: "10px 14px",
    color: colors.text,
    fontSize: "13px",
    outline: "none",
    transition: "border-color 0.15s",
  },
  inputFocused: {
    borderColor: colors.accent,
  },
  sendBtn: {
    padding: "8px 16px",
    borderRadius: "8px",
    border: "none",
    backgroundColor: colors.accent,
    color: "#1e1e2e",
    fontWeight: 600,
    fontSize: "13px",
    cursor: "pointer",
    transition: "background-color 0.15s",
    whiteSpace: "nowrap",
  },
  sendBtnDisabled: {
    opacity: 0.5,
    cursor: "not-allowed",
  },
  progressRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "12px",
    color: colors.textMuted,
    padding: "4px 0",
  },
  spinner: {
    width: "12px",
    height: "12px",
    border: "2px solid transparent",
    borderTopColor: colors.accent,
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  actionsRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "4px 0",
  },
  resultMsg: {
    fontSize: "12px",
    color: "#a6e3a1",
  },
  actionBtns: {
    display: "flex",
    gap: "8px",
  },
  btnAccept: {
    padding: "5px 14px",
    borderRadius: "6px",
    border: "none",
    backgroundColor: "#a6e3a1",
    color: "#1e1e2e",
    fontWeight: 600,
    fontSize: "12px",
    cursor: "pointer",
  },
  btnReject: {
    padding: "5px 14px",
    borderRadius: "6px",
    border: `1px solid ${colors.border}`,
    backgroundColor: "transparent",
    color: colors.text,
    fontWeight: 600,
    fontSize: "12px",
    cursor: "pointer",
  },
  shortcutHint: {
    fontSize: "11px",
    color: colors.textMuted,
    opacity: 0.6,
  },
};

// Inject spinner keyframes
const SPINNER_STYLE_ID = "instruction-bar-spinner";
function injectSpinnerStyle() {
  if (document.getElementById(SPINNER_STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = SPINNER_STYLE_ID;
  style.textContent = `
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);
}

// --- Component ---

export function InstructionBar({
  documentId,
  branch,
  selectedText,
  contextCount = 0,
  onEditStart,
  onEditComplete,
  onAccept,
  onReject,
  onInstructionSubmit,
  onEditError,
}: InstructionBarProps) {
  const { t } = useI18n();
  const { state, dispatch } = useAppContext();
  const [instruction, setInstruction] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [progressMsg, setProgressMsg] = useState("");
  const [editDone, setEditDone] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const wsUrl = `ws://${window.location.host}/ws/edit`;
  const { sendMessage, lastMessage, isConnected } = useWebSocket(wsUrl);

  useEffect(() => {
    injectSpinnerStyle();
  }, []);

  // Handle Cmd/Ctrl+K global shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Handle WebSocket messages for edit progress/completion
  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === "token") {
      const tokenContent = (lastMessage as { type: string; content: string }).content || "";
      // Append token to streaming content
      dispatch({ type: "APPEND_STREAMING_CONTENT", payload: tokenContent });
      if (!progressMsg.startsWith(t('editor.aiWriting'))) {
        setProgressMsg(t('editor.aiWriting'));
      }
    } else if (lastMessage.type === "complete") {
      const data = lastMessage as unknown as WsCompleteMessage;
      setIsLoading(false);
      setEditDone(true);
      setProgressMsg("");
      // Stop streaming
      dispatch({ type: "SET_STREAMING", payload: false });
      // Map backend response to frontend EditResponse
      const editResponse: EditResponse = {
        document_id: data.edit_response.document_id,
        original_content: data.edit_response.original_content,
        new_content: data.edit_response.edited_content,
        diff: data.edit_response.diff_summary || "",
        branch: data.edit_response.branch,
        status: "success",
        commit_hash: data.edit_response.commit_hash,
      };
      onEditComplete(editResponse);
    } else if (lastMessage.type === "error") {
      const data = lastMessage as { type: string; message: string };
      setIsLoading(false);
      setProgressMsg("");
      setError(data.message || "Edit failed");
      dispatch({ type: "CLEAR_STREAMING" });
      onEditError?.(data.message || "Edit failed");
    }
  }, [lastMessage, onEditComplete, dispatch, t, progressMsg]);

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!instruction.trim() || !documentId || isLoading) return;

      setIsLoading(true);
      setEditDone(false);
      setError("");
      setProgressMsg(t('editor.aiThinking'));
      // Start streaming mode
      dispatch({ type: "CLEAR_STREAMING" });
      dispatch({ type: "SET_STREAMING", payload: true });
      onEditStart();
      onInstructionSubmit?.(instruction.trim(), selectedText || undefined);

      sendMessage({
        type: "edit",
        document_id: documentId,
        instruction: instruction.trim(),
        branch,
        selection: selectedText || undefined,
        style_template: state.selectedStyle || undefined,
      });

      setInstruction("");
    },
    [instruction, documentId, branch, selectedText, isLoading, sendMessage, onEditStart, dispatch, t]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // Ignore Enter during IME composition (Chinese/Japanese/Korean input)
      if (e.nativeEvent.isComposing || e.keyCode === 229) {
        return;
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  const handleAccept = useCallback(() => {
    setEditDone(false);
    dispatch({ type: "CLEAR_STREAMING" });
    onAccept();
  }, [onAccept, dispatch]);

  const handleReject = useCallback(() => {
    setEditDone(false);
    dispatch({ type: "CLEAR_STREAMING" });
    onReject();
  }, [onReject, dispatch]);

  return (
    <div style={barStyles.container}>
      {/* Context count hint */}
      <div style={{
        fontSize: "11px",
        color: "#6c7086",
        padding: "4px 12px",
      }}>
        {contextCount > 0
          ? `📋 ${t('interaction.contextCount').replace('{count}', String(contextCount))}`
          : `📋 ${t('interaction.noContext')}`}
      </div>
      {/* Style selector row */}
      {state.styleTemplates.length > 0 && (
        <div style={barStyles.styleRow}>
          <select
            style={barStyles.styleSelect}
            value={state.selectedStyle || ""}
            onChange={(e) =>
              dispatch({ type: "SET_SELECTED_STYLE", name: e.target.value || null })
            }
          >
            <option value="">{t('style.noStyle')}</option>
            {state.styleTemplates.map((tpl) => (
              <option key={tpl.name} value={tpl.name}>
                {tpl.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Selection hint - enhanced */}
      <div style={barStyles.selectionHint}>
        {selectedText ? (
          <>
            <span style={barStyles.selectionBadge}>
              {t('editor.selectionHint').replace('{count}', String(selectedText.length))}
            </span>
          </>
        ) : (
          <span style={{ fontSize: "12px", color: colors.textMuted, opacity: 0.7 }}>
            {t('editor.fullDocHint')}
          </span>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div style={{ ...barStyles.progressRow, color: "#f38ba8" }}>
          <span>Error: {error}</span>
        </div>
      )}

      {/* Loading progress */}
      {isLoading && (
        <div style={barStyles.progressRow}>
          <div style={barStyles.spinner} />
          <span>{progressMsg}</span>
        </div>
      )}

      {/* Edit done actions */}
      {editDone && (
        <div style={barStyles.actionsRow}>
          <span style={barStyles.resultMsg}>{t('editor.editReady')}</span>
          <div style={barStyles.actionBtns}>
            <button style={barStyles.btnReject} onClick={handleReject}>
              {t('editor.reject')}
            </button>
            <button style={barStyles.btnAccept} onClick={handleAccept}>
              {t('editor.accept')}
            </button>
          </div>
        </div>
      )}

      {/* Input row */}
      <div style={barStyles.inputRow}>
        <input
          ref={inputRef}
          type="text"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          onKeyDown={handleKeyDown}
          placeholder={
            selectedText
              ? t('editor.instructionSelection')
              : t('editor.instruction')
          }
          disabled={isLoading}
          style={{
            ...barStyles.input,
            ...(isFocused ? barStyles.inputFocused : {}),
            ...(isLoading ? { opacity: 0.5 } : {}),
          }}
        />
        <button
          onClick={() => handleSubmit()}
          disabled={!instruction.trim() || isLoading || !isConnected}
          style={{
            ...barStyles.sendBtn,
            ...(!instruction.trim() || isLoading || !isConnected
              ? barStyles.sendBtnDisabled
              : {}),
          }}
          onMouseEnter={(e) => {
            if (instruction.trim() && !isLoading) {
              (e.target as HTMLElement).style.backgroundColor = colors.accentHover;
            }
          }}
          onMouseLeave={(e) => {
            (e.target as HTMLElement).style.backgroundColor = colors.accent;
          }}
        >
          {isLoading ? "..." : t('editor.send')}
        </button>
      </div>

      {/* Shortcut hint */}
      <div style={barStyles.shortcutHint}>
        {navigator.platform.includes("Mac") ? "⌘" : "Ctrl"}+K to focus •
        Enter to send
      </div>
    </div>
  );
}
