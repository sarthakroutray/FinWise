import re
from typing import List
from pathlib import Path

import pdfplumber
import pytesseract
import cv2
import numpy as np
from pdf2image import convert_from_path

from app.core.config import config


class BankStatementPDFExtractor:
    """Extracts text from bank statement PDFs via native parsing or OCR fallback."""

    def _is_text_based(self, path: str) -> bool:
        """Return True if avg chars/page > 50 (native text present)."""
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                return False
            total_chars = sum(len(page.extract_text() or "") for page in pdf.pages)
            return (total_chars / len(pdf.pages)) > 50

    def _extract_text_native(self, path: str) -> List[str]:
        """Extract text per page using pdfplumber."""
        pages: List[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
        return pages

    def _extract_text_ocr(self, path: str) -> List[str]:
        """Convert PDF to images, preprocess with OpenCV, run Tesseract OCR."""
        images = convert_from_path(path, dpi=config.OCR_DPI)
        pages: List[str] = []
        for img in images:
            # Convert PIL Image to OpenCV BGR array
            cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            # Grayscale conversion
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            # Otsu thresholding
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # Denoise
            denoised = cv2.fastNlMeansDenoising(thresh, h=30)
            # Run Tesseract
            text = pytesseract.image_to_string(denoised, lang=config.OCR_LANG)
            pages.append(text)
        return pages

    def _clean_text(self, raw: str) -> str:
        """Remove headers/footers, normalize whitespace, strip non-UTF8."""
        # Remove page numbers like "Page 1 of 5" or standalone digits at line boundaries
        cleaned = re.sub(r"(?i)page\s+\d+\s*(of\s+\d+)?", "", raw)
        cleaned = re.sub(r"(?m)^\s*\d{1,3}\s*$", "", cleaned)
        # Remove repeated boilerplate / bank logo text (lines appearing identically)
        lines = cleaned.split("\n")
        seen_counts: dict[str, int] = {}
        for line in lines:
            stripped = line.strip()
            if stripped:
                seen_counts[stripped] = seen_counts.get(stripped, 0) + 1
        # Remove lines that appear more than 2 times (likely headers/footers)
        filtered = [l for l in lines if l.strip() == "" or seen_counts.get(l.strip(), 0) <= 2]
        cleaned = "\n".join(filtered)
        # Fix hyphenation at line breaks
        cleaned = re.sub(r"-\n\s*", "", cleaned)
        # Normalize whitespace
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        # Strip non-UTF8 characters
        cleaned = cleaned.encode("utf-8", errors="ignore").decode("utf-8")
        return cleaned.strip()

    def extract(self, path: str) -> List[str]:
        """Auto-select native vs OCR strategy, return cleaned page texts."""
        if config.PDF_PARSER == "ocr":
            raw_pages = self._extract_text_ocr(path)
        elif config.PDF_PARSER == "native":
            raw_pages = self._extract_text_native(path)
        else:
            # Auto mode: try native first, fallback to OCR
            if self._is_text_based(path):
                raw_pages = self._extract_text_native(path)
            else:
                raw_pages = self._extract_text_ocr(path)
        return [self._clean_text(page) for page in raw_pages]
