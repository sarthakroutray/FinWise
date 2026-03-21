import React, { useState, useRef, useEffect } from "react";
import { Send, Sparkles, User, BrainCircuit, Bot, Loader2, BarChart, FileText, Trash2 } from "lucide-react";
import { BarChart as RechartsBarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from "recharts";
import { cn } from "../utils";
import { useTheme } from "./ThemeProvider";
import { queryRAG } from "../services/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  suggestions?: string[];
  chart?: boolean;
}

const initialMessages: Message[] = [
  {
    id: "1",
    role: "assistant",
    content: "Hi John! I'm your FinWise AI Co-pilot. I noticed your recent spending at Starbucks is unusually high. How can I help you today?",
    suggestions: [
      "Where am I overspending?",
      "Can I afford a vacation next month?",
      "Analyze my recent transactions"
    ]
  }
];

export function AIAssistant() {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { theme, accentColors } = useTheme();
  const isDark = theme === "dark";
  const ac = accentColors;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = (text: string) => {
    if (!text.trim()) return;

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    setTimeout(async () => {
      try {
        const response = await queryRAG(text);
        const aiResponse: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: response.answer,
          sources: response.sources.length > 0 ? response.sources : undefined,
        };
        setMessages(prev => [...prev, aiResponse]);
      } catch (err: any) {
        const aiResponse: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "Sorry, I couldn't connect to the backend. Please make sure the server is running and you've uploaded a bank statement first.",
          suggestions: ["Upload a bank statement first"],
        };
        setMessages(prev => [...prev, aiResponse]);
      } finally {
        setIsLoading(false);
      }
    }, 100);
  };

  const handleClearChat = () => {
    setMessages(initialMessages);
  };

  return (
    <div className={cn(
      "flex flex-col h-[calc(100vh-8rem)] max-w-4xl mx-auto border rounded-2xl shadow-xl overflow-hidden relative",
      isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200"
    )}>
      {/* Header */}
      <div className={cn(
        "flex items-center justify-between gap-4 p-4 border-b backdrop-blur-md sticky top-0 z-10",
        isDark ? "bg-slate-900/80 border-slate-800" : "bg-white/80 border-slate-200"
      )}>
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: `rgba(${ac.rgb},0.2)`, border: `1px solid rgba(${ac.rgb},0.3)` }}>
            <Sparkles className="h-5 w-5" style={{ color: ac[400] }} />
          </div>
          <div>
            <h2 className={cn("text-lg font-semibold flex items-center gap-2", isDark ? "text-slate-100" : "text-slate-900")}>
              FinWise Assistant
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-400 border border-purple-500/20">RAG + LLM</span>
            </h2>
            <p className={cn("text-xs", isDark ? "text-slate-400" : "text-slate-500")}>Your intelligent financial co-pilot</p>
          </div>
        </div>
        <button
          onClick={handleClearChat}
          className={cn("p-2 rounded-lg transition-colors", isDark ? "text-slate-500 hover:text-slate-300 hover:bg-slate-800" : "text-slate-400 hover:text-slate-600 hover:bg-slate-100")}
          title="Clear chat"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 custom-scrollbar">
        {messages.map((msg) => (
          <div key={msg.id} className={cn(
            "flex w-full",
            msg.role === "user" ? "justify-end" : "justify-start"
          )}>
            <div className={cn(
              "flex gap-4 max-w-[85%]",
              msg.role === "user" ? "flex-row-reverse" : "flex-row"
            )}>
              <div className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1",
                msg.role === "user" 
                  ? "text-white" 
                  : (isDark ? "border border-slate-700" : "border border-slate-200")
              )} style={msg.role === "user" ? { background: `linear-gradient(to top right, ${ac[500]}, #8b5cf6)` } : isDark ? { backgroundColor: 'rgb(30,41,59)', color: ac[400] } : { backgroundColor: 'rgb(241,245,249)', color: ac[500] }}>
                {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>
              
              <div className="space-y-2">
                <div className={cn(
                  "p-4 rounded-2xl text-sm leading-relaxed shadow-sm",
                  msg.role === "user" 
                    ? "text-white rounded-tr-sm" 
                    : (isDark ? "bg-slate-800 border border-slate-700 text-slate-200 rounded-tl-sm" : "bg-slate-100 border border-slate-200 text-slate-800 rounded-tl-sm")
                )} style={msg.role === "user" ? { backgroundColor: ac[600] } : undefined}>
                  {msg.content.split('**').map((text, i) => i % 2 === 1 ? <strong key={i} className={msg.role === "user" ? "text-white font-semibold" : "font-semibold"} style={msg.role !== "user" ? { color: ac[400] } : undefined}>{text}</strong> : text)}
                </div>

                {msg.chart && (
                  <div className={cn("p-4 border rounded-xl mt-2", isDark ? "bg-slate-800/50 border-slate-700" : "bg-slate-50 border-slate-200")}>
                    <p className={cn("text-[10px] uppercase tracking-wider mb-3 font-medium", isDark ? "text-slate-500" : "text-slate-400")}>Spending Breakdown — Last 3 Months</p>
                    <div className="h-36 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <RechartsBarChart data={[
                          { name: "Starbucks", value: 420, over: true },
                          { name: "UberEats", value: 310, over: true },
                          { name: "Groceries", value: 250, over: false },
                          { name: "Gas", value: 180, over: false },
                          { name: "Netflix", value: 45, over: false },
                        ]} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                          <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: isDark ? '#94a3b8' : '#64748b', fontSize: 10 }} />
                          <YAxis axisLine={false} tickLine={false} tick={{ fill: isDark ? '#94a3b8' : '#64748b', fontSize: 10 }} tickFormatter={(v) => `$${v}`} />
                          <Tooltip
                            contentStyle={{ backgroundColor: isDark ? '#0f172a' : '#fff', borderColor: isDark ? '#334155' : '#e2e8f0', borderRadius: '0.5rem', fontSize: 12 }}
                            formatter={(value: number) => [`$${value}`, "Spent"]}
                          />
                          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                            {[
                              { name: "Starbucks", value: 420, over: true },
                              { name: "UberEats", value: 310, over: true },
                              { name: "Groceries", value: 250, over: false },
                              { name: "Gas", value: 180, over: false },
                              { name: "Netflix", value: 45, over: false },
                            ].map((entry, i) => (
                              <Cell key={`cell-${i}`} fill={entry.over ? "#f43f5e" : ac[500]} />
                            ))}
                          </Bar>
                        </RechartsBarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-[10px]">
                      <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-rose-500"></div><span className={isDark ? "text-slate-400" : "text-slate-500"}>Above Average</span></div>
                      <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full" style={{ backgroundColor: ac[500] }}></div><span className={isDark ? "text-slate-400" : "text-slate-500"}>Normal</span></div>
                    </div>
                  </div>
                )}

                {msg.sources && msg.sources.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 mt-2">
                    <span className={cn("text-xs font-medium flex items-center gap-1", isDark ? "text-slate-500" : "text-slate-400")}>
                      <BrainCircuit className="h-3 w-3" /> Sources:
                    </span>
                    {msg.sources.map((src, i) => (
                      <span key={i} className={cn("px-2 py-1 rounded-md border text-[10px] flex items-center gap-1", isDark ? "bg-slate-800/80 border-slate-700 text-slate-400" : "bg-slate-100 border-slate-200 text-slate-500")}>
                        <FileText className="h-3 w-3" /> {src}
                      </span>
                    ))}
                  </div>
                )}

                {msg.suggestions && msg.suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {msg.suggestions.map((suggestion, i) => (
                      <button
                        key={i}
                        onClick={() => handleSend(suggestion)}
                        className="px-3 py-1.5 rounded-full text-xs transition-colors"
                        style={{ backgroundColor: `rgba(${ac.rgb},0.1)`, border: `1px solid rgba(${ac.rgb},0.2)`, color: ac[400] }}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex w-full justify-start">
            <div className="flex gap-4 max-w-[85%]">
              <div className={cn("w-8 h-8 rounded-full flex items-center justify-center shrink-0", isDark ? "bg-slate-800 border border-slate-700" : "bg-slate-100 border border-slate-200")} style={{ color: ac[400] }}>
                <Bot className="h-4 w-4" />
              </div>
              <div className={cn("p-4 rounded-2xl rounded-tl-sm flex items-center gap-2", isDark ? "bg-slate-800 border border-slate-700 text-slate-200" : "bg-slate-100 border border-slate-200 text-slate-600")}>
                <Loader2 className="h-4 w-4 animate-spin" style={{ color: ac[400] }} />
                <span className={cn("text-sm", isDark ? "text-slate-400" : "text-slate-500")}>Analyzing financial data...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className={cn("p-4 border-t", isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200")}>
        <form 
          onSubmit={(e) => { e.preventDefault(); handleSend(input); }}
          className="relative flex items-center"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your spending, anomalies, or future predictions..."
            className={cn(
              "w-full border rounded-xl pl-4 pr-12 py-3.5 text-sm focus:outline-none transition-all",
              isDark ? "bg-slate-800 border-slate-700 text-slate-200 placeholder:text-slate-500 shadow-inner" : "bg-slate-50 border-slate-200 text-slate-800 placeholder:text-slate-400"
            )}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className={cn(
              "absolute right-2 p-2 rounded-lg transition-colors",
              "text-white"
            )}
            style={{ backgroundColor: !input.trim() || isLoading ? undefined : ac[600] }}
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
        <div className={cn("flex items-center justify-center gap-4 mt-3 text-[10px]", isDark ? "text-slate-500" : "text-slate-400")}>
          <span className="flex items-center gap-1"><BrainCircuit className="h-3 w-3" /> Uses RAG on your transaction history</span>
        </div>
      </div>
    </div>
  );
}