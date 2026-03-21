from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
    re.compile(r"\bactivity\s+for\b", re.IGNORECASE),
    re.compile(r"\brelationship\s+checking\b", re.IGNORECASE),
    re.compile(r"\baccount\s+summary\b", re.IGNORECASE),
    re.compile(r"\baccount\s+service\s+charges\b", re.IGNORECASE),
    re.compile(r"\bchecks?\s+paid\b", re.IGNORECASE),
    re.compile(r"\bcheck\s+images\b", re.IGNORECASE),
    re.compile(r"\bdeposits?\s+and\s+other\s+credits\b", re.IGNORECASE),
    re.compile(r"\bwithdrawals?\s+and\s+other\s+debits\b", re.IGNORECASE),
    re.compile(r"\bdaily\s+(?:ending\s+)?balance\b", re.IGNORECASE),
    re.compile(r"\bstatement\s+of\s+account\b", re.IGNORECASE),
    re.compile(r"\bservice\s+charges?\s+and\s+fees\b", re.IGNORECASE),
    re.compile(r"\binterest-bearing\s+days\b", re.IGNORECASE),
    re.compile(r"\baverage\s+balance\b", re.IGNORECASE),
]

DATE_TOKEN_REGEX = (
    r"\b\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}\b|"
    r"\b\d{4}[\/\-.]\d{1,2}[\/\-.]\d{1,2}\b|"
    r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}\b|"
    r"\b[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4}\b|"
    r"\b\d{1,2}\s+[A-Za-z]{3,9}\b|"
    r"\b[A-Za-z]{3,9}\s+\d{1,2}\b|"
    r"\b\d{1,2}[\/\-.]\d{1,2}\b"
)
DATE_TOKEN_PATTERN = re.compile(rf"({DATE_TOKEN_REGEX})")
START_DATE_TOKEN_PATTERN = re.compile(rf"^\s*(?P<date>{DATE_TOKEN_REGEX})(?:\s+|$)", re.IGNORECASE)

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
BALANCE_LABEL_PATTERN = re.compile(r"(?i)\b(?:bal|balance|closing|available|ledger|running)\b")
AMOUNT_LABEL_PATTERN = re.compile(r"(?i)\b(?:amt|amount|debit|credit|withdraw(?:al)?|deposit)\b")


@dataclass
class ParseContext:
    source_file: str
    bank_name: str | None = None
    account_number: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    dayfirst_preference: bool | None = None


@dataclass(frozen=True)
class NumericCandidate:
    raw: str
    start: int
    end: int
    signed_value: float | None
    plain_value: float | None
    transaction_type: str | None
    currency: str | None
    digits_only: str
    has_decimal: bool
    has_sign_marker: bool
    has_balance_hint: bool
    has_amount_hint: bool


class BankStatementExtractor:
    """Extract structured transaction rows from bank statements across file formats."""

    def __init__(self, credits_positive: bool = True) -> None:
        self.credits_positive = credits_positive
        self.warnings: list[str] = []
        self.pages_failed: list[int] = []
        self.max_abs_amount = 10_000_000.0
        self.max_abs_balance = 100_000_000.0

    def _reset_state(self) -> None:
        """Clear mutable extraction state for a fresh file run."""
        self.warnings = []
        self.pages_failed = []

    def extract_file(self, input_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Extract transactions and parse report from an input statement file."""
        self._reset_state()
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
        normalized = self._filter_suspicious_rows(normalized, context)

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
                        item["amount"] = round(float(delta), 2)
                        item["transaction_type"] = "debit"
                        item["extraction_confidence"] = "low"
                        self.warnings.append(
                            f"Corrected amount via balance delta on {item.get('date')} ({item.get('description', '')[:30]})"
                        )
                    elif any(h in desc for h in credit_hints) and delta > 0:
                        item["amount"] = round(float(delta), 2)
                        item["transaction_type"] = "credit"
                        item["extraction_confidence"] = "low"
                        self.warnings.append(
                            f"Corrected amount via balance delta on {item.get('date')} ({item.get('description', '')[:30]})"
                        )
                    elif abs(delta) <= max(abs(amount_val) * 0.25, 1.0):
                        item["amount"] = round(float(delta), 2)
                        item["transaction_type"] = "credit" if delta >= 0 else "debit"
                        item["extraction_confidence"] = "low"
                        self.warnings.append(
                            f"Adjusted amount to running-balance delta on {item.get('date')}"
                        )

            if balance_val is not None:
                prev_balance = balance_val
            reconciled.append(item)

        return reconciled

    def _filter_suspicious_rows(
        self,
        rows: list[dict[str, Any]],
        context: ParseContext | None = None,
    ) -> list[dict[str, Any]]:
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
            "relationship checking",
            "account service charges",
            "statement of account",
            "service charges and fees",
            "interest-bearing days",
            "average balance",
        )
        period_start = self._safe_date_from_iso(context.period_start) if context else None
        period_end = self._safe_date_from_iso(context.period_end) if context else None

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
            balance_val: float | None = None
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

            row_date = self._safe_date_from_iso(date_val)
            if row_date and period_start and period_end:
                if row_date < period_start - timedelta(days=7) or row_date > period_end + timedelta(days=7):
                    self.warnings.append(
                        f"Dropped row outside detected statement period on {row.get('date')}: {row.get('description', '')[:60]}"
                    )
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
            if alpha == 0 or (alpha < 3 and digits >= alpha + 2):
                self.warnings.append(
                    f"Dropped low-information description row on {row.get('date')}: {row.get('description', '')[:60]}"
                )
                continue
            if any(term in desc for term in ("sample statement", "you have successfully opened", "beginning balance")):
                self.warnings.append(f"Dropped statement-header row on {row.get('date')}: {row.get('description', '')[:60]}")
                continue
            if row.get("extraction_confidence") == "low":
                if "interest credit" in desc and "service charge" in desc:
                    self.warnings.append(f"Dropped OCR-mixed summary row on {row.get('date')}: {row.get('description', '')[:60]}")
                    continue
                if "terminal" in desc:
                    has_ocr_noise = digits >= 4 or "q0" in desc or "00-00" in desc or " pm " in f" {desc} "
                    if has_ocr_noise and (
                        abs(amount) < 1.0 or (balance_val is not None and abs(balance_val) < max(abs(amount), 50.0))
                    ):
                        self.warnings.append(f"Dropped low-confidence terminal detail row on {row.get('date')}: {row.get('description', '')[:60]}")
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
                    if page_text.strip():
                        context = self._extract_statement_metadata(page_text, context)

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
                        if ocr_text.strip():
                            context = self._extract_statement_metadata(ocr_text, context)
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
            prefer_dayfirst = context.dayfirst_preference
            if prefer_dayfirst is None:
                prefer_dayfirst = self._infer_dayfirst_preference(sample_dates)
                if prefer_dayfirst is not None:
                    context.dayfirst_preference = prefer_dayfirst

            previous_date: str | None = None
            for row in cleaned[header_idx + 1 :]:
                parsed = self._build_row_from_columns(row, header_map, context, prefer_dayfirst, previous_date)
                if parsed is not None:
                    parsed["extraction_confidence"] = "high"
                    parsed_rows.append(parsed)
                    previous_date = parsed["date"]
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
        previous_date: str | None = None,
    ) -> dict[str, Any] | None:
        """Build a normalized transaction row from a mapped table row."""
        max_idx = max(header_map.values())
        if len(row) <= max_idx:
            row = row + [""] * (max_idx - len(row) + 1)

        date_val = self._parse_date(
            row[header_map["date"]],
            prefer_dayfirst=prefer_dayfirst,
            context=context,
            previous_date=previous_date,
        )
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
        context = self._extract_statement_metadata(text, context)
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
        line_list = [" ".join((raw or "").strip().split()) for raw in lines if (raw or "").strip()]
        prefer_dayfirst = context.dayfirst_preference
        if prefer_dayfirst is None:
            prefer_dayfirst = self._infer_dayfirst_preference(line_list)
            if prefer_dayfirst is not None:
                context.dayfirst_preference = prefer_dayfirst

        blocks: list[list[str]] = []
        current_block: list[str] = []
        leading_carry = self._clean_description(carry_description or "") or None

        for line in line_list:
            if self._is_noise_line(line):
                if current_block and self._looks_like_section_break(line):
                    blocks.append(current_block)
                    current_block = []
                continue

            if START_DATE_TOKEN_PATTERN.match(line):
                if current_block:
                    blocks.append(current_block)
                current_block = [line]
                continue

            if current_block:
                if self._looks_like_section_break(line):
                    blocks.append(current_block)
                    current_block = []
                    continue
                current_block.append(line)
            elif not self._looks_like_section_break(line):
                leading_carry = self._clean_description(" ".join(part for part in [leading_carry or "", line] if part))

        if current_block:
            blocks.append(current_block)

        rows: list[dict[str, Any]] = []
        previous_date: str | None = None
        previous_balance: float | None = None
        carry_out: str | None = None

        for idx, block in enumerate(blocks):
            parsed, trailing_carry = self._parse_transaction_block(
                block,
                context=context,
                prefer_dayfirst=prefer_dayfirst,
                previous_date=previous_date,
                previous_balance=previous_balance,
                leading_description=leading_carry if idx == 0 else None,
            )
            leading_carry = None

            if parsed is None:
                if trailing_carry and idx == len(blocks) - 1:
                    carry_out = trailing_carry
                continue

            rows.append(parsed)
            previous_date = parsed["date"]
            balance_after = parsed.get("balance_after")
            try:
                if balance_after not in (None, ""):
                    previous_balance = float(balance_after)
            except Exception:
                pass

        if not rows and leading_carry and not carry_out:
            carry_out = leading_carry

        return rows, carry_out

    def _parse_transaction_block(
        self,
        block_lines: list[str],
        context: ParseContext,
        prefer_dayfirst: bool | None,
        previous_date: str | None,
        previous_balance: float | None,
        leading_description: str | None = None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Parse one date-anchored text block into a transaction row."""
        block_text = self._clean_description(" ".join(part for part in block_lines if part))
        if not block_text:
            return None, None

        date_match = START_DATE_TOKEN_PATTERN.match(block_text)
        if not date_match:
            return None, None

        date_token = date_match.group("date")
        parsed_date = self._parse_date(
            date_token,
            prefer_dayfirst=prefer_dayfirst,
            context=context,
            previous_date=previous_date,
        )
        if parsed_date is None:
            return None, None

        suffix = self._normalize_split_decimals(block_text[date_match.end() :].strip())
        desc_part, amount, currency, tx_type, balance = self._parse_suffix_fields(
            suffix,
            previous_balance=previous_balance,
        )
        description = self._clean_description(" ".join(part for part in [leading_description or "", desc_part] if part))

        if amount is None:
            carry_text = self._clean_description(" ".join(part for part in [date_token, suffix] if part))
            return None, carry_text or None

        description = description or "Unknown"
        reference_text = description if description != "Unknown" else suffix

        return {
            "date": parsed_date,
            "description": description,
            "amount": amount,
            "currency": currency,
            "transaction_type": tx_type,
            "reference_number": self._extract_reference(reference_text),
            "balance_after": balance,
            "bank_name": context.bank_name,
            "account_number": context.account_number,
            "statement_period_start": context.period_start,
            "statement_period_end": context.period_end,
            "source_file": context.source_file,
            "extraction_confidence": "medium",
        }, None

    def _parse_suffix_fields(
        self,
        suffix: str,
        previous_balance: float | None = None,
    ) -> tuple[str, float | None, str | None, str | None, float | None]:
        """Split the post-date segment into description, amount and balance candidates."""
        candidates = self._build_numeric_candidates(suffix)
        if not candidates:
            return self._clean_description(suffix), None, None, None, None

        best = self._select_best_numeric_interpretation(candidates, suffix, previous_balance)
        if best is None:
            return self._clean_description(suffix), None, None, None, None

        return (
            self._clean_description(best["description"]) or "Unknown",
            best["amount"],
            best["currency"],
            best["transaction_type"],
            best["balance"],
        )

    def _parse_unstructured_text(self, text: str, context: ParseContext) -> list[dict[str, Any]]:
        """Parse free-form text as last-resort heuristic extraction."""
        line_rows, _ = self._parse_text_lines(text.splitlines(), context, carry_description=None)
        if line_rows:
            for row in line_rows:
                row["extraction_confidence"] = "low"
            return line_rows

        matches = list(DATE_TOKEN_PATTERN.finditer(text))
        if not matches:
            return []

        prefer_dayfirst = context.dayfirst_preference
        if prefer_dayfirst is None:
            prefer_dayfirst = self._infer_dayfirst_preference(text.splitlines())
            if prefer_dayfirst is not None:
                context.dayfirst_preference = prefer_dayfirst

        rows: list[dict[str, Any]] = []
        previous_date: str | None = None
        previous_balance: float | None = None
        for idx, match in enumerate(matches):
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            chunk = self._clean_description(text[match.start() : end])
            parsed, _ = self._parse_transaction_block(
                [chunk],
                context=context,
                prefer_dayfirst=prefer_dayfirst,
                previous_date=previous_date,
                previous_balance=previous_balance,
            )
            if parsed is None:
                continue
            parsed["extraction_confidence"] = "low"
            rows.append(parsed)
            previous_date = parsed["date"]
            balance_after = parsed.get("balance_after")
            try:
                if balance_after not in (None, ""):
                    previous_balance = float(balance_after)
            except Exception:
                pass
        return rows

    def _looks_like_section_break(self, line: str) -> bool:
        """Return True when a line is a structural header/footer, not a row continuation."""
        text = self._clean_description(line).lower()
        if not text:
            return True
        if any(pat.search(text) for pat in NOISE_PATTERNS):
            return True
        if len(text) > 80 and sum(ch.isdigit() for ch in text) > sum(ch.isalpha() for ch in text):
            return True
        return False

    def _normalize_split_decimals(self, text: str) -> str:
        """Repair OCR cases where decimal points are lost and cents become a separate token."""
        parts = text.split()
        if len(parts) < 2:
            return text

        normalized: list[str] = []
        idx = 0
        while idx < len(parts):
            current = parts[idx]
            nxt = parts[idx + 1] if idx + 1 < len(parts) else None
            prev = parts[idx - 1] if idx > 0 else None
            next_after = parts[idx + 2] if idx + 2 < len(parts) else None

            if (
                nxt is not None
                and re.fullmatch(r"\d{1,3}", current)
                and re.fullmatch(r"\d{2}", nxt)
            ):
                previous_has_decimal = bool(prev and re.fullmatch(r"\d[\d,]*\.\d{2}", prev))
                next_has_decimal = bool(next_after and re.fullmatch(r"\d[\d,]*\.\d{2}", next_after))
                if previous_has_decimal or next_has_decimal or next_after is None:
                    normalized.append(f"{current}.{nxt}")
                    idx += 2
                    continue

            normalized.append(current)
            idx += 1

        return " ".join(normalized)

    def _build_numeric_candidates(self, suffix: str) -> list[NumericCandidate]:
        """Parse all numeric tokens found in a text suffix for later scoring."""
        candidates: list[NumericCandidate] = []
        for match in NUMBER_TOKEN_PATTERN.finditer(suffix):
            raw = match.group(0).strip()
            left_context = suffix[: match.start()].strip()
            prefix_window = suffix[max(0, match.start() - 18) : match.start()]
            signed_value, tx_type, currency = self._parse_amount(raw, left_context)
            plain_value, plain_currency = self._parse_plain_number(raw)
            digits_only = re.sub(r"\D", "", raw)
            candidates.append(
                NumericCandidate(
                    raw=raw,
                    start=match.start(),
                    end=match.end(),
                    signed_value=signed_value,
                    plain_value=plain_value,
                    transaction_type=tx_type,
                    currency=currency or plain_currency,
                    digits_only=digits_only,
                    has_decimal=("." in raw or "," in raw),
                    has_sign_marker=bool(re.search(r"[-+()]|\b(?:CR|DR)\b", raw, re.IGNORECASE)),
                    has_balance_hint=bool(BALANCE_LABEL_PATTERN.search(prefix_window)),
                    has_amount_hint=bool(AMOUNT_LABEL_PATTERN.search(prefix_window)),
                )
            )
        return candidates

    def _select_best_numeric_interpretation(
        self,
        candidates: list[NumericCandidate],
        suffix: str,
        previous_balance: float | None,
    ) -> dict[str, Any] | None:
        """Choose the most plausible amount/balance interpretation from numeric tokens."""
        if not candidates:
            return None

        indexed = list(enumerate(candidates))
        tail = indexed[-5:]
        options: list[dict[str, Any]] = []

        for idx, cand in tail:
            if cand.signed_value is None:
                continue
            options.append(
                self._build_numeric_option(
                    suffix=suffix,
                    candidates=candidates,
                    used_indexes=[idx],
                    amount=cand.signed_value,
                    tx_type=cand.transaction_type or ("credit" if cand.signed_value >= 0 else "debit"),
                    balance=None,
                )
            )

        for pos, (amount_idx, amount_cand) in enumerate(tail):
            if amount_cand.signed_value is None:
                continue
            for balance_idx, balance_cand in tail[pos + 1 :]:
                if balance_cand.plain_value is None:
                    continue
                options.append(
                    self._build_numeric_option(
                        suffix=suffix,
                        candidates=candidates,
                        used_indexes=[amount_idx, balance_idx],
                        amount=amount_cand.signed_value,
                        tx_type=amount_cand.transaction_type or ("credit" if amount_cand.signed_value >= 0 else "debit"),
                        balance=balance_cand.plain_value,
                    )
                )

        for pos, (debit_idx, debit_cand) in enumerate(tail):
            if debit_cand.plain_value is None:
                continue
            for credit_pos, (credit_idx, credit_cand) in enumerate(tail[pos + 1 :], start=pos + 1):
                if credit_cand.plain_value is None:
                    continue
                for balance_idx, balance_cand in tail[credit_pos + 1 :]:
                    if balance_cand.plain_value is None:
                        continue
                    debit = abs(debit_cand.plain_value)
                    credit = abs(credit_cand.plain_value)
                    amount = credit - debit
                    options.append(
                        self._build_numeric_option(
                            suffix=suffix,
                            candidates=candidates,
                            used_indexes=[debit_idx, credit_idx, balance_idx],
                            amount=amount,
                            tx_type="credit" if amount >= 0 else "debit",
                            balance=balance_cand.plain_value,
                        )
                    )

        if not options:
            return None

        best_option: dict[str, Any] | None = None
        best_score: float | None = None
        for option in options:
            score = self._score_numeric_interpretation(option, candidates, suffix, previous_balance)
            option["score"] = score
            if best_score is None or score < best_score:
                best_score = score
                best_option = option
        return best_option

    def _build_numeric_option(
        self,
        suffix: str,
        candidates: list[NumericCandidate],
        used_indexes: list[int],
        amount: float,
        tx_type: str,
        balance: float | None,
    ) -> dict[str, Any]:
        """Materialize one amount/balance interpretation candidate."""
        used = sorted(used_indexes)
        first_start = min(candidates[idx].start for idx in used)
        description = suffix[:first_start].strip()
        currencies = [candidates[idx].currency for idx in used if candidates[idx].currency]
        return {
            "used_indexes": used,
            "description": description,
            "amount": amount,
            "transaction_type": tx_type,
            "balance": balance,
            "currency": currencies[0] if currencies else None,
        }

    def _score_numeric_interpretation(
        self,
        option: dict[str, Any],
        candidates: list[NumericCandidate],
        suffix: str,
        previous_balance: float | None,
    ) -> float:
        """Score one numeric interpretation; lower is better."""
        used = option["used_indexes"]
        amount = float(option["amount"])
        balance = option["balance"]
        description = self._clean_description(option["description"])

        score = 0.0
        last_idx = len(candidates) - 1
        if used[-1] != last_idx:
            score += 6.0
        if balance is not None and len(used) >= 2 and used[-2] != used[-1] - 1:
            score += 1.5
        if len(used) == 3 and (used[0] != used[1] - 1 or used[1] != used[2] - 1):
            score += 1.0
        if balance is None and len(candidates) >= 2:
            trailing_pair = candidates[-2:]
            if all(cand.has_decimal for cand in trailing_pair):
                score += 4.0

        balance_candidate = candidates[used[-1]]
        if balance is not None and balance_candidate.has_balance_hint:
            score -= 1.5
        if balance is not None and len(used) >= 2 and all(candidates[idx].has_decimal for idx in used[-2:]):
            score -= 1.0

        amount_indexes = used[:-1] if balance is not None else used
        for idx in amount_indexes:
            cand = candidates[idx]
            if self._looks_like_reference_token(cand):
                score += 3.5
            if not cand.has_decimal and len(cand.digits_only) >= 5:
                score += 2.5
            if cand.has_amount_hint:
                score -= 0.5

        if previous_balance is not None:
            if balance is None:
                score += 1.5
            else:
                mismatch = abs((previous_balance + amount) - balance)
                score += min(mismatch, 5000.0) / 25.0
                if mismatch <= 0.02:
                    score -= 1.0

        if balance is not None and abs(balance) > self.max_abs_balance:
            score += 100.0
        if abs(amount) > self.max_abs_amount:
            score += 100.0

        alpha = sum(ch.isalpha() for ch in description)
        digits = sum(ch.isdigit() for ch in description)
        if alpha == 0:
            score += 4.0
        elif alpha < 3 and digits >= alpha:
            score += 2.5
        if not description:
            score += 1.5

        inferred_credit = self._is_credit_description(description)
        if inferred_credit and amount < 0:
            score += 1.0
        if not inferred_credit and amount > 0 and not any(candidates[idx].has_sign_marker for idx in amount_indexes):
            score += 0.75

        trailing_text = suffix[candidates[used[-1]].end :].strip()
        if trailing_text:
            score += 1.0

        return score

    @staticmethod
    def _looks_like_reference_token(candidate: NumericCandidate) -> bool:
        """Heuristic for check/reference IDs embedded before the true amount zone."""
        return (
            not candidate.has_decimal
            and not candidate.has_sign_marker
            and len(candidate.digits_only) >= 4
            and not candidate.has_balance_hint
            and not candidate.has_amount_hint
        )

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
            previous_date: str | None = None
            for row in matrix[header_idx + 1 :]:
                parsed = self._build_row_from_columns(row, header_map, context, previous_date=previous_date)
                if parsed:
                    parsed["extraction_confidence"] = "high"
                    rows.append(parsed)
                    previous_date = parsed["date"]

        if rows:
            return rows

        return self._parse_text_payload(soup.get_text("\n"), context)

    def _extract_from_csv(self, input_path: Path, context: ParseContext) -> list[dict[str, Any]]:
        """Extract rows from CSV with auto header normalization."""
        context = self._extract_statement_metadata(
            input_path.read_text(encoding="utf-8", errors="ignore"),
            context,
        )
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
            context = self._extract_statement_metadata(df.fillna("").to_string(index=False), context)
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
        prev_date: str | None = None
        if context.dayfirst_preference is None:
            sample_tokens = [str(v) for v in df[col_map["date"]].head(25).tolist()]
            inferred = self._infer_dayfirst_preference(sample_tokens)
            if inferred is not None:
                context.dayfirst_preference = inferred
        for _, rec in df.iterrows():
            date_val = self._parse_date(
                str(rec.get(col_map["date"], "")),
                context=context,
                previous_date=prev_date,
            )
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
            prev_date = date_val
        return rows

    def _extract_statement_metadata(self, text: str, context: ParseContext) -> ParseContext:
        """Extract statement-level metadata for enrichment fields."""
        if context.dayfirst_preference is None:
            inferred = self._infer_dayfirst_preference(text.splitlines())
            if inferred is not None:
                context.dayfirst_preference = inferred
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
                cleaned = " ".join((line or "").split())
                if not cleaned:
                    continue
                lowered = cleaned.lower()
                m = PERIOD_PATTERN.search(cleaned)
                date_tokens = DATE_TOKEN_PATTERN.findall(cleaned)
                if m:
                    candidate_tokens = [m.group(1).strip(), m.group(2).strip()]
                elif len(date_tokens) >= 2 and ("period" in lowered or ("from" in lowered and "to" in lowered)):
                    candidate_tokens = [date_tokens[0], date_tokens[1]]
                else:
                    continue

                start = self._parse_date(candidate_tokens[0], context=context)
                end = self._parse_date(candidate_tokens[1], context=context, previous_date=start)
                start_dt, end_dt = self._normalize_period_bounds(start, end)
                if start_dt:
                    context.period_start = start_dt.isoformat()
                if end_dt:
                    context.period_end = end_dt.isoformat()
                if context.period_start and context.period_end:
                    break
        return context

    def _parse_date(
        self,
        token: str,
        prefer_dayfirst: bool | None = None,
        context: ParseContext | None = None,
        previous_date: str | None = None,
    ) -> str | None:
        """Parse many date variants into ISO-8601 date strings."""
        value = " ".join((token or "").replace(",", " ").split())
        if not value:
            return None

        inferred_dayfirst = prefer_dayfirst
        if inferred_dayfirst is None and context is not None:
            inferred_dayfirst = context.dayfirst_preference

        # Handle year-first formats explicitly to avoid dayfirst ambiguity.
        if re.match(r"^\d{4}[\/\-.]\d{1,2}[\/\-.]\d{1,2}$", value):
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.date().isoformat()
                except ValueError:
                    continue

        if self._is_partial_date_token(value):
            partial = self._select_best_partial_date(value, inferred_dayfirst, context, previous_date)
            return partial.isoformat() if partial else None

        parse_orders = [inferred_dayfirst, not inferred_dayfirst] if inferred_dayfirst is not None else [True, False]
        for day_first in parse_orders:
            try:
                dt = date_parser.parse(value, dayfirst=day_first, fuzzy=False)
                if dt.year < 1900:
                    continue
                return dt.date().isoformat()
            except (ValueError, OverflowError):
                continue

        return None

    def _select_best_partial_date(
        self,
        token: str,
        prefer_dayfirst: bool | None,
        context: ParseContext | None,
        previous_date: str | None,
    ) -> date | None:
        """Resolve a partial date token to the most plausible year."""
        candidates: list[date] = []
        years = self._candidate_years(context)
        prev_dt = self._safe_date_from_iso(previous_date)
        start_dt = self._safe_date_from_iso(context.period_start) if context else None
        end_dt = self._safe_date_from_iso(context.period_end) if context else None

        if re.match(r"^\d{1,2}[\/\-.]\d{1,2}$", token):
            sep = "/" if "/" in token else ("-" if "-" in token else ".")
            left, right = [int(p) for p in token.split(sep)]
            dayfirst = prefer_dayfirst
            if left > 12 and right <= 12:
                dayfirst = True
            elif right > 12 and left <= 12:
                dayfirst = False
            elif dayfirst is None:
                dayfirst = True if sep == "." else False

            if dayfirst is True:
                ordered_formats = [f"%d{sep}%m"]
            elif dayfirst is False:
                ordered_formats = [f"%m{sep}%d"]
            else:
                ordered_formats = [f"%d{sep}%m", f"%m{sep}%d"]
            for year in years:
                for fmt in ordered_formats:
                    try:
                        candidates.append(datetime.strptime(f"{token} {year}", f"{fmt} %Y").date())
                    except ValueError:
                        continue
        else:
            formats = []
            if re.match(r"^\d{1,2}\s+[A-Za-z]{3,9}$", token):
                formats = ["%d %b", "%d %B"]
            elif re.match(r"^[A-Za-z]{3,9}\s+\d{1,2}$", token):
                formats = ["%b %d", "%B %d"]

            normalized = token.replace(",", "")
            for year in years:
                for fmt in formats:
                    try:
                        candidates.append(datetime.strptime(f"{normalized} {year}", f"{fmt} %Y").date())
                    except ValueError:
                        continue

        if not candidates:
            return None

        unique_candidates = list(dict.fromkeys(candidates))
        today = datetime.now().date()

        def score(candidate: date) -> float:
            value = 0.0
            if start_dt and end_dt:
                if start_dt <= candidate <= end_dt:
                    value -= 5.0
                elif candidate < start_dt:
                    value += min((start_dt - candidate).days, 900) / 20.0
                else:
                    value += min((candidate - end_dt).days, 900) / 20.0

            if prev_dt:
                delta = (candidate - prev_dt).days
                if delta < -7:
                    value += 6.0 + abs(delta) / 15.0
                else:
                    value += abs(delta) / 180.0

            future_days = (candidate - today).days
            if future_days > 45:
                value += 4.0 + future_days / 60.0

            value += abs((candidate - today).days) / 5000.0
            return value

        return min(unique_candidates, key=score)

    @staticmethod
    def _is_partial_date_token(value: str) -> bool:
        """Return True for dates lacking an explicit year component."""
        return bool(
            re.match(r"^\d{1,2}[\/\-.]\d{1,2}$", value)
            or re.match(r"^\d{1,2}\s+[A-Za-z]{3,9}$", value)
            or re.match(r"^[A-Za-z]{3,9}\s+\d{1,2}$", value)
        )

    def _candidate_years(self, context: ParseContext | None) -> list[int]:
        """Build a small plausible year set for resolving partial dates."""
        today = datetime.now().date()
        years = {today.year - 1, today.year, today.year + 1}
        if context is not None:
            for token in (context.period_start, context.period_end):
                dt = self._safe_date_from_iso(token)
                if dt is None:
                    continue
                years.update({dt.year - 1, dt.year, dt.year + 1})
        return sorted(years)

    @staticmethod
    def _safe_date_from_iso(value: str | None) -> date | None:
        """Convert an ISO date string to a date object when possible."""
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    def _normalize_period_bounds(self, start: str | None, end: str | None) -> tuple[date | None, date | None]:
        """Normalize statement period bounds, including common year-rollover cases."""
        start_dt = self._safe_date_from_iso(start)
        end_dt = self._safe_date_from_iso(end)
        if start_dt and end_dt and start_dt > end_dt:
            if start_dt.month >= 11 and end_dt.month <= 2:
                try:
                    end_dt = end_dt.replace(year=end_dt.year + 1)
                except ValueError:
                    pass
            elif end_dt.month >= 11 and start_dt.month <= 2:
                try:
                    start_dt = start_dt.replace(year=start_dt.year - 1)
                except ValueError:
                    pass
            if start_dt and end_dt and start_dt > end_dt:
                start_dt, end_dt = end_dt, start_dt
        return start_dt, end_dt

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
        return any(pat.search(cleaned) for pat in NOISE_PATTERNS)

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

        for numeric_key in ("amount", "balance_after"):
            value = normalized.get(numeric_key)
            if value in (None, ""):
                continue
            try:
                normalized[numeric_key] = round(float(value), 2)
            except Exception:
                normalized[numeric_key] = None

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
