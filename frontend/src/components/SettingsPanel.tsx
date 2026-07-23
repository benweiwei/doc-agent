import { useState, useEffect, useCallback } from "react";
import { Settings, X, Save, Pencil, Trash2, Plus, BookOpen } from "lucide-react";
import { api } from "../api/client";
import { useI18n } from "../context/I18nContext";
import { useAppContext } from "../context/AppContext";
import type { AppConfig, StyleTemplateDTO } from "../types";

// --- Types ---

interface SettingsPanelProps {
  isOpen: boolean;
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
  overlay: "rgba(0,0,0,0.5)",
};

const settingsStyles: Record<string, React.CSSProperties> = {
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.overlay,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modal: {
    backgroundColor: colors.bg,
    borderRadius: "12px",
    border: `1px solid ${colors.border}`,
    width: "440px",
    maxWidth: "90vw",
    maxHeight: "80vh",
    display: "flex",
    flexDirection: "column",
    boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px 20px",
    borderBottom: `1px solid ${colors.border}`,
  },
  headerTitle: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "14px",
    fontWeight: 600,
    color: colors.text,
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
  },
  content: {
    flex: 1,
    overflow: "auto",
    padding: "20px",
  },
  section: {
    marginBottom: "20px",
  },
  sectionTitle: {
    fontSize: "12px",
    fontWeight: 600,
    textTransform: "uppercase",
    color: colors.textMuted,
    letterSpacing: "0.5px",
    marginBottom: "12px",
  },
  fieldGroup: {
    marginBottom: "12px",
  },
  label: {
    display: "block",
    fontSize: "12px",
    color: colors.textMuted,
    marginBottom: "6px",
  },
  input: {
    width: "100%",
    backgroundColor: colors.surface,
    border: `1px solid ${colors.border}`,
    borderRadius: "6px",
    padding: "8px 12px",
    color: colors.text,
    fontSize: "13px",
    outline: "none",
    boxSizing: "border-box",
  },
  select: {
    width: "100%",
    backgroundColor: colors.surface,
    border: `1px solid ${colors.border}`,
    borderRadius: "6px",
    padding: "8px 12px",
    color: colors.text,
    fontSize: "13px",
    outline: "none",
    boxSizing: "border-box",
    appearance: "none",
    cursor: "pointer",
  },
  toggle: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "8px 0",
  },
  toggleLabel: {
    fontSize: "13px",
    color: colors.text,
  },
  toggleSwitch: {
    width: "36px",
    height: "20px",
    borderRadius: "10px",
    cursor: "pointer",
    position: "relative",
    transition: "background-color 0.2s",
    border: "none",
    outline: "none",
  },
  toggleKnob: {
    width: "16px",
    height: "16px",
    borderRadius: "50%",
    backgroundColor: "#fff",
    position: "absolute",
    top: "2px",
    transition: "left 0.2s",
  },
  footer: {
    padding: "12px 20px",
    borderTop: `1px solid ${colors.border}`,
    display: "flex",
    justifyContent: "flex-end",
    gap: "8px",
  },
  saveBtn: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "8px 16px",
    borderRadius: "6px",
    border: "none",
    backgroundColor: colors.accent,
    color: "#1e1e2e",
    fontWeight: 600,
    fontSize: "13px",
    cursor: "pointer",
  },
  cancelBtn: {
    padding: "8px 16px",
    borderRadius: "6px",
    border: `1px solid ${colors.border}`,
    backgroundColor: "transparent",
    color: colors.text,
    fontSize: "13px",
    cursor: "pointer",
  },
  statusMsg: {
    fontSize: "12px",
    padding: "8px 0",
  },
};

// --- Component ---

export function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const { t } = useI18n();
  const [config, setConfig] = useState<AppConfig>({
    llm_provider: "cloud",
    llm_model: "",
    temperature: 0.7,
    style_enabled: false,
    auto_save: true,
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");

  // Load config when opened
  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    setStatusMsg("");
    api
      .getConfig()
      .then((data) => {
        setConfig(data);
      })
      .catch((err) => {
        console.error("Failed to load config:", err);
        setStatusMsg(t('settings.loadFailed'));
      })
      .finally(() => setLoading(false));
  }, [isOpen]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setStatusMsg("");
    try {
      await api.updateConfig(config);
      setStatusMsg(t('settings.savedSuccess'));
      setTimeout(() => onClose(), 800);
    } catch (err) {
      console.error("Failed to save config:", err);
      setStatusMsg(t('settings.saveFailed'));
    } finally {
      setSaving(false);
    }
  }, [config, onClose]);

  const handleLearnStyle = useCallback(async () => {
    setStatusMsg(t('style.learning'));
    try {
      await api.learnStyle();
      setStatusMsg(t('style.learnSuccess'));
    } catch (err) {
      console.error("Failed to learn style:", err);
      setStatusMsg(t('style.learnFailed'));
    }
  }, [t]);

  // Handle Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      style={settingsStyles.overlay as React.CSSProperties}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div style={settingsStyles.modal as React.CSSProperties}>
        {/* Header */}
        <div style={settingsStyles.header}>
          <div style={settingsStyles.headerTitle}>
            <Settings size={16} color={colors.accent} />
            <span>{t('settings.title')}</span>
          </div>
          <button style={settingsStyles.closeBtn} onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div style={settingsStyles.content}>
          {loading ? (
            <div style={{ color: colors.textMuted, fontSize: "13px" }}>
              {t('settings.loading')}
            </div>
          ) : (
            <>
              {/* Model Configuration */}
              <div style={settingsStyles.section}>
                <div style={settingsStyles.sectionTitle}>{t('settings.model')}</div>

                <div style={settingsStyles.fieldGroup}>
                  <label style={settingsStyles.label}>{t('settings.provider')}</label>
                  <select
                    style={settingsStyles.select as React.CSSProperties}
                    value={config.llm_provider}
                    onChange={(e) =>
                      setConfig({ ...config, llm_provider: e.target.value })
                    }
                  >
                    <option value="cloud">Cloud (OpenAI / Anthropic)</option>
                    <option value="local">Local (Ollama)</option>
                  </select>
                </div>

                <div style={settingsStyles.fieldGroup}>
                  <label style={settingsStyles.label}>{t('settings.modelName')}</label>
                  <input
                    style={settingsStyles.input}
                    value={config.llm_model}
                    onChange={(e) =>
                      setConfig({ ...config, llm_model: e.target.value })
                    }
                    placeholder="e.g., gpt-4o, claude-3.5-sonnet, llama3"
                  />
                </div>

                <div style={settingsStyles.fieldGroup}>
                  <label style={settingsStyles.label}>
                    {t('settings.temperature')}: {(config.temperature ?? 0.7).toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={config.temperature ?? 0.7}
                    onChange={(e) =>
                      setConfig({ ...config, temperature: parseFloat(e.target.value) })
                    }
                    style={{ width: "100%", accentColor: colors.accent }}
                  />
                </div>
              </div>

              {/* Style Configuration */}
              <div style={settingsStyles.section}>
                <div style={settingsStyles.sectionTitle}>{t('settings.style')}</div>

                <div style={settingsStyles.toggle}>
                  <span style={settingsStyles.toggleLabel}>{t('settings.styleEnabled')}</span>
                  <button
                    style={{
                      ...(settingsStyles.toggleSwitch as React.CSSProperties),
                      backgroundColor: config.style_enabled
                        ? colors.accent
                        : colors.border,
                    }}
                    onClick={() =>
                      setConfig({ ...config, style_enabled: !config.style_enabled })
                    }
                  >
                    <div
                      style={{
                        ...(settingsStyles.toggleKnob as React.CSSProperties),
                        left: config.style_enabled ? "18px" : "2px",
                      }}
                    />
                  </button>
                </div>

                {config.style_enabled && (
                  <button
                    style={{
                      ...settingsStyles.cancelBtn,
                      marginTop: "8px",
                      fontSize: "12px",
                    }}
                    onClick={handleLearnStyle}
                  >
                    {t('settings.learnStyle')}
                  </button>
                )}
              </div>

              {/* Style Templates */}
              <StyleTemplatesSection />

              {/* General */}
              <div style={settingsStyles.section}>
                <div style={settingsStyles.sectionTitle}>{t('settings.general')}</div>

                <div style={settingsStyles.toggle}>
                  <span style={settingsStyles.toggleLabel}>{t('settings.autoSave')}</span>
                  <button
                    style={{
                      ...(settingsStyles.toggleSwitch as React.CSSProperties),
                      backgroundColor: config.auto_save
                        ? colors.accent
                        : colors.border,
                    }}
                    onClick={() =>
                      setConfig({ ...config, auto_save: !config.auto_save })
                    }
                  >
                    <div
                      style={{
                        ...(settingsStyles.toggleKnob as React.CSSProperties),
                        left: config.auto_save ? "18px" : "2px",
                      }}
                    />
                  </button>
                </div>
              </div>

              {/* Status message */}
              {statusMsg && (
                <div
                  style={{
                    ...settingsStyles.statusMsg,
                    color: statusMsg.includes("Failed") ? "#f38ba8" : "#a6e3a1",
                  }}
                >
                  {statusMsg}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div style={settingsStyles.footer}>
          <button style={settingsStyles.cancelBtn} onClick={onClose}>
            {t('settings.cancel')}
          </button>
          <button
            style={{
              ...settingsStyles.saveBtn,
              ...(saving ? { opacity: 0.6, cursor: "not-allowed" } : {}),
            }}
            onClick={handleSave}
            disabled={saving || loading}
          >
            <Save size={14} />
            {saving ? t('settings.saving') : t('settings.save')}
          </button>
        </div>
      </div>
    </div>
  );
}

// --- Style Templates Sub-component ---

function StyleTemplatesSection() {
  const { t } = useI18n();
  const { dispatch } = useAppContext();
  const [templates, setTemplates] = useState<StyleTemplateDTO[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<StyleTemplateDTO | null>(null);
  const [form, setForm] = useState<StyleTemplateDTO>({
    name: "",
    description: "",
    tone: "",
    vocabulary_level: "",
    formatting_rules: [],
    forbidden_patterns: [],
  });
  const [formRulesText, setFormRulesText] = useState("");
  const [formPatternsText, setFormPatternsText] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const loadTemplates = useCallback(async () => {
    try {
      const list = await api.listStyleTemplates();
      setTemplates(list);
      dispatch({ type: "SET_STYLE_TEMPLATES", templates: list });
    } catch (err) {
      console.error("Failed to load style templates:", err);
    }
  }, [dispatch]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const openCreateForm = () => {
    setEditingTemplate(null);
    setForm({ name: "", description: "", tone: "", vocabulary_level: "", formatting_rules: [], forbidden_patterns: [] });
    setFormRulesText("");
    setFormPatternsText("");
    setShowForm(true);
  };

  const openEditForm = (tpl: StyleTemplateDTO) => {
    setEditingTemplate(tpl);
    setForm({ ...tpl });
    setFormRulesText(tpl.formatting_rules.join("\n"));
    setFormPatternsText(tpl.forbidden_patterns.join("\n"));
    setShowForm(true);
  };

  const handleSaveTemplate = async () => {
    setLoading(true);
    setMsg("");
    const payload: StyleTemplateDTO = {
      ...form,
      formatting_rules: formRulesText.split("\n").filter((s) => s.trim()),
      forbidden_patterns: formPatternsText.split("\n").filter((s) => s.trim()),
    };
    try {
      if (editingTemplate) {
        await api.updateStyleTemplate(editingTemplate.name, payload);
      } else {
        await api.createStyleTemplate(payload);
      }
      setShowForm(false);
      await loadTemplates();
    } catch (err) {
      console.error("Failed to save template:", err);
      setMsg("Failed");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(t('style.deleteConfirm'))) return;
    try {
      await api.deleteStyleTemplate(name);
      await loadTemplates();
    } catch (err) {
      console.error("Failed to delete template:", err);
    }
  };

  const handleLearn = async () => {
    setLoading(true);
    setMsg("");
    try {
      await api.learnStyle();
      setMsg(t('style.learnSuccess'));
    } catch (err) {
      console.error(err);
      setMsg(t('style.learnFailed'));
    } finally {
      setLoading(false);
    }
  };

  const sectionStyle: React.CSSProperties = { marginBottom: "20px" };
  const cardStyle: React.CSSProperties = {
    backgroundColor: colors.surface,
    border: `1px solid ${colors.border}`,
    borderRadius: "8px",
    padding: "10px 12px",
    marginBottom: "8px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  };
  const iconBtn: React.CSSProperties = {
    background: "none",
    border: "none",
    cursor: "pointer",
    padding: "4px",
    borderRadius: "4px",
    display: "flex",
    alignItems: "center",
  };
  const inputStyle: React.CSSProperties = {
    width: "100%",
    backgroundColor: colors.surface,
    border: `1px solid ${colors.border}`,
    borderRadius: "6px",
    padding: "8px 12px",
    color: colors.text,
    fontSize: "13px",
    outline: "none",
    boxSizing: "border-box",
    marginBottom: "8px",
  };

  if (showForm) {
    return (
      <div style={sectionStyle}>
        <div style={{ fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: colors.textMuted, letterSpacing: "0.5px", marginBottom: "12px" }}>
          {editingTemplate ? t('style.edit') : t('style.create')}
        </div>
        <input style={inputStyle} placeholder={t('style.name')} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} disabled={!!editingTemplate} />
        <input style={inputStyle} placeholder={t('style.description')} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <input style={inputStyle} placeholder={t('style.tone')} value={form.tone} onChange={(e) => setForm({ ...form, tone: e.target.value })} />
        <input style={inputStyle} placeholder={t('style.vocabularyLevel')} value={form.vocabulary_level} onChange={(e) => setForm({ ...form, vocabulary_level: e.target.value })} />
        <textarea style={{ ...inputStyle, minHeight: "60px", resize: "vertical" }} placeholder={t('style.formattingRules') + ' (每行一条)'} value={formRulesText} onChange={(e) => setFormRulesText(e.target.value)} />
        <textarea style={{ ...inputStyle, minHeight: "60px", resize: "vertical" }} placeholder={t('style.forbiddenPatterns') + ' (每行一条)'} value={formPatternsText} onChange={(e) => setFormPatternsText(e.target.value)} />
        {msg && <div style={{ fontSize: "12px", color: "#f38ba8", marginBottom: "8px" }}>{msg}</div>}
        <div style={{ display: "flex", gap: "8px" }}>
          <button style={{ padding: "6px 14px", borderRadius: "6px", border: `1px solid ${colors.border}`, backgroundColor: "transparent", color: colors.text, fontSize: "12px", cursor: "pointer" }} onClick={() => setShowForm(false)}>
            {t('settings.cancel')}
          </button>
          <button style={{ padding: "6px 14px", borderRadius: "6px", border: "none", backgroundColor: colors.accent, color: "#1e1e2e", fontWeight: 600, fontSize: "12px", cursor: "pointer", opacity: loading ? 0.6 : 1 }} onClick={handleSaveTemplate} disabled={loading || !form.name.trim()}>
            {t('style.save')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={sectionStyle}>
      <div style={{ fontSize: "12px", fontWeight: 600, textTransform: "uppercase", color: colors.textMuted, letterSpacing: "0.5px", marginBottom: "12px" }}>
        {t('style.title')}
      </div>

      {templates.length === 0 && (
        <div style={{ fontSize: "12px", color: colors.textMuted, marginBottom: "8px" }}>
          {t('style.empty')}
        </div>
      )}

      {templates.map((tpl) => (
        <div key={tpl.name} style={cardStyle}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: "13px", color: colors.text, fontWeight: 500 }}>{tpl.name}</div>
            {tpl.description && <div style={{ fontSize: "11px", color: colors.textMuted, marginTop: "2px" }}>{tpl.description}</div>}
            {tpl.tone && <div style={{ fontSize: "11px", color: colors.textMuted }}>{t('style.tone')}: {tpl.tone}</div>}
          </div>
          <div style={{ display: "flex", gap: "4px" }}>
            <button style={iconBtn} onClick={() => openEditForm(tpl)} title={t('style.edit')}>
              <Pencil size={14} color={colors.textMuted} />
            </button>
            <button style={iconBtn} onClick={() => handleDelete(tpl.name)} title={t('style.delete')}>
              <Trash2 size={14} color="#f38ba8" />
            </button>
          </div>
        </div>
      ))}

      <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
        <button style={{ display: "flex", alignItems: "center", gap: "4px", padding: "6px 12px", borderRadius: "6px", border: `1px solid ${colors.border}`, backgroundColor: "transparent", color: colors.text, fontSize: "12px", cursor: "pointer" }} onClick={openCreateForm}>
          <Plus size={12} /> {t('style.create')}
        </button>
        <button style={{ display: "flex", alignItems: "center", gap: "4px", padding: "6px 12px", borderRadius: "6px", border: `1px solid ${colors.border}`, backgroundColor: "transparent", color: colors.text, fontSize: "12px", cursor: "pointer", opacity: loading ? 0.6 : 1 }} onClick={handleLearn} disabled={loading}>
          <BookOpen size={12} /> {loading ? t('style.learning') : t('style.learn')}
        </button>
      </div>

      {msg && <div style={{ fontSize: "12px", color: "#a6e3a1", marginTop: "8px" }}>{msg}</div>}
    </div>
  );
}
