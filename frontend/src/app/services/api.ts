// ─── TypeScript interfaces matching FastAPI Pydantic models ────────────────

export interface ExtractionMeta {
  method: "csv" | "native_pdf" | "ocr";
  pages: number;
  rows_extracted: number;
  confidence: number;
}

export interface ForecastPoint {
  date: string;
  predicted_amount: number;
}

export interface TransactionRow {
  date: string;
  description: string;
  amount: number;
  balance: number | null;
  category: string;
}

export interface HealthScore {
  score: number;
  grade: string;
  savings_rate: number;
  anomaly_ratio: number;
  forecast_trend: "improving" | "declining" | "stable";
}

export interface AnomalyRow {
  date: string;
  description: string;
  amount: number;
}

export interface AnalyzeResponse {
  health_score: HealthScore;
  recommendations: string[];
  anomalies: AnomalyRow[];
  forecast: ForecastPoint[];
  category_summary: Record<string, number>;
  transactions: TransactionRow[];
  extraction_meta: ExtractionMeta;
}

export interface QueryResponse {
  answer: string;
  sources: string[];
}

export interface HealthCheckResponse {
  status: string;
  app: string;
}

// ─── API functions ────────────────────────────────────────────────────────

const BASE = ""; // Vite proxy handles forwarding to backend

export async function analyzeFile(
  file: File,
  userId: string = "default"
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("user_id", userId);

  const res = await fetch(`${BASE}/analyze`, { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Analyze failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function queryRAG(question: string): Promise<QueryResponse> {
  const res = await fetch(`${BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Query failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function extractCSV(file: File): Promise<Blob> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${BASE}/extract`, { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Extract failed (${res.status}): ${text}`);
  }
  return res.blob();
}

export async function healthCheck(): Promise<HealthCheckResponse> {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed (${res.status})`);
  return res.json();
}
