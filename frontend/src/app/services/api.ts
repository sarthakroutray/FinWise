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
  chart?: {
    type: "bar" | "line" | "pie" | "area";
    title: string;
    data: any[];
  };
}

export interface HealthCheckResponse {
  status: string;
  app: string;
}

export interface DocumentRecord {
  id: number;
  user_uid: string;
  filename: string;
  mime_type: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface DocumentCreatePayload {
  filename: string;
  mime_type?: string;
  metadata?: Record<string, unknown>;
}

// ─── API functions ────────────────────────────────────────────────────────

const BASE = "https://mayank-96615--finwise-backend-fastapi-app.modal.run";

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

export async function analyzeTestDataset(
  userId: string = "default"
): Promise<AnalyzeResponse> {
  const res = await fetch(`${BASE}/analyze/test`, { method: "POST" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Analyze Test Dataset failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function queryRAG(
  question: string,
  use_rlm: boolean = false,
  rlm_provider?: string,
  rlm_model?: string
): Promise<QueryResponse> {
  const res = await fetch(`${BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, use_rlm, rlm_provider, rlm_model }),
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

function buildAuthHeaders(idToken: string): Record<string, string> {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${idToken}`,
  };
}

export async function listDocuments(idToken: string): Promise<DocumentRecord[]> {
  const res = await fetch(`${BASE}/documents`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${idToken}`,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`List documents failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function createDocumentRecord(
  idToken: string,
  payload: DocumentCreatePayload
): Promise<DocumentRecord> {
  const res = await fetch(`${BASE}/documents`, {
    method: "POST",
    headers: buildAuthHeaders(idToken),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Create document failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function deleteDocumentRecord(idToken: string, documentId: number): Promise<void> {
  const res = await fetch(`${BASE}/documents/${documentId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${idToken}`,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Delete document failed (${res.status}): ${text}`);
  }
}

// ── Chat (SSE Streaming) ──────────────────────────────────────────────────

export interface ChatRequestPayload {
  message: string;
  session_id: string;
  financial_context?: Record<string, unknown>;
}

/**
 * Opens an SSE connection to /chat. Returns a function to close the stream.
 * Calls `onEvent(eventType, data)` for each SSE event.
 */
export function streamChat(
  payload: ChatRequestPayload,
  onEvent: (event: string, data: any) => void,
  onError?: (err: Error) => void,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Chat failed (${res.status}): ${text}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let currentEvent = "message";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const rawData = line.slice(6);
            try {
              const parsed = JSON.parse(rawData);
              onEvent(currentEvent, parsed);
            } catch {
              onEvent(currentEvent, rawData);
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        onError?.(err);
      }
    }
  })();

  return () => controller.abort();
}

// ── Scratchpad ────────────────────────────────────────────────────────────

export async function queryScratchpad(
  sessionId: string,
  sql: string,
): Promise<any> {
  const res = await fetch(`${BASE}/scratchpad/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, sql }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Scratchpad query failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function resetScratchpad(sessionId: string): Promise<void> {
  const res = await fetch(`${BASE}/scratchpad/reset/${sessionId}`, {
    method: "POST",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Scratchpad reset failed (${res.status}): ${text}`);
  }
}

