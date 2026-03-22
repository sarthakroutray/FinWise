import { create } from "zustand";

// ── SSE Event Types ────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "agent";
  content: string;
  agentName?: string; // "PennyWise" | "BullRun" | "Arbiter"
  chartConfig?: ChartConfig;
  sources?: string[];
  suggestions?: string[];
  isStreaming?: boolean;
}

export interface ChartConfig {
  component_type: "dynamic_chart";
  chart_engine: "recharts";
  chart_type: "line" | "bar" | "area" | "pie";
  chart_data: Record<string, unknown>[];
  axis_config: { x: string; y: string; x_label?: string; y_label?: string };
  latex_formula?: string;
  result?: number;
  [key: string]: unknown;
}

export interface DebateState {
  isActive: boolean;
  phase: "idle" | "saver" | "investor" | "deliberation" | "verdict" | "done";
  saverText: string;
  investorText: string;
  verdictText: string;
  saverConfidence: number | null;
  investorConfidence: number | null;
  verdictConfidence: number | null;
}

export interface TraceStage {
  name: string;
  ms?: number;
  [key: string]: unknown;
}

export interface DebugTrace {
  trace_id?: string;
  total_ms?: number;
  stages: TraceStage[];
}

// ── Store ──────────────────────────────────────────────────────────────────

interface ChatStore {
  messages: ChatMessage[];
  sessionId: string;
  isLoading: boolean;
  isDebugOpen: boolean;
  debate: DebateState;
  debugTrace: DebugTrace | null;

  // Actions
  setSessionId: (id: string) => void;
  addMessage: (msg: ChatMessage) => void;
  updateLastAssistant: (chunk: string) => void;
  finalizeLastAssistant: () => void;
  setLoading: (v: boolean) => void;
  toggleDebug: () => void;
  setDebugTrace: (trace: DebugTrace) => void;
  clearChat: () => void;

  // Debate actions
  startDebate: () => void;
  setDebatePhase: (phase: DebateState["phase"]) => void;
  appendSaverText: (text: string) => void;
  appendInvestorText: (text: string) => void;
  appendVerdictText: (text: string) => void;
  setAgentConfidence: (agent: string, score: number) => void;
  endDebate: () => void;
  clearDebate: () => void;

  // Chart
  addChart: (config: ChartConfig) => void;
}

const defaultDebate: DebateState = {
  isActive: false,
  phase: "idle",
  saverText: "",
  investorText: "",
  verdictText: "",
  saverConfidence: null,
  investorConfidence: null,
  verdictConfidence: null,
};

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I'm your **FinWise AI** assistant. Upload a bank statement on the Dashboard, then ask me anything about your finances — or try a calculation like *\"compound interest on $10,000 at 5% for 10 years\"*.",
      suggestions: [
        "Where am I overspending?",
        "Should I invest or save?",
        "Analyze my recent transactions",
      ],
    },
  ],
  sessionId: crypto.randomUUID(),
  isLoading: false,
  isDebugOpen: false,
  debate: { ...defaultDebate },
  debugTrace: null,

  setSessionId: (id) => set({ sessionId: id }),

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  updateLastAssistant: (chunk) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && (last.role === "assistant" || last.role === "agent") && last.isStreaming) {
        msgs[msgs.length - 1] = { ...last, content: last.content + chunk };
      }
      return { messages: msgs };
    }),

  finalizeLastAssistant: () =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.isStreaming) {
        msgs[msgs.length - 1] = { ...last, isStreaming: false };
      }
      return { messages: msgs };
    }),

  setLoading: (v) => set({ isLoading: v }),

  toggleDebug: () => set((s) => ({ isDebugOpen: !s.isDebugOpen })),

  setDebugTrace: (trace) => set({ debugTrace: trace }),

  clearChat: () =>
    set({
      messages: [
        {
          id: "welcome",
          role: "assistant",
          content:
            "Chat cleared! Ask me anything about your finances.",
        },
      ],
      sessionId: crypto.randomUUID(),
      debate: { ...defaultDebate },
      debugTrace: null,
    }),

  // ── Debate ─────────────────────────────────────────────────────────
  startDebate: () =>
    set({ debate: { ...defaultDebate, isActive: true, phase: "saver" } }),

  setDebatePhase: (phase) =>
    set((s) => ({ debate: { ...s.debate, phase } })),

  appendSaverText: (text) =>
    set((s) => ({ debate: { ...s.debate, saverText: s.debate.saverText + text } })),

  appendInvestorText: (text) =>
    set((s) => ({ debate: { ...s.debate, investorText: s.debate.investorText + text } })),

  appendVerdictText: (text) =>
    set((s) => ({ debate: { ...s.debate, verdictText: s.debate.verdictText + text } })),

  setAgentConfidence: (agent, score) =>
    set((s) => {
      const updates: Partial<DebateState> = {};
      if (agent === "PennyWise") updates.saverConfidence = score;
      if (agent === "BullRun") updates.investorConfidence = score;
      if (agent === "Arbiter") updates.verdictConfidence = score;
      return { debate: { ...s.debate, ...updates } };
    }),

  endDebate: () =>
    set((s) => ({ debate: { ...s.debate, isActive: false, phase: "done" } })),
    
  clearDebate: () =>
    set((s) => {
      // If a debate was previously completed, save its contents to chat history before destroying it
      if (s.debate.phase === "done") {
        const debateSummary = `**[Debate Concluded]**\n\n**PennyWise (Saver):**\n${s.debate.saverText}\n\n**BullRun (Investor):**\n${s.debate.investorText}\n\n**Arbiter Verdict:**\n${s.debate.verdictText}`;
        const newMsgs = [...s.messages, { id: "deb-" + Date.now(), role: "assistant" as const, content: debateSummary }];
        return { debate: { ...defaultDebate }, messages: newMsgs };
      }
      return { debate: { ...defaultDebate } };
    }),

  // ── Chart ──────────────────────────────────────────────────────────
  addChart: (config) =>
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id: Date.now().toString(),
          role: "assistant" as const,
          content: "",
          chartConfig: config,
        },
      ],
    })),
}));
