"""Upload parser adapter that delegates extraction to the hardened extractor CLI module."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile

from extract import BankStatementExtractor


def _rows_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert extractor rows to canonical pipeline DataFrame columns."""
    if not rows:
        return pd.DataFrame(columns=["date", "description", "amount", "balance", "currency", "extraction_confidence"])

    df = pd.DataFrame(rows)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df["amount"] = df["amount"].round(2)

    if "description" not in df.columns:
        df["description"] = "Unknown"
    else:
        df["description"] = df["description"].fillna("Unknown").astype(str)

    if "balance_after" in df.columns and "balance" not in df.columns:
        df["balance"] = pd.to_numeric(df["balance_after"], errors="coerce")
    elif "balance" not in df.columns:
        df["balance"] = None
    else:
        df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    if "balance" in df.columns:
        df["balance"] = df["balance"].round(2)

    if "currency" not in df.columns:
        df["currency"] = None
    else:
        df["currency"] = df["currency"].fillna("").astype(str).str.upper().replace({"": None})

    if "extraction_confidence" not in df.columns:
        df["extraction_confidence"] = "high"

    df = df.dropna(subset=["date", "amount"]).drop_duplicates()
    return df[["date", "description", "amount", "balance", "currency", "extraction_confidence"]].sort_values("date").reset_index(drop=True)


def parse_statement_with_meta(file: UploadFile) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Parse any uploaded statement format and return both dataframe and extraction metadata."""
    filename = file.filename or "uploaded_statement"
    ext = Path(filename).suffix.lower()
    if not ext:
        raise HTTPException(status_code=400, detail="Uploaded file must include a valid extension")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = Path(tmp.name)

    try:
        extractor = BankStatementExtractor(credits_positive=True)
        try:
            rows, report = extractor.extract_file(tmp_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}") from exc

        df = _rows_to_df(rows)
        method = {
            ".csv": "csv",
            ".tsv": "csv",
            ".pdf": "native_pdf",
            ".xls": "excel",
            ".xlsx": "excel",
            ".xlsm": "excel",
            ".html": "html",
            ".htm": "html",
            ".png": "image",
            ".jpg": "image",
            ".jpeg": "image",
            ".bmp": "image",
            ".tif": "image",
            ".tiff": "image",
            ".txt": "text",
            ".log": "text",
        }.get(ext, "auto")

        meta = {
            "method": method,
            "pages": max(int(report.get("total_pages", 1)), 1),
            "rows_extracted": int(len(df)),
            "total_blocks": max(int(report.get("transactions_found", len(df))), 1),
            "warnings": report.get("warnings", []),
        }
        return df, meta
    finally:
        tmp_path.unlink(missing_ok=True)


def parse_statement(file: UploadFile) -> pd.DataFrame:
    """Parse any uploaded statement format into a normalized dataframe."""
    df, _ = parse_statement_with_meta(file)
    return df
