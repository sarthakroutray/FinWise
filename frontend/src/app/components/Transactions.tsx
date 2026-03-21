import React, { useState, useMemo } from "react";
import { Search, Filter, ShieldAlert, ArrowDownLeft, ArrowUpRight, Activity, Download, ChevronDown, MapPin, Clock, Tag, Upload, FileSpreadsheet, FileText, X, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { cn, formatMoney } from "../utils";
import { useTheme } from "./ThemeProvider";
import { motion, AnimatePresence } from "motion/react";
import { useFinData } from "../store/useFinData";
import { extractCSV } from "../services/api";

interface ImportedTransaction {
  id: string;
  date: string;
  merchant: string;
  amount: number;
  currency?: string | null;
  category: string;
  status: "normal" | "anomaly";
  score: number;
  type?: string;
  location: string;
  note: string;
}

export function Transactions() {
  const [filter, setFilter] = useState<"all" | "anomalies">("all");
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importStep, setImportStep] = useState<"select" | "preview" | "importing" | "done">("select");
  const [importedRows, setImportedRows] = useState<ImportedTransaction[]>([]);
  const [importFileName, setImportFileName] = useState("");
  const { theme, accentColors } = useTheme();
  const isDark = theme === "dark";
  const ac = accentColors;
  const { data: finData, uploadFile, isLoading: finLoading } = useFinData();

  // Derive transactions directly from backend data.
  const transactions: ImportedTransaction[] = useMemo(() => {
    if (!finData?.transactions || finData.transactions.length === 0) return [];
    const anomalyDescs = new Set(finData.anomalies.map(a => a.description));
    return finData.transactions.map((t, i) => ({
      id: `tx-${i}`,
      date: t.date,
      merchant: t.description,
      amount: t.amount,
      currency: t.currency,
      category: t.category,
      status: anomalyDescs.has(t.description) ? "anomaly" as const : "normal" as const,
      score: anomalyDescs.has(t.description) ? 0.95 : 0.05,
      type: anomalyDescs.has(t.description) ? "Anomaly Detected" : undefined,
      location: "",
      note: anomalyDescs.has(t.description) ? "Flagged by Isolation Forest anomaly detection." : "Transaction within expected range.",
    }));
  }, [finData]);

  const filtered = transactions.filter(tx => {
    if (filter === "anomalies" && tx.status !== "anomaly") return false;
    if (search && !tx.merchant.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const cardBg = isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200";
  const textPrimary = isDark ? "text-slate-200" : "text-slate-800";
  const textSecondary = isDark ? "text-slate-400" : "text-slate-500";

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportFileName(file.name);
    setImportStep("importing");
    setShowImportModal(true);

    // Call real backend
    uploadFile(file).then(() => {
      setImportStep("done");
    }).catch(() => {
      setImportStep("select");
    });
  };

  const handleImportConfirm = () => {
    // Already handled by backend call in handleFileSelect
    setImportStep("done");
  };

  const handleImportClose = () => {
    setShowImportModal(false);
    setTimeout(() => {
      setImportStep("select");
      setImportedRows([]);
      setImportFileName("");
    }, 200);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className={cn("text-2xl font-bold", isDark ? "text-slate-100" : "text-slate-900")}>Transaction History</h1>
          <p className={cn("text-sm mt-1", textSecondary)}>Monitored by Isolation Forest Algorithm.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowImportModal(true)}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium border transition-colors",
            )}
            style={{
              backgroundColor: `rgba(${ac.rgb},0.1)`,
              borderColor: `rgba(${ac.rgb},0.2)`,
              color: ac[isDark ? 400 : 600],
            }}
          >
            <Upload className="h-3.5 w-3.5" /> Import Data
          </button>
          <button
            onClick={async () => {
              try {
                const input = document.createElement('input');
                input.type = 'file';
                input.accept = '.csv,.pdf,.xlsx,.xls';
                input.onchange = async (e) => {
                  const file = (e.target as HTMLInputElement).files?.[0];
                  if (!file) return;
                  const blob = await extractCSV(file);
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = 'extracted_transactions.csv';
                  a.click();
                  URL.revokeObjectURL(url);
                };
                input.click();
              } catch (err) {
                console.error('Export failed:', err);
              }
            }}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium border transition-colors",
              isDark ? "bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700" : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
            )}
          >
            <Download className="h-3.5 w-3.5" /> Export CSV
          </button>
        </div>
      </div>

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
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className={cn("w-full max-w-lg rounded-2xl border shadow-2xl overflow-hidden", isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200")}
            >
              {/* Header */}
              <div className={cn("flex items-center justify-between px-6 py-4 border-b", isDark ? "border-slate-800" : "border-slate-100")}>
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ backgroundColor: `rgba(${ac.rgb},0.1)`, color: ac[400] }}>
                    <Upload className="h-4 w-4" style={{ color: ac[400] }} />
                  </div>
                  <div>
                    <h2 className={cn("font-semibold", textPrimary)}>Import Transactions</h2>
                    <p className={cn("text-xs", textSecondary)}>CSV, Excel (.xlsx/.xls), or PDF</p>
                  </div>
                </div>
                <button onClick={handleImportClose} className={cn("p-1.5 rounded-lg transition-colors", isDark ? "hover:bg-slate-800 text-slate-400" : "hover:bg-slate-100 text-slate-500")}>
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Body */}
              <div className="px-6 py-5">
                {importStep === "select" && (
                  <div className="space-y-4">
                    <label className={cn(
                      "flex flex-col items-center justify-center gap-3 p-8 border-2 border-dashed rounded-xl cursor-pointer transition-colors",
                      isDark ? "border-slate-700" : "border-slate-200"
                    )}>
                      <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", isDark ? "bg-slate-800" : "bg-slate-100")}>
                        <FileSpreadsheet className={cn("h-6 w-6", isDark ? "text-slate-400" : "text-slate-500")} />
                      </div>
                      <div className="text-center">
                        <p className={cn("text-sm font-medium", textPrimary)}>Drop file here or click to browse</p>
                        <p className={cn("text-xs mt-1", textSecondary)}>Supports .csv, .xlsx, .xls, .pdf (max 10MB)</p>
                      </div>
                      <input
                        type="file"
                        accept=".csv,.xlsx,.xls,.pdf"
                        onChange={handleFileSelect}
                        className="hidden"
                      />
                    </label>
                    <div className={cn("flex items-center gap-3 p-3 rounded-lg text-xs", isDark ? "bg-slate-800/50 text-slate-400" : "bg-slate-50 text-slate-500")}>
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                      <span>PDF imports use OCR extraction. For best results, ensure your bank statement is clearly formatted.</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { icon: FileSpreadsheet, label: "CSV", desc: "Comma-separated" },
                        { icon: FileSpreadsheet, label: "Excel", desc: ".xlsx / .xls" },
                        { icon: FileText, label: "PDF", desc: "Bank statements" },
                      ].map(fmt => (
                        <div key={fmt.label} className={cn("flex flex-col items-center gap-1.5 p-3 rounded-lg border text-center", isDark ? "border-slate-800 bg-slate-800/30" : "border-slate-100 bg-slate-50/50")}>
                          <fmt.icon className={cn("h-4 w-4", isDark ? "text-slate-500" : "text-slate-400")} />
                          <p className={cn("text-xs font-medium", textPrimary)}>{fmt.label}</p>
                          <p className={cn("text-[10px]", textSecondary)}>{fmt.desc}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {importStep === "preview" && (
                  <div className="space-y-4">
                    <div className={cn("flex items-center gap-3 p-3 rounded-lg border", isDark ? "border-slate-800 bg-slate-800/30" : "border-slate-100 bg-slate-50")}>
                      <FileSpreadsheet className="h-4 w-4" style={{ color: ac[400] }} />
                      <div className="flex-1 min-w-0">
                        <p className={cn("text-xs font-medium truncate", textPrimary)}>{importFileName}</p>
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
                          {importedRows.map(row => (
                            <tr key={row.id} className={row.status === "anomaly" ? (isDark ? "bg-rose-500/5" : "bg-rose-50/50") : ""}>
                              <td className={cn("px-3 py-2 font-medium", textPrimary)}>{row.merchant}</td>
                              <td className={cn("px-3 py-2", textSecondary)}>{row.date.split(" ")[0]}</td>
                              <td className={cn("px-3 py-2 text-right font-mono", row.amount > 0 ? "text-emerald-400" : textPrimary)}>
                                {row.amount > 0 ? "+" : ""}{formatMoney(Math.abs(row.amount), row.currency || undefined)}
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
                      <p className={cn("text-sm font-medium", textPrimary)}>Importing transactions...</p>
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
                      <p className={cn("text-sm font-medium", textPrimary)}>Import Complete!</p>
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

      <div className={cn("border rounded-2xl shadow-lg overflow-hidden", cardBg)}>
        {/* Controls */}
        <div className={cn("p-4 border-b flex flex-col sm:flex-row items-center gap-4 justify-between", isDark ? "border-slate-800 bg-slate-800/20" : "border-slate-100 bg-slate-50/50")}>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search merchants..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className={cn(
                  "w-full border rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none transition-colors",
                  isDark ? "bg-slate-950 border-slate-700 text-slate-200 placeholder:text-slate-500" : "bg-white border-slate-200 text-slate-800 placeholder:text-slate-400"
                )}
              />
            </div>
            <button className={cn("p-2 border rounded-lg transition-colors", isDark ? "bg-slate-800 border-slate-700 text-slate-400 hover:text-white" : "bg-white border-slate-200 text-slate-500 hover:text-slate-800")}>
              <Filter className="h-4 w-4" />
            </button>
          </div>

          <div className={cn("flex items-center gap-2 p-1 rounded-lg border w-full sm:w-auto", isDark ? "bg-slate-950 border-slate-800" : "bg-slate-100 border-slate-200")}>
            <button
              onClick={() => setFilter("all")}
              className={cn(
                "flex-1 sm:px-4 py-1.5 text-xs font-medium rounded-md transition-all",
                filter === "all" ? (isDark ? "bg-slate-800 text-white shadow" : "bg-white text-slate-800 shadow-sm") : (isDark ? "text-slate-400 hover:text-slate-200" : "text-slate-500 hover:text-slate-800")
              )}
            >
              All Activity
            </button>
            <button
              onClick={() => setFilter("anomalies")}
              className={cn(
                "flex-1 sm:px-4 py-1.5 text-xs font-medium rounded-md transition-all flex items-center justify-center gap-1.5",
                filter === "anomalies" ? "bg-rose-500/10 text-rose-400 border border-rose-500/20 shadow" : (isDark ? "text-slate-400 hover:text-slate-200" : "text-slate-500 hover:text-slate-800")
              )}
            >
              <ShieldAlert className="h-3 w-3" />
              Anomalies Flagged
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className={cn("border-b text-xs uppercase tracking-wider", isDark ? "border-slate-800 text-slate-500 bg-slate-900/50" : "border-slate-100 text-slate-400 bg-slate-50/80")}>
                <th className="px-6 py-4 font-medium">Transaction</th>
                <th className="px-6 py-4 font-medium">Date</th>
                <th className="px-6 py-4 font-medium">Category</th>
                <th className="px-6 py-4 font-medium">Status & Risk Score</th>
                <th className="px-6 py-4 font-medium text-right">Amount</th>
                <th className="px-6 py-4"></th>
              </tr>
            </thead>
            <tbody className={cn("divide-y text-sm", isDark ? "divide-slate-800/50" : "divide-slate-100")}>
              {filtered.map(tx => (
                <React.Fragment key={tx.id}>
                <tr className={cn(
                  "transition-colors group cursor-pointer",
                  isDark ? "hover:bg-slate-800/50" : "hover:bg-slate-50",
                  tx.status === "anomaly" ? (isDark ? "bg-rose-500/5" : "bg-rose-50/50") : "",
                  expandedId === tx.id && (isDark ? "bg-slate-800/30" : "bg-slate-50")
                )} onClick={() => setExpandedId(expandedId === tx.id ? null : tx.id)}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-10 h-10 rounded-xl flex items-center justify-center border",
                        tx.amount > 0 ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : 
                        tx.status === "anomaly" ? "bg-rose-500/10 text-rose-400 border-rose-500/20 shadow-[0_0_15px_rgba(244,63,94,0.15)]" : (isDark ? "bg-slate-800 text-slate-300 border-slate-700" : "bg-slate-100 text-slate-500 border-slate-200")
                      )}>
                        {tx.amount > 0 ? <ArrowDownLeft className="h-5 w-5" /> : <ArrowUpRight className="h-5 w-5" />}
                      </div>
                      <div>
                        <p className={cn("font-semibold", textPrimary)}>{tx.merchant}</p>
                        {tx.status === "anomaly" && (
                          <p className="text-[10px] text-rose-400 flex items-center gap-1 mt-0.5 font-medium">
                            <Activity className="h-3 w-3" /> {tx.type}
                          </p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className={cn("px-6 py-4 whitespace-nowrap text-xs", textSecondary)}>
                    {tx.date}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={cn("px-2.5 py-1 rounded-md text-xs border", isDark ? "bg-slate-800 text-slate-300 border-slate-700" : "bg-slate-100 text-slate-600 border-slate-200")}>
                      {tx.category}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {tx.status === "anomaly" ? (
                      <div className="flex items-center gap-2">
                        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-500/10 text-rose-400 text-xs font-bold border border-rose-500/20">
                          <ShieldAlert className="h-3.5 w-3.5" /> High Risk
                        </span>
                        <span className={cn("text-xs font-mono", isDark ? "text-slate-500" : "text-slate-400")}>Score: {tx.score}</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs font-medium border border-emerald-500/20">
                          Verified
                        </span>
                        <span className={cn("text-xs font-mono", isDark ? "text-slate-500" : "text-slate-400")}>Score: {tx.score}</span>
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    <p className={cn(
                      "font-bold",
                      tx.amount > 0 ? "text-emerald-400" : textPrimary
                    )}>
                      {tx.amount > 0 ? "+" : "-"}{formatMoney(Math.abs(tx.amount), tx.currency || undefined)}
                    </p>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    <button className={cn(
                      "text-xs font-medium hover:opacity-80 transition-all flex items-center gap-1 ml-auto",
                      expandedId === tx.id ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                    )} style={{ color: ac[400] }}>
                      <ChevronDown className={cn("h-3 w-3 transition-transform", expandedId === tx.id && "rotate-180")} />
                      {expandedId === tx.id ? "Less" : "Details"}
                    </button>
                  </td>
                </tr>
                <AnimatePresence>
                  {expandedId === tx.id && (
                    <tr>
                      <td colSpan={6}>
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          <div className={cn("px-6 py-4 flex flex-wrap gap-6 border-b", isDark ? "bg-slate-800/20 border-slate-800/50" : "bg-slate-50/80 border-slate-100")}>
                            <div className="flex items-center gap-2">
                              <MapPin className={cn("h-3.5 w-3.5", isDark ? "text-slate-500" : "text-slate-400")} />
                              <span className={cn("text-xs", textSecondary)}>{tx.location}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Clock className={cn("h-3.5 w-3.5", isDark ? "text-slate-500" : "text-slate-400")} />
                              <span className={cn("text-xs", textSecondary)}>{tx.date}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Tag className={cn("h-3.5 w-3.5", isDark ? "text-slate-500" : "text-slate-400")} />
                              <span className={cn("text-xs", textSecondary)}>{tx.category}</span>
                            </div>
                            <div className="flex-1 min-w-[200px]">
                              <p className={cn("text-xs leading-relaxed", isDark ? "text-slate-400" : "text-slate-500")}>
                                <span className={cn("font-medium", isDark ? "text-slate-300" : "text-slate-600")}>AI Analysis: </span>
                                {tx.note}
                              </p>
                            </div>
                            {tx.status === "anomaly" && (
                              <div className="flex items-center gap-2">
                                <button className="px-3 py-1.5 rounded-md bg-rose-500/10 text-rose-400 text-xs font-medium border border-rose-500/20 hover:bg-rose-500/20 transition-colors">
                                  Dispute
                                </button>
                                <button className="px-3 py-1.5 rounded-md bg-emerald-500/10 text-emerald-400 text-xs font-medium border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors">
                                  Mark Safe
                                </button>
                              </div>
                            )}
                          </div>
                        </motion.div>
                      </td>
                    </tr>
                  )}
                </AnimatePresence>
                </React.Fragment>
              ))}
              
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className={cn("px-6 py-12 text-center", isDark ? "text-slate-500" : "text-slate-400")}>
                    No transactions found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className={cn("flex items-center justify-between px-6 py-3 border-t", isDark ? "border-slate-800" : "border-slate-100")}>
          <p className={cn("text-xs", textSecondary)}>Showing {filtered.length} of {transactions.length} transactions</p>
          <div className="flex items-center gap-1">
            {[1, 2, 3].map(p => (
              <button key={p} className={cn(
                "w-8 h-8 rounded-md text-xs font-medium transition-colors",
                p === 1 ? "" : (isDark ? "text-slate-400 hover:bg-slate-800" : "text-slate-500 hover:bg-slate-100")
              )} style={p === 1 ? { backgroundColor: `rgba(${ac.rgb},0.2)`, color: ac[400] } : undefined}>{p}</button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}