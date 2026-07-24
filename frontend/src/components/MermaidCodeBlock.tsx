/**
 * A CodeBlock variant that renders Mermaid diagrams.
 *
 * Behaviour:
 * - While the caret is inside the block, the raw Mermaid source is shown and
 *   remains fully editable (it stays a normal ```mermaid code block).
 * - When editing ends (the caret leaves the block), the source is rendered
 *   into an SVG diagram.
 * - If rendering fails, the source stays visible together with an error notice.
 *
 * The node keeps the name "codeBlock" so Markdown round-tripping (```mermaid)
 * works unchanged.
 */
import CodeBlock from "@tiptap/extension-code-block";
import {
  ReactNodeViewRenderer,
  NodeViewWrapper,
  NodeViewContent,
  type NodeViewProps,
} from "@tiptap/react";
import { useCallback, useEffect, useState } from "react";
import mermaid from "mermaid";
import { useI18n } from "../context/I18nContext";

let mermaidInitialized = false;
function ensureMermaid() {
  if (mermaidInitialized) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    securityLevel: "loose",
    fontFamily: "system-ui, -apple-system, sans-serif",
  });
  mermaidInitialized = true;
}

function MermaidNodeView({ node, editor, getPos }: NodeViewProps) {
  const { t } = useI18n();
  const isMermaid = node.attrs.language === "mermaid";
  const [editing, setEditing] = useState(true);
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");

  // Track whether the caret is inside this block => editing mode.
  useEffect(() => {
    if (!isMermaid) return;
    const update = () => {
      const pos = typeof getPos === "function" ? getPos() : undefined;
      if (typeof pos !== "number") return;
      const { from, to } = editor.state.selection;
      const end = pos + node.nodeSize;
      setEditing(editor.isFocused && from >= pos && to <= end);
    };
    update();
    editor.on("selectionUpdate", update);
    editor.on("transaction", update);
    editor.on("focus", update);
    editor.on("blur", update);
    return () => {
      editor.off("selectionUpdate", update);
      editor.off("transaction", update);
      editor.off("focus", update);
      editor.off("blur", update);
    };
  }, [editor, getPos, node, isMermaid]);

  // Render the diagram once editing stops.
  useEffect(() => {
    if (!isMermaid || editing) return;
    const code = node.textContent.trim();
    if (!code) {
      setSvg("");
      setError("");
      return;
    }
    ensureMermaid();
    let cancelled = false;
    (async () => {
      try {
        await mermaid.parse(code); // throws on invalid syntax
        const id = "mmd-" + Math.random().toString(36).slice(2, 10);
        const { svg: rendered } = await mermaid.render(id, code);
        if (!cancelled) {
          setSvg(rendered);
          setError("");
        }
      } catch (e) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : String(e);
          setError(msg);
          setSvg("");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isMermaid, editing, node.textContent]);

  const focusIntoBlock = useCallback(() => {
    const pos = typeof getPos === "function" ? getPos() : undefined;
    if (typeof pos !== "number") return;
    editor.chain().focus().setTextSelection(pos + 1).run();
  }, [editor, getPos]);

  // Non-mermaid code blocks render as a plain editable code block.
  if (!isMermaid) {
    return (
      <NodeViewWrapper as="div">
        <pre>
          <NodeViewContent as="code" />
        </pre>
      </NodeViewWrapper>
    );
  }

  const showDiagram = !editing && !!svg && !error;

  return (
    <NodeViewWrapper as="div" className="mermaid-block">
      <div style={{ display: showDiagram ? "none" : "block" }}>
        <div className="mermaid-label">{t("editor.mermaidLabel")}</div>
        <pre>
          <NodeViewContent as="code" />
        </pre>
      </div>
      {error && !editing && (
        <div className="mermaid-error">
          {t("editor.diagramRenderFailed")}: {error}
        </div>
      )}
      {showDiagram && (
        <div
          className="mermaid-preview"
          title={t("editor.mermaidEditHint")}
          onClick={focusIntoBlock}
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      )}
    </NodeViewWrapper>
  );
}

export const MermaidCodeBlock = CodeBlock.extend({
  addNodeView() {
    return ReactNodeViewRenderer(MermaidNodeView);
  },
});
