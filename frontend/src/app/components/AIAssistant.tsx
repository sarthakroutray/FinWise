import React, { useState, useRef, useEffect, useCallback } from "react";
import { Send, Sparkles, User, BrainCircuit, Bot, Loader2, Trash2, Bug } from "lucide-react";
import { cn } from "../utils";
import { useTheme } from "./ThemeProvider";
import { streamChat } from "../services/api";
import { useChatStore, type ChartConfig, type DebugTrace } from "../store/useChatStore";
import { DynamicChart } from "./chat/DynamicChart";
import { DebateView } from "./chat/DebateView";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { DebugPanel } from "./chat/DebugPanel";

export function AIAssistant() {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<(() => void) | null>(null);
  const { theme, accentColors: ac } = useTheme();
  const isDark = theme === "dark";

  const {
    messages,
    sessionId,
    isLoading,
    debate,
    isDebugOpen,
    setLoading,
    addMessage,
    updateLastAssistant,
    finalizeLastAssistant,
    toggleDebug,
    setDebugTrace,
    clearChat,
    addChart,
    startDebate,
    setDebatePhase,
    appendSaverText,
    appendInvestorText,
    appendVerdictText,
    endDebate,
    setAgentConfidence,
  } = useChatStore();

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, debate.saverText, debate.investorText, debate.verdictText, scrollToBottom]);

  const handleSend = useCallback(
    (text: string) => {
      if (!text.trim() || isLoading) return;
      setInput("");
      setLoading(true);

      // Add user message
      addMessage({
        id: Date.now().toString(),
        role: "user",
        content: text,
      });

      // Add placeholder streaming assistant message
      addMessage({
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "",
        isStreaming: true,
      });

      const cancel = streamChat(
        { message: text, session_id: sessionId },
        (event, data) => {
          switch (event) {
            case "token":
              updateLastAssistant(data.text || "");
              break;

            case "chart":
              finalizeLastAssistant();
              addChart(data as ChartConfig);
              break;

            case "tool_call":
              // Show tool call inline
              updateLastAssistant(`\n\n🔧 *Calling ${data.name}...*\n`);
              break;

            case "tool_result":
              if (data.component_type === "dynamic_chart") {
                addChart(data as ChartConfig);
              }
              break;

            case "debate_start":
              finalizeLastAssistant();
              startDebate();
              break;

            case "agent_pitch":
              if (data.phase === "start" && data.agent === "PennyWise") {
                setDebatePhase("saver");
              } else if (data.phase === "start" && data.agent === "BullRun") {
                setDebatePhase("investor");
              } else if (data.text) {
                if (data.agent === "PennyWise") appendSaverText(data.text);
                else if (data.agent === "BullRun") appendInvestorText(data.text);
              }
              break;

            case "deliberation":
              setDebatePhase("deliberation");
              break;

            case "verdict":
              if (data.phase === "start") {
                setDebatePhase("verdict");
              } else if (data.text) {
                appendVerdictText(data.text);
              }
              break;

            case "debate_end":
              endDebate();
              break;

            case "debate_trigger":
              // Normal response confidence too low — debate will start
              finalizeLastAssistant();
              addMessage({
                id: Date.now().toString(),
                role: "assistant",
                content: `⚡ Confidence is ${Math.round((data.confidence || 0) * 100)}% — let me bring in the specialists for a deeper analysis...`,
              });
              break;

            case "debug":
              setDebugTrace(data as DebugTrace);
              break;

            case "agent_confidence":
              setAgentConfidence(data.agent, data.score);
              break;

            case "done":
              finalizeLastAssistant();
              setLoading(false);
              break;

            case "error":
              finalizeLastAssistant();
              addMessage({
                id: Date.now().toString(),
                role: "assistant",
                content: `❌ Error: ${data.message || "Something went wrong."}`,
              });
              setLoading(false);
              break;
          }
        },
        (err) => {
          finalizeLastAssistant();
          addMessage({
            id: Date.now().toString(),
            role: "assistant",
            content: `❌ Connection error: ${err.message}. Is the backend running?`,
          });
          setLoading(false);
        },
      );

      cancelRef.current = cancel;
    },
    [isLoading, sessionId, setLoading, addMessage, updateLastAssistant, finalizeLastAssistant, addChart, startDebate, setDebatePhase, appendSaverText, appendInvestorText, appendVerdictText, endDebate, setDebugTrace, setAgentConfidence],
  );


  return (
    <>
      <div
        className={cn(
          "flex flex-col h-[calc(100vh-8rem)] max-w-4xl mx-auto border rounded-2xl shadow-xl overflow-hidden relative",
          isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200",
        )}
      >
        {/* Header */}
        <div
          className={cn(
            "flex items-center justify-between gap-4 p-4 border-b backdrop-blur-md sticky top-0 z-10",
            isDark ? "bg-slate-900/80 border-slate-800" : "bg-white/80 border-slate-200",
          )}
        >
          <div className="flex items-center gap-4">
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center"
              style={{ backgroundColor: `rgba(${ac.rgb},0.2)`, border: `1px solid rgba(${ac.rgb},0.3)` }}
            >
              <Sparkles className="h-5 w-5" style={{ color: ac[400] }} />
            </div>
            <div>
              <h2
                className={cn(
                  "text-lg font-semibold flex items-center gap-2",
                  isDark ? "text-slate-100" : "text-slate-900",
                )}
              >
                FinWise Assistant
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-400 border border-purple-500/20">
                  Gemini + RAG
                </span>
              </h2>
              <p className={cn("text-xs", isDark ? "text-slate-400" : "text-slate-500")}>
                Your intelligent financial co-pilot
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={toggleDebug}
              className={cn(
                "p-2 rounded-lg transition-colors text-xs flex items-center gap-1",
                isDebugOpen
                  ? "text-amber-400 bg-amber-500/10"
                  : isDark
                    ? "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
                    : "text-slate-400 hover:text-slate-600 hover:bg-slate-100",
              )}
              title="Toggle debug panel"
            >
              <Bug className="h-4 w-4" />
            </button>
            <button
              onClick={clearChat}
              className={cn(
                "p-2 rounded-lg transition-colors",
                isDark
                  ? "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
                  : "text-slate-400 hover:text-slate-600 hover:bg-slate-100",
              )}
              title="Clear chat"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 custom-scrollbar">
          {messages.map((msg) => (
            <div key={msg.id}>
              {/* Chart messages */}
              {msg.chartConfig && <DynamicChart config={msg.chartConfig} />}

              {/* Text messages */}
              {msg.content && (
                <div className={cn("flex w-full", msg.role === "user" ? "justify-end" : "justify-start")}>
                  <div className={cn("flex gap-4 max-w-[85%]", msg.role === "user" ? "flex-row-reverse" : "flex-row")}>
                    <div
                      className={cn(
                        "w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1",
                        msg.role === "user"
                          ? "text-white"
                          : isDark
                            ? "border border-slate-700"
                            : "border border-slate-200",
                      )}
                      style={
                        msg.role === "user"
                          ? { background: `linear-gradient(to top right, ${ac[500]}, #8b5cf6)` }
                          : isDark
                            ? { backgroundColor: "rgb(30,41,59)", color: ac[400] }
                            : { backgroundColor: "rgb(241,245,249)", color: ac[500] }
                      }
                    >
                      {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                    </div>
                    <div className="space-y-2">
                      <div
                        className={cn(
                          "p-4 rounded-2xl text-sm leading-relaxed shadow-sm whitespace-pre-wrap",
                          msg.role === "user"
                            ? "text-white rounded-tr-sm"
                            : isDark
                              ? "bg-slate-800 border border-slate-700 text-slate-200 rounded-tl-sm"
                              : "bg-slate-100 border border-slate-200 text-slate-800 rounded-tl-sm",
                        )}
                        style={msg.role === "user" ? { backgroundColor: ac[600] } : undefined}
                      >
                        <MarkdownRenderer content={msg.content} />
                        {msg.isStreaming && (
                          <span
                            className="inline-block w-1.5 h-4 ml-0.5 align-text-bottom rounded-sm animate-pulse"
                            style={{ backgroundColor: ac[400] }}
                          />
                        )}
                      </div>

                      {/* Sources */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="flex flex-wrap items-center gap-2 mt-2">
                          <span className={cn("text-xs font-medium flex items-center gap-1", isDark ? "text-slate-500" : "text-slate-400")}>
                            <BrainCircuit className="h-3 w-3" /> Sources:
                          </span>
                          {msg.sources.map((src, i) => (
                            <span
                              key={i}
                              className={cn(
                                "px-2 py-1 rounded-md border text-[10px]",
                                isDark ? "bg-slate-800/80 border-slate-700 text-slate-400" : "bg-slate-100 border-slate-200 text-slate-500",
                              )}
                            >
                              {src}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Suggestion chips */}
                      {msg.suggestions && msg.suggestions.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3">
                          {msg.suggestions.map((s, i) => (
                            <button
                              key={i}
                              onClick={() => handleSend(s)}
                              className="px-3 py-1.5 rounded-full text-xs transition-colors"
                              style={{
                                backgroundColor: `rgba(${ac.rgb},0.1)`,
                                border: `1px solid rgba(${ac.rgb},0.2)`,
                                color: ac[400],
                              }}
                            >
                              {s}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Debate View */}
          {(debate.isActive || debate.phase === "done") && <DebateView />}

          {/* Loading indicator */}
          {isLoading && !debate.isActive && messages[messages.length - 1]?.content === "" && (
            <div className="flex w-full justify-start">
              <div className="flex gap-4 max-w-[85%]">
                <div
                  className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                    isDark ? "bg-slate-800 border border-slate-700" : "bg-slate-100 border border-slate-200",
                  )}
                  style={{ color: ac[400] }}
                >
                  <Bot className="h-4 w-4" />
                </div>
                <div
                  className={cn(
                    "p-4 rounded-2xl rounded-tl-sm flex items-center gap-2",
                    isDark ? "bg-slate-800 border border-slate-700 text-slate-200" : "bg-slate-100 border border-slate-200 text-slate-600",
                  )}
                >
                  <Loader2 className="h-4 w-4 animate-spin" style={{ color: ac[400] }} />
                  <span className={cn("text-sm", isDark ? "text-slate-400" : "text-slate-500")}>
                    Thinking...
                  </span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className={cn("p-4 border-t", isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200")}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend(input);
            }}
            className="relative flex items-center"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your spending, run calculations, or get investment advice..."
              className={cn(
                "w-full border rounded-xl pl-4 pr-12 py-3.5 text-sm focus:outline-none transition-all",
                isDark
                  ? "bg-slate-800 border-slate-700 text-slate-200 placeholder:text-slate-500 shadow-inner"
                  : "bg-slate-50 border-slate-200 text-slate-800 placeholder:text-slate-400",
              )}
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className={cn("absolute right-2 p-2 rounded-lg transition-colors", "text-white")}
              style={{ backgroundColor: !input.trim() || isLoading ? undefined : ac[600] }}
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
          <div className={cn("flex items-center justify-center gap-4 mt-3 text-[10px]", isDark ? "text-slate-500" : "text-slate-400")}>
            <span className="flex items-center gap-1">
              <BrainCircuit className="h-3 w-3" /> Gemini Pro + RAG + MCP Tools
            </span>
          </div>
        </div>
      </div>

      {/* Debug Panel (fixed overlay) */}
      <DebugPanel />
    </>
  );
}