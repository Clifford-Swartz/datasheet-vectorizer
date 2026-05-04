"""
Run the datasheet vectorizer over every part in part_to_pdf.json.
Writes vectorized_all.json: { PART: { fields: {...}, sources: [...], pdf: "...", error: null/str } }
"""
import json
import sys
import time
import traceback

sys.path.insert(0, ".")
from datasheet_vectorizer import vectorize


def main():
    part_to_pdf = json.load(open("part_to_pdf.json"))
    out = {}
    n_ok = n_err = 0
    n_total = len(part_to_pdf)
    t0 = time.time()

    for i, (part, pdf) in enumerate(part_to_pdf.items(), 1):
        try:
            result = vectorize.vectorize(pdf, part, max_pages=15)
            out[part] = {
                "fields": result["fields"],
                "sources": result.get("sources", []),
                "pdf": pdf,
                "error": None,
            }
            n_ok += 1
        except Exception as e:
            out[part] = {
                "fields": {},
                "sources": [],
                "pdf": pdf,
                "error": f"{type(e).__name__}: {e}",
            }
            n_err += 1

        if i % 50 == 0 or i == n_total:
            elapsed = time.time() - t0
            rate = i / max(elapsed, 0.01)
            eta = (n_total - i) / max(rate, 0.01)
            print(f"[{i}/{n_total}] ok={n_ok} err={n_err}  rate={rate:.1f}/s  eta={eta/60:.1f}min")
            with open("vectorized_all.partial.json", "w") as f:
                json.dump(out, f, indent=2)

    with open("vectorized_all.json", "w") as f:
        json.dump(out, f, indent=2)

    print()
    print(f"Done. ok={n_ok} err={n_err} of {n_total} ({n_ok/n_total*100:.1f}% ok)")


if __name__ == "__main__":
    main()
