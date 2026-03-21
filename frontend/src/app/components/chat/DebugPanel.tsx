import React from "react";
import { motion, AnimatePresence } from "motion/react";
import { Bug, X, Clock, Cpu, Database, Zap } from "lucide-react";
import { cn } from "../../utils";
import { useTheme } from "../ThemeProvider";
import { useChatStore } from "../../store/useChatStore";

/**
 * Slide-out debug panel — "Under the Hood" view showing
 * trace data, RAG chunks, model info, and latency.
 */
export function DebugPanel() {
  const { theme, accentColors: ac } = useTheme();
  const isDark = theme === "dark";
  const { isDebugOpen, toggleDebug, debugTrace } = useChatStore();

  return (
    <AnimatePresence>
      {isDebugOpen && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", damping: 25, stiffness: 300 }}
          className={cn(
            "fixed top-0 right-0 h-full w-96 z-50 shadow-2xl border-l flex flex-col",
            isDark
              ? "bg-slate-950 border-slate-800 text-slate-300"
              : "bg-gray-50 border-gray-200 text-gray-700"
          )}
        >
          {/* Header */}
          <div className={cn(
            "flex items-center justify-between px-4 py-3 border-b",
            isDark ? "border-slate-800" : "border-gray-200"
          )}>
            <div className="flex items-center gap-2">
              <Bug className="h-4 w-4" style={{ color: ac[400] }} />
              <span className="text-sm font-semibold">Under the Hood</span>
            </div>
            <button
              onClick={toggleDebug}
              className={cn(
                "p-1 rounded-md transition-colors",
                isDark ? "hover:bg-slate-800" : "hover:bg-gray-200"
              )}
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-xs">
            {debugTrace ? (
              <>
                {/* Trace ID */}
                <div>
                  <Label icon={<Zap className="h-3 w-3" />} text="Trace ID" />
                  <code className={cn("block mt-1 px-2 py-1 rounded",
                    isDark ? "bg-slate-900 text-slate-400" : "bg-gray-100 text-gray-500"
                  )}>
                    {debugTrace.trace_id || "—"}
                  </code>
                </div>

                {/* Total Time */}
                {debugTrace.total_ms !== undefined && (
                  <div>
                    <Label icon={<Clock className="h-3 w-3" />} text="Total Time" />
                    <div className="mt-1 text-lg font-bold" style={{ color: ac[400] }}>
                      {debugTrace.total_ms}ms
                    </div>
                  </div>
                )}

                {/* Pipeline Stages */}
                <div>
                  <Label icon={<Cpu className="h-3 w-3" />} text="Pipeline Stages" />
                  <div className="mt-2 space-y-2">
                    {debugTrace.stages.map((stage, i) => (
                      <div
                        key={i}
                        className={cn(
                          "rounded-lg px-3 py-2 border",
                          isDark ? "bg-slate-900/60 border-slate-800" : "bg-white border-gray-200"
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold capitalize">
                            {stage.name.replace(/_/g, " ")}
                          </span>
                          {stage.ms !== undefined && (
                            <span className={cn(
                              "text-[10px] px-1.5 py-0.5 rounded",
                              stage.ms > 1000
                                ? "bg-amber-500/15 text-amber-400"
                                : "bg-emerald-500/15 text-emerald-400"
                            )}>
                              {stage.ms}ms
                            </span>
                          )}
                        </div>
                        {/* Show extra fields */}
                        {Object.entries(stage)
                          .filter(([k]) => !["name", "ms"].includes(k))
                          .map(([k, v]) => (
                            <div key={k} className={cn(
                              "mt-1 text-[10px] flex gap-2",
                              isDark ? "text-slate-500" : "text-gray-400"
                            )}>
                              <span className="uppercase">{k}:</span>
                              <span className={isDark ? "text-slate-400" : "text-gray-600"}>
                                {typeof v === "object" ? JSON.stringify(v) : String(v)}
                              </span>
                            </div>
                          ))}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className={cn("text-center py-12", isDark ? "text-slate-600" : "text-gray-400")}>
                <Database className="h-8 w-8 mx-auto mb-2 opacity-40" />
                <p>No trace data yet.</p>
                <p className="text-[10px] mt-1">Send a message to see the pipeline breakdown.</p>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Label({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold opacity-60">
      {icon} {text}
    </div>
  );
}
