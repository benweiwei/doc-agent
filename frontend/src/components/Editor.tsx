import { useEditor, EditorContent, Editor as TiptapEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Image from "@tiptap/extension-image";
import { Markdown } from 'tiptap-markdown';
import { MermaidCodeBlock } from "./MermaidCodeBlock";
import { useEffect, useCallback, useMemo, useRef, useState } from "react";
import { useI18n } from "../context/I18nContext";

// --- Types ---

interface EditorProps {
  content: string;
  onChange: (content: string) => void;
  editable?: boolean;
  diffMode?: boolean;
  originalContent?: string;
  editedContent?: string;
  onAcceptEdit?: () => void;
  onRejectEdit?: () => void;
  onSelectionChange?: (selectedText: string) => void;
  /** Upload an image file, returning its URL to embed in the document. */
  onImageUpload?: (file: File) => Promise<string>;
  /** Convert the given code into a Mermaid diagram definition. */
  onGenerateDiagram?: (code: string) => Promise<string>;
}

// --- Style constants ---

const colors = {
  bg: "#1e1e2e",
  text: "#cdd6f4",
  textMuted: "#a6adc8",
  border: "#313244",
  accent: "#89b4fa",
  accentHover: "#a6c8ff",
  diffAdd: "rgba(166,227,161,0.2)",
  diffDel: "rgba(243,139,168,0.2)",
  surface: "#181825",
};

const toolbarStyles: Record<string, React.CSSProperties> = {
  toolbar: {
    display: "flex",
    alignItems: "center",
    gap: "2px",
    padding: "4px 8px",
    backgroundColor: colors.surface,
    borderBottom: `1px solid ${colors.border}`,
    flexWrap: "wrap",
  },
  btn: {
    width: "32px",
    height: "28px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    border: "none",
    borderRadius: "4px",
    backgroundColor: "transparent",
    color: colors.textMuted,
    cursor: "pointer",
    fontSize: "13px",
    fontWeight: 600,
    fontFamily: "system-ui, -apple-system, sans-serif",
    lineHeight: 1,
  },
  btnActive: {
    backgroundColor: "#45475a",
    color: colors.accent,
  },
  separator: {
    width: "1px",
    height: "18px",
    backgroundColor: colors.border,
    margin: "0 4px",
  },
};

const editorStyles: Record<string, React.CSSProperties> = {
  wrapper: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    height: "100%",
    position: "relative",
  },
  editorWithGutter: {
    flex: 1,
    display: "flex",
    flexDirection: "row",
    overflow: "auto",
  },
  gutter: {
    width: "24px",
    minWidth: "24px",
    borderRight: "1px solid #313244",
    cursor: "pointer",
    userSelect: "none",
    position: "relative",
  },
  gutterLine: {
    width: "100%",
    height: "100%",
    position: "absolute",
    top: 0,
    left: 0,
  },
  editorContainer: {
    flex: 1,
    overflow: "auto",
    fontSize: "15px",
    lineHeight: "1.7",
    color: colors.text,
  },
  diffContainer: {
    flex: 1,
    overflow: "auto",
    fontSize: "15px",
    lineHeight: "1.7",
    color: colors.text,
    padding: "8px 0",
  },
  diffActions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: "8px",
    padding: "12px 0",
  },
  btnAccept: {
    padding: "6px 16px",
    borderRadius: "6px",
    border: "none",
    backgroundColor: "#a6e3a1",
    color: "#1e1e2e",
    fontWeight: 600,
    fontSize: "13px",
    cursor: "pointer",
  },
  btnReject: {
    padding: "6px 16px",
    borderRadius: "6px",
    border: `1px solid ${colors.border}`,
    backgroundColor: "transparent",
    color: colors.text,
    fontWeight: 600,
    fontSize: "13px",
    cursor: "pointer",
  },
  diffLine: {
    padding: "2px 12px",
    fontFamily: "ui-monospace, 'SF Mono', Menlo, monospace",
    fontSize: "13px",
    whiteSpace: "pre-wrap" as const,
    wordBreak: "break-word" as const,
  },
  diffAdd: {
    backgroundColor: colors.diffAdd,
    borderLeft: "3px solid #a6e3a1",
  },
  diffDel: {
    backgroundColor: colors.diffDel,
    textDecoration: "line-through",
    borderLeft: "3px solid #f38ba8",
    opacity: 0.8,
  },
  diffCtx: {
    opacity: 0.7,
  },
};

// --- Diff utility ---

function computeLineDiff(original: string, edited: string) {
  const oldLines = original.split("\n");
  const newLines = edited.split("\n");
  const result: { type: "add" | "del" | "ctx"; text: string }[] = [];

  // Simple LCS-based diff
  const m = oldLines.length;
  const n = newLines.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    Array(n + 1).fill(0)
  );

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i]![j] = dp[i - 1]![j - 1]! + 1;
      } else {
        dp[i]![j] = Math.max(dp[i - 1]![j]!, dp[i]![j - 1]!);
      }
    }
  }

  // Backtrack
  const seq: { oldIdx: number; newIdx: number }[] = [];
  let i = m,
    j = n;
  while (i > 0 && j > 0) {
    if (oldLines[i - 1] === newLines[j - 1]) {
      seq.unshift({ oldIdx: i - 1, newIdx: j - 1 });
      i--;
      j--;
    } else if (dp[i - 1]![j]! > dp[i]![j - 1]!) {
      i--;
    } else {
      j--;
    }
  }

  let oi = 0,
    ni = 0;
  for (const s of seq) {
    while (oi < s.oldIdx) {
      result.push({ type: "del", text: oldLines[oi]! });
      oi++;
    }
    while (ni < s.newIdx) {
      result.push({ type: "add", text: newLines[ni]! });
      ni++;
    }
    result.push({ type: "ctx", text: oldLines[oi]! });
    oi++;
    ni++;
  }
  while (oi < m) {
    result.push({ type: "del", text: oldLines[oi]! });
    oi++;
  }
  while (ni < n) {
    result.push({ type: "add", text: newLines[ni]! });
    ni++;
  }

  return result;
}

// --- Global TipTap styles (injected once) ---

const TIPTAP_STYLE_ID = "tiptap-editor-styles";

function injectTipTapStyles() {
  if (document.getElementById(TIPTAP_STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = TIPTAP_STYLE_ID;
  style.textContent = `
    .tiptap-editor .ProseMirror {
      outline: none;
      min-height: 300px;
      caret-color: #cdd6f4;
      color: #cdd6f4;
    }
    .tiptap-editor .ProseMirror p.is-editor-empty:first-child::before {
      content: attr(data-placeholder);
      float: left;
      color: #6c7086;
      pointer-events: none;
      height: 0;
    }
    .tiptap-editor .ProseMirror h1 {
      font-size: 1.8em;
      margin: 0.8em 0 0.4em;
      font-weight: 700;
      color: #cdd6f4;
    }
    .tiptap-editor .ProseMirror h2 {
      font-size: 1.4em;
      margin: 0.7em 0 0.3em;
      font-weight: 600;
      color: #cdd6f4;
    }
    .tiptap-editor .ProseMirror h3 {
      font-size: 1.2em;
      margin: 0.6em 0 0.3em;
      font-weight: 600;
      color: #cdd6f4;
    }
    .tiptap-editor .ProseMirror ul,
    .tiptap-editor .ProseMirror ol {
      padding-left: 1.5em;
    }
    .tiptap-editor .ProseMirror code {
      background: #313244;
      border-radius: 3px;
      padding: 0.2em 0.4em;
      font-size: 0.9em;
      font-family: ui-monospace, 'SF Mono', Menlo, monospace;
    }
    .tiptap-editor .ProseMirror pre {
      background: #11111b;
      border-radius: 6px;
      padding: 12px 16px;
      overflow-x: auto;
    }
    .tiptap-editor .ProseMirror pre code {
      background: none;
      padding: 0;
    }
    .tiptap-editor .ProseMirror blockquote {
      border-left: 3px solid #89b4fa;
      padding-left: 12px;
      margin-left: 0;
      color: #a6adc8;
    }
    .tiptap-editor .ProseMirror hr {
      border: none;
      border-top: 1px solid #313244;
      margin: 1.5em 0;
    }
    .tiptap-editor .ProseMirror img {
      max-width: 100%;
      height: auto;
      border-radius: 6px;
      margin: 8px 0;
    }
    .tiptap-editor .ProseMirror img.ProseMirror-selectednode {
      outline: 2px solid #89b4fa;
    }
    .tiptap-editor .mermaid-block {
      margin: 8px 0;
    }
    .tiptap-editor .mermaid-label {
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.5px;
      color: #6c7086;
      text-transform: uppercase;
      margin-bottom: 2px;
    }
    .tiptap-editor .mermaid-preview {
      background: #181825;
      border: 1px solid #313244;
      border-radius: 6px;
      padding: 12px;
      text-align: center;
      cursor: pointer;
      overflow-x: auto;
    }
    .tiptap-editor .mermaid-preview svg {
      max-width: 100%;
      height: auto;
    }
    .tiptap-editor .mermaid-error {
      background: rgba(243,139,168,0.12);
      border: 1px solid #f38ba8;
      border-radius: 6px;
      padding: 8px 12px;
      margin-top: 4px;
      color: #f38ba8;
      font-size: 12px;
      white-space: pre-wrap;
      word-break: break-word;
    }
  `;
  document.head.appendChild(style);
}

// --- Toolbar Component ---

function Toolbar({ editor, editorMode, onModeChange, onImageUpload, onGenerateDiagram }: { editor: TiptapEditor | null; editorMode: 'visual' | 'source'; onModeChange: (mode: 'visual' | 'source') => void; onImageUpload?: (file: File) => Promise<string>; onGenerateDiagram?: (code: string) => Promise<string> }) {
  const [, setForceUpdate] = useState(0);
  const [busy, setBusy] = useState<null | 'image' | 'diagram'>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { t } = useI18n();

  // Re-render toolbar when selection/content changes
  useEffect(() => {
    if (!editor) return;
    const update = () => setForceUpdate((n) => n + 1);
    editor.on("selectionUpdate", update);
    editor.on("transaction", update);
    return () => {
      editor.off("selectionUpdate", update);
      editor.off("transaction", update);
    };
  }, [editor]);

  const handleImagePick = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file
    if (!file || !editor || !onImageUpload) return;
    setBusy('image');
    try {
      const url = await onImageUpload(file);
      editor.chain().focus().setImage({ src: url, alt: file.name }).run();
    } catch (err) {
      console.error("Image upload failed:", err);
      alert(t('editor.imageUploadFailed'));
    } finally {
      setBusy(null);
    }
  }, [editor, onImageUpload, t]);

  const handleGenerateDiagram = useCallback(async () => {
    if (!editor || !onGenerateDiagram) return;
    const { from, to } = editor.state.selection;
    const code = editor.state.doc.textBetween(from, to, "\n").trim();
    if (!code) {
      alert(t('editor.diagramNoSelection'));
      return;
    }
    setBusy('diagram');
    try {
      const mermaid = await onGenerateDiagram(code);
      if (mermaid) {
        editor.chain().focus().insertContent({
          type: 'codeBlock',
          attrs: { language: 'mermaid' },
          content: [{ type: 'text', text: mermaid }],
        }).run();
      }
    } catch (err) {
      console.error("Diagram generation failed:", err);
      alert(t('editor.diagramFailed'));
    } finally {
      setBusy(null);
    }
  }, [editor, onGenerateDiagram, t]);

  if (!editor) return null;

  const btnStyle = (isActive: boolean): React.CSSProperties => ({
    ...toolbarStyles.btn,
    ...(isActive ? toolbarStyles.btnActive : {}),
  });

  const modeBtnStyle = (isActive: boolean): React.CSSProperties => ({
    padding: "2px 10px",
    fontSize: "11px",
    fontWeight: 600,
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    backgroundColor: "transparent",
    color: isActive ? colors.accent : "#6c7086",
    minWidth: "48px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  });

  return (
    <div style={toolbarStyles.toolbar}>
      {/* Inline formatting */}
      <button
        style={btnStyle(editor.isActive("bold"))}
        onClick={() => editor.chain().focus().toggleBold().run()}
        title="Bold (Ctrl+B)"
        onMouseEnter={(e) => { if (!editor.isActive("bold")) (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
        onMouseLeave={(e) => { if (!editor.isActive("bold")) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        B
      </button>
      <button
        style={{ ...btnStyle(editor.isActive("italic")), fontStyle: "italic" }}
        onClick={() => editor.chain().focus().toggleItalic().run()}
        title="Italic (Ctrl+I)"
        onMouseEnter={(e) => { if (!editor.isActive("italic")) (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
        onMouseLeave={(e) => { if (!editor.isActive("italic")) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        I
      </button>
      <button
        style={{ ...btnStyle(editor.isActive("strike")), textDecoration: "line-through" }}
        onClick={() => editor.chain().focus().toggleStrike().run()}
        title="Strikethrough"
        onMouseEnter={(e) => { if (!editor.isActive("strike")) (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
        onMouseLeave={(e) => { if (!editor.isActive("strike")) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        S
      </button>

      {/* Headings */}
      <button
        style={btnStyle(editor.isActive("heading", { level: 1 }))}
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        title="Heading 1"
        onMouseEnter={(e) => { if (!editor.isActive("heading", { level: 1 })) (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
        onMouseLeave={(e) => { if (!editor.isActive("heading", { level: 1 })) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        <span style={{ fontSize: "13px" }}>H1</span>
      </button>
      <button
        style={btnStyle(editor.isActive("heading", { level: 2 }))}
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        title="Heading 2"
        onMouseEnter={(e) => { if (!editor.isActive("heading", { level: 2 })) (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
        onMouseLeave={(e) => { if (!editor.isActive("heading", { level: 2 })) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        <span style={{ fontSize: "12px" }}>H2</span>
      </button>
      <button
        style={btnStyle(editor.isActive("heading", { level: 3 }))}
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        title="Heading 3"
        onMouseEnter={(e) => { if (!editor.isActive("heading", { level: 3 })) (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
        onMouseLeave={(e) => { if (!editor.isActive("heading", { level: 3 })) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        <span style={{ fontSize: "11px" }}>H3</span>
      </button>

      <div style={toolbarStyles.separator} />

      {/* Block elements */}
      <button
        style={btnStyle(editor.isActive("bulletList"))}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        title="Bullet List"
        onMouseEnter={(e) => { if (!editor.isActive("bulletList")) (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
        onMouseLeave={(e) => { if (!editor.isActive("bulletList")) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="9" y1="6" x2="20" y2="6"/><line x1="9" y1="12" x2="20" y2="12"/><line x1="9" y1="18" x2="20" y2="18"/><circle cx="4" cy="6" r="1.5" fill="currentColor" stroke="none"/><circle cx="4" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="4" cy="18" r="1.5" fill="currentColor" stroke="none"/></svg>
      </button>
      <button
        style={btnStyle(editor.isActive("orderedList"))}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        title="Ordered List"
        onMouseEnter={(e) => { if (!editor.isActive("orderedList")) (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
        onMouseLeave={(e) => { if (!editor.isActive("orderedList")) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="10" y1="6" x2="20" y2="6"/><line x1="10" y1="12" x2="20" y2="12"/><line x1="10" y1="18" x2="20" y2="18"/><text x="2" y="8" fontSize="7" fill="currentColor" stroke="none" fontFamily="sans-serif">1</text><text x="2" y="14" fontSize="7" fill="currentColor" stroke="none" fontFamily="sans-serif">2</text><text x="2" y="20" fontSize="7" fill="currentColor" stroke="none" fontFamily="sans-serif">3</text></svg>
      </button>
      <button
        style={btnStyle(editor.isActive("blockquote"))}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        title="Blockquote"
        onMouseEnter={(e) => { if (!editor.isActive("blockquote")) (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
        onMouseLeave={(e) => { if (!editor.isActive("blockquote")) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/></svg>
      </button>
      <button
        style={btnStyle(editor.isActive("codeBlock"))}
        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
        title="Code Block"
        onMouseEnter={(e) => { if (!editor.isActive("codeBlock")) (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
        onMouseLeave={(e) => { if (!editor.isActive("codeBlock")) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
      </button>

      <div style={toolbarStyles.separator} />

      {/* Horizontal rule */}
      <button
        style={btnStyle(false)}
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
        title="Horizontal Rule"
        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="2" y1="12" x2="22" y2="12"/></svg>
      </button>

      {(onImageUpload || onGenerateDiagram) && <div style={toolbarStyles.separator} />}

      {/* Image import */}
      {onImageUpload && (
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={handleImagePick}
          />
          <button
            style={btnStyle(false)}
            onClick={() => fileInputRef.current?.click()}
            disabled={busy !== null}
            title={t('editor.insertImage')}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
          >
            {busy === 'image'
              ? <span style={{ fontSize: "11px" }}>…</span>
              : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>}
          </button>
        </>
      )}

      {/* Code -> architecture diagram */}
      {onGenerateDiagram && (
        <button
          style={btnStyle(false)}
          onClick={handleGenerateDiagram}
          disabled={busy !== null}
          title={t('editor.codeToDiagram')}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "#313244"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}
        >
          {busy === 'diagram'
            ? <span style={{ fontSize: "11px" }}>…</span>
            : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><path d="M6.5 10v2.5a1 1 0 0 0 1 1H14"/></svg>}
        </button>
      )}

      {/* Spacer to push mode toggle to the right */}
      <div style={{ flex: 1 }} />

      {/* Visual / Source mode toggle */}
      <div style={{ display: "flex", alignItems: "center", border: `1px solid ${colors.border}`, borderRadius: "4px", overflow: "hidden" }}>
        <button
          style={modeBtnStyle(editorMode === 'visual')}
          onClick={() => onModeChange('visual')}
          title={t('editor.visual')}
        >
          {t('editor.visual')}
        </button>
        <button
          style={modeBtnStyle(editorMode === 'source')}
          onClick={() => onModeChange('source')}
          title={t('editor.source')}
        >
          {t('editor.source')}
        </button>
      </div>
    </div>
  );
}

// --- Component ---

export function Editor({
  content,
  onChange,
  editable = true,
  diffMode = false,
  originalContent = "",
  editedContent = "",
  onAcceptEdit,
  onRejectEdit,
  onSelectionChange,
  onImageUpload,
  onGenerateDiagram,
}: EditorProps) {
  // Inject global styles on mount
  useEffect(() => {
    injectTipTapStyles();
  }, []);

  const gutterRef = useRef<HTMLDivElement>(null);
  const [hoveredGutterY, setHoveredGutterY] = useState<number | null>(null);
  const [editorMode, setEditorMode] = useState<'visual' | 'source'>('visual');
  const [sourceContent, setSourceContent] = useState('');

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        codeBlock: false,
      }),
      MermaidCodeBlock,
      Placeholder.configure({
        placeholder: "Start writing documentation here...",
      }),
      Markdown.configure({
        html: false,
        transformCopiedText: true,
        transformPastedText: true,
      }),
      Image.configure({
        inline: false,
        allowBase64: true,
      }),
    ],
    content,
    editable: editable && !diffMode,
    onUpdate: ({ editor: ed }) => {
      const md = ed.storage.markdown.getMarkdown();
      onChange(md);
    },
    onSelectionUpdate: ({ editor: ed }) => {
      if (onSelectionChange) {
        const { from, to } = ed.state.selection;
        if (from !== to) {
          const text = ed.state.doc.textBetween(from, to, " ");
          onSelectionChange(text);
        } else {
          onSelectionChange("");
        }
      }
    },
  });

  // Sync content from props when it changes externally
  useEffect(() => {
    if (editor && !editor.isDestroyed) {
      const currentMd = editor.storage.markdown.getMarkdown();
      if (content !== currentMd) {
        editor.commands.setContent(content, false);
      }
    }
  }, [content, editor]);

  // Sync editable
  useEffect(() => {
    if (editor && !editor.isDestroyed) {
      editor.setEditable(editable && !diffMode);
    }
  }, [editable, diffMode, editor]);

  // Compute diff lines
  const diffLines = useMemo(() => {
    if (!diffMode) return [];
    return computeLineDiff(originalContent, editedContent);
  }, [diffMode, originalContent, editedContent]);

  const handleAccept = useCallback(() => {
    onAcceptEdit?.();
  }, [onAcceptEdit]);

  const handleReject = useCallback(() => {
    onRejectEdit?.();
  }, [onRejectEdit]);

  // Gutter click: select the paragraph at click position
  const handleGutterClick = useCallback(
    (e: React.MouseEvent) => {
      if (!editor) return;
      const gutterEl = gutterRef.current;
      if (!gutterEl) return;

      // Get the editor DOM element
      const editorDom = editor.view.dom;
      const editorRect = editorDom.getBoundingClientRect();

      // Find the position at coordinates
      const pos = editor.view.posAtCoords({ left: editorRect.left + 12, top: e.clientY });
      if (!pos) return;

      // Resolve to get the paragraph node
      const resolved = editor.state.doc.resolve(pos.pos);
      // Find the closest top-level block node
      const depth = resolved.depth;
      if (depth >= 1) {
        const start = resolved.before(1);
        const end = resolved.after(1);
        editor.commands.setTextSelection({ from: start + 1, to: end - 1 });
      }
    },
    [editor]
  );

  const handleGutterMouseMove = useCallback((e: React.MouseEvent) => {
    setHoveredGutterY(e.clientY);
  }, []);

  const handleGutterMouseLeave = useCallback(() => {
    setHoveredGutterY(null);
  }, []);

  // --- Mode switching logic ---
  const handleModeChange = useCallback((mode: 'visual' | 'source') => {
    if (mode === editorMode) return;
    if (mode === 'source') {
      // Switching to source: grab markdown from TipTap
      if (editor && !editor.isDestroyed) {
        setSourceContent(editor.storage.markdown.getMarkdown());
      }
    } else {
      // Switching to visual: sync source back to TipTap
      if (editor && !editor.isDestroyed) {
        editor.commands.setContent(sourceContent, false);
      }
    }
    setEditorMode(mode);
  }, [editorMode, editor, sourceContent]);

  const handleSourceChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setSourceContent(val);
    onChange(val);
  }, [onChange]);

  // --- Render ---

  if (diffMode) {
    return (
      <div style={editorStyles.wrapper}>
        <div style={editorStyles.diffContainer}>
          {diffLines.map((line, idx) => {
            let lineStyle: React.CSSProperties = {
              ...editorStyles.diffLine,
            };
            if (line.type === "add") {
              lineStyle = { ...lineStyle, ...editorStyles.diffAdd };
            } else if (line.type === "del") {
              lineStyle = { ...lineStyle, ...editorStyles.diffDel };
            } else {
              lineStyle = { ...lineStyle, ...editorStyles.diffCtx };
            }
            return (
              <div key={idx} style={lineStyle}>
                <span style={{ marginRight: "8px", opacity: 0.5, userSelect: "none" }}>
                  {line.type === "add" ? "+" : line.type === "del" ? "-" : " "}
                </span>
                {line.text || "\u00A0"}
              </div>
            );
          })}
        </div>
        <div style={editorStyles.diffActions}>
          <button
            style={editorStyles.btnReject}
            onClick={handleReject}
            onMouseEnter={(e) => {
              (e.target as HTMLElement).style.backgroundColor = "#313244";
            }}
            onMouseLeave={(e) => {
              (e.target as HTMLElement).style.backgroundColor = "transparent";
            }}
          >
            Reject
          </button>
          <button
            style={editorStyles.btnAccept}
            onClick={handleAccept}
            onMouseEnter={(e) => {
              (e.target as HTMLElement).style.backgroundColor = "#94e2a5";
            }}
            onMouseLeave={(e) => {
              (e.target as HTMLElement).style.backgroundColor = "#a6e3a1";
            }}
          >
            Accept
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={editorStyles.wrapper} className="tiptap-editor">
      {editable && <Toolbar editor={editor} editorMode={editorMode} onModeChange={handleModeChange} onImageUpload={onImageUpload} onGenerateDiagram={onGenerateDiagram} />}
      {editorMode === 'visual' ? (
        <div style={editorStyles.editorWithGutter}>
          {/* Gutter for paragraph selection */}
          <div
            ref={gutterRef}
            style={{
              ...editorStyles.gutter,
              backgroundColor: hoveredGutterY !== null ? "rgba(137,180,250,0.06)" : "transparent",
            }}
            onClick={handleGutterClick}
            onMouseMove={handleGutterMouseMove}
            onMouseLeave={handleGutterMouseLeave}
          />
          <div style={editorStyles.editorContainer}>
            <EditorContent editor={editor} />
          </div>
        </div>
      ) : (
        <textarea
          value={sourceContent}
          onChange={handleSourceChange}
          spellCheck={false}
          wrap="off"
          style={{
            flex: 1,
            width: "100%",
            height: "100%",
            resize: "none",
            backgroundColor: "#1e1e2e",
            color: "#cdd6f4",
            border: `1px solid #45475a`,
            borderRadius: "4px",
            padding: "12px 16px",
            fontSize: "14px",
            lineHeight: "1.7",
            fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
            outline: "none",
            overflow: "auto",
          }}
        />
      )}
    </div>
  );
}
