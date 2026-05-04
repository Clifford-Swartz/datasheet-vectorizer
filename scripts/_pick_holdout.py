"""Pick 30 parts for held-out validation, stratified across families not in ground_truth."""
import json
import random
from collections import defaultdict

random.seed(42)

gt = json.load(open("ground_truth.json", encoding="utf-8-sig"))
gt_parts = set(gt.keys())
gt_families_prefix = set()
for p in gt_parts:
    # Use first 6 chars as a rough family prefix to avoid sampling the same family
    gt_families_prefix.add(p[:6])

vectorized = json.load(open("vectorized_all.json", encoding="utf-8-sig"))

# Group by PDF — that's our truer "family" for held-out
by_pdf = defaultdict(list)
for part, info in vectorized.items():
    if part in gt_parts:
        continue
    if info.get("error"):
        continue
    fields = info.get("fields", {})
    if len(fields) < 8:  # skip very sparse extractions (architecture manuals etc.)
        continue
    by_pdf[info["pdf"]].append(part)

# Sample: pick at most 1 part per PDF, prioritize PDFs with many parts (more representative)
pdfs_sorted = sorted(by_pdf.items(), key=lambda x: -len(x[1]))

picked = []
seen_prefixes = set(gt_families_prefix)
for pdf, parts in pdfs_sorted:
    # Pick one part from this PDF whose first 6 chars haven't been used
    candidates = [p for p in parts if p[:6] not in seen_prefixes]
    if not candidates:
        candidates = parts
    p = random.choice(candidates)
    picked.append({"part": p, "pdf": pdf})
    seen_prefixes.add(p[:6])
    if len(picked) >= 30:
        break

# Save
with open("holdout_sample.json", "w") as f:
    json.dump(picked, f, indent=2)

print(f"Picked {len(picked)} held-out parts:")
for x in picked:
    pdf_short = x["pdf"].replace("datasheets\\", "")[:55]
    print(f"  {x['part']:<25} -> {pdf_short}")
