from typing import List, Dict, Any

import pandas as pd
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from app.ingestion.parser import parse_statement_with_meta
from app.features.engineer import engineer_features
from app.scoring.health_score import compute_health_score
from app.recommendations.engine import generate_recommendations
from app.services import anomaly_detector, forecaster, rag_pipeline

router = APIRouter()


class ExtractionMeta(BaseModel):
    method: str
    pages: int
    rows_extracted: int
    confidence: float


class AnalyzeResponse(BaseModel):
    health_score: Dict[str, Any]
    recommendations: List[str]
    anomalies: List[Dict[str, Any]]
    forecast: List[Dict[str, Any]]
    category_summary: Dict[str, float]
    transactions: List[Dict[str, Any]]
    extraction_meta: ExtractionMeta


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)) -> AnalyzeResponse:
    """Full analysis pipeline: parse → engineer → anomaly → forecast → score → recommend."""
    raw_df, parse_meta = parse_statement_with_meta(file)
    method = str(parse_meta.get("method", "auto"))
    pages = int(parse_meta.get("pages", 1) or 1)
    total_blocks = int(parse_meta.get("total_blocks", len(raw_df)) or len(raw_df))

    # Feature engineering
    featured_df = engineer_features(raw_df)

    # Anomaly detection (auto-trains if model missing)
    anomaly_detector.load()
    anomaly_df = anomaly_detector.predict(featured_df)

    # Forecasting (auto-trains if model missing)
    daily_spend = featured_df.set_index("date")["amount"].resample("D").sum().fillna(0)
    forecaster.load()
    forecast = forecaster.predict(daily_spend, horizon=30)

    # Health score
    health = compute_health_score(featured_df, anomaly_df, forecast)

    # Recommendations
    recs = generate_recommendations(health, featured_df)

    # Build RAG index from transaction descriptions
    descriptions = featured_df["description"].dropna().tolist()
    if descriptions:
        # Create document chunks: monthly summaries + individual descriptions
        chunks = descriptions.copy()
        if "category" in featured_df.columns:
            for cat, group in featured_df.groupby("category"):
                total = group["amount"].sum()
                count = len(group)
                chunks.append(f"Category {cat}: {count} transactions totaling {total:.2f}")
        rag_pipeline.build_index(chunks)
        rag_pipeline.set_full_context(featured_df)

    # Anomaly rows for response
    anomaly_rows = anomaly_df[anomaly_df["is_anomaly"] == True][
        ["date", "description", "amount"]
    ].copy()
    anomaly_rows["date"] = anomaly_rows["date"].dt.strftime("%Y-%m-%d")
    anomalies_list = anomaly_rows.to_dict(orient="records")

    # Category summary
    category_summary = {}
    if "category" in featured_df.columns:
        cat_spend = featured_df[featured_df["amount"] < 0].groupby("category")["amount"].sum().abs()
        category_summary = cat_spend.to_dict()

    # Extraction confidence
    rows_extracted = int(parse_meta.get("rows_extracted", len(raw_df)) or len(raw_df))
    confidence = rows_extracted / total_blocks if total_blocks > 0 else 1.0

    # Format forecast for frontend (List[Dict[str, Any]])
    # We use a 30-day window starting from the last date in the dataframe
    import datetime
    last_date = featured_df["date"].max() if not featured_df.empty else datetime.date.today()
    forecast_list = []
    for i, val in enumerate(forecast):
        target_date = last_date + datetime.timedelta(days=i+1)
        forecast_list.append({
            "date": target_date.strftime("%Y-%m-%d"),
            "predicted_amount": float(val)
        })

    # Format transactions for frontend
    transactions_list = []
    if not raw_df.empty:
        df_display = raw_df.copy()
        if "date" in df_display.columns:
            df_display["date"] = df_display["date"].dt.strftime("%Y-%m-%d")
        transactions_list = df_display.to_dict(orient="records")

    return AnalyzeResponse(
        health_score=health,
        recommendations=recs,
        anomalies=anomalies_list,
        forecast=forecast_list,
        category_summary=category_summary,
        transactions=transactions_list,
        extraction_meta=ExtractionMeta(
            method=method,
            pages=pages,
            rows_extracted=rows_extracted,
            confidence=round(min(confidence, 1.0), 4),
        ),
    )
