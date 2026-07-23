import { useState } from "react";
import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";
import { X, Columns, AlignJustify } from "lucide-react";
import { useI18n } from "../context/I18nContext";

// --- Types ---

interface DiffViewProps {
  oldContent: string;
  newContent: string;
  oldTitle?: string;
  newTitle?: string;
  onClose: () => void;
}

// --- Style constants ---

const colors = {
  text: "#cdd6f4",
  textMuted: "#a6adc8",
  border: "#313244",
  accent: "#89b4fa",
  bg: "#1e1e2e",
  surface: "#181825",
};

const diffStyles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    overflow: "hidden",
    backgroundColor: colors.bg,
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "8px 12px",
    borderBottom: `1px solid ${colors.border}`,
    backgroundColor: colors.surface,
    flexShrink: 0,
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  title: {
    fontSize: "12px",
    fontWeight: 600,
    color: colors.text,
  },
  stats: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "11px",
  },
  statAdd: {
    color: "#a6e3a1",
    fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace",
  },
  statDel: {
    color: "#f38ba8",
    fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace",
  },
  headerRight: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
  },
  modeBtn: {
    background: "none",
    border: `1px solid ${colors.border}`,
    color: colors.textMuted,
    cursor: "pointer",
    padding: "3px 8px",
    borderRadius: "4px",
    display: "flex",
    alignItems: "center",
    gap: "4px",
    fontSize: "11px",
  },
  modeBtnActive: {
    borderColor: colors.accent,
    color: colors.accent,
  },
  closeBtn: {
    background: "none",
    border: "none",
    color: colors.textMuted,
    cursor: "pointer",
    padding: "4px",
    borderRadius: "4px",
    display: "flex",
    alignItems: "center",
    marginLeft: "8px",
  },
  content: {
    flex: 1,
    overflow: "auto",
  },
};

// --- react-diff-viewer custom styles for dark theme ---

const diffViewerStyles = {
  variables: {
    dark: {
      diffViewerBackground: "#1e1e2e",
      diffViewerColor: "#cdd6f4",
      addedBackground: "rgba(166,227,161,0.12)",
      addedColor: "#a6e3a1",
      removedBackground: "rgba(243,139,168,0.12)",
      removedColor: "#f38ba8",
      wordAddedBackground: "rgba(166,227,161,0.3)",
      wordRemovedBackground: "rgba(243,139,168,0.3)",
      addedGutterBackground: "rgba(166,227,161,0.08)",
      removedGutterBackground: "rgba(243,139,168,0.08)",
      gutterBackground: "#181825",
      gutterBackgroundDark: "#11111b",
      highlightBackground: "rgba(137,180,250,0.1)",
      highlightGutterBackground: "rgba(137,180,250,0.08)",
      codeFoldGutterBackground: "#181825",
      codeFoldBackground: "#11111b",
      emptyLineBackground: "#1e1e2e",
      gutterColor: "#6c7086",
      addedGutterColor: "#a6e3a1",
      removedGutterColor: "#f38ba8",
      codeFoldContentColor: "#a6adc8",
    },
  },
  line: {
    padding: "2px 10px",
    fontSize: "13px",
    fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace",
  },
  gutter: {
    padding: "0 8px",
    minWidth: "35px",
  },
};

// --- Helpers ---

function computeStats(oldContent: string, newContent: string) {
  const oldLines = oldContent.split("\n");
  const newLines = newContent.split("\n");
  // Simple approximation: count new lines that don't exist in old, and vice versa
  const added = newLines.filter((l) => !oldLines.includes(l)).length;
  const removed = oldLines.filter((l) => !newLines.includes(l)).length;
  return { added, removed };
}

// --- Component ---

export function DiffView({
  oldContent,
  newContent,
  oldTitle = "Original",
  newTitle = "Modified",
  onClose,
}: DiffViewProps) {
  const { t } = useI18n();
  const [splitView, setSplitView] = useState(false);
  const stats = computeStats(oldContent, newContent);

  return (
    <div style={diffStyles.container as React.CSSProperties}>
      {/* Header bar */}
      <div style={diffStyles.header}>
        <div style={diffStyles.headerLeft}>
          <span style={diffStyles.title}>
            {oldTitle} → {newTitle}
          </span>
          <div style={diffStyles.stats}>
            <span style={diffStyles.statAdd}>+{stats.added}</span>
            <span style={diffStyles.statDel}>-{stats.removed}</span>
          </div>
        </div>
        <div style={diffStyles.headerRight}>
          <button
            style={{
              ...diffStyles.modeBtn,
              ...(!splitView ? diffStyles.modeBtnActive : {}),
            }}
            onClick={() => setSplitView(false)}
            title={t('diff.unified')}
          >
            <AlignJustify size={12} />
            {t('diff.unified')}
          </button>
          <button
            style={{
              ...diffStyles.modeBtn,
              ...(splitView ? diffStyles.modeBtnActive : {}),
            }}
            onClick={() => setSplitView(true)}
            title={t('diff.split')}
          >
            <Columns size={12} />
            {t('diff.split')}
          </button>
          <button
            style={diffStyles.closeBtn}
            onClick={onClose}
            title={t('diff.close')}
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Diff content */}
      <div style={diffStyles.content}>
        <ReactDiffViewer
          oldValue={oldContent}
          newValue={newContent}
          splitView={splitView}
          useDarkTheme={true}
          leftTitle={oldTitle}
          rightTitle={newTitle}
          compareMethod={DiffMethod.WORDS}
          styles={diffViewerStyles}
        />
      </div>
    </div>
  );
}
