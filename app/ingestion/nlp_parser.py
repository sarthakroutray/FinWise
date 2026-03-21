import re
from typing import List, Optional

import pandas as pd
import spacy
from dateutil import parser as dateutil_parser

from app.core.config import config


class TransactionNLPParser:
    """Converts unstructured OCR/text pages into structured transaction rows."""

    def __init__(self) -> None:
        self.nlp = spacy.load(config.NER_MODEL)
        # Date patterns: DD/MM/YYYY, MM-DD-YYYY, YYYY-MM-DD, written months
        self._date_patterns = [
            re.compile(r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b"),
            re.compile(r"\b(\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})\b"),
            re.compile(
                r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
                r"\s+\d{2,4})\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
                r"\s+\d{1,2},?\s+\d{2,4})\b",
                re.IGNORECASE,
            ),
        ]
        # Amount patterns: optional currency symbol, commas, decimals, CR/DR suffix
        self._amount_pattern = re.compile(
            r"(?:[$€£₹]\s?)?([\d,]+\.\d{2})\s*(?:(CR|DR))?", re.IGNORECASE
        )
        # Balance pattern
        self._balance_pattern = re.compile(
            r"(?:bal(?:ance)?\.?\s*[:=]?\s*)(?:[$€£₹]\s?)?([\d,]+\.\d{2})", re.IGNORECASE
        )

    def _extract_dates(self, text: str) -> List[str]:
        """Extract and normalize all dates to YYYY-MM-DD."""
        raw_dates: List[str] = []
        for pat in self._date_patterns:
            raw_dates.extend(pat.findall(text))
        normalized: List[str] = []
        for raw in raw_dates:
            try:
                dt = dateutil_parser.parse(raw, dayfirst=True)
                normalized.append(dt.strftime("%Y-%m-%d"))
            except (ValueError, OverflowError):
                continue
        return normalized

    def _extract_amounts(self, text: str) -> List[float]:
        """Extract signed amounts; CR = positive, DR = negative; default negative (spend)."""
        results: List[float] = []
        for match in self._amount_pattern.finditer(text):
            value = float(match.group(1).replace(",", ""))
            suffix = (match.group(2) or "").upper()
            if suffix == "CR":
                results.append(value)
            elif suffix == "DR":
                results.append(-value)
            else:
                results.append(-value)  # default to debit
        return results

    def _extract_balances(self, text: str) -> List[float]:
        """Extract balance figures from text."""
        results: List[float] = []
        for match in self._balance_pattern.finditer(text):
            results.append(float(match.group(1).replace(",", "")))
        return results

    def _extract_descriptions(self, doc: spacy.tokens.Doc) -> List[str]:
        """Use spaCy NER + POS to extract merchant/transaction descriptions."""
        descriptions: List[str] = []
        # Collect ORG, PRODUCT, GPE entities
        entity_texts = [ent.text for ent in doc.ents if ent.label_ in ("ORG", "PRODUCT", "GPE")]
        if entity_texts:
            descriptions.extend(entity_texts)
        else:
            # Fallback: noun chunks
            for chunk in doc.noun_chunks:
                if len(chunk.text.strip()) > 2:
                    descriptions.append(chunk.text.strip())
        return descriptions

    def _align_rows(
        self,
        dates: List[str],
        amounts: List[float],
        descriptions: List[str],
        balances: List[float],
    ) -> List[dict]:
        """Zip aligned lists into row dicts, padding misalignment with None."""
        max_len = max(len(dates), len(amounts), 1)
        # Pad shorter lists
        def pad(lst: list, length: int) -> list:
            return lst + [None] * (length - len(lst))

        dates = pad(dates, max_len)
        amounts = pad(amounts, max_len)
        descriptions = pad(descriptions, max_len)
        balances = pad(balances, max_len)
        rows: List[dict] = []
        for i in range(max_len):
            # Drop rows missing both date and amount
            if dates[i] is None and amounts[i] is None:
                continue
            rows.append({
                "date": dates[i],
                "description": descriptions[i] if i < len(descriptions) else None,
                "amount": amounts[i],
                "balance": balances[i] if i < len(balances) else None,
            })
        return rows

    def parse_pages(self, pages: List[str]) -> pd.DataFrame:
        """Parse page texts into a structured DataFrame."""
        full_text = "\n".join(pages)
        # Split into transaction blocks anchored by date patterns
        block_pattern = re.compile(
            r"(?=\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b"
            r"|\b\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}\b"
            r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))",
            re.IGNORECASE,
        )
        blocks = block_pattern.split(full_text)
        # Re-attach the date anchor to each block
        positions = [m.start() for m in block_pattern.finditer(full_text)]
        all_rows: List[dict] = []
        for idx, pos in enumerate(positions):
            end = positions[idx + 1] if idx + 1 < len(positions) else len(full_text)
            block = full_text[pos:end].strip()
            if not block:
                continue
            dates = self._extract_dates(block)
            amounts = self._extract_amounts(block)
            balances = self._extract_balances(block)
            doc = self.nlp(block)
            descriptions = self._extract_descriptions(doc)
            rows = self._align_rows(dates, amounts, descriptions, balances)
            all_rows.extend(rows)
        if not all_rows:
            return pd.DataFrame(columns=["date", "description", "amount", "balance"])
        df = pd.DataFrame(all_rows)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
        df = df.dropna(subset=["date", "amount"])
        df = df.drop_duplicates().sort_values("date").reset_index(drop=True)
        return df
