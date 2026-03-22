import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Shield, TrendingUp, Scale, Loader2, CheckCircle2, ChevronDown, ChevronRight, MessageSquareDashed } from "lucide-react";
import { cn } from "../../utils";
import { useTheme } from "../ThemeProvider";
import { useChatStore } from "../../store/useChatStore";
import { MarkdownRenderer } from "../MarkdownRenderer";

export const cleanText = (text: string) => {
  return text.replace(/(?:```json\s*)?\{[\s\S]*?"confidence"[\s\S]*?\}(?:\s*```)?/g, "").trim();
};

export function DebateView() {
  const { theme, accentColors: ac } = useTheme();
  const isDark = theme === "dark";
  const { debate } = useChatStore();
  
  // As requested, Agent Pitches are collapsed by default.
  // They just show a neat animation while deliberation is active.
  const [isCollapsed, setIsCollapsed] = useState(true);

  if (!debate.isActive && debate.phase === "idle") return null;

  const isPitchingPhase = debate.isActive && debate.phase !== "deliberation" && debate.phase !== "verdict" && debate.phase !== "done";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "rounded-2xl border p-4 my-4 space-y-4",
        isDark ? "bg-slate-800/40 border-slate-700" : "bg-slate-50 border-slate-200"
      )}
    >
      {/* Header (Collapsible toggle) */}
      <div 
        className="flex flex-col sm:flex-row sm:items-center gap-3 select-none cursor-pointer"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-2 text-xs uppercase tracking-wider font-semibold" style={{ color: ac[400] }}>
          {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          <Scale className="h-4 w-4" />
          Financial Debate
        </div>

        {/* Dynamic Badges / Animation when collapsed */}
        <div className="flex items-center gap-2 ml-auto">
          {debate.isActive && isCollapsed && (
            <motion.div 
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="flex items-center gap-1.5 px-3 py-1 rounded-full border shadow-sm"
              style={{ backgroundColor: isDark ? "rgba(15, 23, 42, 0.4)" : "white", borderColor: `rgba(${ac.rgb}, 0.2)` }}
            >
              <motion.div animate={{ scale: [1, 1.4, 1], opacity: [0.5, 1, 0.5] }} transition={{ repeat: Infinity, duration: 1.2 }} className="w-1.5 h-1.5 rounded-full bg-blue-400" />
              <motion.div animate={{ scale: [1, 1.4, 1], opacity: [0.5, 1, 0.5] }} transition={{ repeat: Infinity, duration: 1.2, delay: 0.2 }} className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
              <motion.div animate={{ scale: [1, 1.4, 1], opacity: [0.5, 1, 0.5] }} transition={{ repeat: Infinity, duration: 1.2, delay: 0.4 }} className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span className="text-[10px] ml-1 font-medium tracking-wide" style={{ color: ac[500] }}>
                AGENTS DELIBERATING
              </span>
            </motion.div>
          )}

          {debate.phase === "done" && (
            <span className="text-[10px] font-bold px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-500 flex items-center gap-1 border border-emerald-500/20 shadow-sm transition-all hover:bg-emerald-500/25">
              <CheckCircle2 className="h-3 w-3" /> RESOLVED
            </span>
          )}
        </div>
      </div>

      <AnimatePresence>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="space-y-4 overflow-hidden"
          >
            {/* Agent Pitches — Side by side */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 pt-2">
              {/* Saver Card */}
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
                className={cn(
                  "rounded-xl border p-4 relative flex flex-col overflow-hidden max-h-[500px] overflow-y-auto",
                  "[&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/60 hover:[&::-webkit-scrollbar-thumb]:bg-white/80 [&::-webkit-scrollbar-thumb]:rounded-full",
                  isDark ? "bg-slate-900/60 border-slate-700" : "bg-white border-slate-200"
                )}
              >
                <div className="flex items-center gap-2 mb-3 sticky top-0 py-2 -mx-2 px-2 z-10 rounded-t-lg" style={{ backgroundColor: isDark ? "rgba(15, 23, 42, 0.95)" : "rgba(255, 255, 255, 0.95)" }}>
                  <div className="w-8 h-8 rounded-full bg-blue-500/15 flex items-center justify-center shrink-0">
                    <Shield className="h-4 w-4 text-blue-400" />
                  </div>
                  <div>
                    <div className={cn("text-sm font-bold tracking-tight", isDark ? "text-blue-300" : "text-blue-600")}>PennyWise</div>
                    <div className={cn("text-[10px] uppercase font-bold tracking-wider", isDark ? "text-slate-500" : "text-slate-400")}>Conservative</div>
                  </div>
                  {debate.saverConfidence !== null ? (
                    <div className="ml-auto text-[10px] font-extrabold px-2 py-1 rounded border border-blue-500/20 bg-blue-500/10 text-blue-400">
                      C.S {Math.round(debate.saverConfidence)}%
                    </div>
                  ) : isPitchingPhase && (
                    <Loader2 className="h-4 w-4 ml-auto animate-spin text-blue-400" />
                  )}
                </div>
                <div className={cn("flex-grow", isDark ? "text-slate-300" : "text-slate-700")}>
                  {debate.saverText ? <MarkdownRenderer content={cleanText(debate.saverText)} /> : (
                    <span className={cn("italic flex items-center gap-2 text-xs", isDark ? "text-slate-600" : "text-slate-400")}>
                      <MessageSquareDashed className="h-3 w-3" /> Preparing pitch...
                    </span>
                  )}
                </div>
              </motion.div>

              {/* Investor Card */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 }}
                className={cn(
                  "rounded-xl border p-4 relative flex flex-col overflow-hidden max-h-[500px] overflow-y-auto",
                  "[&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/60 hover:[&::-webkit-scrollbar-thumb]:bg-white/80 [&::-webkit-scrollbar-thumb]:rounded-full",
                  isDark ? "bg-slate-900/60 border-slate-700" : "bg-white border-slate-200"
                )}
              >
                <div className="flex items-center gap-2 mb-3 sticky top-0 py-2 -mx-2 px-2 z-10 rounded-t-lg" style={{ backgroundColor: isDark ? "rgba(15, 23, 42, 0.95)" : "rgba(255, 255, 255, 0.95)" }}>
                  <div className="w-8 h-8 rounded-full bg-emerald-500/15 flex items-center justify-center shrink-0">
                    <TrendingUp className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div>
                    <div className={cn("text-sm font-bold tracking-tight", isDark ? "text-emerald-300" : "text-emerald-600")}>BullRun</div>
                    <div className={cn("text-[10px] uppercase font-bold tracking-wider", isDark ? "text-slate-500" : "text-slate-400")}>Growth Focus</div>
                  </div>
                  {debate.investorConfidence !== null ? (
                    <div className="ml-auto text-[10px] font-extrabold px-2 py-1 rounded border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
                      C.S {Math.round(debate.investorConfidence)}%
                    </div>
                  ) : isPitchingPhase && (
                    <Loader2 className="h-4 w-4 ml-auto animate-spin text-emerald-400" />
                  )}
                </div>
                <div className={cn("flex-grow", isDark ? "text-slate-300" : "text-slate-700")}>
                  {debate.investorText ? <MarkdownRenderer content={cleanText(debate.investorText)} /> : (
                    <span className={cn("italic flex items-center gap-2 text-xs", isDark ? "text-slate-600" : "text-slate-400")}>
                      <MessageSquareDashed className="h-3 w-3" /> Preparing pitch...
                    </span>
                  )}
                </div>
              </motion.div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Verdict Panel - Always visible once created */}
      <AnimatePresence>
        {(debate.phase === "verdict" || debate.phase === "done") && debate.verdictText && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className={cn(
              "rounded-xl border p-5 shadow-sm mt-2 relative",
              isDark ? "bg-slate-900/80 border-slate-700" : "bg-white border-slate-200"
            )}
            style={{ 
              borderColor: `rgba(${ac.rgb}, 0.5)`, 
              backgroundColor: isDark ? `rgba(${ac.rgb}, 0.03)` : `rgba(${ac.rgb}, 0.05)`,
              boxShadow: `0 4px 20px -5px rgba(${ac.rgb}, 0.15)`
            }}
          >
            <div className="flex items-center gap-2 mb-4">
              <div className="p-1.5 rounded bg-black/5 dark:bg-white/10">
                <Scale className="h-4 w-4" style={{ color: ac[500] }} />
              </div>
              <span className="text-sm font-bold uppercase tracking-widest" style={{ color: ac[500] }}>
                Final Decision
              </span>
              {debate.verdictConfidence !== null ? (
                <div className="ml-auto text-[11px] font-extrabold px-2.5 py-0.5 rounded-full border shadow-sm" style={{ color: ac[600], borderColor: ac[400], backgroundColor: `rgba(${ac.rgb}, 0.15)` }}>
                  Confidence: {Math.round(debate.verdictConfidence)}%
                </div>
              ) : debate.phase === "verdict" && (
                <div className="ml-auto flex items-center gap-2">
                  <span className="text-[10px] uppercase font-bold opacity-60">Synthesizing</span>
                  <Loader2 className="h-4 w-4 animate-spin" style={{ color: ac[400] }} />
                </div>
              )}
            </div>
            
            <div className={cn("text-base", isDark ? "text-slate-200" : "text-slate-800")}>
              <MarkdownRenderer content={cleanText(debate.verdictText)} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
