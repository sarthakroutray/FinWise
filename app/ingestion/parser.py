import tempfile
from pathlib import Path

import pandas as pd
from fastapi import UploadFile, HTTPException

from app.ingestion.pdf_extractor import BankStatementPDFExtractor
from app.ingestion.nlp_parser import TransactionNLPParser


def parse_statement(file: UploadFile) -> pd.DataFrame:
    """Parse uploaded bank statement (.csv or .pdf) into a clean DataFrame."""
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    if ext == ".csv":
        return _parse_csv(file)
    elif ext == ".pdf":
        return _parse_pdf(file)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {ext}")


def _parse_csv(file: UploadFile) -> pd.DataFrame:
    """Read CSV and normalize columns."""
    df = pd.read_csv(file.file)
    # Normalize column names to lowercase
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    # Map common column name variants
    col_map = {}
    for col in df.columns:
        if "date" in col:
            col_map[col] = "date"
        elif "desc" in col or "narr" in col or "particular" in col:
            col_map[col] = "description"
        elif "amount" in col or "debit" in col or "credit" in col:
            col_map[col] = "amount"
        elif "bal" in col:
            col_map[col] = "balance"
    df = df.rename(columns=col_map)
    # Ensure required columns exist
    for required in ["date", "amount"]:
        if required not in df.columns:
            raise HTTPException(status_code=400, detail=f"CSV missing required column: {required}")
    if "description" not in df.columns:
        df["description"] = "Unknown"
    if "balance" not in df.columns:
        df["balance"] = None
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    df = df.dropna(subset=["date", "amount"])
    df = df[["date", "description", "amount", "balance"]].sort_values("date").reset_index(drop=True)
    return df


def _parse_pdf(file: UploadFile) -> pd.DataFrame:
    """Extract transactions from PDF via native parsing or OCR."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        extractor = BankStatementPDFExtractor()
        pages = extractor.extract(tmp_path)
        parser = TransactionNLPParser()
        df = parser.parse_pages(pages)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return df
