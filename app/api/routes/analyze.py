from typing import List, Dict, Any

import io
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ingestion.parser import parse_statement, parse_statement_with_meta
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
    currency: str | None = None
    category: str
    extraction_confidence: str = "high"


class AnalyzeResponse(BaseModel):
    health_score: Dict[str, Any]
    recommendations: List[str]
    anomalies: List[Dict[str, Any]]
    forecast: List[ForecastPoint]   # now includes dates
    category_summary: Dict[str, float]
    transactions: List[TransactionRow]  # extracted rows visible to caller
    extraction_meta: ExtractionMeta


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_forecast_points(forecast_values: list[float], last_date: date) -> List[ForecastPoint]:
    """Attach calendar dates to raw forecast floats."""
    points = []
    for i, val in enumerate(forecast_values, start=1):
        day = last_date + timedelta(days=i)
        safe_val = float(val)
        if not math.isfinite(safe_val):
            safe_val = 0.0
        points.append(ForecastPoint(date=day.isoformat(), predicted_amount=round(safe_val, 2)))
    return points


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Return a finite float for API payloads."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return float(default)
    return num if math.isfinite(num) else float(default)


def _safe_optional_float(value: Any) -> float | None:
    """Return a finite float or None for nullable payload fields."""
    if value is None or pd.isna(value):
        return None
    num = _safe_float(value, default=0.0)
    return num if math.isfinite(num) else None


def _make_json_safe(value: Any) -> Any:
    """Recursively convert non-finite numerics to JSON-safe values."""
    if isinstance(value, dict):
        return {str(k): _make_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_make_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_make_json_safe(v) for v in value)
    if isinstance(value, np.floating):
        return _safe_float(value)
    if isinstance(value, float):
        return _safe_float(value)
    return value


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    file: UploadFile = File(...),
    user_id: str = Form(default="default"),
) -> AnalyzeResponse:
    """Upload statement file → extraction pipeline → prediction + RAG indexing."""

    # --- Stage 1: Parse (all supported formats) ---
    raw_df, parse_meta = parse_statement_with_meta(file)
    method = str(parse_meta.get("method", "auto"))
    pages = int(parse_meta.get("pages", 1))
    total_blocks = int(parse_meta.get("total_blocks", max(len(raw_df), 1)))

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
    anomaly_rows["amount"] = anomaly_rows["amount"].apply(_safe_float)
    anomalies_list = anomaly_rows.to_dict(orient="records")

    category_summary: Dict[str, float] = {}
    if "category" in featured_df.columns:
        cat_spend = featured_df[featured_df["amount"] < 0].groupby("category")["amount"].sum().abs()
        category_summary = {str(k): _safe_float(v) for k, v in cat_spend.to_dict().items()}

    # Build typed transaction list
    tx_df = anomaly_df[["date", "description", "amount", "balance"]].copy()
    if "currency" in anomaly_df.columns:
        tx_df["currency"] = anomaly_df["currency"].values
    elif "currency" in featured_df.columns:
        tx_df["currency"] = featured_df["currency"].values
    else:
        tx_df["currency"] = None
    if "category" in featured_df.columns:
        tx_df["category"] = featured_df["category"].values
    else:
        tx_df["category"] = "Other"
    # Carry per-row extraction confidence from the raw DataFrame if available
    if "extraction_confidence" in raw_df.columns:
        tx_df["extraction_confidence"] = raw_df["extraction_confidence"].reindex(tx_df.index).fillna("high").values
    else:
        tx_df["extraction_confidence"] = "high"
    tx_df["date"] = tx_df["date"].dt.strftime("%Y-%m-%d")
    tx_df["description"] = tx_df["description"].fillna("").astype(str)
    tx_df["currency"] = tx_df["currency"].fillna("").astype(str).str.upper().replace({"": None})
    tx_df["category"] = tx_df["category"].fillna("Other").astype(str)
    tx_df["amount"] = tx_df["amount"].apply(_safe_float)
    tx_df["balance"] = tx_df["balance"].apply(_safe_optional_float)

    health = {
        "score": _safe_float(health.get("score", 0.0)),
        "grade": str(health.get("grade", "F")),
        "savings_rate": _safe_float(health.get("savings_rate", 0.0)),
        "anomaly_ratio": _safe_float(health.get("anomaly_ratio", 0.0)),
        "forecast_trend": str(health.get("forecast_trend", "stable")),
    }

    safe_total_blocks = max(total_blocks, 1)
    confidence = round(min(rows_extracted / safe_total_blocks, 1.0), 4)
    transactions = [
        TransactionRow(**row)
        for row in tx_df[["date", "description", "amount", "balance", "currency", "category", "extraction_confidence"]].to_dict(orient="records")
    ]

    response = AnalyzeResponse(
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
            confidence=_safe_float(confidence),
        ),
    )
    safe_payload = _make_json_safe(response.model_dump())
    return AnalyzeResponse.model_validate(safe_payload)


@router.post("/extract", summary="Extract transactions from a PDF or CSV as a downloadable CSV file")
async def extract(file: UploadFile = File(...)) -> StreamingResponse:
    """
    Upload a PDF or CSV bank statement.
    Returns the extracted transactions as a clean, downloadable CSV — useful for
    inspection before running the full /analyze pipeline.
    """
    raw_df = parse_statement(file)

    csv_bytes = raw_df.to_csv(index=False).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=extracted_transactions.csv"},
    )
