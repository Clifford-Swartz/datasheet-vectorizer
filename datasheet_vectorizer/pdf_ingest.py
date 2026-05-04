"""
PDF ingest module — extract text and tables from datasheet PDFs.
Caches results so we don't re-parse the same PDF twice.
"""

import os
import json
import hashlib
import subprocess
from pathlib import Path

import pdfplumber

CACHE_DIR = Path(__file__).parent.parent / ".pdf_cache"
CACHE_DIR.mkdir(exist_ok=True)


def _pdf_hash(pdf_path):
    """Hash the file contents for cache invalidation."""
    h = hashlib.md5()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def _cache_path(pdf_path, kind):
    name = Path(pdf_path).stem
    return CACHE_DIR / f"{name}_{_pdf_hash(pdf_path)}_{kind}.json"


def extract_layout_text(pdf_path, max_pages=20):
    """
    Extract text with layout preserved using pdfplumber.
    Uses extract_text(layout=True) which respects character positions.
    Returns list of pages, each is a string.
    Cached to disk.
    """
    cache = _cache_path(pdf_path, f"layout_{max_pages}p")
    if cache.exists():
        with open(cache, "r", encoding="utf-8") as f:
            return json.load(f)

    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:max_pages]:
            try:
                # layout=True preserves spatial positions
                text = page.extract_text(layout=True) or ""
            except Exception:
                text = ""
            pages.append(text)

    with open(cache, "w", encoding="utf-8") as f:
        json.dump(pages, f)
    return pages


def extract_plain_text(pdf_path, max_pages=20):
    """Plain text extraction (no layout). Cached."""
    cache = _cache_path(pdf_path, f"plain_{max_pages}p")
    if cache.exists():
        with open(cache, "r", encoding="utf-8") as f:
            return json.load(f)

    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:max_pages]:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            pages.append(text)

    with open(cache, "w", encoding="utf-8") as f:
        json.dump(pages, f)
    return pages


def extract_tables_pdfplumber(pdf_path, max_pages=20):
    """
    Use pdfplumber to extract tables with structure preserved.
    Returns list of (page_num, table_data) where table_data is a 2D list.
    Cached.
    """
    cache = _cache_path(pdf_path, f"tables_{max_pages}p")
    if cache.exists():
        with open(cache, "r", encoding="utf-8") as f:
            return json.load(f)

    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages[:max_pages], start=1):
            try:
                page_tables = page.extract_tables()
                for table in page_tables:
                    # Filter empty/tiny tables
                    if table and len(table) > 1:
                        tables.append({"page": page_num, "data": table})
            except Exception:
                continue

    with open(cache, "w", encoding="utf-8") as f:
        json.dump(tables, f)
    return tables


def extract_text_with_positions(pdf_path, page_num):
    """
    Get characters with bounding boxes for one page.
    Useful for column-aware table parsing.
    """
    with pdfplumber.open(pdf_path) as pdf:
        if page_num > len(pdf.pages):
            return []
        page = pdf.pages[page_num - 1]
        return page.chars  # list of {text, x0, x1, top, bottom, ...}


def search_pages(pdf_path, keywords, max_pages=20):
    """Find page numbers containing any of the keywords."""
    pages = extract_plain_text(pdf_path, max_pages)
    matches = []
    for i, text in enumerate(pages, start=1):
        text_lower = text.lower()
        for kw in keywords:
            if kw.lower() in text_lower:
                matches.append((i, kw))
                break
    return matches


if __name__ == "__main__":
    import sys
    pdf = sys.argv[1] if len(sys.argv) > 1 else "PIC32CMGV_datasheet.pdf"

    print(f"Testing on: {pdf}")
    print(f"\nFirst 500 chars of page 1 (layout):")
    pages = extract_layout_text(pdf, max_pages=2)
    print(pages[0][:500])

    print(f"\n\nSearching for 'Configuration Summary':")
    matches = search_pages(pdf, ["Configuration Summary", "Family Features", "Peripheral Overview"])
    print(matches)

    print(f"\n\nTables found via pdfplumber:")
    tables = extract_tables_pdfplumber(pdf, max_pages=15)
    for t in tables[:5]:
        print(f"  Page {t['page']}: {len(t['data'])} rows x {len(t['data'][0]) if t['data'] else 0} cols")
        if t['data']:
            print(f"    Header: {t['data'][0][:5]}")
