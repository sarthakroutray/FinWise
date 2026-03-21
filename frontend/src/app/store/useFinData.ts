import React, { createContext, useContext, useState, useCallback } from "react";
import { analyzeFile, type AnalyzeResponse } from "../services/api";

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
