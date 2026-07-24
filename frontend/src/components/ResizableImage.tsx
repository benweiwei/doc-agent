/**
 * An Image node that can be resized after insertion.
 *
 * - Adds a `width` attribute (pixels).
 * - Renders a React NodeView with a drag handle at the bottom-right corner
 *   (visible when the image is selected) to resize it interactively.
 * - Persists the width across Markdown round-trips by serializing to an
 *   `<img ... width="N">` HTML tag when a width is set (plain `![](src)`
 *   otherwise). Requires the Markdown extension to have `html: true`.
 */
import Image from "@tiptap/extension-image";
import {
  ReactNodeViewRenderer,
  NodeViewWrapper,
  type NodeViewProps,
} from "@tiptap/react";
import { useCallback, useRef } from "react";

function ResizableImageView({
  node,
  updateAttributes,
  selected,
  editor,
}: NodeViewProps) {
  const imgRef = useRef<HTMLImageElement>(null);
  const width = node.attrs.width as number | null;

  const startResize = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const startX = e.clientX;
      const startW = imgRef.current?.offsetWidth || 0;
      const onMove = (ev: MouseEvent) => {
        const newW = Math.max(40, startW + (ev.clientX - startX));
        updateAttributes({ width: Math.round(newW) });
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [updateAttributes]
  );

  return (
    <NodeViewWrapper
      as="div"
      className="resizable-image"
      style={{
        display: "inline-block",
        position: "relative",
        lineHeight: 0,
        maxWidth: "100%",
      }}
    >
      <img
        ref={imgRef}
        src={node.attrs.src}
        alt={node.attrs.alt || ""}
        title={node.attrs.title || ""}
        draggable={false}
        style={{
          width: width ? `${width}px` : "auto",
          maxWidth: "100%",
          height: "auto",
          borderRadius: "6px",
          display: "block",
          outline: selected ? "2px solid #89b4fa" : "none",
        }}
      />
      {selected && editor.isEditable && (
        <span
          onMouseDown={startResize}
          title="拖动调整大小"
          style={{
            position: "absolute",
            right: -5,
            bottom: -5,
            width: 12,
            height: 12,
            background: "#89b4fa",
            border: "2px solid #1e1e2e",
            borderRadius: "50%",
            cursor: "nwse-resize",
          }}
        />
      )}
    </NodeViewWrapper>
  );
}

export const ResizableImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      width: {
        default: null,
        parseHTML: (element) => {
          const attr = element.getAttribute("width");
          if (attr) return parseInt(attr, 10) || null;
          const styleWidth = (element as HTMLElement).style?.width;
          if (styleWidth && styleWidth.endsWith("px")) {
            return parseInt(styleWidth, 10) || null;
          }
          return null;
        },
        renderHTML: (attributes) =>
          attributes.width ? { width: attributes.width } : {},
      },
    };
  },
  addNodeView() {
    return ReactNodeViewRenderer(ResizableImageView);
  },
  addStorage() {
    return {
      markdown: {
        serialize(state: any, node: any) {
          const { src, alt, title, width } = node.attrs;
          if (width) {
            const a = alt ? ` alt="${alt}"` : "";
            const tt = title ? ` title="${title}"` : "";
            state.write(`<img src="${src}"${a}${tt} width="${width}">`);
          } else {
            const tt = title ? ` "${title}"` : "";
            state.write(`![${alt || ""}](${src}${tt})`);
          }
          state.closeBlock(node);
        },
        parse: {},
      },
    };
  },
});
