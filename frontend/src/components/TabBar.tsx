import { X } from "lucide-react";
import { useState } from "react";
import { useI18n } from "../context/I18nContext";

// --- Types ---

interface TabBarProps {
  tabs: Array<{ docId: string; title: string }>;
  activeTabId: string | null;
  unsavedDocIds?: Set<string>;
  onSwitchTab: (docId: string) => void;
  onCloseTab: (docId: string) => void;
}

// --- Style constants ---

const colors = {
  bg: "#181825",
  tabDefault: "#1e1e2e",
  tabActive: "#313244",
  text: "#cdd6f4",
  textMuted: "#a6adc8",
  border: "#313244",
  accent: "#89b4fa",
  closeHover: "#f38ba8",
};

const tabBarStyles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    alignItems: "center",
    backgroundColor: colors.bg,
    borderBottom: `1px solid ${colors.border}`,
    height: "32px",
    minHeight: "32px",
    overflow: "hidden",
    paddingLeft: "4px",
  },
  tabsScroll: {
    display: "flex",
    alignItems: "center",
    flex: 1,
    overflow: "auto",
    scrollbarWidth: "none",
  },
  tab: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "0 12px",
    height: "32px",
    fontSize: "12px",
    color: colors.textMuted,
    cursor: "pointer",
    borderRight: `1px solid ${colors.border}`,
    backgroundColor: colors.tabDefault,
    whiteSpace: "nowrap",
    userSelect: "none",
    transition: "background-color 0.1s",
  },
  tabActive: {
    backgroundColor: colors.tabActive,
    color: colors.text,
    borderBottom: `2px solid ${colors.accent}`,
  },
  tabTitle: {
    maxWidth: "120px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  closeBtn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: "16px",
    height: "16px",
    borderRadius: "3px",
    border: "none",
    background: "none",
    color: colors.textMuted,
    cursor: "pointer",
    padding: 0,
    flexShrink: 0,
  },
};

// --- Component ---

export function TabBar({ tabs, activeTabId, unsavedDocIds, onSwitchTab, onCloseTab }: TabBarProps) {
  const { t } = useI18n();
  const [hoverCloseId, setHoverCloseId] = useState<string | null>(null);

  if (tabs.length === 0) return null;

  return (
    <div style={tabBarStyles.container}>
      <div style={tabBarStyles.tabsScroll}>
        {tabs.map((tab) => {
          const isActive = tab.docId === activeTabId;
          return (
            <div
              key={tab.docId}
              style={{
                ...tabBarStyles.tab,
                ...(isActive ? tabBarStyles.tabActive : {}),
              }}
              onClick={() => onSwitchTab(tab.docId)}
            >
              <span style={tabBarStyles.tabTitle}>
                {unsavedDocIds?.has(tab.docId) && (
                  <span style={{ color: colors.accent, marginRight: "4px" }}>●</span>
                )}
                {tab.title || t("document.untitled")}
              </span>
              <button
                style={{
                  ...tabBarStyles.closeBtn,
                  color: hoverCloseId === tab.docId ? colors.closeHover : colors.textMuted,
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  onCloseTab(tab.docId);
                }}
                onMouseEnter={() => setHoverCloseId(tab.docId)}
                onMouseLeave={() => setHoverCloseId(null)}
                title={t("tabs.close")}
              >
                <X size={12} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
