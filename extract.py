from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pdfplumber
from dateutil import parser as date_parser
from PIL import Image

LOGGER = logging.getLogger("bank_extractor")

OUTPUT_COLUMNS = [
    "date",
    "description",
    "amount",
    "currency",
    "transaction_type",
    "reference_number",
    "balance_after",
    "bank_name",
    "account_number",
    "statement_period_start",
    "statement_period_end",
    "source_file",
    "extraction_confidence",
]

NOISE_PATTERNS = [
    re.compile(r"^page\s+\d+(\s+of\s+\d+)?$", re.IGNORECASE),
    re.compile(r"^date\s+description", re.IGNORECASE),
    re.compile(r"^opening\s+balance", re.IGNORECASE),
    re.compile(r"^closing\s+balance", re.IGNORECASE),
    re.compile(r"^total\b", re.IGNORECASE),
    re.compile(r"^summary\b", re.IGNORECASE),
]

DATE_TOKEN_PATTERN = re.compile(
    r"(\b\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}\b|"
    r"\b\d{4}[\/\-.]\d{1,2}[\/\-.]\d{1,2}\b|"
    r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}\b|"
    r"\b[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4}\b|"
    r"\b\d{1,2}[\/\-.]\d{1,2}\b)"
)

NUMBER_TOKEN_PATTERN = re.compile(
    r"\(?[-+]?(?:\d+(?:[.,]\d+)*|[.,]\d+)(?:\)?)(?:\s*(?:CR|DR))?",
    re.IGNORECASE,
)
REF_PATTERN = re.compile(r"\b(?:ref|utr|txn|tx|rrn|chq|cheque|check)\s*[:#-]?\s*([A-Za-z0-9\-/]{4,})\b", re.IGNORECASE)
ACCOUNT_PATTERN = re.compile(r"\b(?:a\/c|account)\s*(?:no|number)?\s*[:#-]?\s*([A-Za-z0-9*Xx-]{6,})", re.IGNORECASE)
PERIOD_PATTERN = re.compile(
    r"(?:from|period)\s+(.+?)\s+(?:to|-)\s+(.+)",
    re.IGNORECASE,
)
BANK_PATTERN = re.compile(r"\b([A-Z][A-Za-z& ]+\s+bank)\b", re.IGNORECASE)


@dataclass
class ParseContext:
    source_file: str
    bank_name: str | None = None
    account_number: str | None = None
    period_start: str | None = None
    period_end: str | None = None


class BankStatementExtractor:
    """Extract structured transaction rows from bank statements across file formats."""

    def __init__(self, credits_positive: bool = True) -> None:
        self.credits_positive = credits_positive
        self.warnings: list[str] = []
        self.pages_failed: list[int] = []
        self.max_abs_amount = 10_000_000.0
        self.max_abs_balance = 100_000_000.0

    def extract_file(self, input_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Extract transactions and parse report from an input statement file."""
        ext = input_path.suffix.lower()
        context = ParseContext(source_file=input_path.name)

        rows: list[dict[str, Any]]
        total_pages = 1
        if ext == ".pdf":
            rows, total_pages = self._extract_from_pdf(input_path, context)
        elif ext in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
            text = self._ocr_image(input_path)
            context = self._extract_statement_metadata(text, context)
            rows = self._parse_text_payload(text, context)
        elif ext in {".html", ".htm"}:
            html = input_path.read_text(encoding="utf-8", errors="ignore")
            rows = self._extract_from_html(html, context)
        elif ext == ".csv":
            rows = self._extract_from_csv(input_path, context)
        elif ext in {".xlsx", ".xls"}:
            rows = self._extract_from_excel(input_path, context)
        elif ext in {".txt", ".log"}:
            text = input_path.read_text(encoding="utf-8", errors="ignore")
            context = self._extract_statement_metadata(text, context)
            rows = self._parse_text_payload(text, context)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        rows = self._reconcile_amounts_with_balance(rows)
        normalized = [self._normalize_output_row(r, context) for r in rows]
        normalized = [r for r in normalized if r["date"] and r["amount"] is not None]
        normalized = self._filter_suspicious_rows(normalized)

        report = {
            "total_pages": total_pages,
            "pages_failed": self.pages_failed,
            "transactions_found": len(normalized),
            "transactions_skipped": max(len(rows) - len(normalized), 0),
            "warnings": self.warnings,
        }
        return normalized, report

    def _reconcile_amounts_with_balance(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Use running-balance deltas to correct obviously corrupted amount values."""
        reconciled: list[dict[str, Any]] = []
        prev_balance: float | None = None

        for row in rows:
            item = dict(row)
            amount = item.get("amount")
            balance = item.get("balance_after")

            try:
                amount_val = float(amount) if amount is not None else None
            except Exception:
                amount_val = None
            try:
                balance_val = float(balance) if balance not in (None, "") else None
            except Exception:
                balance_val = None

            if amount_val is not None and balance_val is not None and prev_balance is not None:
                delta = balance_val - prev_balance
                delta_mismatch = abs(amount_val - delta)
                # Correct rows where OCR likely fused reference/check number with amount.
                if abs(delta) > 0 and (
                    amount_val == 0
                    or abs(amount_val) > max(abs(delta) * 3.0, 100.0)
                    or (abs(amount_val) > 1 and abs(delta / amount_val) < 0.2)
                    or delta_mismatch > max(5.0, abs(delta) * 0.35)
                ):
                    desc = str(item.get("description") or "").lower()
                    debit_hints = ("purchase", "withdraw", "check", "charge", "fee", "debit")
                    credit_hints = ("credit", "deposit", "salary", "interest", "refund")
                    if any(h in desc for h in debit_hints) and delta < 0:
                        item["amount"] = float(delta)
                        item["transaction_type"] = "debit"
                        item["extraction_confidence"] = "low"
                        self.warnings.append(
                            f"Corrected amount via balance delta on {item.get('date')} ({item.get('description', '')[:30]})"
                        )
                    elif any(h in desc for h in credit_hints) and delta > 0:
                        item["amount"] = float(delta)
                        item["transaction_type"] = "credit"
                        item["extraction_confidence"] = "low"
                        self.warnings.append(
                            f"Corrected amount via balance delta on {item.get('date')} ({item.get('description', '')[:30]})"
                        )
                    elif abs(delta) <= max(abs(amount_val) * 0.25, 1.0):
                        item["amount"] = float(delta)
                        item["transaction_type"] = "credit" if delta >= 0 else "debit"
                        item["extraction_confidence"] = "low"
                        self.warnings.append(
                            f"Adjusted amount to running-balance delta on {item.get('date')}"
                        )

            if balance_val is not None:
                prev_balance = balance_val
            reconciled.append(item)

        return reconciled

    def _filter_suspicious_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop rows that are almost certainly OCR artifacts or parser corruption."""
        filtered: list[dict[str, Any]] = []
        now_year = datetime.now().year
        noise_terms = (
            "account transactions",
            "activity for",
            "checks paid",
            "check images",
            "deposits and other credits",
            "withdrawals and other debits",
        )

        for row in rows:
            try:
                amount = float(row.get("amount"))
            except Exception:
                self.warnings.append(f"Dropped row with invalid amount: {row}")
                continue

            if abs(amount) > self.max_abs_amount:
                self.warnings.append(f"Dropped suspicious amount {amount} in row dated {row.get('date')}")
                continue

            if abs(amount) < 0.005:
                self.warnings.append(f"Dropped near-zero amount row on {row.get('date')}")
                continue

            bal = row.get("balance_after")
            if bal not in (None, ""):
                try:
                    balance_val = float(bal)
                    if abs(balance_val) > self.max_abs_balance:
                        self.warnings.append(f"Dropped row with suspicious balance {balance_val} on {row.get('date')}")
                        continue
                except Exception:
                    row["balance_after"] = None

            date_val = str(row.get("date") or "")
            year = None
            if len(date_val) >= 4 and date_val[:4].isdigit():
                year = int(date_val[:4])
            if year is not None and (year < 2000 or year > now_year + 1):
                self.warnings.append(f"Dropped row with implausible year {year}: {row.get('description', '')[:60]}")
                continue

            desc = str(row.get("description") or "").lower()
            if any(term in desc for term in noise_terms):
                self.warnings.append(f"Dropped header-like row on {row.get('date')}: {row.get('description', '')[:60]}")
                continue

            if (
                row.get("balance_after") not in (None, "")
                and abs(float(row.get("balance_after") or 0.0)) < 0.005
                and abs(amount) <= 1.0
                and ("terminal" in desc or "credit" in desc)
            ):
                self.warnings.append(f"Dropped OCR artifact row on {row.get('date')}: {row.get('description', '')[:60]}")
                continue

            digits = sum(ch.isdigit() for ch in desc)
            alpha = sum(ch.isalpha() for ch in desc)
            if len(desc) > 80 and digits > alpha * 2:
                self.warnings.append(f"Dropped OCR-noisy row on {row.get('date')}: {row.get('description', '')[:60]}")
                continue

            filtered.append(row)

        return filtered

    def _extract_from_pdf(self, pdf_path: Path, context: ParseContext) -> tuple[list[dict[str, Any]], int]:
        """Extract rows from PDF using table, regex, and heuristic text strategies."""
        rows: list[dict[str, Any]] = []
        total_pages = 0
        full_text_chunks: list[str] = []

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            carry_description: str | None = None

            for idx, page in enumerate(pdf.pages, start=1):
                try:
                    page_text = page.extract_text() or ""
                    full_text_chunks.append(page_text)

                    page_rows = self._parse_tables_from_page(page, context)
                    if not page_rows:
                        line_rows, carry_description = self._parse_text_lines(
                            page_text.splitlines(),
                            context,
                            carry_description=carry_description,
                        )
                        page_rows = line_rows

                    if not page_rows and not page_text.strip():
                        self.warnings.append(f"Page {idx}: no text layer, OCR fallback attempted")
                        ocr_text = self._ocr_pdf_page(page)
                        full_text_chunks.append(ocr_text)
                        line_rows, carry_description = self._parse_text_lines(
                            ocr_text.splitlines(),
                            context,
                            carry_description=carry_description,
                        )
                        page_rows = line_rows

                    if not page_rows and page_text.strip():
                        # Heuristic fallback for unusual layouts.
                        page_rows = self._parse_unstructured_text(page_text, context)

                    rows.extend(page_rows)
                except Exception as exc:  # noqa: BLE001
                    self.pages_failed.append(idx)
                    self.warnings.append(f"Page {idx} failed: {exc}")
                    LOGGER.exception("Failed parsing page %s", idx)

        all_text = "\n".join(full_text_chunks)
        context = self._extract_statement_metadata(all_text, context)
        enriched = [self._normalize_output_row(r, context) for r in rows]
        return enriched, total_pages

    def _parse_tables_from_page(self, page: pdfplumber.page.Page, context: ParseContext) -> list[dict[str, Any]]:
        """Parse transaction rows from detected table structures on a PDF page."""
        parsed_rows: list[dict[str, Any]] = []
        tables = page.extract_tables() or []
        for table in tables:
            if not table:
                continue
            cleaned = [[(c or "").strip() for c in row] for row in table if row]
            if not cleaned:
                continue

            header_map, header_idx = self._detect_header_map(cleaned)
            if header_map is None:
                continue

            # Infer date ordering for ambiguous day/month values from this table section.
            sample_dates = [
                (r[header_map["date"]] if len(r) > header_map["date"] else "")
                for r in cleaned[header_idx + 1 : header_idx + 31]
            ]
            prefer_dayfirst = self._infer_dayfirst_preference(sample_dates)

            for row in cleaned[header_idx + 1 :]:
                parsed = self._build_row_from_columns(row, header_map, context, prefer_dayfirst)
                if parsed is not None:
                    parsed["extraction_confidence"] = "high"
                    parsed_rows.append(parsed)
        return parsed_rows

    def _detect_header_map(self, rows: list[list[str]]) -> tuple[dict[str, int] | None, int]:
        """Detect transaction-related column indexes from table header rows."""
        candidates = {
            "date": ["date", "value date", "txn date", "transaction date"],
            "description": ["description", "narration", "particulars", "details"],
            "debit": ["debit", "withdrawal", "dr"],
            "credit": ["credit", "deposit", "cr"],
            "amount": ["amount", "transaction amount"],
            "balance": ["balance", "running balance", "closing balance"],
            "currency": ["currency", "ccy"],
            "reference_number": ["reference", "ref", "txn id", "chq", "cheque"],
        }

        max_scan = min(len(rows), 5)
        for ridx in range(max_scan):
            normalized = [self._norm_header(col) for col in rows[ridx]]
            mapping: dict[str, int] = {}
            for idx, col in enumerate(normalized):
                for key, words in candidates.items():
                    if key in mapping:
                        continue
                    if any(w in col for w in words):
                        mapping[key] = idx
            if "date" in mapping and "description" in mapping and (
                "amount" in mapping or ("debit" in mapping and "credit" in mapping)
            ):
                return mapping, ridx

        return None, -1

    def _build_row_from_columns(
        self,
        row: list[str],
        header_map: dict[str, int],
        context: ParseContext,
        prefer_dayfirst: bool | None = None,
    ) -> dict[str, Any] | None:
        """Build a normalized transaction row from a mapped table row."""
        max_idx = max(header_map.values())
        if len(row) <= max_idx:
            row = row + [""] * (max_idx - len(row) + 1)

        date_val = self._parse_date(row[header_map["date"]], prefer_dayfirst=prefer_dayfirst)
        if date_val is None:
            return None

        description = self._clean_description(row[header_map["description"]])
        currency = None
        if "currency" in header_map:
            currency = self._extract_currency(row[header_map["currency"]])

        amount: float | None
        tx_type: str | None
        if "amount" in header_map:
            amount, tx_type, inferred_currency = self._parse_amount(row[header_map["amount"]], description)
            currency = currency or inferred_currency
        else:
            debit, _, cur1 = self._parse_amount(row[header_map["debit"]], description)
            credit, _, cur2 = self._parse_amount(row[header_map["credit"]], description)
            currency = currency or cur1 or cur2
            debit_val = abs(debit) if debit is not None else 0.0
            credit_val = abs(credit) if credit is not None else 0.0
            if debit_val == 0.0 and credit_val == 0.0:
                return None
            amount = credit_val - debit_val
            tx_type = "credit" if amount >= 0 else "debit"
            if not self.credits_positive:
                amount = -amount
                tx_type = "debit" if tx_type == "credit" else "credit"

        if "balance" in header_map:
            balance_val, cur3 = self._parse_plain_number(row[header_map["balance"]])
        else:
            balance_val, cur3 = None, None
        currency = currency or cur3

        reference_number = None
        if "reference_number" in header_map:
            reference_number = self._extract_reference(row[header_map["reference_number"]])
        reference_number = reference_number or self._extract_reference(description)

        return {
            "date": date_val,
            "description": description,
            "amount": amount,
            "currency": currency,
            "transaction_type": tx_type,
            "reference_number": reference_number,
            "balance_after": balance_val,
            "bank_name": context.bank_name,
            "account_number": context.account_number,
            "statement_period_start": context.period_start,
            "statement_period_end": context.period_end,
            "source_file": context.source_file,
            "extraction_confidence": "high",
        }

    def _parse_text_payload(self, text: str, context: ParseContext) -> list[dict[str, Any]]:
        """Parse plain text payload by regex lines then heuristic fallback."""
        line_rows, _ = self._parse_text_lines(text.splitlines(), context, carry_description=None)
        if line_rows:
            return line_rows
        return self._parse_unstructured_text(text, context)

    def _parse_text_lines(
        self,
        lines: Iterable[str],
        context: ParseContext,
        carry_description: str | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Parse date-led statement lines into transaction rows."""
        line_list = list(lines)
        prefer_dayfirst = self._infer_dayfirst_preference(line_list)
        rows: list[dict[str, Any]] = []
        current_carry = carry_description

        for raw in line_list:
            line = " ".join((raw or "").strip().split())
            if not line:
                continue
            if self._is_noise_line(line):
                continue

            date_match = DATE_TOKEN_PATTERN.search(line)
            if not date_match:
                if rows:
                    rows[-1]["description"] = self._clean_description(f"{rows[-1]['description']} {line}")
                    rows[-1]["extraction_confidence"] = "medium"
                else:
                    current_carry = f"{current_carry or ''} {line}".strip()
                continue

            date_token = date_match.group(1)
            parsed_date = self._parse_date(date_token, prefer_dayfirst=prefer_dayfirst)
            if parsed_date is None:
                continue

            prefix = line[: date_match.start()].strip()
            suffix = line[date_match.end() :].strip()
            desc_part, amount, currency, tx_type, balance = self._parse_suffix_fields(suffix)
            description = self._clean_description(" ".join([prefix, current_carry or "", desc_part]).strip())
            current_carry = None

            if amount is None:
                continue

            rows.append(
                {
                    "date": parsed_date,
                    "description": description or "Unknown",
                    "amount": amount,
                    "currency": currency,
                    "transaction_type": tx_type,
                    "reference_number": self._extract_reference(description),
                    "balance_after": balance,
                    "bank_name": context.bank_name,
                    "account_number": context.account_number,
                    "statement_period_start": context.period_start,
                    "statement_period_end": context.period_end,
                    "source_file": context.source_file,
                    "extraction_confidence": "medium",
                }
            )

        return rows, current_carry

    def _parse_suffix_fields(self, suffix: str) -> tuple[str, float | None, str | None, str | None, float | None]:
        """Split the post-date segment into description, amount and balance candidates."""
        number_matches = list(NUMBER_TOKEN_PATTERN.finditer(suffix))
        if not number_matches:
            return suffix, None, None, None, None

        first_num_start = number_matches[0].start()
        description = suffix[:first_num_start].strip()

        raw_tokens = [m.group(0) for m in number_matches]
        parsed_amounts: list[tuple[float | None, str | None, str | None]] = [
            self._parse_amount(tok, description) for tok in raw_tokens
        ]
        currencies = [p[2] for p in parsed_amounts if p[2]]

        if not any(p[0] is not None for p in parsed_amounts):
            return description, None, None, None, None

        amount: float | None = None
        tx_type: str | None = None
        balance: float | None = None

        if len(raw_tokens) >= 3:
            debit_amt, _, _ = self._parse_amount(raw_tokens[-3], description)
            credit_amt, _, _ = self._parse_amount(raw_tokens[-2], description)
            balance, bal_currency = self._parse_plain_number(raw_tokens[-1])
            if bal_currency:
                currencies.append(bal_currency)

            debit = abs(debit_amt) if debit_amt is not None else 0.0
            credit = abs(credit_amt) if credit_amt is not None else 0.0
            amount = credit - debit
            tx_type = "credit" if amount >= 0 else "debit"
        elif len(raw_tokens) == 2:
            amount, tx_type, cur_a = self._parse_amount(raw_tokens[0], description)
            balance, bal_currency = self._parse_plain_number(raw_tokens[1])
            if cur_a:
                currencies.append(cur_a)
            if bal_currency:
                currencies.append(bal_currency)
            if amount is None:
                return description, None, None, None, None
        else:
            amount, tx_type, cur_a = self._parse_amount(raw_tokens[0], description)
            if cur_a:
                currencies.append(cur_a)
            if amount is None:
                return description, None, None, None, None

        if amount is not None and not self.credits_positive:
            amount = -amount
            tx_type = "debit" if tx_type == "credit" else "credit"

        return description, amount, (currencies[0] if currencies else None), tx_type, balance

    def _parse_unstructured_text(self, text: str, context: ParseContext) -> list[dict[str, Any]]:
        """Parse free-form text as last-resort heuristic extraction."""
        rows: list[dict[str, Any]] = []
        for chunk in re.split(r"\n{2,}", text):
            line_rows, _ = self._parse_text_lines(chunk.splitlines(), context, carry_description=None)
            for row in line_rows:
                row["extraction_confidence"] = "low"
                rows.append(row)
        return rows

    def _extract_from_html(self, html: str, context: ParseContext) -> list[dict[str, Any]]:
        """Extract rows from HTML tables and text blocks."""
        try:
            from bs4 import BeautifulSoup
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"beautifulsoup4 not installed: {exc}")
            return self._parse_text_payload(html, context)

        soup = BeautifulSoup(html, "html.parser")
        context = self._extract_statement_metadata(soup.get_text(" "), context)
        rows: list[dict[str, Any]] = []

        for table in soup.find_all("table"):
            matrix: list[list[str]] = []
            for tr in table.find_all("tr"):
                cells = tr.find_all(["th", "td"])
                matrix.append([c.get_text(" ", strip=True) for c in cells])
            if not matrix:
                continue
            header_map, header_idx = self._detect_header_map(matrix)
            if header_map is None:
                continue
            for row in matrix[header_idx + 1 :]:
                parsed = self._build_row_from_columns(row, header_map, context)
                if parsed:
                    parsed["extraction_confidence"] = "high"
                    rows.append(parsed)

        if rows:
            return rows

        return self._parse_text_payload(soup.get_text("\n"), context)

    def _extract_from_csv(self, input_path: Path, context: ParseContext) -> list[dict[str, Any]]:
        """Extract rows from CSV with auto header normalization."""
        df = pd.read_csv(input_path, dtype=str, encoding="utf-8", keep_default_na=False)
        return self._extract_rows_from_dataframe(df, context)

    def _extract_from_excel(self, input_path: Path, context: ParseContext) -> list[dict[str, Any]]:
        """Extract rows from all Excel sheets with header normalization."""
        try:
            excel = pd.ExcelFile(input_path)
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"Excel parsing unavailable: {exc}")
            return []
        all_rows: list[dict[str, Any]] = []
        for sheet in excel.sheet_names:
            df = pd.read_excel(excel, sheet_name=sheet, dtype=str)
            sheet_rows = self._extract_rows_from_dataframe(df.fillna(""), context)
            all_rows.extend(sheet_rows)
        return all_rows

    def _extract_rows_from_dataframe(self, df: pd.DataFrame, context: ParseContext) -> list[dict[str, Any]]:
        """Convert a generic dataframe into normalized transaction rows."""
        if df.empty:
            return []

        normalized_cols = {col: self._norm_header(str(col)) for col in df.columns}
        col_map: dict[str, str] = {}
        for original, norm in normalized_cols.items():
            if "date" in norm and "date" not in col_map:
                col_map["date"] = original
            elif any(k in norm for k in ["description", "narration", "particular", "details"]) and "description" not in col_map:
                col_map["description"] = original
            elif any(k in norm for k in ["withdraw", "debit", "dr"]) and "debit" not in col_map:
                col_map["debit"] = original
            elif any(k in norm for k in ["deposit", "credit", "cr"]) and "credit" not in col_map:
                col_map["credit"] = original
            elif "amount" in norm and "amount" not in col_map:
                col_map["amount"] = original
            elif "balance" in norm and "balance" not in col_map:
                col_map["balance"] = original
            elif any(k in norm for k in ["currency", "ccy"]) and "currency" not in col_map:
                col_map["currency"] = original
            elif any(k in norm for k in ["reference", "ref", "utr", "txn id", "chq"]) and "reference_number" not in col_map:
                col_map["reference_number"] = original

        if "date" not in col_map:
            return []

        rows: list[dict[str, Any]] = []
        prev_balance: float | None = None
        for _, rec in df.iterrows():
            date_val = self._parse_date(str(rec.get(col_map["date"], "")))
            if date_val is None:
                continue

            description = self._clean_description(str(rec.get(col_map.get("description", ""), "")))
            currency = self._extract_currency(str(rec.get(col_map.get("currency", ""), ""))) if "currency" in col_map else None

            amount: float | None
            tx_type: str | None
            amount_token = str(rec.get(col_map.get("amount", ""), "")) if "amount" in col_map else ""
            if "amount" in col_map:
                amount, tx_type, inferred_currency = self._parse_amount(amount_token, description)
                currency = currency or inferred_currency
            else:
                debit, _, cur1 = self._parse_amount(str(rec.get(col_map.get("debit", ""), "")), description)
                credit, _, cur2 = self._parse_amount(str(rec.get(col_map.get("credit", ""), "")), description)
                currency = currency or cur1 or cur2
                debit_val = abs(debit) if debit is not None else 0.0
                credit_val = abs(credit) if credit is not None else 0.0
                if debit_val == 0.0 and credit_val == 0.0:
                    continue
                amount = credit_val - debit_val
                tx_type = "credit" if amount >= 0 else "debit"
                if not self.credits_positive:
                    amount = -amount
                    tx_type = "debit" if tx_type == "credit" else "credit"

            if amount is None:
                continue

            balance = None
            if "balance" in col_map:
                balance, cur3 = self._parse_plain_number(str(rec.get(col_map["balance"], "")))
                currency = currency or cur3

            if "amount" in col_map and balance is not None and prev_balance is not None:
                has_explicit_sign = bool(re.search(r"\b(?:CR|DR)\b|[\-()]", amount_token, re.IGNORECASE))
                if not has_explicit_sign and amount is not None:
                    delta = balance - prev_balance
                    if abs(abs(delta) - abs(amount)) <= max(0.01, abs(amount) * 0.02):
                        amount = delta
                        tx_type = "credit" if amount >= 0 else "debit"
                        if not self.credits_positive:
                            amount = -amount
                            tx_type = "debit" if tx_type == "credit" else "credit"

            if balance is not None:
                prev_balance = balance

            ref = str(rec.get(col_map.get("reference_number", ""), "")).strip() if "reference_number" in col_map else None
            ref = ref or self._extract_reference(description)

            rows.append(
                {
                    "date": date_val,
                    "description": description or "Unknown",
                    "amount": amount,
                    "currency": currency,
                    "transaction_type": tx_type,
                    "reference_number": ref,
                    "balance_after": balance,
                    "bank_name": context.bank_name,
                    "account_number": context.account_number,
                    "statement_period_start": context.period_start,
                    "statement_period_end": context.period_end,
                    "source_file": context.source_file,
                    "extraction_confidence": "high",
                }
            )
        return rows

    def _extract_statement_metadata(self, text: str, context: ParseContext) -> ParseContext:
        """Extract statement-level metadata for enrichment fields."""
        if not context.bank_name:
            m = BANK_PATTERN.search(text)
            if m:
                context.bank_name = m.group(1).strip()
        if not context.account_number:
            m = ACCOUNT_PATTERN.search(text)
            if m:
                context.account_number = m.group(1).strip()
        if not context.period_start or not context.period_end:
            for line in text.splitlines():
                m = PERIOD_PATTERN.search(line)
                if not m:
                    continue
                start = self._parse_date(m.group(1).strip())
                end = self._parse_date(m.group(2).strip())
                if start:
                    context.period_start = start
                if end:
                    context.period_end = end
                if context.period_start and context.period_end:
                    break
        return context

    def _parse_date(self, token: str, prefer_dayfirst: bool | None = None) -> str | None:
        """Parse many date variants into ISO-8601 date strings."""
        value = " ".join((token or "").split())
        if not value:
            return None

        # Handle year-first formats explicitly to avoid dayfirst ambiguity.
        if re.match(r"^\d{4}[\/\-.]\d{1,2}[\/\-.]\d{1,2}$", value):
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.date().isoformat()
                except ValueError:
                    continue

        if re.match(r"^\d{1,2}[\/\-.]\d{1,2}$", value):
            year = datetime.now().year
            sep = "/" if "/" in value else ("-" if "-" in value else ".")
            left, right = [int(p) for p in value.split(sep)]

            # Resolve obvious non-ambiguous cases first.
            inferred_dayfirst = prefer_dayfirst
            if left > 12 and right <= 12:
                inferred_dayfirst = True
            elif right > 12 and left <= 12:
                inferred_dayfirst = False
            elif inferred_dayfirst is None:
                # Practical defaults by separator when still ambiguous.
                inferred_dayfirst = True if sep == "." else False

            fmts = [
                ("%d/%m", "%d-%m", "%d.%m"),
                ("%m/%d", "%m-%d", "%m.%d"),
            ]
            format_order = [fmts[0], fmts[1]] if inferred_dayfirst else [fmts[1], fmts[0]]

            for group in format_order:
                for fmt in group:
                    try:
                        dt = datetime.strptime(value, fmt).replace(year=year)
                        return dt.date().isoformat()
                    except ValueError:
                        continue

        parse_orders = [prefer_dayfirst, not prefer_dayfirst] if prefer_dayfirst is not None else [True, False]
        for day_first in parse_orders:
            try:
                dt = date_parser.parse(value, dayfirst=day_first, fuzzy=False)
                if dt.year < 1900:
                    continue
                return dt.date().isoformat()
            except (ValueError, OverflowError):
                continue

        return None

    def _infer_dayfirst_preference(self, samples: Iterable[str]) -> bool | None:
        """Infer day-first preference from a batch of date-containing strings."""
        dayfirst_votes = 0
        monthfirst_votes = 0

        for sample in samples:
            text = str(sample or "")
            m = DATE_TOKEN_PATTERN.search(text)
            if not m:
                continue
            token = m.group(1)
            # Dotted dates are most often day-first in statements.
            if "." in token:
                dayfirst_votes += 1
                continue

            parts = re.split(r"[\/\-.]", token)
            if len(parts) < 2:
                continue
            if len(parts[0]) == 4:
                continue

            try:
                left = int(parts[0])
                right = int(parts[1])
            except ValueError:
                continue

            if left > 12 and right <= 12:
                dayfirst_votes += 1
            elif right > 12 and left <= 12:
                monthfirst_votes += 1

        if dayfirst_votes == 0 and monthfirst_votes == 0:
            return None
        if dayfirst_votes == monthfirst_votes:
            return None
        return dayfirst_votes > monthfirst_votes

        return None

    def _parse_amount(self, token: str, description_hint: str) -> tuple[float | None, str | None, str | None]:
        """Parse amount token into signed float, transaction type, and currency."""
        raw = (token or "").strip()
        if not raw:
            return None, None, None

        currency = self._extract_currency(raw)
        tx_hint_credit = self._is_credit_description(description_hint)

        upper = raw.upper()
        has_explicit_numeric_sign = bool(re.search(r"[\-+()]", raw))
        sign_multiplier = 1.0
        if "DR" in upper:
            sign_multiplier = -1.0
        elif "CR" in upper:
            sign_multiplier = 1.0

        if raw.startswith("(") and raw.endswith(")"):
            sign_multiplier = -1.0

        cleaned = re.sub(r"[^0-9,().\-+]", "", raw)
        cleaned = cleaned.replace("(", "").replace(")", "")

        if cleaned.count(",") > 0 and cleaned.count(".") > 0:
            last_comma = cleaned.rfind(",")
            last_dot = cleaned.rfind(".")
            if last_comma > last_dot:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif cleaned.count(",") > 0 and cleaned.count(".") == 0:
            if len(cleaned.split(",")[-1]) in {1, 2}:
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")

        try:
            value = float(cleaned)
        except ValueError:
            return None, None, currency

        if (
            sign_multiplier == 1.0
            and "DR" not in upper
            and "CR" not in upper
            and not has_explicit_numeric_sign
        ):
            # Infer sign when marker absent.
            sign_multiplier = 1.0 if tx_hint_credit else -1.0

        signed = value * sign_multiplier
        if not self.credits_positive:
            signed = -signed

        tx_type = "credit" if signed >= 0 else "debit"
        return signed, tx_type, currency

    def _parse_plain_number(self, token: str) -> tuple[float | None, str | None]:
        """Parse a numeric token without debit/credit sign inference."""
        raw = (token or "").strip()
        if not raw:
            return None, None

        currency = self._extract_currency(raw)
        cleaned = re.sub(r"[^0-9,().\-+]", "", raw)
        is_negative = cleaned.startswith("(") and cleaned.endswith(")")
        cleaned = cleaned.replace("(", "").replace(")", "")

        if cleaned.count(",") > 0 and cleaned.count(".") > 0:
            last_comma = cleaned.rfind(",")
            last_dot = cleaned.rfind(".")
            if last_comma > last_dot:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif cleaned.count(",") > 0 and cleaned.count(".") == 0:
            if len(cleaned.split(",")[-1]) in {1, 2}:
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")

        try:
            value = float(cleaned)
        except ValueError:
            return None, currency

        if is_negative and value > 0:
            value = -value
        return value, currency

    def _extract_currency(self, text: str) -> str | None:
        """Extract a 3-letter currency code or infer from symbol."""
        s = (text or "").upper()
        for code in ("USD", "EUR", "GBP", "INR", "AUD", "CAD", "JPY"):
            if code in s:
                return code
        if "$" in s:
            return "USD"
        if "EUR" in s or "\u20ac" in text:
            return "EUR"
        if "GBP" in s or "\u00a3" in text:
            return "GBP"
        if "\u20b9" in text:
            return "INR"
        return None

    def _extract_reference(self, text: str | None) -> str | None:
        """Extract transaction reference number from free text."""
        if not text:
            return None
        m = REF_PATTERN.search(text)
        return m.group(1) if m else None

    @staticmethod
    def _clean_description(text: str) -> str:
        """Normalize multi-line and noisy description text."""
        return " ".join((text or "").replace("\n", " ").split()).strip()

    @staticmethod
    def _norm_header(text: str) -> str:
        """Normalize header text for column auto-detection."""
        return " ".join((text or "").strip().lower().replace("_", " ").split())

    @staticmethod
    def _is_credit_description(text: str) -> bool:
        """Infer credit/debit orientation from transaction description."""
        s = (text or "").lower()
        credit_words = ["credit", "deposit", "salary", "refund", "interest"]
        debit_words = ["debit", "purchase", "withdraw", "atm", "charge", "fee", "payment", "check", "cheque"]
        if any(w in s for w in credit_words):
            return True
        if any(w in s for w in debit_words):
            return False
        return False

    @staticmethod
    def _is_noise_line(line: str) -> bool:
        """Detect header/footer/summary noise lines that should be skipped."""
        cleaned = " ".join((line or "").strip().split())
        if not cleaned:
            return True
        return any(pat.match(cleaned) for pat in NOISE_PATTERNS)

    def _ocr_pdf_page(self, page: pdfplumber.page.Page) -> str:
        """OCR a PDF page image using easyocr first, then pytesseract if available."""
        try:
            pil = page.to_image(resolution=250).original
            return self._ocr_pil(pil)
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"OCR page fallback failed: {exc}")
            return ""

    def _ocr_image(self, image_path: Path) -> str:
        """OCR an image file to text with graceful engine fallback."""
        with Image.open(image_path) as img:
            return self._ocr_pil(img)

    def _ocr_pil(self, img: Image.Image) -> str:
        """Run OCR with easyocr (no tesseract binary) and fallback to pytesseract."""
        # Alternative to Tesseract: easyocr works directly via Python package.
        try:
            import numpy as np
            import easyocr

            reader = easyocr.Reader(["en"], gpu=False)
            arr = np.array(img.convert("RGB"))
            chunks = reader.readtext(arr, detail=1, paragraph=False)
            if chunks:
                # Reconstruct text lines from token-level OCR boxes to reduce mega-line merges.
                tokens: list[tuple[float, float, str]] = []
                for item in chunks:
                    if not item or len(item) < 2:
                        continue
                    box, text = item[0], str(item[1]).strip()
                    if not text:
                        continue
                    ys = [p[1] for p in box]
                    xs = [p[0] for p in box]
                    y_center = sum(ys) / max(len(ys), 1)
                    x_min = min(xs)
                    tokens.append((y_center, x_min, text))

                tokens.sort(key=lambda t: (t[0], t[1]))
                lines: list[list[tuple[float, str]]] = []
                y_tolerance = 12.0
                for y, x, text in tokens:
                    if not lines:
                        lines.append([(x, text)])
                        current_y = y
                        continue
                    if abs(y - current_y) <= y_tolerance:
                        lines[-1].append((x, text))
                    else:
                        lines.append([(x, text)])
                        current_y = y

                merged_lines: list[str] = []
                for line in lines:
                    line.sort(key=lambda t: t[0])
                    merged = " ".join(part for _, part in line).strip()
                    if merged:
                        merged_lines.append(merged)

                if merged_lines:
                    return "\n".join(merged_lines)
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"easyocr unavailable/failed: {exc}")

        try:
            import pytesseract

            return pytesseract.image_to_string(img)
        except Exception as exc:  # noqa: BLE001
            self.warnings.append(f"pytesseract fallback failed: {exc}")
            return ""

    def _normalize_output_row(self, row: dict[str, Any], context: ParseContext) -> dict[str, Any]:
        """Guarantee output schema completeness with explicit nullables."""
        normalized = {k: row.get(k) for k in OUTPUT_COLUMNS}
        normalized["bank_name"] = normalized.get("bank_name") or context.bank_name
        normalized["account_number"] = normalized.get("account_number") or context.account_number
        normalized["statement_period_start"] = normalized.get("statement_period_start") or context.period_start
        normalized["statement_period_end"] = normalized.get("statement_period_end") or context.period_end
        normalized["source_file"] = normalized.get("source_file") or context.source_file

        for key in OUTPUT_COLUMNS:
            if key not in normalized:
                normalized[key] = None

        if normalized["extraction_confidence"] not in {"high", "medium", "low"}:
            normalized["extraction_confidence"] = "low"

        return normalized


def write_csv_with_warnings(output_csv: Path, rows: list[dict[str, Any]], warnings: list[str]) -> None:
    """Write UTF-8 quoted CSV rows and append a commented warnings section."""
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=OUTPUT_COLUMNS,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_ALL,
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in OUTPUT_COLUMNS})

        f.write("\n# WARNINGS\n")
        if warnings:
            for w in warnings:
                escaped = w.replace("\n", " ").strip()
                f.write(f"# {escaped}\n")
        else:
            f.write("# none\n")


def write_report(report_path: Path, report: dict[str, Any]) -> None:
    """Write JSON parse report to disk."""
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def main() -> None:
    """Run CLI extraction and emit CSV plus parse report artifacts."""
    parser = argparse.ArgumentParser(description="Extract structured transactions from bank statements.")
    parser.add_argument("input_file", type=str, help="Input statement path")
    parser.add_argument(
        "--debits-positive",
        action="store_true",
        help="Store debits as positive and credits as negative",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(message)s")

    input_path = Path(args.input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    extractor = BankStatementExtractor(credits_positive=not args.debits_positive)
    rows, report = extractor.extract_file(input_path)

    output_csv = Path(f"{input_path}.csv")
    report_path = input_path.parent / "parse_report.json"

    write_csv_with_warnings(output_csv, rows, extractor.warnings)
    write_report(report_path, report)

    print(f"Transactions extracted: {len(rows)}")
    print(f"CSV written: {output_csv}")
    print(f"Report written: {report_path}")


if __name__ == "__main__":
    main()
