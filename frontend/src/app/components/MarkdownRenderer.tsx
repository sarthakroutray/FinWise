import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { cn } from "../utils";
import { useTheme } from "./ThemeProvider";

export function MarkdownRenderer({ content, className }: { content: string; className?: string }) {
  const { theme, accentColors: ac } = useTheme();
  const isDark = theme === "dark";

  return (
    <div
      className={cn(
        "max-w-none break-words text-sm leading-relaxed",
        isDark ? "text-slate-300 [&_h1]:text-slate-100 [&_h2]:text-slate-200 [&_strong]:text-slate-200 [&_a]:text-blue-400" 
               : "text-slate-700 [&_h1]:text-slate-900 [&_h2]:text-slate-800 [&_strong]:text-slate-900 [&_a]:text-blue-600",
        "[&_ol]:list-decimal [&_ul]:list-disc [&_li]:ml-5 [&_p]:mb-3 last:[&_p]:mb-0",
        "[&_h1]:text-xl [&_h1]:font-bold [&_h1]:mb-4",
        "[&_h2]:text-lg [&_h2]:font-semibold [&_h2]:mb-3 [&_h2]:mt-4",
        "[&_h3]:text-base [&_h3]:font-medium [&_h3]:mb-2 [&_h3]:mt-3",
        "[&_strong]:font-bold",
        "[&_a]:underline",
        className
      )}
      style={{
        "--tw-prose-links": `rgba(${ac.rgb}, 1)`,
        "--tw-prose-bullets": `rgba(${ac.rgb}, 0.5)`,
      } as React.CSSProperties}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
