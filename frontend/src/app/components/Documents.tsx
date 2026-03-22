import React, { useCallback, useMemo, useState } from "react";
import { FileUp, Loader2, Trash2, RefreshCw, ShieldCheck, FolderOpen } from "lucide-react";
import { toast } from "sonner";
import { cn } from "../utils";
import { useTheme } from "./ThemeProvider";
import { useAuth } from "../auth/AuthProvider";
import { useFinData } from "../store/useFinData";
import {
  deleteDocumentRecord,
  listDocuments,
  type DocumentRecord,
} from "../services/api";

export function Documents() {
  const { theme, accentColors } = useTheme();
  const { user, signIn, signUp, isConfigured, isLoading: authLoading } = useAuth();
  const { uploadFile, isLoading: analyzeLoading, data: finData } = useFinData();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isAuthBusy, setIsAuthBusy] = useState(false);

  const [docs, setDocs] = useState<DocumentRecord[]>([]);
  const [isDocsLoading, setIsDocsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const isDark = theme === "dark";
  const ac = accentColors;

  const cardBg = isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200";
  const textPrimary = isDark ? "text-slate-200" : "text-slate-800";
  const textSecondary = isDark ? "text-slate-400" : "text-slate-500";

  const loadDocuments = useCallback(async () => {
    if (!user) {
      setDocs([]);
      return;
    }
    setIsDocsLoading(true);
    try {
      const token = await user.getIdToken();
      const records = await listDocuments(token);
      setDocs(records);
    } catch (err) {
      console.error(err);
      toast.error("Failed to load documents");
    } finally {
      setIsDocsLoading(false);
    }
  }, [user]);

  React.useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const signInHandler = useCallback(async () => {
    if (!email || !password) {
      toast.error("Enter email and password");
      return;
    }
    setIsAuthBusy(true);
    try {
      await signIn(email.trim(), password);
      toast.success("Signed in");
      setPassword("");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Sign in failed";
      toast.error(message);
    } finally {
      setIsAuthBusy(false);
    }
  }, [email, password, signIn]);

  const signUpHandler = useCallback(async () => {
    if (!email || !password) {
      toast.error("Enter email and password");
      return;
    }
    setIsAuthBusy(true);
    try {
      await signUp(email.trim(), password);
      toast.success("Account created");
      setPassword("");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Sign up failed";
      toast.error(message);
    } finally {
      setIsAuthBusy(false);
    }
  }, [email, password, signUp]);

  const uploadHandler = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      setIsUploading(true);
      try {
        await uploadFile(file, user?.uid);
        toast.success("File analyzed and metadata saved");
        await loadDocuments();
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Upload failed";
        toast.error(message);
      } finally {
        setIsUploading(false);
        event.target.value = "";
      }
    },
    [loadDocuments, uploadFile, user?.uid]
  );

  const deleteHandler = useCallback(
    async (docId: number) => {
      if (!user) {
        return;
      }
      try {
        const token = await user.getIdToken();
        await deleteDocumentRecord(token, docId);
        setDocs((prev) => prev.filter((d) => d.id !== docId));
        toast.success("Document removed");
      } catch (err) {
        console.error(err);
        toast.error("Delete failed");
      }
    },
    [user]
  );

  const summary = useMemo(() => {
    if (!finData) {
      return "Upload a statement to generate insights and persist metadata.";
    }
    return `Latest analysis: ${finData.transactions.length} transactions, ${finData.anomalies.length} anomalies, score ${finData.health_score.score}.`;
  }, [finData]);

  return (
    <div className="max-w-5xl mx-auto space-y-5 sm:space-y-6">
      <div>
        <h1 className={cn("text-2xl font-bold", isDark ? "text-slate-100" : "text-slate-900")}>Documents & Uploads</h1>
        <p className={cn("text-sm mt-1", textSecondary)}>
          Upload statements, run analysis, and keep per-user metadata in Neon.
        </p>
      </div>

      {!isConfigured && (
        <div className={cn("border rounded-xl p-4", cardBg)}>
          <p className={textPrimary}>Firebase client config is missing.</p>
          <p className={cn("text-xs mt-1", textSecondary)}>
            Add VITE_FIREBASE_* values to frontend environment variables.
          </p>
        </div>
      )}

      {!user ? (
        <div className={cn("border rounded-2xl p-4 sm:p-6 space-y-4", cardBg)}>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5" style={{ color: ac[500] }} />
            <h2 className={cn("text-lg font-semibold", textPrimary)}>Sign in to manage your documents</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={cn(
                "px-3 py-2 rounded-lg border text-sm",
                isDark ? "bg-slate-800 border-slate-700 text-slate-100" : "bg-slate-50 border-slate-200 text-slate-900"
              )}
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={cn(
                "px-3 py-2 rounded-lg border text-sm",
                isDark ? "bg-slate-800 border-slate-700 text-slate-100" : "bg-slate-50 border-slate-200 text-slate-900"
              )}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => {
                void signInHandler();
              }}
              disabled={isAuthBusy || authLoading}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white"
              style={{ backgroundColor: ac[600] }}
            >
              {isAuthBusy ? "Please wait..." : "Sign In"}
            </button>
            <button
              onClick={() => {
                void signUpHandler();
              }}
              disabled={isAuthBusy || authLoading}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium border",
                isDark ? "border-slate-700 text-slate-200" : "border-slate-300 text-slate-700"
              )}
            >
              Create Account
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className={cn("border rounded-2xl p-4 sm:p-6 space-y-4", cardBg)}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <FileUp className="h-5 w-5" style={{ color: ac[500] }} />
                <h2 className={cn("text-lg font-semibold", textPrimary)}>Upload and Analyze</h2>
              </div>
              <label className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white cursor-pointer" style={{ backgroundColor: ac[600] }}>
                {(isUploading || analyzeLoading) ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
                Select Statement
                <input
                  type="file"
                  accept=".csv,.pdf,.png,.jpg,.jpeg,.xlsx,.xls,.txt"
                  onChange={uploadHandler}
                  className="hidden"
                  disabled={isUploading || analyzeLoading}
                />
              </label>
            </div>
            <p className={cn("text-sm", textSecondary)}>{summary}</p>
          </div>

          <div className={cn("border rounded-2xl p-4 sm:p-6", cardBg)}>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <div className="flex items-center gap-2">
                <FolderOpen className="h-5 w-5" style={{ color: ac[500] }} />
                <h2 className={cn("text-lg font-semibold", textPrimary)}>Stored Metadata</h2>
              </div>
              <button
                onClick={() => {
                  void loadDocuments();
                }}
                className={cn("inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border", isDark ? "border-slate-700 text-slate-300" : "border-slate-300 text-slate-700")}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", isDocsLoading && "animate-spin")} />
                Refresh
              </button>
            </div>

            {isDocsLoading ? (
              <div className={cn("text-sm", textSecondary)}>Loading documents...</div>
            ) : docs.length === 0 ? (
              <div className={cn("text-sm", textSecondary)}>No documents yet for this user.</div>
            ) : (
              <div className="space-y-3">
                {docs.map((doc) => {
                  const txCount = Number(doc.metadata?.transactions_count ?? 0);
                  const anomalyCount = Number(doc.metadata?.anomalies_count ?? 0);
                  const score = Number(doc.metadata?.health_score ?? 0);
                  return (
                    <div
                      key={doc.id}
                      className={cn(
                        "rounded-xl border p-4 flex flex-wrap items-start justify-between gap-3",
                        isDark ? "border-slate-800 bg-slate-800/30" : "border-slate-200 bg-slate-50"
                      )}
                    >
                      <div className="min-w-0">
                        <p className={cn("text-sm font-semibold truncate", textPrimary)}>{doc.filename}</p>
                        <p className={cn("text-xs mt-1", textSecondary)}>
                          {new Date(doc.created_at).toLocaleString()} • {doc.mime_type || "unknown"}
                        </p>
                        <p className={cn("text-xs mt-2", textSecondary)}>
                          {txCount} transactions • {anomalyCount} anomalies • score {score}
                        </p>
                      </div>
                      <button
                        onClick={() => {
                          void deleteHandler(doc.id);
                        }}
                        className={cn(
                          "inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs border",
                          isDark
                            ? "border-rose-400/30 text-rose-300 hover:bg-rose-500/10"
                            : "border-rose-300 text-rose-600 hover:bg-rose-50"
                        )}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
