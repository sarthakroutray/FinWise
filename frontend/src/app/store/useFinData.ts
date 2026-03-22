import React, { createContext, useContext, useState, useCallback } from "react";
import { analyzeFile, createDocumentRecord, type AnalyzeResponse } from "../services/api";
import { getFirebaseIdToken } from "../auth/firebase";

const FIN_DATA_STORAGE_KEY = "finwise:lastAnalyzeResponse";

function loadStoredFinData(): AnalyzeResponse | null {
  try {
    const raw = localStorage.getItem(FIN_DATA_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AnalyzeResponse;
  } catch {
    return null;
  }
}

function persistFinData(data: AnalyzeResponse | null): void {
  try {
    if (!data) {
      localStorage.removeItem(FIN_DATA_STORAGE_KEY);
      return;
    }
    localStorage.setItem(FIN_DATA_STORAGE_KEY, JSON.stringify(data));
  } catch {
    // Ignore storage errors (private mode/quota limits)
  }
}

interface FinDataState {
  data: AnalyzeResponse | null;
  isLoading: boolean;
  error: string | null;
  uploadFile: (file: File, userId?: string) => Promise<void>;
  loadTestDataset: (userId?: string) => Promise<void>;
  clearData: () => void;
}

const FinDataContext = createContext<FinDataState | null>(null);

export function FinDataProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<AnalyzeResponse | null>(() => loadStoredFinData());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uploadFile = useCallback(async (file: File, userId?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await analyzeFile(file, userId);
      setData(result);
      persistFinData(result);

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

  const loadTestDataset = useCallback(async (userId?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      // dynamically import to map exactly to the updated api.ts
      const api = await import("../services/api");
      const result = await api.analyzeTestDataset(userId);
      setData(result);
      persistFinData(result);

      // Best-effort metadata persistence for authenticated users.
      const idToken = await getFirebaseIdToken();
      if (idToken) {
        try {
          await api.createDocumentRecord(idToken, {
            filename: "usa_paypal_statement.pdf",
            mime_type: "application/pdf",
            metadata: {
              size_bytes: 45000,
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
      setError(err.message || "Test Dataset Analysis failed");
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearData = useCallback(() => {
    setData(null);
    setError(null);
    persistFinData(null);
  }, []);

  return React.createElement(
    FinDataContext.Provider,
    { value: { data, isLoading, error, uploadFile, loadTestDataset, clearData } },
    children
  );
}

export function useFinData(): FinDataState {
  const ctx = useContext(FinDataContext);
  if (!ctx) throw new Error("useFinData must be used within FinDataProvider");
  return ctx;
}
