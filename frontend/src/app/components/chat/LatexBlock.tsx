import React, { useEffect, useRef } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { cn } from "../../utils";
import { useTheme } from "../ThemeProvider";

interface Props {
  formula: string;
  block?: boolean;
}

/**
 * Renders a LaTeX formula using KaTeX.
 * Supports both inline ($...$) and display ($$...$$) math.
 */
export function LatexBlock({ formula, block = true }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();
  const isDark = theme === "dark";

  useEffect(() => {
    if (ref.current) {
      try {
        katex.render(formula, ref.current, {
          displayMode: block,
          throwOnError: false,
          trust: true,
        });
      } catch {
        if (ref.current) ref.current.textContent = formula;
      }
    }
  }, [formula, block]);

  return (
    <div
      ref={ref}
      className={cn(
        "my-2 overflow-x-auto",
        block ? "text-center py-3 px-4 rounded-lg" : "inline",
        block && (isDark ? "bg-slate-800/60" : "bg-slate-50 border border-slate-200"),
        isDark ? "text-slate-100" : "text-slate-800"
      )}
    />
  );
}

/**
 * Parses a text string and replaces $$...$$ blocks with rendered LaTeX.
 * Returns an array of React nodes.
 */
export function parseLatex(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /\$\$(.*?)\$\$/gs;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    // Text before the LaTeX block
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <LatexBlock key={match.index} formula={match[1].trim()} block={true} />
    );
    lastIndex = regex.lastIndex;
  }

  // Remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}
