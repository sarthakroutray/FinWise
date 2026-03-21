import React, { createContext, useContext, useState, useCallback } from "react";
import { analyzeFile, createDocumentRecord, type AnalyzeResponse } from "../services/api";
import { getFirebaseIdToken } from "../auth/firebase";

interface FinDataState {
  data: AnalyzeResponse | null;
  isLoading: boolean;
  error: string | null;
  uploadFile: (file: File, userId?: string) => Promise<void>;
  clearData: () => void;
}

const FinDataContext = createContext<FinDataState | null>(null);

export function FinDataProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uploadFile = useCallback(async (file: File, userId?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await analyzeFile(file, userId);
      setData(result);

      // Best-effort metadata persistence for authenticated users.
      const idToken = await getFirebaseIdToken();
      if (idToken) {
        try {
          await createDocumentRecord(idToken, {
            filename: file.name,
            mime_type: file.type || "application/octet-stream",
            metadata: {
              size_bytes: file.size,
              analyzed_at: new Date().toISOString(),
              transactions_count: result.transactions.length,
              anomalies_count: result.anomalies.length,
              health_score: result.health_score.score,
              extraction_meta: result.extraction_meta,
            },
          });
        } catch (persistError) {
          console.warn("Document metadata persistence skipped:", persistError);
        }
      }
    } catch (err: any) {
      setError(err.message || "Analysis failed");
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearData = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  return React.createElement(
    FinDataContext.Provider,
    { value: { data, isLoading, error, uploadFile, clearData } },
    children
  );
}

export function useFinData(): FinDataState {
  const ctx = useContext(FinDataContext);
  if (!ctx) throw new Error("useFinData must be used within FinDataProvider");
  return ctx;
}
