# datasheet-vectorizer

Extracts structured parametric data from Microchip MCU datasheet PDFs.
Input: a PDF + a part number. Output: JSON with up to 59 canonical fields
(Program_Memory_KB, RAM_KB, Pincount, peripheral counts, voltage range,
temp range, etc.).

No ML, no LLM. Pure regex + table parsing + a lookup dictionary.

## What's in this repo

- [datasheet_vectorizer/](datasheet_vectorizer/) — the extraction package
- [scripts/](scripts/) — discovery, validation, and operational scripts
- [docs/](docs/) — architecture, accuracy methodology, handoff notes
- Top-level JSONs/CSV — current state of the catalog (2,253 Microchip parts)

## Quick start

```bash
pip install pdfplumber openpyxl

# Vectorize one part from a PDF you already have
python -c "from datasheet_vectorizer import vectorize; \
  print(vectorize.vectorize('path/to/datasheet.pdf', 'PIC18F46Q10', max_pages=15)['fields'])"
```

## Where the catalog data comes from

PDFs are NOT in this repo (~2.4 GB, and they're Microchip's content). To
reconstruct the local PDF cache:

```bash
# 1. (One-time) Discover datasheet URLs for the catalog. The discovery scripts
#    use the Microchip MCP server's product-document search. The URLs that
#    were found are already saved to family_datasheets.json — you only need
#    to re-discover if you're adding new parts.

# 2. Download all PDFs whose URLs are in family_datasheets.json:
python scripts/_download_datasheets.py
# Creates a 'datasheets/' directory with the PDFs (about 230 unique files).

# 3. Build the per-part-to-PDF mapping:
python scripts/_build_part_to_pdf.py

# 4. Vectorize all parts:
python scripts/_vectorize_all.py
# Writes vectorized_all.json. Takes ~10 min cold, ~2 min warm.

# 5. Audit which parts have a PDF that actually contains them:
python scripts/_count_wrong_pdfs_v2.py

# 6. Null-out the contaminated outputs for parts whose PDF doesn't contain them:
python scripts/_null_wrong_pdf_parts.py
```

## Current state (as of 2026-05-04)

- **2,253 parts** vectorized (out of 2,311 in the source catalog)
- **2,022 parts (89.7%)** have a correctly-mapped PDF; their outputs are real
- **231 parts (10.3%)** have no usable datasheet — they're flagged with `wrong_pdf: true` and have empty fields rather than contaminated defaults
- Per-cell accuracy on correctly-mapped parts: **~80%** (measured by held-out blind verification)
- Outputs: [vectorized_all.json](vectorized_all.json), [vectorized_all.csv](vectorized_all.csv) (59 columns)

See [docs/ACCURACY.md](docs/ACCURACY.md) for the full methodology.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how the pipeline works
- [docs/ACCURACY.md](docs/ACCURACY.md) — what we measured and how
- [docs/HANDOFF.md](docs/HANDOFF.md) — known issues and next steps

## License

Code is yours to license as you wish. Datasheet PDFs (not redistributed in this
repo) belong to Microchip Technology Inc.
