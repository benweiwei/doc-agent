import { useState, useEffect, useCallback } from "react";
import { Clock, Eye } from "lucide-react";
import { api } from "../api/client";
import { useI18n } from "../context/I18nContext";
import type { VersionInfo } from "../types";

// --- Types ---

interface HistoryPanelProps {
  docId: string;
  branch: string;
  onViewDiff: (commitHash: string) => void;
}

// --- Style constants ---

const colors = {
  text: "#cdd6f4",
  textMuted: "#a6adc8",
  border: "#313244",
  accent: "#89b4fa",
  hover: "#313244",
  surface: "#1e1e2e",
  timelineLine: "#313244",
  timelineDot: "#89b4fa",
};

const historyStyles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    overflow: "auto",
    padding: "4px 0",
  },
  emptyState: {
    padding: "16px 12px",
    fontSize: "12px",
    color: colors.textMuted,
    textAlign: "center",
  },
  timelineItem: {
    display: "flex",
    gap: "10px",
    padding: "8px 12px",
    cursor: "pointer",
    position: "relative",
    transition: "background-color 0.1s",
  },
  timelineLeft: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    width: "16px",
    flexShrink: 0,
  },
  timelineDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    backgroundColor: colors.timelineDot,
    marginTop: "4px",
    flexShrink: 0,
  },
  timelineLine: {
    flex: 1,
    width: "2px",
    backgroundColor: colors.timelineLine,
    marginTop: "4px",
  },
  timelineContent: {
    flex: 1,
    minWidth: 0,
  },
  commitMessage: {
    fontSize: "12px",
    color: colors.text,
    lineHeight: "1.4",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  commitMeta: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginTop: "3px",
    fontSize: "11px",
    color: colors.textMuted,
  },
  commitHash: {
    fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace",
    fontSize: "10px",
    color: colors.accent,
    opacity: 0.8,
  },
  viewBtn: {
    background: "none",
    border: "none",
    color: colors.textMuted,
    cursor: "pointer",
    padding: "2px 4px",
    borderRadius: "3px",
    display: "flex",
    alignItems: "center",
    marginLeft: "auto",
    opacity: 0,
    transition: "opacity 0.1s",
  },
  loadingState: {
    padding: "16px 12px",
    fontSize: "12px",
    color: colors.textMuted,
    textAlign: "center",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "8px",
  },
};

// --- Helpers ---

function formatTimestamp(timestamp: string): string {
  const d = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 30) return `${diffD}d ago`;
  return d.toLocaleDateString();
}

function shortHash(hash: string): string {
  return hash.slice(0, 7);
}

// --- Component ---

export function HistoryPanel({ docId, branch, onViewDiff }: HistoryPanelProps) {
  const { t } = useI18n();
  const [history, setHistory] = useState<VersionInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const fetchHistory = useCallback(async () => {
    if (!docId) return;
    setLoading(true);
    try {
      const data = await api.getHistory(docId);
      setHistory(data);
    } catch (err) {
      console.error("Failed to fetch history:", err);
      setHistory([]);
    } finally {
      setLoading(false);
    }
  }, [docId]);

  // Fetch history when docId or branch changes
  useEffect(() => {
    fetchHistory();
  }, [fetchHistory, branch]);

  if (!docId) {
    return (
      <div style={historyStyles.emptyState as React.CSSProperties}>
        {t('document.selectToView')}
      </div>
    );
  }

  if (loading) {
    return (
      <div style={historyStyles.loadingState as React.CSSProperties}>
        <Clock size={14} />
        {t('history.loading')}
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div style={historyStyles.emptyState as React.CSSProperties}>
        {t('history.empty')}
      </div>
    );
  }

  return (
    <div style={historyStyles.container as React.CSSProperties}>
      {history.map((version, idx) => (
        <div
          key={version.id}
          style={{
            ...(historyStyles.timelineItem as React.CSSProperties),
            backgroundColor: hoveredIdx === idx ? colors.hover : "transparent",
          }}
          onClick={() => onViewDiff(version.id)}
          onMouseEnter={() => setHoveredIdx(idx)}
          onMouseLeave={() => setHoveredIdx(null)}
        >
          {/* Timeline visual */}
          <div style={historyStyles.timelineLeft as React.CSSProperties}>
            <div style={historyStyles.timelineDot} />
            {idx < history.length - 1 && <div style={historyStyles.timelineLine} />}
          </div>

          {/* Content */}
          <div style={historyStyles.timelineContent}>
            <div style={historyStyles.commitMessage as React.CSSProperties}>
              {version.message || "Untitled commit"}
            </div>
            <div style={historyStyles.commitMeta}>
              <span style={historyStyles.commitHash}>{shortHash(version.id)}</span>
              <span>{formatTimestamp(version.timestamp)}</span>
              <button
                style={{
                  ...(historyStyles.viewBtn as React.CSSProperties),
                  opacity: hoveredIdx === idx ? 1 : 0,
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  onViewDiff(version.id);
                }}
                title="View diff"
              >
                <Eye size={12} />
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
