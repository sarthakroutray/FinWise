import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { 
  ArrowUpRight, 
  ArrowDownRight, 
  Wallet, 
  TrendingUp, 
  CreditCard, 
  Activity,
  ShieldAlert,
  BrainCircuit,
  PieChart as PieChartIcon,
  Sparkles,
  Heart,
  Upload,
  FileSpreadsheet,
  FileText,
  X,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronRight,
  ChevronDown,
  ChevronUp
} from "lucide-react";
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  RadialBarChart,
  RadialBar
} from "recharts";
import { cn, formatMoney } from "../utils";
import { useTheme } from "./ThemeProvider";
import { motion } from "motion/react";
import { AnimatePresence } from "motion/react";
import { useFinData } from "../store/useFinData";

const CATEGORY_COLORS: Record<string, string> = {
  Housing: "#6366f1", "Food & Dining": "#ec4899", Food: "#8b5cf6",
  Transport: "#8b5cf6", Entertainment: "#f43f5e", Utilities: "#10b981",
  Groceries: "#06b6d4", Shopping: "#f59e0b", Transfer: "#ef4444",
  Income: "#10b981", Other: "#64748b",
};
function getCatColor(cat: string) { return CATEGORY_COLORS[cat] || "#6366f1"; }

// Mouse-following glow hook
function useMouseGlow(glowColor: string = "rgba(99,102,241,0.12)", glowSize: number = 250) {
  const ref = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const handleMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      if (glowRef.current) {
        glowRef.current.style.background = `radial-gradient(${glowSize}px circle at ${x}px ${y}px, ${glowColor}, transparent 70%)`;
      }
    };
    const handleEnter = () => setIsHovered(true);
    const handleLeave = () => setIsHovered(false);
    el.addEventListener("mousemove", handleMove);
    el.addEventListener("mouseenter", handleEnter);
    el.addEventListener("mouseleave", handleLeave);
    return () => {
      el.removeEventListener("mousemove", handleMove);
      el.removeEventListener("mouseenter", handleEnter);
      el.removeEventListener("mouseleave", handleLeave);
    };
  }, [glowColor, glowSize]);

  return { ref, glowRef, isHovered };
}

// Reusable GlowCard wrapper
function GlowCard({
  children,
  className,
  glowColor = "rgba(99,102,241,0.12)",
  glowSize = 250,
  motionProps,
  style,
}: {
  children: React.ReactNode;
  className?: string;
  glowColor?: string;
  glowSize?: number;
  motionProps?: any;
  style?: React.CSSProperties;
}) {
  const { ref, glowRef, isHovered } = useMouseGlow(glowColor, glowSize);

  return (
    <motion.div
      ref={ref}
      className={cn("relative overflow-hidden", className)}
      style={style}
      {...motionProps}
    >
      <div
        ref={glowRef}
        className="absolute inset-0 pointer-events-none transition-opacity duration-300 z-0"
        style={{ opacity: isHovered ? 1 : 0 }}
      />
      <div className="relative z-10">{children}</div>
    </motion.div>
  );
}

export function Dashboard() {
  const { theme, accentColors } = useTheme();
  const { data: finData, isLoading: finLoading, uploadFile } = useFinData();
  const isDark = theme === "dark";
  const ac = accentColors;
  const [activeRange, setActiveRange] = useState("6M");
  const [showImportModal, setShowImportModal] = useState(false);
  const [importExpanded, setImportExpanded] = useState(true);
  const [importStep, setImportStep] = useState<"select" | "preview" | "importing" | "done">("select");
  const [importedRows, setImportedRows] = useState<any[]>([]);
  const [importFileName, setImportFileName] = useState("");
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [dropZoneHighlight, setDropZoneHighlight] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const dragCounterRef = useRef(0);
  const { loadTestDataset } = useFinData();

  // Derive chart data from real backend response
  const healthScore = finData?.health_score?.score ?? 0;
  const healthData = [{ name: 'Score', value: healthScore, fill: healthScore >= 80 ? '#10b981' : healthScore >= 60 ? '#f59e0b' : '#ef4444' }];

  const categoryData = useMemo(() => {
    if (!finData?.category_summary || Object.keys(finData.category_summary).length === 0) return [];
    return Object.entries(finData.category_summary).map(([name, value]) => ({ name, value: Math.abs(value), color: getCatColor(name) }));
  }, [finData]);

  const spendData = useMemo(() => {
    if (!finData?.forecast || finData.forecast.length === 0) return [];
    return finData.forecast.slice(0, 9).map((pt, i) => ({
      name: new Date(pt.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      predicted: Math.round(pt.predicted_amount),
    }));
  }, [finData]);

  const anomalies = useMemo(() => {
    if (!finData?.anomalies || finData.anomalies.length === 0) return [];
    return finData.anomalies.map((a, i) => ({ id: i + 1, merchant: a.description, amount: Math.abs(a.amount), date: a.date, type: "Anomaly Detected", severity: "high" as const }));
  }, [finData]);

  const budgetData = useMemo(() => {
    if (!finData?.category_summary || Object.keys(finData.category_summary).length === 0) return [];
    return Object.entries(finData.category_summary).slice(0, 5).map(([category, spent]) => ({
      category, spent: Math.abs(spent), budget: Math.abs(spent) * 1.2, color: getCatColor(category),
    }));
  }, [finData]);

  const currencyCode = useMemo(() => {
    const txCurrency = finData?.transactions?.find(t => t.currency)?.currency;
    return txCurrency || "USD";
  }, [finData]);

  const totalBalance = useMemo(() => {
    if (!finData?.transactions || finData.transactions.length === 0) return formatMoney(0, currencyCode);
    const lastBal = finData.transactions.find(t => t.balance != null)?.balance;
    return lastBal != null ? formatMoney(lastBal, currencyCode) : formatMoney(0, currencyCode);
  }, [finData, currencyCode]);

  const monthlySpend = useMemo(() => {
    if (!finData?.transactions || finData.transactions.length === 0) return formatMoney(0, currencyCode);
    const total = finData.transactions.filter(t => t.amount < 0).reduce((s, t) => s + Math.abs(t.amount), 0);
    return formatMoney(total, currencyCode);
  }, [finData, currencyCode]);

  const recentTransactions = useMemo(() => {
    if (!finData?.transactions || finData.transactions.length === 0) return [];
    return finData.transactions.slice(0, 5).map((t, i) => ({
      id: i + 1, name: t.description, category: t.category, amount: t.amount,
      date: t.date, positive: t.amount > 0,
    }));
  }, [finData]);

  const cardBg = isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200";
  const textPrimary = isDark ? "text-slate-100" : "text-slate-900";
  const textSecondary = isDark ? "text-slate-400" : "text-slate-500";
  const textMuted = isDark ? "text-slate-500" : "text-slate-400";

  const stagger = (i: number) => ({
    initial: { opacity: 0, y: 16 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.35, delay: i * 0.06, ease: "easeOut" },
  });

  const processFile = useCallback((file: File) => {
    const validTypes = ['.csv', '.xlsx', '.xls', '.pdf', 'text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel', 'application/pdf'];
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!validTypes.includes(ext) && !validTypes.includes(file.type)) return;
    
    setPendingFile(file);
    setImportFileName(file.name);
    setShowImportModal(true);
    setImportStep("importing");

    // Call real backend
    uploadFile(file).then(() => {
      setImportStep("done");
    }).catch(() => {
      setImportStep("select");
    });
  }, [uploadFile]);

  // Global drag-and-drop detection
  useEffect(() => {
    const handleDragEnter = (e: DragEvent) => {
      e.preventDefault();
      dragCounterRef.current++;
      if (e.dataTransfer?.types.includes('Files')) {
        setIsDraggingOver(true);
      }
    };
    const handleDragLeave = (e: DragEvent) => {
      e.preventDefault();
      dragCounterRef.current--;
      if (dragCounterRef.current === 0) {
        setIsDraggingOver(false);
      }
    };
    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
    };
    const handleDrop = (e: DragEvent) => {
      e.preventDefault();
      dragCounterRef.current = 0;
      setIsDraggingOver(false);
      setDropZoneHighlight(false);
      const file = e.dataTransfer?.files?.[0];
      if (file) processFile(file);
    };

    window.addEventListener('dragenter', handleDragEnter);
    window.addEventListener('dragleave', handleDragLeave);
    window.addEventListener('dragover', handleDragOver);
    window.addEventListener('drop', handleDrop);
    return () => {
      window.removeEventListener('dragenter', handleDragEnter);
      window.removeEventListener('dragleave', handleDragLeave);
      window.removeEventListener('dragover', handleDragOver);
      window.removeEventListener('drop', handleDrop);
    };
  }, [processFile]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    processFile(file);
  };

  const handleModalDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDropZoneHighlight(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) processFile(file);
  };

  const handleImportConfirm = () => {
    if (!pendingFile) return;
    setImportStep("importing");
    uploadFile(pendingFile).then(() => {
      setImportStep("done");
    }).catch(() => {
      setImportStep("select");
    });
  };

  const handleImportClose = () => {
    setShowImportModal(false);
    setTimeout(() => { setImportStep("select"); setImportedRows([]); setImportFileName(""); setPendingFile(null); }, 200);
  };

  return (
    <div className="space-y-5 sm:space-y-6 max-w-7xl mx-auto relative">
      {/* Full-page drag overlay */}
      <AnimatePresence>
        {isDraggingOver && !showImportModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md"
            style={{ pointerEvents: 'all' }}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className={cn(
                "w-full max-w-md mx-4 rounded-3xl border-2 border-dashed p-12 flex flex-col items-center gap-5 text-center",
              )}
              style={{
                borderColor: ac[400],
                backgroundColor: `rgba(${ac.rgb},0.1)`,
                boxShadow: `0 0 80px rgba(${ac.rgb},0.3)`,
              }}
            >
              <motion.div
                animate={{ y: [0, -8, 0] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                className="w-20 h-20 rounded-2xl flex items-center justify-center"
                style={{ backgroundColor: `rgba(${ac.rgb},0.2)`, border: `1px solid rgba(${ac.rgb},0.3)` }}
              >
                <Upload className="h-10 w-10" style={{ color: ac[400] }} />
              </motion.div>
              <div>
                <p className="text-lg font-semibold text-white">Drop your file to import</p>
                <p className="text-sm mt-2" style={{ color: `rgba(${ac.rgb},0.6)` }}>CSV, Excel (.xlsx/.xls), or PDF bank statements</p>
              </div>
              <div className="flex items-center gap-2 mt-1">
                {["CSV", "XLSX", "PDF"].map(fmt => (
                  <span key={fmt} className="px-3 py-1 rounded-full text-xs font-medium" style={{ backgroundColor: `rgba(${ac.rgb},0.2)`, color: ac[400], border: `1px solid rgba(${ac.rgb},0.3)` }}>
                    .{fmt.toLowerCase()}
                  </span>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
        <div>
          <h1 className={cn("text-2xl font-bold", textPrimary)}>{getGreeting()}, John</h1>
          <p className={cn("text-sm mt-1", textSecondary)}>Here's your AI-powered financial snapshot.</p>
        </div>
        <div className={cn("grid grid-cols-4 w-full sm:w-auto items-center gap-1.5 rounded-lg p-1 border", isDark ? "bg-slate-800/50 border-slate-700/50" : "bg-slate-100 border-slate-200")}>
          {['1M', '3M', '6M', 'YTD'].map(range => (
            <button key={range} onClick={() => setActiveRange(range)} className={cn(
              "px-2 sm:px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
              range !== activeRange && (isDark ? "text-slate-400 hover:text-slate-200" : "text-slate-500 hover:text-slate-800")
            )}
            style={range === activeRange ? { backgroundColor: `rgba(${ac.rgb},0.2)`, color: ac[400] } : undefined}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Collapsible Import Banner */}
      <motion.div {...stagger(0)}>
        <ImportBanner
          isDark={isDark}
          ac={ac}
          expanded={importExpanded}
          onToggle={() => setImportExpanded(!importExpanded)}
          onImportClick={() => setShowImportModal(true)}
          textSecondary={textSecondary}
        />
      </motion.div>

      {/* Import Modal */}
      <AnimatePresence>
        {showImportModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
            onClick={(e) => e.target === e.currentTarget && handleImportClose()}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 10 }}
              className={cn("w-full max-w-lg max-h-[88dvh] rounded-2xl border shadow-2xl overflow-hidden", isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200")}
            >
              <div className={cn("flex items-center justify-between px-6 py-4 border-b", isDark ? "border-slate-800" : "border-slate-100")}>
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ backgroundColor: `rgba(${ac.rgb},0.1)` }}>
                    <Upload className="h-4 w-4" style={{ color: ac[400] }} />
                  </div>
                  <div>
                    <h2 className={cn("font-semibold", isDark ? "text-slate-200" : "text-slate-800")}>Import Transactions</h2>
                    <p className={cn("text-xs", textSecondary)}>CSV, Excel (.xlsx/.xls), or PDF</p>
                  </div>
                </div>
                <button onClick={handleImportClose} className={cn("p-1.5 rounded-lg transition-colors", isDark ? "hover:bg-slate-800 text-slate-400" : "hover:bg-slate-100 text-slate-500")}>
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="px-4 sm:px-6 py-5 overflow-y-auto max-h-[calc(88dvh-4.5rem)]">
                {importStep === "select" && (
                  <div className="space-y-4">
                    <label
                      className={cn(
                        "flex flex-col items-center justify-center gap-3 p-8 border-2 border-dashed rounded-xl cursor-pointer transition-all",
                        dropZoneHighlight
                          ? "scale-[1.02]"
                          : isDark ? "border-slate-700" : "border-slate-200"
                      )}
                      style={dropZoneHighlight ? { borderColor: ac[400], backgroundColor: `rgba(${ac.rgb},0.1)` } : undefined}
                      onDragOver={(e) => { e.preventDefault(); setDropZoneHighlight(true); }}
                      onDragLeave={() => setDropZoneHighlight(false)}
                      onDrop={handleModalDrop}
                    >
                      <motion.div
                        animate={dropZoneHighlight ? { y: [0, -6, 0] } : {}}
                        transition={{ duration: 1, repeat: Infinity }}
                        className={cn("w-12 h-12 rounded-xl flex items-center justify-center", !dropZoneHighlight && (isDark ? "bg-slate-800" : "bg-slate-100"))}
                        style={dropZoneHighlight ? { backgroundColor: `rgba(${ac.rgb},0.2)` } : undefined}
                      >
                        <FileSpreadsheet className={cn("h-6 w-6", !dropZoneHighlight && (isDark ? "text-slate-400" : "text-slate-500"))} style={dropZoneHighlight ? { color: ac[400] } : undefined} />
                      </motion.div>
                      <div className="text-center">
                        <p className={cn("text-sm font-medium", isDark ? "text-slate-200" : "text-slate-800")}>
                          {dropZoneHighlight ? "Release to upload" : "Drop file here or click to browse"}
                        </p>
                        <p className={cn("text-xs mt-1", textSecondary)}>Supports .csv, .xlsx, .xls, .pdf (max 10MB)</p>
                      </div>
                      <input type="file" accept=".csv,.xlsx,.xls,.pdf" onChange={handleFileSelect} className="hidden" />
                    </label>
                    <div className={cn("flex items-center gap-3 p-3 rounded-lg text-xs", isDark ? "bg-slate-800/50 text-slate-400" : "bg-slate-50 text-slate-500")}>
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                      <span>PDF imports use OCR extraction. For best results, ensure your bank statement is clearly formatted.</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      {[
                        { icon: FileSpreadsheet, label: "CSV", desc: "Comma-separated" },
                        { icon: FileSpreadsheet, label: "Excel", desc: ".xlsx / .xls" },
                        { icon: FileText, label: "PDF", desc: "Bank statements" },
                      ].map(fmt => (
                        <div key={fmt.label} className={cn("flex flex-col items-center gap-1.5 p-3 rounded-lg border text-center", isDark ? "border-slate-800 bg-slate-800/30" : "border-slate-100 bg-slate-50/50")}>
                          <fmt.icon className={cn("h-4 w-4", isDark ? "text-slate-500" : "text-slate-400")} />
                          <p className={cn("text-xs font-medium", isDark ? "text-slate-200" : "text-slate-800")}>{fmt.label}</p>
                          <p className={cn("text-[10px]", textSecondary)}>{fmt.desc}</p>
                        </div>
                      ))}
                    </div>
                    <button 
                      onClick={() => {
                        setImportStep("importing");
                        loadTestDataset().then(() => {
                           setImportStep("done");
                        }).catch(() => {
                           setImportStep("select");
                        });
                      }} 
                      className={cn(
                        "mt-2 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-medium border transition-colors",
                        isDark ? "bg-indigo-500/10 text-indigo-400 border-indigo-500/20 hover:bg-indigo-500/20" : "bg-indigo-50 text-indigo-600 border-indigo-200 hover:bg-indigo-100"
                      )}
                    >
                      <Sparkles className="h-4 w-4" /> Load USA PayPal Test Dataset
                    </button>
                  </div>
                )}

                {importStep === "preview" && (
                  <div className="space-y-4">
                    <div className={cn("flex items-center gap-3 p-3 rounded-lg border", isDark ? "border-slate-800 bg-slate-800/30" : "border-slate-100 bg-slate-50")}>
                      <FileSpreadsheet className="h-4 w-4" style={{ color: ac[400] }} />
                      <div className="flex-1 min-w-0">
                        <p className={cn("text-xs font-medium truncate", isDark ? "text-slate-200" : "text-slate-800")}>{importFileName}</p>
                        <p className={cn("text-[10px]", textSecondary)}>{importedRows.length} transactions detected</p>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Parsed</span>
                    </div>
                    <div className={cn("rounded-lg border overflow-hidden", isDark ? "border-slate-800" : "border-slate-200")}>
                      <table className="w-full text-xs">
                        <thead>
                          <tr className={cn("border-b", isDark ? "border-slate-800 bg-slate-800/50 text-slate-500" : "border-slate-100 bg-slate-50 text-slate-400")}>
                            <th className="px-3 py-2 text-left font-medium">Merchant</th>
                            <th className="px-3 py-2 text-left font-medium">Date</th>
                            <th className="px-3 py-2 text-right font-medium">Amount</th>
                            <th className="px-3 py-2 text-center font-medium">Status</th>
                          </tr>
                        </thead>
                        <tbody className={cn("divide-y", isDark ? "divide-slate-800/50" : "divide-slate-100")}>
                          {importedRows.map((row: any) => (
                            <tr key={row.id} className={row.status === "anomaly" ? (isDark ? "bg-rose-500/5" : "bg-rose-50/50") : ""}>
                              <td className={cn("px-3 py-2 font-medium", isDark ? "text-slate-200" : "text-slate-800")}>{row.merchant}</td>
                              <td className={cn("px-3 py-2", textSecondary)}>{row.date.split(" ")[0]}</td>
                              <td className={cn("px-3 py-2 text-right font-mono", row.amount > 0 ? "text-emerald-400" : (isDark ? "text-slate-200" : "text-slate-800"))}>
                                {row.amount > 0 ? "+" : ""}{row.amount.toFixed(2)}
                              </td>
                              <td className="px-3 py-2 text-center">
                                {row.status === "anomaly" ? (
                                  <span className="px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 text-[10px] font-medium">Flagged</span>
                                ) : (
                                  <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-medium">OK</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => { setImportStep("select"); setImportedRows([]); }} className={cn("px-4 py-2 rounded-lg text-xs font-medium transition-colors", isDark ? "text-slate-400 hover:bg-slate-800" : "text-slate-500 hover:bg-slate-100")}>
                        Back
                      </button>
                      <button onClick={handleImportConfirm} className="px-4 py-2 rounded-lg text-xs font-medium text-white transition-colors" style={{ backgroundColor: ac[500] }}>
                        Import {importedRows.length} Transactions
                      </button>
                    </div>
                  </div>
                )}

                {importStep === "importing" && (
                  <div className="flex flex-col items-center justify-center py-8 gap-4">
                    <Loader2 className="h-8 w-8 animate-spin" style={{ color: ac[400] }} />
                    <div className="text-center">
                      <p className={cn("text-sm font-medium", isDark ? "text-slate-200" : "text-slate-800")}>Importing transactions...</p>
                      <p className={cn("text-xs mt-1", textSecondary)}>Running Isolation Forest anomaly detection</p>
                    </div>
                  </div>
                )}

                {importStep === "done" && (
                  <div className="flex flex-col items-center justify-center py-8 gap-4">
                    <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center">
                      <CheckCircle2 className="h-6 w-6 text-emerald-400" />
                    </div>
                    <div className="text-center">
                      <p className={cn("text-sm font-medium", isDark ? "text-slate-200" : "text-slate-800")}>Import Complete!</p>
                      <p className={cn("text-xs mt-1", textSecondary)}>{finData?.transactions?.length ?? 0} transactions available from backend analysis</p>
                    </div>
                    <button onClick={handleImportClose} className="px-4 py-2 rounded-lg text-xs font-medium text-white transition-colors" style={{ backgroundColor: ac[500] }}>
                      Done
                    </button>
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <motion.div {...stagger(1)}>
          <MetricCard title="Total Balance" value={totalBalance} change={finData ? `${finData.health_score.grade}` : "No data"} isPositive={true} icon={Wallet} color="indigo" isDark={isDark} />
        </motion.div>
        <motion.div {...stagger(2)}>
          <MetricCard title="Monthly Spend" value={monthlySpend} change={finData ? `${finData.health_score.forecast_trend}` : "No data"} isPositive={true} icon={CreditCard} color="emerald" isDark={isDark} />
        </motion.div>
        <motion.div {...stagger(3)}>
          <MetricCard title="Savings Rate" value={finData ? `${(finData.health_score.savings_rate * 100).toFixed(1)}%` : "0.0%"} change={finData ? `Score: ${finData.health_score.score}` : "No data"} isPositive={true} icon={TrendingUp} color="purple" isDark={isDark} />
        </motion.div>
        
        {/* Risk Status */}
        <GlowCard
          className={cn("border rounded-2xl p-5 shadow-lg flex flex-col justify-between cursor-default", isDark ? "bg-slate-900 border-rose-900/50" : "bg-white border-rose-200")}
          glowColor="rgba(244,63,94,0.12)"
          glowSize={200}
          motionProps={{ ...stagger(4), whileHover: { y: -4, transition: { duration: 0.2 } } }}
        >
          <div className="flex items-center justify-between">
            <motion.div className="p-2.5 rounded-xl bg-rose-500/10 text-rose-500 border border-rose-500/20" whileHover={{ rotate: [0, -8, 8, 0], transition: { duration: 0.4 } }}>
              <ShieldAlert className="h-5 w-5" />
            </motion.div>
            <div className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full text-rose-400 bg-rose-400/10">
              <Activity className="h-3 w-3" />
              Attention
            </div>
          </div>
          <div className="mt-4">
            <h3 className={cn("text-sm font-medium", isDark ? "text-slate-400" : "text-slate-500")}>Risk Status</h3>
            <p className="text-2xl font-bold mt-1 text-rose-400">{anomalies.length} Alert{anomalies.length !== 1 ? 's' : ''}</p>
          </div>
        </GlowCard>

        {/* Financial Health Score */}
        <GlowCard
          className={cn("border rounded-2xl p-5 shadow-lg flex flex-col justify-between cursor-default", cardBg)}
          glowColor="rgba(245,158,11,0.1)"
          glowSize={180}
          motionProps={{ ...stagger(5), whileHover: { y: -4, transition: { duration: 0.2 } } }}
        >
          <div className="flex items-center justify-between">
            <motion.div className={cn("p-2.5 rounded-xl border", healthScore >= 80 ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" : healthScore >= 60 ? "bg-amber-500/10 text-amber-500 border-amber-500/20" : "bg-rose-500/10 text-rose-500 border-rose-500/20")} whileHover={{ rotate: [0, -10, 10, 0], transition: { duration: 0.4 } }}>
              <Heart className="h-5 w-5" />
            </motion.div>
            <div className={cn("flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full", healthScore >= 80 ? "text-emerald-400 bg-emerald-400/10" : healthScore >= 60 ? "text-amber-400 bg-amber-400/10" : "text-rose-400 bg-rose-400/10")}>
              {healthScore >= 80 ? "Excellent" : healthScore >= 60 ? "Good" : "Needs Work"}
            </div>
          </div>
          <div className="mt-4">
            <h3 className={cn("text-sm font-medium", isDark ? "text-slate-400" : "text-slate-500")}>Health Score</h3>
            <p className={cn("text-2xl font-bold mt-1", healthScore >= 80 ? "text-emerald-400" : healthScore >= 60 ? "text-amber-400" : "text-rose-400")}>{healthScore}/100</p>
          </div>
        </GlowCard>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 sm:gap-6">
        {/* Main Chart */}
        <GlowCard
          className={cn("lg:col-span-2 border rounded-2xl p-5 shadow-lg flex flex-col cursor-default", cardBg)}
          glowColor="rgba(99,102,241,0.08)"
          glowSize={350}
          motionProps={{ ...stagger(6), whileHover: { y: -3, transition: { duration: 0.25 } } }}
        >
          <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none rounded-2xl" style={{ boxShadow: isDark ? "inset 0 1px 0 0 rgba(99,102,241,0.1)" : "inset 0 1px 0 0 rgba(99,102,241,0.08)" }} />
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
            <div>
              <h3 className={cn("text-base font-semibold flex items-center gap-2", isDark ? "text-slate-200" : "text-slate-800")}>
                <BrainCircuit className="h-4 w-4" style={{ color: ac[400] }} />
                Spending Forecast (LSTM)
              </h3>
              <p className={cn("text-xs mt-1", textMuted)}>Actual vs Predicted spending for the next 2 months</p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full" style={{ backgroundColor: ac[500] }}></div><span className={textSecondary}>Actual</span></div>
              <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full border border-dashed" style={{ borderColor: ac[500] }}></div><span className={textSecondary}>Predicted</span></div>
            </div>
          </div>
          <div className="w-full mt-auto overflow-x-auto">
            <div className="h-72 min-w-[520px] sm:min-w-0">
              <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={spendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs key="defs">
                  <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid key="grid" strokeDasharray="3 3" vertical={false} stroke={isDark ? "#334155" : "#e2e8f0"} opacity={0.5} />
                <XAxis key="xaxis" dataKey="name" axisLine={false} tickLine={false} tick={{ fill: isDark ? '#94a3b8' : '#64748b', fontSize: 12 }} dy={10} />
                <YAxis key="yaxis" axisLine={false} tickLine={false} tick={{ fill: isDark ? '#94a3b8' : '#64748b', fontSize: 12 }} tickFormatter={(value) => `${(value/1000).toFixed(1)}k ${currencyCode}`} />
                <Tooltip 
                  key="tooltip"
                  contentStyle={{ backgroundColor: isDark ? '#0f172a' : '#fff', borderColor: isDark ? '#334155' : '#e2e8f0', borderRadius: '0.5rem', color: isDark ? '#f8fafc' : '#0f172a' }}
                  itemStyle={{ color: isDark ? '#e2e8f0' : '#334155' }}
                  formatter={(value: number) => formatMoney(Number(value), currencyCode)}
                />
                <Area key="area-actual" type="monotone" dataKey="actual" stroke="#6366f1" strokeWidth={3} fillOpacity={1} fill="url(#colorActual)" />
                <Area key="area-predicted" type="monotone" dataKey="predicted" stroke="#8b5cf6" strokeWidth={2} strokeDasharray="5 5" fillOpacity={1} fill="url(#colorPredicted)" />
              </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </GlowCard>

        {/* Categories */}
        <GlowCard
          className={cn("border rounded-2xl p-5 shadow-lg flex flex-col cursor-default", cardBg)}
          glowColor="rgba(139,92,246,0.1)"
          glowSize={250}
          motionProps={{ ...stagger(7), whileHover: { y: -3, transition: { duration: 0.25 } } }}
        >
          <h3 className={cn("text-base font-semibold flex items-center gap-2 mb-6", isDark ? "text-slate-200" : "text-slate-800")}>
            <PieChartIcon className="h-4 w-4 text-purple-400" />
            Spend by Category
          </h3>
          <div className="flex-1 relative">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  key="pie"
                  data={categoryData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                  stroke="none"
                >
                  {categoryData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  key="tooltip"
                  contentStyle={{ backgroundColor: isDark ? '#0f172a' : '#fff', borderColor: isDark ? '#334155' : '#e2e8f0', borderRadius: '0.5rem' }}
                  itemStyle={{ color: isDark ? '#e2e8f0' : '#334155' }}
                  formatter={(value) => formatMoney(Number(value), currencyCode)}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex items-center justify-center flex-col pointer-events-none">
              <span className={cn("text-xs", textSecondary)}>Total</span>
              <span className={cn("font-bold text-lg", textPrimary)}>{formatMoney(categoryData.reduce((sum, c) => sum + c.value, 0), currencyCode)}</span>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {categoryData.map(c => (
              <div key={c.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: c.color }}></div>
                  <span className={cn("truncate max-w-[120px]", isDark ? "text-slate-300" : "text-slate-600")}>{c.name}</span>
                </div>
                <span className={cn("font-medium", textSecondary)}>{formatMoney(c.value, currencyCode)}</span>
              </div>
            ))}
          </div>
        </GlowCard>
      </div>

      {/* Budget Progress */}
      <GlowCard
        className={cn("border rounded-2xl p-5 shadow-lg cursor-default", cardBg)}
        glowColor="rgba(245,158,11,0.08)"
        glowSize={350}
        motionProps={{ ...stagger(8), whileHover: { y: -3, transition: { duration: 0.25 } } }}
      >
        <h3 className={cn("text-base font-semibold flex items-center gap-2 mb-5", isDark ? "text-slate-200" : "text-slate-800")}>
          <Activity className="h-4 w-4 text-amber-400" />
          Monthly Budget Tracking
        </h3>
        <div className="space-y-4">
          {budgetData.map(b => {
            const pct = Math.min((b.spent / b.budget) * 100, 100);
            const over = b.spent > b.budget;
            return (
              <div key={b.category}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: b.color }}></div>
                    <span className={cn("text-sm", isDark ? "text-slate-300" : "text-slate-700")}>{b.category}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={cn("text-xs font-mono", over ? "text-rose-400" : textSecondary)}>
                      {formatMoney(b.spent, currencyCode)} / {formatMoney(b.budget, currencyCode)}
                    </span>
                    {over && <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">Over</span>}
                  </div>
                </div>
                <div className={cn("h-2 rounded-full overflow-hidden", isDark ? "bg-slate-800" : "bg-slate-100")}>
                  <motion.div
                    className="h-full rounded-full"
                    style={{ backgroundColor: over ? "#f43f5e" : b.color }}
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.8, delay: 0.5, ease: "easeOut" }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </GlowCard>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 sm:gap-6">
        {/* Fraud / Anomalies */}
        <GlowCard
          className={cn("border rounded-2xl p-5 shadow-lg cursor-default", isDark ? "bg-slate-900 border-rose-900/30" : "bg-white border-rose-200")}
          glowColor="rgba(244,63,94,0.08)"
          glowSize={300}
          motionProps={{ ...stagger(9), whileHover: { y: -3, transition: { duration: 0.25 } } }}
        >
          <div className="flex flex-wrap items-start justify-between gap-2 mb-4">
            <h3 className={cn("text-base font-semibold flex items-center gap-2", isDark ? "text-slate-200" : "text-slate-800")}>
              <ShieldAlert className="h-4 w-4 text-rose-500" />
              Risk & Fraud Detection
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/20 ml-2">
                Isolation Forest
              </span>
            </h3>
            <button className="text-xs hover:opacity-80 transition-opacity" style={{ color: ac[400] }}>View All</button>
          </div>
          
          <div className="space-y-3">
            {anomalies.map(a => (
              <motion.div
                key={a.id}
                whileHover={{ x: 4, transition: { duration: 0.15 } }}
                className={cn(
                  "p-3 rounded-xl border flex items-center justify-between transition-colors cursor-pointer",
                  isDark ? "bg-slate-800/50 border-slate-700/50 hover:bg-slate-800" : "bg-slate-50 border-slate-200 hover:bg-slate-100"
                )}
              >
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "p-2 rounded-lg",
                    a.severity === 'high' ? "bg-rose-500/10 text-rose-400" : "bg-amber-500/10 text-amber-400"
                  )}>
                    <Activity className="h-4 w-4" />
                  </div>
                  <div>
                    <p className={cn("text-sm font-medium", isDark ? "text-slate-200" : "text-slate-800")}>{a.merchant}</p>
                    <p className={cn("text-xs mt-0.5 flex items-center gap-1.5", textMuted)}>
                      <span className={a.severity === 'high' ? "text-rose-400" : "text-amber-400"}>{a.type}</span>
                      <span className={cn("w-1 h-1 rounded-full", isDark ? "bg-slate-600" : "bg-slate-300")}></span>
                      {a.date}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={cn("text-sm font-bold", isDark ? "text-slate-200" : "text-slate-800")}>{formatMoney(a.amount, currencyCode)}</p>
                  <button className={cn("text-[10px] mt-1 border px-2 py-0.5 rounded transition-colors", isDark ? "text-slate-400 hover:text-white border-slate-700" : "text-slate-500 hover:text-slate-800 border-slate-300")}>Review</button>
                </div>
              </motion.div>
            ))}
            
            <div className={cn("p-3 rounded-xl border flex items-start gap-3")} style={isDark ? { backgroundColor: `rgba(${ac.rgb},0.05)`, borderColor: `rgba(${ac.rgb},0.2)` } : { backgroundColor: `rgba(${ac.rgb},0.05)`, borderColor: `rgba(${ac.rgb},0.2)` }}>
              <Sparkles className="h-5 w-5 shrink-0 mt-0.5" style={{ color: ac[400] }} />
              <div>
                <p className="text-sm font-medium" style={{ color: ac[400] }}>AI Suggestion</p>
                <p className={cn("text-xs mt-1 leading-relaxed", textSecondary)}>
                  You are spending 38% of your income on food, which is higher than the recommended 15%. Consider reducing dining out to stay on track for your vacation goal.
                </p>
              </div>
            </div>
          </div>
        </GlowCard>

        {/* Recent Transactions */}
        <GlowCard
          className={cn("border rounded-2xl p-5 shadow-lg flex flex-col cursor-default", cardBg)}
          glowColor="rgba(16,185,129,0.08)"
          glowSize={300}
          motionProps={{ ...stagger(10), whileHover: { y: -3, transition: { duration: 0.25 } } }}
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className={cn("text-base font-semibold flex items-center gap-2", isDark ? "text-slate-200" : "text-slate-800")}>
              <Wallet className="h-4 w-4 text-emerald-400" />
              Recent Transactions
            </h3>
            <button className="text-xs hover:opacity-80 transition-opacity" style={{ color: ac[400] }}>View All</button>
          </div>
          
          <div className="space-y-0.5 flex-1 overflow-y-auto pr-1 sm:pr-2 custom-scrollbar">
            {recentTransactions.map(t => (
              <motion.div
                key={t.id}
                whileHover={{ x: 3, transition: { duration: 0.15 } }}
                className={cn("flex items-center justify-between py-2.5 border-b last:border-0 cursor-pointer rounded-lg px-1 -mx-1 transition-colors", isDark ? "border-slate-800/50 hover:bg-slate-800/30" : "border-slate-100 hover:bg-slate-50")}
              >
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold",
                    t.positive ? "bg-emerald-500/10 text-emerald-400" : (isDark ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-600")
                  )}>
                    {t.name.charAt(0)}
                  </div>
                  <div>
                    <p className={cn("text-sm font-medium", isDark ? "text-slate-200" : "text-slate-800")}>{t.name}</p>
                    <p className={cn("text-[10px] uppercase tracking-wider", textMuted)}>{t.category}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={cn(
                    "text-sm font-semibold",
                    t.positive ? "text-emerald-400" : (isDark ? "text-slate-300" : "text-slate-700")
                  )}>
                    {t.positive ? "+" : "-"}{formatMoney(Math.abs(t.amount), currencyCode)}
                  </p>
                  <p className={cn("text-[10px]", textMuted)}>{t.date}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </GlowCard>
      </div>
    </div>
  );
}

function MetricCard({ title, value, change, isPositive, icon: Icon, color, isDark }: any) {
  const { accentColors: ac } = useTheme();
  const colorMap: Record<string, { bg: string; text: string; border: string; glow: string }> = {
    indigo: { bg: "bg-indigo-500/10", text: "text-indigo-500", border: "border-indigo-500/20", glow: "rgba(99,102,241,0.15)" },
    emerald: { bg: "bg-emerald-500/10", text: "text-emerald-500", border: "border-emerald-500/20", glow: "rgba(16,185,129,0.15)" },
    purple: { bg: "bg-purple-500/10", text: "text-purple-500", border: "border-purple-500/20", glow: "rgba(139,92,246,0.15)" },
  };
  
  const c = colorMap[color] || colorMap.indigo;

  return (
    <GlowCard
      className={cn("border rounded-2xl p-5 shadow-lg flex flex-col justify-between cursor-default", isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200")}
      glowColor={c.glow}
      glowSize={200}
      motionProps={{ whileHover: { y: -4, transition: { duration: 0.2, ease: "easeOut" } } }}
    >
      <div className="flex items-center justify-between">
        <motion.div
          className={cn("p-2.5 rounded-xl border", c.bg, c.text, c.border)}
          whileHover={{ rotate: [0, -10, 10, 0], transition: { duration: 0.4 } }}
        >
          <Icon className="h-5 w-5" />
        </motion.div>
        <div className={cn(
          "flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full",
          isPositive ? "text-emerald-400 bg-emerald-400/10" : "text-rose-400 bg-rose-400/10"
        )}>
          {isPositive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
          {change}
        </div>
      </div>
      <div className="mt-4">
        <h3 className={cn("text-sm font-medium", isDark ? "text-slate-400" : "text-slate-500")}>{title}</h3>
        <p className={cn("text-2xl font-bold mt-1", isDark ? "text-slate-100" : "text-slate-900")}>{value}</p>
      </div>
    </GlowCard>
  );
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function ImportBanner({ isDark, ac, expanded, onToggle, onImportClick, textSecondary }: any) {
  const { ref, glowRef, isHovered } = useMouseGlow(`rgba(${ac.rgb},0.12)`, 300);

  return (
    <div
      ref={ref}
      className={cn(
        "relative overflow-hidden border rounded-2xl transition-all",
        isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200"
      )}
    >
      {/* Mouse-following glow */}
      <div
        ref={glowRef}
        className="absolute inset-0 pointer-events-none transition-opacity duration-300 z-0"
        style={{ opacity: isHovered ? 1 : 0 }}
      />

      {/* Header row - always visible */}
      <div
        className="relative z-10 flex items-center gap-3 sm:gap-4 px-4 sm:px-5 py-4 cursor-pointer"
        onClick={(e) => { e.stopPropagation(); onToggle(); }}
      >
        <div className="p-2.5 rounded-xl shrink-0" style={{ backgroundColor: `rgba(${ac.rgb},0.1)`, border: `1px solid rgba(${ac.rgb},0.2)` }}>
          <Upload className="h-5 w-5" style={{ color: ac[500] }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={cn("text-sm font-semibold", isDark ? "text-slate-200" : "text-slate-800")}>
              Import Transaction Data
            </span>
            <span className="px-1.5 py-0.5 rounded text-[9px] font-medium" style={{ backgroundColor: `rgba(${ac.rgb},0.15)`, color: ac[400] }}>
              AI-Powered
            </span>
          </div>
          {!expanded && (
            <p className={cn("text-xs mt-0.5", textSecondary)}>
              Drag & drop or click to upload CSV, Excel, or PDF statements
            </p>
          )}
        </div>
        <div className="hidden sm:flex items-center gap-1.5">
          {["CSV", "XLS", "PDF"].map(fmt => (
            <span key={fmt} className={cn(
              "px-2 py-0.5 rounded text-[10px] font-medium",
              isDark ? "bg-slate-800 text-slate-500" : "bg-slate-100 text-slate-400"
            )}>
              .{fmt.toLowerCase()}
            </span>
          ))}
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onToggle(); }}
          className={cn(
            "p-1.5 rounded-lg transition-colors shrink-0",
            isDark ? "hover:bg-slate-800 text-slate-500" : "hover:bg-slate-100 text-slate-400"
          )}
        >
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {/* Expanded content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden relative z-10"
          >
            <div className={cn("px-4 sm:px-5 pb-5 pt-0 border-t", isDark ? "border-slate-800/50" : "border-slate-100")}>
              <p className={cn("text-sm mt-4 mb-4", textSecondary)}>
                Upload your bank statements for AI-powered anomaly detection via Isolation Forest. Drag & drop anywhere on the page, or click below.
              </p>
              <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                <button
                  onClick={(e) => { e.stopPropagation(); onImportClick(); }}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-white transition-colors"
                  style={{ backgroundColor: ac[500] }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = ac[600])}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = ac[500])}
                >
                  Import Files
                </button>
                <div className="flex flex-wrap items-center gap-2">
                  {[
                    { icon: FileSpreadsheet, label: "CSV" },
                    { icon: FileSpreadsheet, label: "Excel" },
                    { icon: FileText, label: "PDF" },
                  ].map(fmt => (
                    <div key={fmt.label} className={cn(
                      "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs",
                      isDark ? "border-slate-800 bg-slate-800/30 text-slate-400" : "border-slate-200 bg-slate-50 text-slate-500"
                    )}>
                      <fmt.icon className="h-3.5 w-3.5" />
                      {fmt.label}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}