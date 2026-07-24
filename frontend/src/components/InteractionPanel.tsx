import { useState } from "react";
import { useAppContext } from "../context/AppContext";
import { useI18n } from "../context/I18nContext";
import type { InteractionRecord } from "../types";
import { ChevronDown, ChevronRight } from "lucide-react";

// --- Style constants ---

const colors = {
  text: "#cdd6f4",
  textMuted: "#6c7086",
  border: "#313244",
  accent: "#89b4fa",
  surface: "#1e1e2e",
  hover: "#313244",
  userBubbleBg: "#313244",
  aiBubbleBg: "#181825",
  statusGreen: "#a6e3a1",
  statusRed: "#f38ba8",
  statusBlue: "#89b4fa",
  statusYellow: "#f9e2af",
};

// --- Helpers ---

function formatTime(timestamp: string): string {
  const d = new Date(timestamp);
  const h = d.getHours().toString().padStart(2, "0");
  const m = d.getMinutes().toString().padStart(2, "0");
  return `${h}:${m}`;
}

function getStatusDotColor(status: InteractionRecord["status"]): string {
  switch (status) {
    case "accepted":
    case "completed":
      return colors.statusGreen;
    case "rejected":
    case "error":
      return colors.statusRed;
    case "pending":
    case "streaming":
      return colors.statusBlue;
    default:
      return colors.textMuted;
  }
}

function truncateText(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "...";
}

function agentEventColor(kind: string): string {
  switch (kind) {
    case "tool_call":
      return colors.statusBlue;
    case "tool_result":
      return colors.statusGreen;
    case "step":
    default:
      return colors.textMuted;
  }
}

// --- Component ---

export function InteractionPanel() {
  const { state } = useAppContext();
  const { t } = useI18n();
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const records = state.interactionHistory;
  const timeline = state.agentTimeline;

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Live agent activity timeline (step / tool_call / tool_result).
  const timelineBlock = timeline.length > 0 ? (
    <div style={{
      borderBottom: `1px solid ${colors.border}`,
      padding: "8px 12px",
      display: "flex",
      flexDirection: "column",
      gap: "6px",
    }}>
      <div style={{
        fontSize: "10px",
        fontWeight: 600,
        letterSpacing: "0.5px",
        textTransform: "uppercase",
        color: colors.accent,
      }}>
        {t("agent.timeline")}
      </div>
      {timeline.map((ev) => (
        <div key={ev.id} style={{ display: "flex", gap: "8px", alignItems: "flex-start" }}>
          <span style={{
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            marginTop: "5px",
            backgroundColor: agentEventColor(ev.kind),
            flexShrink: 0,
          }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: "11px",
              color: colors.text,
              fontFamily: ev.kind === "step"
                ? "system-ui, -apple-system, sans-serif"
                : "ui-monospace, 'SF Mono', Menlo, monospace",
            }}>
              {ev.label}
            </div>
            {ev.detail && (
              <pre style={{
                margin: "2px 0 0",
                fontSize: "10px",
                color: colors.textMuted,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                maxHeight: "80px",
                overflow: "auto",
                fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace",
              }}>
                {ev.detail.length > 300 ? ev.detail.slice(0, 300) + "\n..." : ev.detail}
              </pre>
            )}
          </div>
        </div>
      ))}
    </div>
  ) : null;

  if (records.length === 0 && timeline.length === 0) {
    return (
      <div style={{
        padding: "16px 12px",
        fontSize: "12px",
        color: colors.textMuted,
        textAlign: "center",
      }}>
        {t("interaction.empty")}
      </div>
    );
  }

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100%",
      overflow: "auto",
      padding: "4px 0",
    }}>
      {timelineBlock}
      {records.map((record) => {
        const isExpanded = expandedIds.has(record.id);
        const dotColor = getStatusDotColor(record.status);
        const statusKey = record.status as string;
        const statusLabel = t(`interaction.${statusKey}` as Parameters<typeof t>[0]);

        return (
          <div key={record.id} style={{ borderBottom: `1px solid ${colors.border}` }}>
            {/* Compact row */}
            <div
              onClick={() => toggleExpand(record.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "6px 10px",
                height: "32px",
                cursor: "pointer",
                backgroundColor: "transparent",
                transition: "background-color 0.1s",
                boxSizing: "border-box",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = colors.hover;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = "transparent";
              }}
            >
              {/* Expand indicator */}
              {isExpanded
                ? <ChevronDown size={11} color={colors.textMuted} />
                : <ChevronRight size={11} color={colors.textMuted} />
              }
              {/* Time */}
              <span style={{
                fontSize: "10px",
                color: colors.textMuted,
                whiteSpace: "nowrap",
                fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace",
              }}>
                {formatTime(record.timestamp)}
              </span>
              {/* Instruction summary */}
              <span style={{
                flex: 1,
                fontSize: "12px",
                color: colors.text,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}>
                {truncateText(record.instruction, 40)}
              </span>
              {/* Status dot */}
              <span style={{
                width: "7px",
                height: "7px",
                borderRadius: "50%",
                backgroundColor: dotColor,
                flexShrink: 0,
              }} title={statusLabel} />
            </div>

            {/* Expanded detail */}
            {isExpanded && (
              <div style={{
                padding: "8px 12px 12px 28px",
                maxHeight: "300px",
                overflow: "auto",
                display: "flex",
                flexDirection: "column",
                gap: "8px",
              }}>
                {/* Full instruction */}
                <div style={{
                  backgroundColor: colors.userBubbleBg,
                  borderRadius: "6px",
                  padding: "8px 10px",
                }}>
                  <div style={{
                    fontSize: "10px",
                    color: colors.accent,
                    marginBottom: "4px",
                    fontWeight: 600,
                  }}>
                    {t("interaction.instruction")}
                  </div>
                  <div style={{
                    fontSize: "12px",
                    color: colors.text,
                    lineHeight: "1.5",
                    wordBreak: "break-word",
                    whiteSpace: "pre-wrap",
                  }}>
                    {record.instruction}
                  </div>
                  {record.selection && (
                    <div style={{
                      marginTop: "6px",
                      padding: "4px 8px",
                      borderLeft: `2px solid ${colors.accent}`,
                      fontSize: "11px",
                      color: colors.textMuted,
                      lineHeight: "1.4",
                    }}>
                      <span style={{ fontSize: "10px", color: colors.accent, display: "block", marginBottom: "2px" }}>
                        {t("interaction.selection")}:
                      </span>
                      {record.selection.length > 200
                        ? record.selection.slice(0, 200) + "..."
                        : record.selection}
                    </div>
                  )}
                </div>

                {/* AI result */}
                {(record.resultSummary || record.editedContent) && (
                  <div style={{
                    backgroundColor: colors.aiBubbleBg,
                    borderLeft: `3px solid ${colors.accent}`,
                    borderRadius: "0 6px 6px 0",
                    padding: "8px 10px",
                  }}>
                    <div style={{
                      fontSize: "10px",
                      color: colors.accent,
                      marginBottom: "4px",
                      fontWeight: 600,
                    }}>
                      {t("interaction.result")}
                    </div>
                    {record.resultSummary && (
                      <div style={{
                        fontSize: "12px",
                        color: colors.text,
                        lineHeight: "1.5",
                        marginBottom: record.editedContent ? "6px" : "0",
                      }}>
                        {record.resultSummary}
                      </div>
                    )}
                    {record.editedContent && (
                      <div style={{
                        fontSize: "11px",
                        color: colors.textMuted,
                        lineHeight: "1.5",
                        fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace",
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                        maxHeight: "150px",
                        overflow: "auto",
                        padding: "6px 8px",
                        backgroundColor: "rgba(0,0,0,0.2)",
                        borderRadius: "4px",
                      }}>
                        {record.editedContent.length > 500
                          ? record.editedContent.slice(0, 500) + "\n..."
                          : record.editedContent}
                      </div>
                    )}
                  </div>
                )}

                {/* Meta: document, status */}
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  fontSize: "10px",
                  color: colors.textMuted,
                }}>
                  {record.documentId && (
                    <span style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                      📄 {record.documentId.split("/").pop()}
                    </span>
                  )}
                  <span style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "3px",
                    color: dotColor,
                  }}>
                    <span style={{
                      width: "5px",
                      height: "5px",
                      borderRadius: "50%",
                      backgroundColor: dotColor,
                    }} />
                    {statusLabel}
                  </span>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
