from typing import List, Dict, Any

import io
import re
import tempfile
from pathlib import Path as _Path
from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ingestion.pdf_extractor import BankStatementPDFExtractor
from app.ingestion.nlp_parser import TransactionNLPParser
from app.ingestion.parser import parse_statement
from app.features.engineer import engineer_features
from app.scoring.health_score import compute_health_score
from app.recommendations.engine import generate_recommendations
from app import services

router = APIRouter()


# ─── Pydantic response models ────────────────────────────────────────────────

class ExtractionMeta(BaseModel):
    method: str             # "csv" | "native_pdf" | "ocr"
    pages: int
    rows_extracted: int
    confidence: float       # rows_extracted / detected_transaction_blocks


class ForecastPoint(BaseModel):
    date: str               # YYYY-MM-DD
    predicted_amount: float


class TransactionRow(BaseModel):
    date: str
    description: str
    amount: float
    balance: float | None
    category: str


class AnalyzeResponse(BaseModel):
    health_score: Dict[str, Any]
    recommendations: List[str]
    anomalies: List[Dict[str, Any]]
    forecast: List[ForecastPoint]   # now includes dates
    category_summary: Dict[str, float]
    transactions: List[TransactionRow]  # extracted rows visible to caller
    extraction_meta: ExtractionMeta


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_pdf_with_meta(file_content: bytes) -> tuple[pd.DataFrame, str, int, int]:
    """Run PDF extraction; return (df, method, pages, total_blocks)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    try:
        extractor = BankStatementPDFExtractor()
        method = "native_pdf"
        if not extractor._is_text_based(tmp_path):
            method = "ocr"
        raw_pages = extractor.extract(tmp_path)
        pages = len(raw_pages)
        parser = TransactionNLPParser()
        df = parser.parse_pages(raw_pages)
        full_text = "\n".join(raw_pages)
        block_pattern = re.compile(
            r"(?:\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b"
            r"|\b\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}\b"
            r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))",
            re.IGNORECASE,
        )
        total_blocks = max(len(block_pattern.findall(full_text)), 1)
    finally:
        _Path(tmp_path).unlink(missing_ok=True)
    return df, method, pages, total_blocks


def _build_forecast_points(forecast_values: list[float], last_date: date) -> List[ForecastPoint]:
    """Attach calendar dates to raw forecast floats."""
    points = []
    for i, val in enumerate(forecast_values, start=1):
        day = last_date + timedelta(days=i)
        points.append(ForecastPoint(date=day.isoformat(), predicted_amount=round(float(val), 2)))
    return points


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    file: UploadFile = File(...),
    user_id: str = Form(default="default"),
) -> AnalyzeResponse:
    """Upload CSV or PDF → full analysis pipeline → prediction + RAG indexing."""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # --- Stage 1: Parse ---
    if ext == "csv":
        method, pages = "csv", 1
        raw_df = parse_statement(file)
        total_blocks = len(raw_df)
    else:
        content = await file.read()
        raw_df, method, pages, total_blocks = _extract_pdf_with_meta(content)

    rows_extracted = len(raw_df)
    if rows_extracted == 0:
        return AnalyzeResponse(
            health_score={"score": 0, "grade": "F", "savings_rate": 0.0, "anomaly_ratio": 0.0, "forecast_trend": "stable"},
            recommendations=["No transactions could be extracted. Please upload a valid bank statement."],
            anomalies=[], forecast=[], category_summary={}, transactions=[],
            extraction_meta=ExtractionMeta(method=method, pages=pages, rows_extracted=0, confidence=0.0),
        )

    # --- Stage 2: Feature engineering ---
    featured_df = engineer_features(raw_df)

    # --- Stage 3: Anomaly detection ---
    anomaly_df = services.anomaly_detector.predict(featured_df)

    # --- Stage 4: LSTM forecast (hybrid strategy: per-user → global → exp-smoothing) ---
    daily_spend = featured_df.set_index("date")["amount"].resample("D").sum().fillna(0)
    forecast_values = services.forecaster.predict(daily_spend, horizon=30, user_id=user_id)
    last_date = featured_df["date"].max().date()
    forecast_points = _build_forecast_points(forecast_values.tolist(), last_date)

    # --- Stage 5: Health score ---
    health = compute_health_score(featured_df, anomaly_df, forecast_values)

    # --- Stage 6: Recommendations ---
    recs = generate_recommendations(health, featured_df)

    # --- Stage 7: Build RAG index ---
    chunks: List[str] = featured_df["description"].dropna().tolist()
    if "category" in featured_df.columns:
        for cat, group in featured_df.groupby("category"):
            chunks.append(f"Category {cat}: {len(group)} transactions totaling {group['amount'].sum():.2f}")
    featured_df["month_year"] = featured_df["date"].dt.to_period("M")
    for period, group in featured_df.groupby("month_year"):
        income = group.loc[group["amount"] > 0, "amount"].sum()
        spend = group.loc[group["amount"] < 0, "amount"].sum()
        chunks.append(f"Month {period}: income={income:.2f}, spending={spend:.2f}, net={income + spend:.2f}")
    if chunks:
        services.rag_pipeline.build_index(chunks)

    # --- Build response ---
    anomaly_rows = anomaly_df[anomaly_df["is_anomaly"] == True][["date", "description", "amount"]].copy()
    anomaly_rows["date"] = anomaly_rows["date"].dt.strftime("%Y-%m-%d")
    anomalies_list = anomaly_rows.to_dict(orient="records")

    category_summary: Dict[str, float] = {}
    if "category" in featured_df.columns:
        cat_spend = featured_df[featured_df["amount"] < 0].groupby("category")["amount"].sum().abs()
        category_summary = cat_spend.to_dict()

    # Build typed transaction list
    tx_df = anomaly_df[["date", "description", "amount", "balance"]].copy()
    if "category" in featured_df.columns:
        tx_df["category"] = featured_df["category"].values
    else:
        tx_df["category"] = "Other"
    tx_df["date"] = tx_df["date"].dt.strftime("%Y-%m-%d")
    tx_df["description"] = tx_df["description"].fillna("").astype(str)
    tx_df["category"] = tx_df["category"].fillna("Other").astype(str)
    transactions = [
        TransactionRow(**row)
        for row in tx_df[["date", "description", "amount", "balance", "category"]].to_dict(orient="records")
    ]

    return AnalyzeResponse(
        health_score=health,
        recommendations=recs,
        anomalies=anomalies_list,
        forecast=forecast_points,
        category_summary=category_summary,
        transactions=transactions,
        extraction_meta=ExtractionMeta(
            method=method,
            pages=pages,
            rows_extracted=rows_extracted,
            confidence=round(min(rows_extracted / total_blocks, 1.0), 4),
        ),
    )


@router.post("/extract", summary="Extract transactions from a PDF or CSV as a downloadable CSV file")
async def extract(file: UploadFile = File(...)) -> StreamingResponse:
    """
    Upload a PDF or CSV bank statement.
    Returns the extracted transactions as a clean, downloadable CSV — useful for
    inspection before running the full /analyze pipeline.
    """
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "csv":
        raw_df = parse_statement(file)
    else:
        content = await file.read()
        raw_df, _, _, _ = _extract_pdf_with_meta(content)

    csv_bytes = raw_df.to_csv(index=False).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=extracted_transactions.csv"},
    )
