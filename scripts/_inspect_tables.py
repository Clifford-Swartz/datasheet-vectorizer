"""Show what the table extractor currently sees in PIC18/PIC24/dsPIC datasheets."""
import sys
sys.path.insert(0, ".")
from datasheet_vectorizer import pdf_ingest, table_extractor

pdf = sys.argv[1]
target = sys.argv[2] if len(sys.argv) > 2 else None

print(f"=== {pdf} ===\n")

raw = pdf_ingest.extract_tables_pdfplumber(pdf, max_pages=15)
print(f"Total raw tables in first 15 pages: {len(raw)}\n")

# What the device-features detector picks up
candidates = table_extractor.find_device_features_tables(pdf, max_pages=15)
print(f"Device-features candidates: {len(candidates)}")
for i, t in enumerate(candidates):
    print(f"\n  [Candidate {i}]  page={t['page']} orient_orig={t['orientation_original']}")
    print(f"  Header: {t['header']}")
    print(f"  Row count: {len(t['rows'])}")
    for r in t["rows"][:3]:
        print(f"    {r}")

# Now show the first 3 raw tables verbatim so we can see what the parser DIDN'T pick up
print("\n--- First 3 raw tables (verbatim) ---")
for i, t in enumerate(raw[:3]):
    print(f"\n[Raw {i}] page={t['page']}  rows={len(t['data'])}")
    for r in t["data"][:6]:
        print(f"  {r}")

if target:
    print(f"\n--- Looking for {target} ---")
    merged, sources = table_extractor.extract_all_for_part(pdf, target, max_pages=15)
    print(f"Sources: {sources}")
    for k, v in merged.items():
        print(f"  {k}: {v!r}")
