"""Improved wrong-PDF audit with fuzzy matching for revision suffixes and formatting variants.

A part is considered "in PDF" if any of these match the PDF text:
  1. Exact part name
  2. Part name with trailing single rev letter stripped
  3. Part name with optional dashes/spaces inserted between letter/digit boundaries
     (e.g. "PIC32CM5164JH01032" -> "PIC32CM 5164 JH01 032" or "PIC32CM JH01")
  4. The non-numeric "core" of the part name (helps with "ATSAML10" vs "SAM L10")
"""
import json
import os
import re
import sys
sys.path.insert(0, ".")
from datasheet_vectorizer import pdf_ingest

vec = json.load(open("vectorized_all.json", encoding="utf-8-sig"))


def variants(part):
    """Return a list of strings to try matching against PDF text.
    Compose all sensible transformations: strip AT prefix, strip rev letter,
    strip both, plus spaced/hyphenated forms."""
    p = part.upper()
    base_forms = {p}

    # Strip trailing single revision letter
    if len(p) >= 4 and p[-1].isalpha() and p[-2].isdigit():
        base_forms.add(p[:-1])

    # Strip AT prefix
    if p.startswith("AT") and len(p) > 2:
        base_forms.add(p[2:])
        # Combined: strip AT AND trailing rev letter
        no_at = p[2:]
        if len(no_at) >= 4 and no_at[-1].isalpha() and no_at[-2].isdigit():
            base_forms.add(no_at[:-1])

    out = []
    for form in base_forms:
        out.append(form)
        # Spaced
        spaced = re.sub(r"([A-Z]+)(\d+)", r"\1 \2", form)
        spaced = re.sub(r"(\d+)([A-Z]+)", r"\1 \2", spaced)
        if spaced != form:
            out.append(spaced)
        # Hyphenated
        hyphenated = re.sub(r"([A-Z]+)(\d+)", r"\1-\2", form)
        if hyphenated != form:
            out.append(hyphenated)
    return out


by_pdf = {}
for part, info in vec.items():
    pdf = info.get("pdf")
    if not pdf:
        continue
    by_pdf.setdefault(pdf, []).append(part)

print(f"Unique PDFs: {len(by_pdf)}")

wrong_pdf_parts = []
right_pdf_parts = []

for pdf, parts in by_pdf.items():
    if not os.path.exists(pdf):
        wrong_pdf_parts.extend(parts)
        continue
    try:
        text = pdf_ingest.extract_plain_text(pdf, max_pages=20)
        if isinstance(text, list):
            text = "\n".join(str(t) for t in text)
        text_up = text.upper()
    except Exception:
        wrong_pdf_parts.extend(parts)
        continue

    for part in parts:
        found = False
        for variant in variants(part):
            if variant in text_up:
                found = True
                break
        if found:
            right_pdf_parts.append(part)
        else:
            wrong_pdf_parts.append(part)

total = len(right_pdf_parts) + len(wrong_pdf_parts)
print()
print("=" * 70)
print("CATALOG-WIDE WRONG-PDF AUDIT (fuzzy v2)")
print("=" * 70)
print(f"Total parts:                {total}")
print(f"Part appears in its PDF:    {len(right_pdf_parts)} ({100*len(right_pdf_parts)/total:.1f}%)")
print(f"Part NOT in its PDF:        {len(wrong_pdf_parts)} ({100*len(wrong_pdf_parts)/total:.1f}%)")
print()

from collections import Counter
pdf_to_wrong = Counter()
for p in wrong_pdf_parts:
    pdf_to_wrong[vec[p]["pdf"]] += 1
print("Top 15 wrong-PDF buckets:")
for pdf, n in sorted(pdf_to_wrong.items(), key=lambda x: -x[1])[:15]:
    bn = pdf.replace("datasheets\\", "")[:60]
    print(f"  {n:>4}  {bn}")

with open("wrong_pdf_audit.json", "w") as f:
    json.dump({
        "total": total,
        "right_pdf_count": len(right_pdf_parts),
        "wrong_pdf_count": len(wrong_pdf_parts),
        "wrong_pdf_parts": wrong_pdf_parts,
        "right_pdf_parts": right_pdf_parts,
    }, f, indent=2)
print("\nWrote wrong_pdf_audit.json")
